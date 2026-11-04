# kabooz/session/downloads.py
"""
Download methods for QobuzSession.

Extracted from session/__init__.py to keep QobuzSession navigable.
Every method here is still called as self.download_track(), etc. —
mixin composition means they operate on a QobuzSession instance and
have full access to self.config, self.client, self.store, self._dev.

Public import path unchanged.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from ..dev import dev_log
from ..download.downloader import Downloader, DownloadResult, GoodieResult
from ..download.lyrics import fetch_lyrics
from ..download.musicbrainz import lookup_isrc, apply_mb_tags
from ..download.tagger import Tagger
from ..download.naming import sanitize
from ..exceptions import (
    APIError, NotFoundError, NotStreamableError, PoolModeError,
    TokenExpiredError, InvalidCredentialsError, NoAuthError,
)
from ..models.album import Album
from ..models.track import Track
from ..quality import Quality

from ._types import (
    _parse_quality,
    TrackDownloadResult,
    AlbumDownloadResult,
    PlaylistDownloadResult,
    ProgressCallback,
    TrackStartCallback,
    TrackDoneCallback,
    TrackFailCallback,
    AlbumStartCallback,
)


def _slice_range(
    items,
    *,
    start: int = 1,
    end: int | None = None,
    disc: int | None = None,
    warnings_out: list[str] | None = None,
):
    """
    Slice an ordered collection by 1-based inclusive range, with
    optional disc filtering.

    Returns list of (original_position, item) tuples.

    warnings_out: optional list. When provided, harmless-but-
    probably-unintentional conditions append a warning string.
    """
    indexed = list(enumerate(items, 1))

    if disc is not None:
        if disc == 1 and warnings_out is not None and items:
            all_monodisc = all(
                (getattr(it, "media_number", None) or 1) == 1
                for it in items
            )
            if all_monodisc:
                warnings_out.append(
                    "--disc 1 had no effect (album has only one disc)"
                )
        indexed = [
            (i, it) for i, it in indexed
            if (getattr(it, "media_number", None) or 1) == disc
        ]
        if not indexed:
            raise ValueError(f"disc {disc} not found in collection")

    n = len(indexed)
    if start > n:
        raise ValueError(
            f"start={start} exceeds available count ({n})"
        )

    if end is not None and end > n:
        if warnings_out is not None:
            warnings_out.append(
                f"end={end} exceeded available count ({n}); using {n}"
            )
        end_actual = n
    else:
        end_actual = n if end is None else end

    if end_actual < start:
        raise ValueError(
            f"end={end} is less than start={start}"
        )

    return indexed[start - 1:end_actual]


class DownloadsMixin:
    """Mixin providing download_* and their helpers.
    Composed into QobuzSession via class inheritance. Methods assume
    the full QobuzSession context (self.config, self.client, self.store,
    self._dev)."""

    def _post_download(
        self,
        result: DownloadResult,
        track:  Track,
        album:  Optional[Album] = None,
        embed_cover:       Optional[bool] = None,
        fetch_lyrics_flag: Optional[bool] = None,
        save_cover_file:   Optional[bool] = None,
        cover_size:        Optional[str]  = None,
        sidecar_size:      Optional[str]  = None,
    ) -> TrackDownloadResult:
        cfg = self.config
        t   = cfg.tagging
        mb  = cfg.musicbrainz

        # Build effective tagging config with per-download size overrides.
        # No-op when both are None — falls through to cfg.tagging.
        if cover_size or sidecar_size:
            t = dataclasses.replace(
                t,
                embed_cover_size=cover_size or t.embed_cover_size,
                sidecar_cover_size=sidecar_size or t.sidecar_cover_size,
            )

        _embed_cover  = embed_cover       if embed_cover       is not None else t.embed_cover
        _fetch_lyrics = fetch_lyrics_flag if fetch_lyrics_flag is not None else t.fetch_lyrics
        _save_cover   = save_cover_file   if save_cover_file   is not None else t.save_cover_file

        # ── Skip guard ────────────────────────────────────────────────────
        # The final file already existed before this run — the .part
        # convention guarantees both download and tagging completed on a
        # prior run, so there is nothing to do here.
        if result.skipped:
            return TrackDownloadResult(result, track, album)

        tagged = lyrics_found = mb_enriched = False

        if not t.enabled:
            # Tagging disabled — just rename .part → final and return.
            self._finalise(result)
            return TrackDownloadResult(result, track, album)

        lyrics_result = None
        if _fetch_lyrics:
            artist_name = (
                track.performer.name if track.performer
                else (album.artist.name if album and album.artist else "")
            )
            lyrics_result = fetch_lyrics(
                title=track.title,
                artist=artist_name,
                album=album.title if album else None,
                duration=track.duration,
            )
            lyrics_found = bool(lyrics_result and lyrics_result.found)

        if not result.dev_stub:
            Tagger().tag(
                path=result.path,
                track=track,
                album=album,
                lyrics=lyrics_result,
                embed_cover=_embed_cover,
                tagging_config=t,
            )
            tagged = True

        if mb.enabled and track.isrc and not result.dev_stub:
            mb_result = lookup_isrc(track.isrc)
            if mb_result.found:
                apply_mb_tags(result.path, mb_result)
                mb_enriched = True

        # ── Rename .part → final ──────────────────────────────────────────
        # Every pipeline step that writes to the file is done. Only now do
        # we rename to the final path — making "file exists" an unambiguous
        # "fully complete" signal, exactly like yt-dlp's convention.
        # If anything above raised an exception, the .part file stays on
        # disk. The next run will detect the complete .part, skip the
        # download, and retry the tagging pipeline automatically.
        if not result.dev_stub:
            self._finalise(result)

        # ── Save .lrc sidecar file ────────────────────────────────────────
        # Written after _finalise so result.path is the final audio path.
        if (
            cfg.tagging.save_lrc_file
            and lyrics_result
            and lyrics_result.found
            and lyrics_result.synced
            and not result.dev_stub
        ):
            try:
                lrc_path = result.path.with_suffix(".lrc")
                lrc_path.write_text(lyrics_result.synced, encoding="utf-8")
            except OSError:
                pass

        # ── Save standalone cover file ────────────────────────────────────
        # Must happen after _finalise so result.path is the final path.
        if _save_cover and not result.dev_stub:
            if album:
                self._save_cover_file(
                    result.path.parent, album,
                    size=t.sidecar_cover_size,
                )
            else:
                self._save_cover_file(
                    result.path.parent,
                    album=None,
                    track=track,
                    track_stem=result.path.stem,
                    size=t.sidecar_cover_size,
                )

        if cfg.local_data.track_history and not result.dev_stub:
            try:
                self.store.log_play(
                    track_id=str(track.id),
                    title=track.display_title,
                    artist=track.performer.name if track.performer else "",
                    album=(album or track.album) and (
                        album.title if album else track.album.title  # type: ignore
                    ) or "",
                )
            except Exception:
                pass

        return TrackDownloadResult(
            result, track, album, tagged, lyrics_found, mb_enriched,
        )

    @staticmethod
    def _finalise(result: DownloadResult) -> None:
        """
        Rename result.path from <name>.part to <name> (mutates result.path).

        If the path doesn't end with '.part' (dev mode writes directly to
        the final path) this is a no-op, so it is always safe to call.
        """
        if result.path.name.endswith(".part"):
            final = result.path.with_name(result.path.name[:-5])
            result.path.rename(final)
            result.path = final

    def download_track(
        self,
        url_or_id:         str,
        quality:           Optional[Quality]          = None,
        dest_dir:          Optional[Path]             = None,
        template:          Optional[str]              = None,
        embed_cover:       Optional[bool]             = None,
        fetch_lyrics_flag: Optional[bool]             = None,
        save_cover_file:   Optional[bool]             = None,
        cover_size:        Optional[str]              = None,
        sidecar_size:      Optional[str]              = None,
        on_progress:       Optional[ProgressCallback] = None,
        workers:           Optional[int]              = None,
        external_downloader: Optional[str]            = None,
    ) -> TrackDownloadResult:
        cfg = self.config
        _, track_id = self.resolve_id(url_or_id, "track")
        q      = quality or _parse_quality(cfg.download.quality)
        dest   = dest_dir or Path(cfg.download.output_dir)
        tmpl   = template or cfg.naming.single
        n_work = workers  or cfg.download.max_workers
        ext_dl = external_downloader or cfg.download.external_downloader

        track_obj = self.client.get_track(track_id)
        url_info  = self.client.get_track_url(track_id, quality=q)

        with Downloader(
            read_timeout=cfg.download.read_timeout,
            connect_timeout=cfg.download.connect_timeout,
            max_workers=n_work,
            max_retries=cfg.download.max_retries,
            external_downloader=ext_dl,
            naming_template=tmpl,
            dev=self._dev,
        ) as dl:
            result = dl.download_track(
                track=track_obj, url_info=url_info,
                dest_dir=dest, album=None, on_progress=on_progress,
            )

        return self._post_download(
            result, track_obj, None,
            embed_cover=embed_cover,
            fetch_lyrics_flag=fetch_lyrics_flag,
            save_cover_file=save_cover_file,
            cover_size=cover_size,
            sidecar_size=sidecar_size,
        )

    def download_album(
        self,
        url_or_id:         str,
        quality:           Optional[Quality]            = None,
        dest_dir:          Optional[Path]               = None,
        template:          Optional[str]                = None,
        embed_cover:       Optional[bool]               = None,
        fetch_lyrics_flag: Optional[bool]               = None,
        save_cover_file:   Optional[bool]               = None,
        cover_size:        Optional[str]                = None,
        sidecar_size:      Optional[str]                = None,
        start:             int               = 1,
        end:               Optional[int]     = None,
        disc:              Optional[int]     = None,
        on_warning:        Optional[Callable[[str], None]] = None,
        download_goodies:  bool                         = True,
        on_track_start:    Optional[TrackStartCallback] = None,
        on_track_done:     Optional[TrackDoneCallback]  = None,
        on_track_fail:     Optional[TrackFailCallback]  = None,
        on_progress:       Optional[ProgressCallback]   = None,
        workers:           Optional[int]                = None,
        external_downloader: Optional[str]              = None,
    ) -> AlbumDownloadResult:
        from ..dev import dev_log

        cfg = self.config
        _, album_id = self.resolve_id(url_or_id, "album")
        q      = quality or _parse_quality(cfg.download.quality)
        dest   = dest_dir or Path(cfg.download.output_dir)
        n_work = workers  or cfg.download.max_workers
        ext_dl = external_downloader or cfg.download.external_downloader

        album_obj    = self.client.get_album(album_id)
        release_type = (album_obj.release_type or "album").lower()

        if template:
            tmpl = template
        elif release_type == "single":
            tmpl = cfg.naming.single
        elif release_type == "ep":
            tmpl = cfg.naming.ep
        elif release_type == "compilation":
            tmpl = cfg.naming.compilation
        else:
            tmpl = cfg.naming.album

        agg           = AlbumDownloadResult(album=album_obj)
        track_results: list[DownloadResult] = []

        summaries = (
            album_obj.tracks.items
            if album_obj.tracks
            and len(album_obj.tracks.items) >= (album_obj.tracks.total or 0)
            else list(self.client.iter_album_tracks(album_id))
        )
        _sw: list[str] = []
        summaries = [s for _, s in _slice_range(
            summaries, start=start, end=end, disc=disc,
            warnings_out=_sw,
        )]
        if on_warning:
            for _w in _sw:
                on_warning(_w)
        total = len(summaries)

        with Downloader(
            read_timeout=cfg.download.read_timeout,
            connect_timeout=cfg.download.connect_timeout,
            max_workers=n_work,
            max_retries=cfg.download.max_retries,
            external_downloader=ext_dl,
            naming_template=tmpl,
            dev=self._dev,
        ) as dl:
            for i, summary in enumerate(summaries, 1):
                if on_track_start:
                    title = getattr(summary, "display_title",
                                    getattr(summary, "title", ""))
                    on_track_start(title, i, total)

                try:
                    track_obj = self.client.get_track(str(summary.id))
                    url_info  = self.client.get_track_url(str(track_obj.id), quality=q)
                except (NotStreamableError, APIError, httpx.TransportError) as exc:
                    _reason = str(exc)
                    agg.failed.append(f"{summary.title} — {_reason}")
                    if on_track_fail:
                        on_track_fail(summary.title, _reason)
                    continue
                except (APIError, httpx.TransportError) as exc:
                    _title = getattr(summary, "display_title", getattr(summary, "title", str(summary.id)))
                    dev_log(f"[red]track {summary.id} error: {exc}[/red]")
                    _reason = f"{type(exc).__name__}: {exc}"
                    agg.failed.append(f"{_title} — {_reason}")
                    if on_track_fail:
                        on_track_fail(_title, _reason)
                    continue
                try:
                    dl_result = dl.download_track(
                        track=track_obj, url_info=url_info,
                        dest_dir=dest, album=album_obj, on_progress=on_progress,
                    )
                except Exception as exc:
                    dev_log(f"[red]track {track_obj.id} download error: {exc}[/red]")
                    _reason = f"{type(exc).__name__}: {exc}"
                    agg.failed.append(f"{track_obj.display_title} — {_reason}")
                    if on_track_fail:
                        on_track_fail(track_obj.display_title, _reason)
                    continue

                tdr = self._post_download(
                    dl_result, track_obj, album_obj,
                    embed_cover=embed_cover,
                    fetch_lyrics_flag=fetch_lyrics_flag,
                    save_cover_file=save_cover_file,
                    cover_size=cover_size,
                    sidecar_size=sidecar_size,
                )

                agg.tracks.append(tdr)
                if cfg.musicbrainz.enabled and track_obj.isrc and not dl_result.dev_stub:
                    agg.mb_attempted += 1
                    if tdr.mb_enriched:
                        agg.mb_succeeded += 1
            if on_track_done:
                on_track_done(tdr)

            if download_goodies and album_obj.goodies:
                album_dir = dest
                for r in track_results:
                    candidate = r.path.parent
                    if album_obj.media_count and album_obj.media_count > 1:
                        candidate = candidate.parent
                    if candidate.is_dir():
                        album_dir = candidate
                        break
                for goodie in album_obj.goodies:
                    gr = dl.download_goodie(goodie, album_dir)
                    if gr.ok:
                        agg.goodies_ok += 1
                    else:
                        agg.goodies_failed += 1

        return agg

    def download_album_goodies(
        self,
        url_or_id: str,
        dest_dir:  Optional[Path] = None,
        on_progress_each: Optional[Callable[[str, int, int], None]] = None,
    ) -> list:
        """
        Download only the bonus files (goodies) for an album.

        Goodies are non-audio extras bundled with an album — typically a
        booklet PDF, but may also be hi-res videos or other digital files.
        They are placed in ``<dest_dir>/<Album [Format] [Year]>/``.

        Parameters:
            on_progress_each: Called for each goodie as it downloads:
                              (filename, bytes_done, total_bytes).

        Returns a list of GoodieResult objects. Empty list if no goodies.
        """
        from ..download.downloader import Downloader
        from ..download.naming import quality_tag

        cfg = self.config
        _, album_id = self.resolve_id(url_or_id, "album")
        dest = dest_dir or Path(cfg.download.output_dir)

        album_obj = self.client.get_album(album_id)
        if not album_obj.goodies:
            return []

        # Mirror the folder name that download_album would create so goodies
        # land next to any already-downloaded audio files.
        qtag = quality_tag(
            album_obj.maximum_bit_depth,
            album_obj.maximum_sampling_rate,
        )
        year = (
            f" [{album_obj.release_date_original[:4]}]"
            if album_obj.release_date_original else ""
        )
        album_dir = dest / sanitize(
            f"{album_obj.display_title} [{qtag}]{year}"
        )
        album_dir.mkdir(parents=True, exist_ok=True)

        # ── Pre-compute deduplicated filenames ─────────────────────────────
        # On case-insensitive filesystems (Android, macOS) two goodies whose
        # sanitized names differ only in case would collide.  We resolve
        # clashes upfront so every goodie gets a unique path.
        def _goodie_filename(goodie) -> str:
            url = goodie.original_url or goodie.url or ""
            url_filename = url.split("?")[0].rstrip("/").split("/")[-1]
            ext = ""
            if "." in url_filename:
                ext = "." + url_filename.rsplit(".", 1)[-1].lower()
            base = sanitize(goodie.name) if goodie.name else (
                sanitize(url_filename) if url_filename else f"goodie_{goodie.id}"
            )
            return base + ext

        used: dict[str, int] = {}
        dest_paths: list[Path] = []
        for goodie in album_obj.goodies:
            name = _goodie_filename(goodie)
            stem, _, ext = name.rpartition(".")
            ext = ("." + ext) if ext else ""
            key = stem.lower()
            if key in used:
                used[key] += 1
                unique_name = f"{stem} ({used[key]}){ext}"
            else:
                used[key] = 1
                unique_name = name
            dest_paths.append(album_dir / unique_name)

        # ── Download ───────────────────────────────────────────────────────
        results = []
        with Downloader(
            read_timeout=cfg.download.read_timeout,
            connect_timeout=cfg.download.connect_timeout,
            max_retries=cfg.download.max_retries,
            dev=self._dev,
        ) as dl:
            for goodie, path in zip(album_obj.goodies, dest_paths):
                progress_cb = None
                if on_progress_each:
                    name = path.name
                    progress_cb = lambda done, total, n=name: on_progress_each(n, done, total)
                url = goodie.original_url or goodie.url
                if not url:
                    results.append(GoodieResult(
                        path=path, goodie=goodie, error="No URL available",
                    ))
                    continue
                try:
                    r = dl._download_goodie_to_path(url, path, progress_cb)
                    results.append(GoodieResult(
                        path=r.path, goodie=goodie, skipped=r.skipped,
                    ))
                except Exception as exc:
                    results.append(GoodieResult(
                        path=path, goodie=goodie, error=str(exc),
                    ))

        return results

    def download_artist_discography(
        self,
        url_or_id:      str,
        release_type:   Optional[str]   = None,
        quality:        Optional[Quality] = None,
        dest_dir:       Optional[Path]   = None,
        template:       Optional[str]    = None,
        on_album_start: Optional[AlbumStartCallback] = None,
        on_track_start: Optional[TrackStartCallback] = None,
        on_track_done:  Optional[TrackDoneCallback]  = None,
        on_track_fail:  Optional[TrackFailCallback]  = None,
        workers:        Optional[int]    = None,
        cover_size:     Optional[str]    = None,
        sidecar_size:   Optional[str]    = None,
        start:          int              = 1,
        end:            Optional[int]    = None,
        on_warning:     Optional[Callable[[str], None]] = None,
    ) -> list[AlbumDownloadResult]:
        """
        Download every release in an artist's discography.

        All albums are rooted under <dest_dir>/<ArtistName>/ so that a
        bare `qobuz artist 123` produces a clean, self-contained folder
        rather than mixing albums from different artists in the same
        directory.  The artist name used for the folder is the canonical
        name returned by the API for the queried artist ID — not the
        per-album albumartist field, which can vary across releases.

        Template selection (when no explicit --template is passed):
          · album / other  → naming.artist   (no {albumartist} prefix;
                                              the artist folder is injected here)
          · single         → naming.single   (flat, e.g. "Artist - Title")
          · ep             → naming.ep
          · compilation    → naming.compilation

        on_album_start(album_title, album_index, album_total) is fired
        before each album so the CLI/TUI can print a clear header.
        """
        from ..dev import dev_log

        cfg = self.config
        _, artist_id = self.resolve_id(url_or_id, "artist")

        # ── Resolve artist name for the top-level folder ───────────────────
        base_dest = dest_dir or Path(cfg.download.output_dir)
        try:
            artist_obj = self.client.get_artist(artist_id, extras="")
            artist_dir = base_dest / sanitize(artist_obj.name)
        except Exception as exc:
            dev_log(f"[yellow]Could not fetch artist name ({exc}), using base dest[/yellow]")
            artist_dir = base_dest

        # ── Enumerate releases ─────────────────────────────────────────────
        try:
            releases = [
                r for r in self.client.iter_releases(
                    artist_id, release_type=release_type, page_size=100,
                )
                if r.id
            ]
        except Exception as exc:
            raise RuntimeError(
                f"Failed to list releases for artist {artist_id}: {exc}"
            ) from exc

        _sw: list[str] = []
        releases = [r for _, r in _slice_range(
            releases, start=start, end=end, warnings_out=_sw,
        )]
        if on_warning:
            for _w in _sw:
                on_warning(_w)

        total   = len(releases)
        results = []

        for i, release in enumerate(releases, 1):
            try:
                album_obj = self.client.get_album(release.id)
            except APIError as exc:
                dev_log(f"[yellow]album {release.id} fetch error (skipping): {exc}[/yellow]")
                continue

            if on_album_start:
                on_album_start(album_obj.display_title, i, total)

            if template:
                effective_template: Optional[str] = template
            else:
                rtype = (album_obj.release_type or "album").lower()
                if rtype == "single":
                    effective_template = None
                elif rtype == "ep":
                    effective_template = None
                elif rtype == "compilation":
                    effective_template = None
                else:
                    effective_template = cfg.naming.artist

            try:
                agg = self.download_album(
                    release.id,
                    quality=quality,
                    dest_dir=artist_dir,
                    template=effective_template,
                    cover_size=cover_size,
                    sidecar_size=sidecar_size,
                    on_track_start=on_track_start,
                    on_track_done=on_track_done,
                    on_track_fail=on_track_fail,
                    workers=workers,
                )
                results.append(agg)
            except NotStreamableError:
                dev_log(f"[yellow]{album_obj.display_title!r} not streamable — skipped[/yellow]")
            except APIError as exc:
                dev_log(f"[red]{album_obj.display_title!r} API error: {exc}[/red]")
            except Exception as exc:
                dev_log(
                    f"[red]{album_obj.display_title!r} unexpected error "
                    f"({type(exc).__name__}): {exc}[/red]"
                )

        return results

    def download_playlist(
        self,
        url_or_id:         str,
        quality:           Optional[Quality] = None,
        dest_dir:          Optional[Path]    = None,
        template:          Optional[str]     = None,
        embed_cover:       Optional[bool]    = None,
        fetch_lyrics_flag: Optional[bool]    = None,
        save_cover_file:   Optional[bool]    = None,
        cover_size:        Optional[str]     = None,
        sidecar_size:      Optional[str]     = None,
        start:             int               = 1,
        end:               Optional[int]     = None,
        on_warning:        Optional[Callable[[str], None]] = None,
        on_track_start:    Optional[TrackStartCallback] = None,
        on_track_done:     Optional[TrackDoneCallback]  = None,
        on_track_fail:     Optional[TrackFailCallback]  = None,
        on_progress:       Optional[ProgressCallback]   = None,
        workers:           Optional[int]     = None,
        external_downloader: Optional[str]   = None,
        write_m3u:         bool              = False,
    ) -> PlaylistDownloadResult:
        cfg = self.config
        _, playlist_id = self.resolve_id(url_or_id, "playlist")
        q      = quality or _parse_quality(cfg.download.quality)
        dest   = dest_dir or Path(cfg.download.output_dir)
        tmpl   = template or cfg.naming.playlist
        n_work = workers  or cfg.download.max_workers
        ext_dl = external_downloader or cfg.download.external_downloader

        pl    = self.client.get_playlist(playlist_id, limit=1)
        total = pl.tracks_count
        agg   = PlaylistDownloadResult(name=pl.name)
        m3u:  list[str] = ["#EXTM3U"]

        all_summaries = list(
            self.client.iter_playlist_track_summaries(playlist_id)
        )
        _sw: list[str] = []
        try:
            sliced = _slice_range(
                all_summaries, start=start, end=end,
                warnings_out=_sw,
            )
        except ValueError as exc:
            raise ValueError(
                f"Cannot download playlist: {exc}"
            ) from exc
        if on_warning:
            for _w in _sw:
                on_warning(_w)
        total = len(sliced)

        with Downloader(
            read_timeout=cfg.download.read_timeout,
            connect_timeout=cfg.download.connect_timeout,
            max_workers=n_work,
            max_retries=cfg.download.max_retries,
            external_downloader=ext_dl,
            naming_template=tmpl,
            dev=self._dev,
        ) as dl:
            for original_pos, summary in sliced:
                if on_track_start:
                    on_track_start(summary.title, original_pos, total)

                try:
                    track_obj = self.client.get_track(str(summary.id))
                    album_obj = None
                    if track_obj.album:
                        try:
                            album_obj = self.client.get_album(track_obj.album.id)
                        except Exception:
                            pass
                    url_info = self.client.get_track_url(str(track_obj.id), quality=q)
                except (NotStreamableError, APIError) as exc:
                    _reason = str(exc)
                    agg.failed.append(f"{summary.title} — {_reason}")
                    if on_track_fail:
                        on_track_fail(summary.title, _reason)
                    continue

                try:
                    dl_result = dl.download_track(
                        track=track_obj, url_info=url_info,
                        dest_dir=dest, album=None, on_progress=on_progress,
                        playlist_name=pl.name, playlist_index=original_pos,
                    )
                except Exception as exc:
                    _reason = f"{type(exc).__name__}: {exc}"
                    agg.failed.append(f"{track_obj.display_title} — {_reason}")
                    if on_track_fail:
                        on_track_fail(track_obj.display_title, _reason)
                    continue

                tdr = self._post_download(
                    dl_result, track_obj, album_obj,
                    embed_cover=embed_cover,
                    fetch_lyrics_flag=fetch_lyrics_flag,
                    save_cover_file=save_cover_file,
                    cover_size=cover_size,
                    sidecar_size=sidecar_size,
                )
                agg.tracks.append(tdr)
                m3u.append(str(dl_result.path))
                if on_track_done:
                    on_track_done(tdr)

        if write_m3u and len(m3u) > 1:
            pl_dir = dest / sanitize(pl.name)
            pl_dir.mkdir(parents=True, exist_ok=True)
            (pl_dir / f"{sanitize(pl.name)}.m3u8").write_text(
                "\n".join(m3u), encoding="utf-8"
            )
        return agg

    def download_local_playlist(
        self,
        playlist_name_or_id: str,
        quality:        Optional[Quality] = None,
        dest_dir:       Optional[Path]    = None,
        template:       Optional[str]     = None,
        on_track_start: Optional[TrackStartCallback] = None,
        on_track_done:  Optional[TrackDoneCallback]  = None,
        workers:        Optional[int]     = None,
        cover_size:     Optional[str]     = None,
        sidecar_size:   Optional[str]     = None,
    ) -> PlaylistDownloadResult:
        cfg = self.config
        pl  = self.store.get_playlist_by_name(playlist_name_or_id)
        if not pl:
            for c in self.store.list_playlists():
                if c["id"].startswith(playlist_name_or_id):
                    pl = c; break
        if not pl:
            raise ValueError(f"Local playlist not found: {playlist_name_or_id!r}")

        tracks = self.store.get_playlist_tracks(pl["id"])
        q      = quality or _parse_quality(cfg.download.quality)
        dest   = dest_dir or Path(cfg.download.output_dir)
        tmpl   = template or cfg.naming.playlist
        n_work = workers  or cfg.download.max_workers
        agg    = PlaylistDownloadResult(name=pl["name"])

        with Downloader(
            read_timeout=cfg.download.read_timeout,
            connect_timeout=cfg.download.connect_timeout,
            max_workers=n_work,
            max_retries=cfg.download.max_retries,
            naming_template=tmpl,
            dev=self._dev,
        ) as dl:
            for i, t in enumerate(tracks, 1):
                if on_track_start:
                    on_track_start(t.get("title", t["track_id"]), i, len(tracks))
                try:
                    track_obj = self.client.get_track(t["track_id"])
                    url_info  = self.client.get_track_url(t["track_id"], quality=q)
                except Exception:
                    agg.failed += 1; continue
                try:
                    dl_result = dl.download_track(
                        track=track_obj, url_info=url_info,
                        dest_dir=dest, album=None,
                        playlist_name=pl["name"], playlist_index=i,
                    )
                except Exception:
                    agg.failed += 1; continue
                tdr = self._post_download(
                    dl_result, track_obj,
                    cover_size=cover_size,
                    sidecar_size=sidecar_size,
                )
                agg.tracks.append(tdr)
                if on_track_done:
                    on_track_done(tdr)
        return agg

    def download_favorites(
        self,
        fav_type:          str                           = "tracks",
        quality:           Optional[Quality]             = None,
        dest_dir:          Optional[Path]                = None,
        save_cover_file:   Optional[bool]                = None,
        cover_size:        Optional[str]                 = None,
        sidecar_size:      Optional[str]                 = None,
        on_track_start:    Optional[TrackStartCallback]  = None,
        on_track_done:     Optional[TrackDoneCallback]   = None,
        workers:           Optional[int]                 = None,
    ) -> PlaylistDownloadResult:
        cfg  = self.config
        q    = quality or _parse_quality(cfg.download.quality)
        dest = dest_dir or Path(cfg.download.output_dir)
        agg  = PlaylistDownloadResult(name=f"Favorites ({fav_type})")

        if fav_type == "albums":
            for album_obj in self.client.iter_favorites(type="albums"):
                try:
                    r = self.download_album(
                        str(album_obj.id), quality=q, dest_dir=dest,
                        on_track_start=on_track_start,
                        on_track_done=on_track_done,
                        workers=workers,
                        cover_size=cover_size,
                        sidecar_size=sidecar_size,
                    )
                    agg.tracks.extend(r.tracks)
                    agg.failed += r.failed
                except Exception as exc:
                    agg.failed.append(f"{album_obj.display_title} — {exc}")
            return agg

        with Downloader(
            read_timeout=cfg.download.read_timeout,
            connect_timeout=cfg.download.connect_timeout,
            max_workers=workers or cfg.download.max_workers,
            max_retries=cfg.download.max_retries,
            naming_template=cfg.naming.single,
            dev=self._dev,
        ) as dl:
            for i, track_obj in enumerate(
                self.client.iter_favorites(type="tracks"), 1
            ):
                if on_track_start:
                    on_track_start(track_obj.display_title, i, 0)
                try:
                    url_info  = self.client.get_track_url(str(track_obj.id), quality=q)
                    dl_result = dl.download_track(
                        track=track_obj, url_info=url_info, dest_dir=dest, album=None,
                    )
                except Exception as exc:
                    agg.failed.append(f"{getattr(track_obj, 'display_title', '?')} — {exc}"); continue

                tdr = self._post_download(
                    dl_result, track_obj,
                    cover_size=cover_size,
                    sidecar_size=sidecar_size,
                )
        return agg

    def download_purchases(
        self,
        purchase_type:  str              = "albums",
        quality:        Optional[Quality] = None,
        dest_dir:       Optional[Path]   = None,
        on_track_start: Optional[TrackStartCallback] = None,
        on_track_done:  Optional[TrackDoneCallback]  = None,
        workers:        Optional[int]    = None,
        cover_size:     Optional[str]    = None,
        sidecar_size:   Optional[str]    = None,
    ) -> PlaylistDownloadResult:
        cfg  = self.config
        q    = quality or _parse_quality(cfg.download.quality)
        dest = dest_dir or Path(cfg.download.output_dir)
        agg  = PlaylistDownloadResult(name=f"Purchases ({purchase_type})")

        if purchase_type == "albums":
            for album_obj in self.client.iter_purchases(type="albums"):
                try:
                    r = self.download_album(
                        str(album_obj.id), quality=q, dest_dir=dest,
                        on_track_start=on_track_start, on_track_done=on_track_done,
                        workers=workers,
                        cover_size=cover_size,
                        sidecar_size=sidecar_size,
                    )
                    agg.tracks.extend(r.tracks)
                    agg.failed += r.failed
                except Exception as exc:
                    agg.failed.append(f"{album_obj.display_title} — {exc}")
            return agg

        with Downloader(
            read_timeout=cfg.download.read_timeout,
            connect_timeout=cfg.download.connect_timeout,
            max_workers=workers or cfg.download.max_workers,
            max_retries=cfg.download.max_retries,
            naming_template=cfg.naming.single,
            dev=self._dev,
        ) as dl:
            for i, track_obj in enumerate(
                self.client.iter_purchases(type="tracks"), 1
            ):
                if on_track_start:
                    on_track_start(
                        getattr(track_obj, "display_title", str(track_obj)), i, 0
                    )
                try:
                    url_info  = self.client.get_track_url(str(track_obj.id), quality=q)
                    dl_result = dl.download_track(
                        track=track_obj, url_info=url_info, dest_dir=dest, album=None,
                    )
                except Exception as exc:
                    agg.failed.append(f"{getattr(track_obj, 'display_title', '?')} — {exc}"); continue
                tdr = self._post_download(
                    dl_result, track_obj,
                    cover_size=cover_size,
                    sidecar_size=sidecar_size,
                )
                agg.tracks.append(tdr)
                if on_track_done:
                    on_track_done(tdr)
        return agg

    def _save_cover_file(
        self,
        folder: Path,
        album: Optional[Album] = None,
        track: Optional[Track] = None,
        track_stem: Optional[str] = None,
        size: str = "original",
    ) -> None:
        """
        Save cover art as a JPEG file alongside the audio.

        For album downloads (album is not None):
            Writes  <folder>/cover.jpg
            All tracks in the folder share the same release, so one
            canonical cover file is the right behaviour.

        For single-track downloads (album is None, track_stem provided):
            Writes  <folder>/<track_stem>.jpg
            Multiple singles may land in the same dest_dir, so we name
            the cover after the audio file to avoid collisions:
                "01. One More Time.flac"  →  "01. One More Time.jpg"

        Image URL resolution order:
            1. album.image (full Album object, highest quality)
            2. track.album.image (TrackAlbum embedded in the Track)
        """
        url: Optional[str] = None

        if album and album.image:
            url = album.image.url_for_size(size)
        elif track and track.album and track.album.image:
            img = track.album.image
            if hasattr(img, "url_for_size"):
                url = img.url_for_size(size)
            elif isinstance(img, dict):
                url = img.get("large") or img.get("small")

        if not url:
            return

        filename = "cover.jpg" if track_stem is None else f"{track_stem}.jpg"
        cover_path = folder / filename

        if cover_path.exists():
            return

        try:
            import httpx
            with httpx.Client(follow_redirects=True, timeout=30) as c:
                r = c.get(url)
                r.raise_for_status()
                cover_path.write_bytes(r.content)
        except Exception:
            pass
