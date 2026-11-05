# kabooz/cli/downloads.py
"""
Download commands: track, album, playlist, artist, favorites,
purchases, goodies, and lpl_download.

Extracted from cli/__init__.py. Uses app and lpl_app from ._app
for command registration; helpers (console, _quality, _cover_size,
_session, etc.) from .helpers and ._app.

Public import path unchanged — commands register themselves via
@app.command() / @lpl_app.command() decorators at import time.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from ._app import app, lpl_app, _session
from .helpers import (
    console, err_console, _warn_cb,
    _quality, _cover_size, _resolve_id, _cfg,
    _make_progress, _on_track_start, _on_track_done,
    _on_album_start, _print_failed, _handle_auth_error,
)

from ..exceptions import (
    APIError, NotFoundError, NotStreamableError, PoolModeError,
    TokenExpiredError, InvalidCredentialsError, NoAuthError,
)


@app.command()
def track(
    url_or_id:  str            = typer.Argument(...),
    output:     Optional[Path] = typer.Option(None,  "-o"),
    quality:    Optional[str]  = typer.Option(None,  "-q"),
    lyrics:     Optional[bool] = typer.Option(None,  "--lyrics/--no-lyrics"),
    cover:      Optional[bool] = typer.Option(None,  "--cover/--no-cover"),
    save_cover: Optional[bool] = typer.Option(None,  "--save-cover/--no-save-cover"),
    connections: Optional[int] = typer.Option(None, "-x", "--connections",
        help="Byte-range chunks per track (default from config)"),
    no_chunks: bool = typer.Option(False, "--no-chunks",
        help="Disable chunked download even if -x > 1"),
    template:   Optional[str]  = typer.Option(None,  "--template"),
    cover_size: Optional[str] = typer.Option(None, "--cover-size",
        help="Embedded cover size: thumbnail | small | large | original"),
    save_cover_size: Optional[str] = typer.Option(None, "--save-cover-size",
        help="Sidecar cover size: thumbnail | small | large | original"),
) -> None:
    """Download a single track."""
    cfg  = _cfg()
    q    = _quality(quality)
    sess = _session(cfg)

    with _make_progress() as prog:
        task = prog.add_task("[dim]Downloading…[/dim]", total=None)

        def on_progress(written: int, total: int) -> None:
            prog.update(task, completed=written, total=total or None)

        try:
            result = sess.download_track(
                url_or_id,
                quality=q,
                dest_dir=output or Path(cfg.download.output_dir),
                template=template,
                embed_cover=cover,
                fetch_lyrics_flag=lyrics,
                save_cover_file=save_cover,
                on_progress=on_progress,
                connections=connections,
                no_chunks=no_chunks,
                cover_size=_cover_size(cover_size),
                sidecar_size=_cover_size(save_cover_size),
            )
        except (TokenExpiredError, InvalidCredentialsError, NoAuthError) as exc:
            _handle_auth_error(exc)
        except NotStreamableError as exc:
            err_console.print(f"[red]Not streamable:[/red] {exc}")
            raise typer.Exit(code=1)
        except APIError as exc:
            err_console.print(f"[red]API error:[/red] {exc}")
            raise typer.Exit(code=1)

    dl = result.download
    if dl.skipped and not dl.dev_stub:
        console.print(f"[yellow]Skipped[/yellow] (already complete): {dl.path}")
    else:
        suffix = ""
        if result.lyrics_found:
            suffix += "  [dim]lyrics embedded[/dim]"
        console.print(f"[green]Done:[/green] {dl.path}{suffix}")

@app.command()
def album(
    url_or_id:  str            = typer.Argument(...),
    output:     Optional[Path] = typer.Option(None,  "-o"),
    quality:    Optional[str]  = typer.Option(None,  "-q"),
    lyrics:     Optional[bool] = typer.Option(None,  "--lyrics/--no-lyrics"),
    cover:      Optional[bool] = typer.Option(None,  "--cover/--no-cover"),
    save_cover: Optional[bool] = typer.Option(None,  "--save-cover/--no-save-cover"),
    goodies:    Optional[bool] = typer.Option(None,  "--goodies/--no-goodies"),
    connections: Optional[int] = typer.Option(None, "-x", "--connections",
        help="Byte-range chunks per track (default from config)"),
    no_chunks: bool = typer.Option(False, "--no-chunks",
        help="Disable chunked download even if -x > 1"),
    template:   Optional[str]  = typer.Option(None,  "--template"),
    cover_size: Optional[str] = typer.Option(None, "--cover-size",
        help="Embedded cover size: thumbnail | small | large | original"),
    save_cover_size: Optional[str] = typer.Option(None, "--save-cover-size",
        help="Sidecar cover size: thumbnail | small | large | original"),
    start: int = typer.Option(1, "--start",
        help="1-based track index (global, or per-disc if --disc is set)"),
    end: Optional[int] = typer.Option(None, "--end",
        help="1-based track index to end at (inclusive)"),
    disc: Optional[int] = typer.Option(None, "--disc",
        help="Filter to this disc; --start/--end become per-disc indices"),
    no_warnings: bool = typer.Option(False, "--no-warnings",
        help="Suppress harmless range warnings"),
) -> None:
    """Download a full album."""
    cfg  = _cfg()
    q    = _quality(quality)
    sess = _session(cfg)

    # current_task holds the Rich task ID for the active track's progress bar.
    # We use a list as a mutable container so the closures below can mutate it.
    current_task: list = []

    with _make_progress() as prog:

        def on_progress(written: int, total: int) -> None:
            if current_task:
                prog.update(current_task[0], completed=written, total=total or None)

        def on_track_start(title: str, index: int, total_tracks: int) -> None:
            _on_track_start(title, index, total_tracks)
            # Replace the progress bar for each new track.
            if current_task:
                prog.remove_task(current_task[0])
                current_task.clear()
            current_task.append(
                prog.add_task(f"  [dim]{title[:60]}[/dim]", total=None)
            )

        def on_track_fail(title: str, reason: str) -> None:
            if current_task:
                prog.remove_task(current_task[0])
                current_task.clear()
            prog.console.print(f"    [red]✗ {reason}[/red]")

        try:
            result = sess.download_album(
                url_or_id,
                quality=q,
                dest_dir=output or Path(cfg.download.output_dir),
                template=template,
                embed_cover=cover,
                fetch_lyrics_flag=lyrics,
                save_cover_file=save_cover,
                start=start, end=end, disc=disc,
                on_warning=_warn_cb(no_warnings),
                download_goodies=goodies if goodies is not None else True,
                on_track_start=on_track_start,
                on_track_done=_on_track_done,
                on_track_fail=on_track_fail,
                on_progress=on_progress,
                connections=connections,
                no_chunks=no_chunks,
                cover_size=_cover_size(cover_size),
                sidecar_size=_cover_size(save_cover_size),
            )
        except (TokenExpiredError, InvalidCredentialsError, NoAuthError) as exc:
            _handle_auth_error(exc)
        except ValueError as exc:
            err_console.print(f"[red]Invalid range:[/red] {exc}")
            raise typer.Exit(code=1)
        except APIError as exc:
            err_console.print(f"[red]API error:[/red] {exc}")
            raise typer.Exit(code=1)

    console.print(
        f"\n[green]Done.[/green] "
        f"{result.succeeded} downloaded, {result.skipped} skipped"
        + (f", [red]{len(result.failed)} failed[/red]" if result.failed else "") + "."
    )

    if result.mb_attempted > 0 and result.mb_succeeded == 0:
        err_console.print(
            f"\n[yellow]MusicBrainz returned no data for all "
            f"{result.mb_attempted} track(s).[/yellow] "
            "Two common causes:\n"
            "  [dim]·[/dim] Network blocks access to musicbrainz.org "
            "Test with:\n"
            "    [dim]curl -v 'https://musicbrainz.org/ws/2/isrc/TEST?fmt=json'[/dim]\n"
            "  [dim]·[/dim] The ISRCs are not in MusicBrainz's database "
        )

@app.command()
def goodies(
    url_or_id: str            = typer.Argument(..., help="Album URL or bare album ID"),
    output:    Optional[Path] = typer.Option(None, "-o", "--output",
                                             help="Destination directory"),
) -> None:
    """
    Download only the bonus files (goodies) for an album.

    Goodies are non-audio extras bundled with an album purchase —
    typically a booklet PDF, but may also include hi-res videos or
    other digital files. Audio tracks are not downloaded.

    Files are placed in  <output>/<Album [Format] [Year]>/

    Examples
    ────────
      qobuz goodies https://open.qobuz.com/album/0093046758769
      qobuz goodies 0093046758769 -o ~/Downloads
    """
    cfg  = _cfg()
    sess = _session(cfg)

    try:
        with _make_progress() as prog:
            current: list = []

            def on_progress(filename: str, done: int, total: int) -> None:
                if not current:
                    current.append(
                        prog.add_task(f"  [dim]{filename[:60]}[/dim]", total=None)
                    )
                prog.update(current[0], completed=done, total=total or None)

            def on_next(filename: str, done: int, total: int) -> None:
                # Reset task for each new file
                if current:
                    prog.remove_task(current[0])
                    current.clear()
                on_progress(filename, done, total)

            results = sess.download_album_goodies(
                url_or_id,
                dest_dir=output or Path(cfg.download.output_dir),
                on_progress_each=on_next,
            )
    except (TokenExpiredError, InvalidCredentialsError, NoAuthError) as exc:
        _handle_auth_error(exc)
    except NotFoundError:
        err_console.print(f"[red]Album not found:[/red] {url_or_id}")
        raise typer.Exit(code=1)
    except APIError as exc:
        err_console.print(f"[red]API error:[/red] {exc}")
        raise typer.Exit(code=1)

    if not results:
        console.print("[yellow]This album has no goodies.[/yellow]")
        return

    ok      = [r for r in results if r.ok and not r.skipped]
    skipped = [r for r in results if r.ok and r.skipped]
    failed  = [r for r in results if not r.ok]

    for r in ok:
        console.print(f"[green]Downloaded:[/green] {r.path.name}")
    for r in skipped:
        console.print(f"[yellow]Skipped[/yellow] (already complete): {r.path.name}")
    for r in failed:
        console.print(f"[red]Failed:[/red] {r.goodie.name} — {r.error}")

    console.print(
        f"\n[green]Done.[/green] "
        f"{len(ok)} downloaded, {len(skipped)} skipped"
        + (f", [red]{len(failed)} failed[/red]" if failed else "")
        + "."
    )

@app.command()
def playlist(
    url_or_id:  str            = typer.Argument(...),
    output:     Optional[Path] = typer.Option(None, "-o"),
    quality:    Optional[str]  = typer.Option(None, "-q"),
    lyrics:     Optional[bool] = typer.Option(None, "--lyrics/--no-lyrics"),
    cover:      Optional[bool] = typer.Option(None, "--cover/--no-cover"),
    save_cover: Optional[bool] = typer.Option(None, "--save-cover/--no-save-cover"),
    connections: Optional[int] = typer.Option(None, "-x", "--connections",
        help="Byte-range chunks per track (default from config)"),
    no_chunks: bool = typer.Option(False, "--no-chunks",
        help="Disable chunked download even if -x > 1"),
    template:   Optional[str]  = typer.Option(None, "--template"),
    m3u:        bool           = typer.Option(False, "--m3u"),
    cover_size: Optional[str] = typer.Option(None, "--cover-size",
        help="Embedded cover size: thumbnail | small | large | original"),
    save_cover_size: Optional[str] = typer.Option(None, "--save-cover-size",
        help="Sidecar cover size: thumbnail | small | large | original"),
    start: int = typer.Option(1, "--start",
        help="1-based playlist position ({index} preserves original)"),
    end: Optional[int] = typer.Option(None, "--end",
        help="1-based playlist position to end at (inclusive)"),
    no_warnings: bool = typer.Option(False, "--no-warnings",
        help="Suppress harmless range warnings"),
) -> None:
    """Download a full playlist (all pages, pagination-proof)."""
    cfg  = _cfg()
    q    = _quality(quality)
    sess = _session(cfg)
    try:
        result = sess.download_playlist(
            url_or_id,
            quality=q,
            dest_dir=output or Path(cfg.download.output_dir),
            template=template,
            embed_cover=cover,
            fetch_lyrics_flag=lyrics,
            save_cover_file=save_cover,
            start=start, end=end,
            on_warning=_warn_cb(no_warnings),
            on_track_start=_on_track_start,
            on_track_done=_on_track_done,
            connections=connections,
            no_chunks=no_chunks,
            cover_size=_cover_size(cover_size),
            sidecar_size=_cover_size(save_cover_size),
            write_m3u=m3u,
        )
    except (TokenExpiredError, InvalidCredentialsError, NoAuthError) as exc:
        _handle_auth_error(exc)
    except ValueError as exc:
        err_console.print(f"[red]Invalid range:[/red] {exc}")
        raise typer.Exit(code=1)
    except APIError as exc:
        err_console.print(f"[red]API error:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(
        f"\n[green]Done.[/green] "
        f"{result.succeeded} downloaded, {result.skipped} skipped"
        + (f", [red]{len(result.failed)} failed[/red]" if result.failed else "") + "."
    )

@app.command()
def artist(
    url_or_id:    str            = typer.Argument(..., help="Artist ID or Qobuz URL"),
    output:       Optional[Path] = typer.Option(None,  "-o", "--output"),
    quality:      Optional[str]  = typer.Option(None,  "-q", "--quality"),
    release_type: Optional[str]  = typer.Option(
        None, "--type", "-t",
        help="album, live, compilation, epSingle, other, download. "
             "Omit for all. Combine with commas.",
    ),
    connections: Optional[int] = typer.Option(None, "-x", "--connections",
        help="Byte-range chunks per track (default from config)"),
    no_chunks: bool = typer.Option(False, "--no-chunks",
        help="Disable chunked download even if -x > 1"),
    template:     Optional[str]  = typer.Option(None,  "--template"),
    cover_size: Optional[str] = typer.Option(None, "--cover-size",
        help="Embedded cover size: thumbnail | small | large | original"),
    save_cover_size: Optional[str] = typer.Option(None, "--save-cover-size",
        help="Sidecar cover size: thumbnail | small | large | original"),
    start: int = typer.Option(1, "--start",
        help="1-based release index (over releases, NOT tracks)"),
    end: Optional[int] = typer.Option(None, "--end",
        help="1-based release index to end at (inclusive)"),
    no_warnings: bool = typer.Option(False, "--no-warnings",
        help="Suppress harmless range warnings"),
) -> None:
    """
    Download an artist's full discography.

    \b
    Examples:
        kabooz artist 298
        kabooz artist https://open.qobuz.com/artist/298 --type album
        kabooz artist 298 --type album,live -q flac_16
    """
    cfg  = _cfg()
    q    = _quality(quality)
    sess = _session(cfg)

    try:
        artist_id  = _resolve_id(url_or_id, "artist")
        artist_obj = sess.get_artist(artist_id, extras="")
        console.print(
            f"[cyan]Downloading discography:[/cyan] [bold]{artist_obj.name}[/bold]"
            + (f"  [dim](type: {release_type})[/dim]" if release_type else "")
        )
    except Exception as exc:
        err_console.print(f"[red]Could not fetch artist:[/red] {exc}")
        raise typer.Exit(code=1)

    grand_ok   = 0
    grand_skip = 0
    grand_fail = 0

    def on_done(r) -> None:
        nonlocal grand_ok, grand_skip
        if r.download.skipped:
            grand_skip += 1
            console.print("       [yellow]↩ already complete[/yellow]")
        else:
            grand_ok += 1

    try:
        results = sess.download_artist_discography(
            url_or_id,
            release_type=release_type,
            quality=q,
            dest_dir=output or Path(cfg.download.output_dir),
            template=template,
            start=start, end=end,
            on_warning=_warn_cb(no_warnings),
            on_album_start=_on_album_start,
            on_track_start=_on_track_start,
            on_track_done=on_done,
            connections=connections,
            no_chunks=no_chunks,
            cover_size=_cover_size(cover_size),
            sidecar_size=_cover_size(save_cover_size),
        )
        grand_fail = sum(len(r.failed) for r in results)
    except (TokenExpiredError, InvalidCredentialsError, NoAuthError) as exc:
        _handle_auth_error(exc)
    except ValueError as exc:
        err_console.print(f"[red]Invalid range:[/red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(
        f"\n[green]Done.[/green] "
        f"{len(results)} albums · {grand_ok} tracks downloaded · "
        f"{grand_skip} skipped"
        + (f" · [red]{grand_fail} failed[/red]" if grand_fail else "") + "."
    )
    for r in results:
        _print_failed(r.failed, label=f"Failed in {r.album.display_title}")

@app.command()
def favorites(
    fav_type: str            = typer.Option("tracks", "--type", "-t",
                                            help="tracks or albums"),
    output:   Optional[Path] = typer.Option(None, "-o", "--output"),
    quality:  Optional[str]  = typer.Option(None, "-q", "--quality"),
    connections: Optional[int] = typer.Option(None, "-x", "--connections",
        help="Byte-range chunks per track (default from config)"),
    no_chunks: bool = typer.Option(False, "--no-chunks",
        help="Disable chunked download even if -x > 1"),
    cover_size: Optional[str] = typer.Option(None, "--cover-size",
        help="Embedded cover size: thumbnail | small | large | original"),
    save_cover_size: Optional[str] = typer.Option(None, "--save-cover-size",
        help="Sidecar cover size: thumbnail | small | large | original"),
) -> None:
    """
    Download all favorited tracks or albums.

    \b
    Examples:
        qobuz favorites
        qobuz favorites --type albums -q flac_16
    """
    if fav_type not in ("tracks", "albums"):
        err_console.print("[red]--type must be 'tracks' or 'albums'[/red]")
        raise typer.Exit(code=1)

    cfg  = _cfg()
    q    = _quality(quality)
    sess = _session(cfg)
    console.print(f"[cyan]Downloading favorite {fav_type}…[/cyan]")
    try:
        result = sess.download_favorites(
            fav_type=fav_type,
            quality=q,
            dest_dir=output or Path(cfg.download.output_dir),
            on_track_start=_on_track_start,
            on_track_done=_on_track_done,
            connections=connections,
            no_chunks=no_chunks,
            cover_size=_cover_size(cover_size),
            sidecar_size=_cover_size(save_cover_size),
        )
    except PoolModeError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    except (TokenExpiredError, InvalidCredentialsError, NoAuthError) as exc:
        _handle_auth_error(exc)
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(
        f"\n[green]Done.[/green] "
        f"{result.succeeded} downloaded, {result.skipped} skipped"
        + (f", [red]{len(result.failed)} failed[/red]" if result.failed else "") + "."
    )

@app.command()
def purchases(
    purchase_type: str            = typer.Option("albums", "--type", "-t",
                                                 help="albums or tracks"),
    output:        Optional[Path] = typer.Option(None, "-o", "--output"),
    quality:       Optional[str]  = typer.Option(None, "-q", "--quality"),
    connections: Optional[int] = typer.Option(None, "-x", "--connections",
        help="Byte-range chunks per track (default from config)"),
    no_chunks: bool = typer.Option(False, "--no-chunks",
        help="Disable chunked download even if -x > 1"),
    cover_size: Optional[str] = typer.Option(None, "--cover-size",
        help="Embedded cover size: thumbnail | small | large | original"),
    save_cover_size: Optional[str] = typer.Option(None, "--save-cover-size",
        help="Sidecar cover size: thumbnail | small | large | original"),
) -> None:
    """Download all purchased albums or tracks."""
    if purchase_type not in ("albums", "tracks"):
        err_console.print("[red]--type must be 'albums' or 'tracks'[/red]")
        raise typer.Exit(code=1)

    cfg  = _cfg()
    q    = _quality(quality)
    sess = _session(cfg)
    console.print(f"[cyan]Downloading purchased {purchase_type}…[/cyan]")
    try:
        result = sess.download_purchases(
            purchase_type=purchase_type,
            quality=q,
            dest_dir=output or Path(cfg.download.output_dir),
            on_track_start=_on_track_start,
            on_track_done=_on_track_done,
            connections=connections,
            no_chunks=no_chunks,
            cover_size=_cover_size(cover_size),
            sidecar_size=_cover_size(save_cover_size),
        )
    except (TokenExpiredError, InvalidCredentialsError, NoAuthError) as exc:
        _handle_auth_error(exc)
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(
        f"\n[green]Done.[/green] "
        f"{result.succeeded} downloaded, {result.skipped} skipped"
        + (f", [red]{len(result.failed)} failed[/red]" if result.failed else "") + "."
    )

@lpl_app.command("download")
def lpl_download(
    name:     str            = typer.Argument(...),
    output:   Optional[Path] = typer.Option(None, "-o"),
    quality:  Optional[str]  = typer.Option(None, "-q"),
    connections: Optional[int] = typer.Option(None, "-x", "--connections",
        help="Byte-range chunks per track (default from config)"),
    no_chunks: bool = typer.Option(False, "--no-chunks",
        help="Disable chunked download even if -x > 1"),
    template: Optional[str]  = typer.Option(None, "--template"),
    cover_size: Optional[str] = typer.Option(None, "--cover-size",
        help="Embedded cover size: thumbnail | small | large | original"),
    save_cover_size: Optional[str] = typer.Option(None, "--save-cover-size",
        help="Sidecar cover size: thumbnail | small | large | original"),
) -> None:
    """Download all tracks in a local playlist."""
    cfg  = _cfg()
    q    = _quality(quality)
    sess = _session(cfg)
    try:
        result = sess.download_local_playlist(
            name,
            quality=q,
            dest_dir=output or Path(cfg.download.output_dir),
            template=template,
            on_track_start=_on_track_start,
            on_track_done=_on_track_done,
            connections=connections,
            no_chunks=no_chunks,
            cover_size=_cover_size(cover_size),
            sidecar_size=_cover_size(save_cover_size),
        )
    except ValueError as exc:
        err_console.print(f"[red]{exc}[/red]"); raise typer.Exit(code=1)
    except (TokenExpiredError, InvalidCredentialsError, NoAuthError) as exc:
        _handle_auth_error(exc)
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)

    console.print(
        f"\n[green]Done.[/green] "
        f"{result.succeeded} downloaded, {result.skipped} skipped"
        + (f", [red]{len(result.failed)} failed[/red]" if result.failed else "") + "."
    )

_URL_FIELDS = [
    "track_id", "url", "format_id", "format", "mime_type",
    "bit_depth", "sampling_rate", "quality_label",
    "requested_quality", "reported",
]
_META_FIELDS = [
    "title", "artist", "album", "album_id", "duration",
    "isrc", "composer", "work", "year", "genre",
]


@app.command("url")
def stream_url(
    url_or_id: str = typer.Argument(..., help="Qobuz track URL or bare track ID"),
    quality: Optional[str] = typer.Option(None, "-q", "--quality",
        help="Quality: cd, hires, etc. Default: config."),
    json_output: bool = typer.Option(False, "--json",
        help="Format output as JSON. Changes format only, not content. "
             "Use --field to select fields."),
    field: Optional[str] = typer.Option(None, "--field",
        help="Comma-separated field names. Default: url."),
    report: bool = typer.Option(False, "--report",
        help="Opt in to reporting stream start to Qobuz. Off by default "
             "so scripted `kabooz url | xargs curl` does not create false "
             "play events."),
) -> None:
    """
    Resolve a track to its CDN stream URL.

    \b
    Examples:
      kabooz url 3503454                          # bare URL, fast
      kabooz url 3503454 --json                   # same, as JSON
      kabooz url 3503454 --field bit_depth        # bare value
      kabooz url 3503454 --field url,title --json # multiple fields, JSON
      kabooz url 3503454 --report | xargs mpv     # opt in to reporting

    \b
    Stream reporting:
      Download commands: never report
      TUI playback: always report (existing behaviour)
      kabooz url: silent; use --report to opt in
    """
    import json as _json

    sess = _session()
    try:
        _, track_id = sess.resolve_id(url_or_id, "track")
    except ValueError as exc:
        err_console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    q = sess.resolve_quality(quality)

    requested: list[str] = []
    if field:
        requested = [f.strip() for f in field.split(",") if f.strip()]
        unknown = [f for f in requested if f not in _URL_FIELDS + _META_FIELDS]
        if unknown:
            err_console.print(f"[red]Unknown field(s):[/red] {', '.join(unknown)}")
            err_console.print(f"[dim]URL fields:[/dim] {', '.join(_URL_FIELDS)}")
            err_console.print(f"[dim]Metadata fields (extra call):[/dim] {', '.join(_META_FIELDS)}")
            raise typer.Exit(code=1)
    else:
        requested = ["url"]

    need_meta = any(f in _META_FIELDS for f in requested)

    try:
        info = sess.resolve_stream(track_id, quality=q, report=report)
    except NotStreamableError as exc:
        err_console.print(f"[red]Not streamable:[/red] {exc}")
        raise typer.Exit(code=1)
    except (TokenExpiredError, InvalidCredentialsError, NoAuthError) as exc:
        _handle_auth_error(exc)
    except APIError as exc:
        err_console.print(f"[red]API error:[/red] {exc}")
        raise typer.Exit(code=1)

    def _tier(fmt_id: int) -> str:
        return {5: "MP3 320kbps", 6: "FLAC 16-bit / 44.1kHz",
                7: "FLAC 24-bit / 96kHz", 27: "FLAC 24-bit / 192kHz",
                }.get(fmt_id, f"format_id={fmt_id}")

    base = {
        "track_id": info.track_id, "url": info.url,
        "format_id": info.format_id,
        "format": "MP3" if info.format_id == 5 else "FLAC",
        "mime_type": info.mime_type, "bit_depth": info.bit_depth,
        "sampling_rate": info.sampling_rate,
        "quality_label": _tier(info.format_id),
        "requested_quality": q.name.lower(), "reported": report,
    }

    meta = {f: None for f in _META_FIELDS}
    if need_meta:
        try:
            t = sess.get_track(track_id)
            meta = {
                "title": t.display_title,
                "artist": t.performer.name if t.performer else None,
                "album": t.album.display_title if t.album else None,
                "album_id": t.album.id if t.album else None,
                "duration": t.duration,
                "isrc": t.isrc,
                "composer": t.composer.name if t.composer else None,
                "work": t.work,
                "year": (t.album.release_date_original or "")[:4] if t.album else None,
                "genre": (t.album.genre.name if t.album and t.album.genre
                         else (t.album.genres_list[0] if t.album and t.album.genres_list else None)),
            }
        except Exception:
            pass

    all_vals = {**base, **meta}
    selected = {k: all_vals.get(k) for k in requested}

    if json_output:
        typer.echo(_json.dumps(selected, indent=2, ensure_ascii=False))
        return

    if len(requested) == 1:
        v = selected[requested[0]]
        if v is None:
            typer.echo("null")
        elif isinstance(v, bool):
            typer.echo("true" if v else "false")
        elif isinstance(v, (dict, list)):
            typer.echo(_json.dumps(v, ensure_ascii=False))
        else:
            typer.echo(str(v))
    else:
        for k in requested:
            v = selected[k]
            if v is None:
                typer.echo("null")
            elif isinstance(v, bool):
                typer.echo("true" if v else "false")
            else:
                typer.echo(str(v))

