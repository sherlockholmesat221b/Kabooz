# kabooz/download/downloader.py
from __future__ import annotations

import shlex
import threading
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, IO, Optional

import httpx

from ..models.track import Track
from ..models.album import Album, Goodie
from .naming import resolve_track_path, sanitize
from .rate_limiter import RateLimiter


# ── Result objects ─────────────────────────────────────────────────────────

@dataclass
class DownloadResult:
    """
    Returned by every track download method.

    Attributes:
        path:          Absolute path where the file was written.
                       For a fresh/resumed download this is the .part path
                       until session._post_download renames it to the final
                       path after tagging completes.
        bytes_written: Bytes written this session (partial for resumes).
        total_bytes:   Total file size in bytes.
        skipped:       Final file already exists — nothing to do.
        resumed:       Download was resumed from a partial .part file.
        dev_stub:      True when the file is a stub (not real audio).
                       When True, the full tagging pipeline is skipped.
    """
    path: Path
    bytes_written: int
    total_bytes: int
    skipped: bool = False
    resumed: bool = False
    dev_stub: bool = False


@dataclass
class GoodieResult:
    """Result of downloading a single goodie (bonus file)."""
    path: Path
    goodie: Goodie
    skipped: bool = False
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class AlbumDownloadResult:
    """Aggregate result of downloading a full album."""
    tracks:  list[DownloadResult]       = field(default_factory=list)
    goodies: list[GoodieResult]         = field(default_factory=list)
    failed:  list[tuple[int, str]]      = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.tracks if not r.skipped)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.tracks if r.skipped)


# ── Downloader ─────────────────────────────────────────────────────────────

def _plan_chunks(total: int, n: int) -> list[tuple[int, int]]:
    """Split [0, total-1] into n contiguous (start, end) byte ranges."""
    if n < 1:
        n = 1
    if total <= 0:
        return [(0, 0)]
    n = min(n, total)
    base = total // n
    ranges = []
    for i in range(n):
        start = i * base
        end = total - 1 if i == n - 1 else start + base - 1
        ranges.append((start, end))
    return ranges


def _assemble_chunks(chunk_paths: list[Path], dest: Path) -> None:
    """Concatenate chunk files into dest, then remove them."""
    tmp = Path(str(dest) + ".tmp")
    with open(tmp, "wb") as out:
        for cp in chunk_paths:
            with open(cp, "rb") as inp:
                shutil.copyfileobj(inp, out, length=1024 * 1024)
    tmp.replace(dest)
    for cp in chunk_paths:
        try:
            cp.unlink()
        except FileNotFoundError:
            pass


class Downloader:
    """
    Downloads audio files and goodies from Qobuz CDN URLs.

    Features
    ────────
    - .part file convention: bytes are written to <dest>.part and only
      renamed to the final path after the full post-download pipeline
      (tagging, MusicBrainz, etc.) completes successfully in session.py.
      This means final_path.exists() is an unambiguous "fully done" signal,
      identical to how yt-dlp works.
    - Skip / resume logic:
        · final_path.exists()             → skip everything (skipped=True)
        · part_path size >= Content-Length → bytes complete, re-tag only
        · part_path size < Content-Length  → resume from offset
        · no part_path                    → fresh download
    - Optional multithreaded album/playlist downloads via max_workers.
    - Optional external downloader (e.g. aria2c) via a shell template.
    - Naming template support (passed through to resolve_track_path).
    - Goodie (bonus file) downloading into the album folder.
    - Dev mode: writes real audio (transcoded from the embedded Opus clip)
      instead of streaming from Qobuz. Falls back to a sine wave if the
      clip isn't baked yet, then to stub bytes as a last resort.
      Dev mode writes directly to the final path (no .part) since it
      never does real network I/O.

    External downloader template
    ────────────────────────────
    Set external_downloader to a shell command with {url} and {output}
    placeholders. {output} will be the .part path; session renames it
    after tagging. Examples:

        "aria2c -x 16 -s 16 -d {dir} -o {filename} {url}"
        "wget -O {output} {url}"

    When set, the built-in httpx streaming is bypassed entirely for file
    downloads. Skip/resume logic still runs first.

    Threading
    ─────────
    max_workers=1 (default) is sequential. Higher values parallelise
    track downloads within an album or playlist. Each worker uses its
    own httpx.Client to avoid connection sharing issues.
    """

    def __init__(
        self,
        http_client: Optional[httpx.Client] = None,
        chunk_size: int = 8192,
        read_timeout: float = 300.0,
        connect_timeout: float = 10.0,
        max_workers: int = 1,
        max_retries: int = 2,
        external_downloader: str = "",
        naming_template: Optional[str] = None,
        dev: bool = False,
        connections_per_track: int = 1,
        chunk_size_mb: int = 10,
        rate_limit_kbps: int = 0,
    ) -> None:
        self._chunk_size          = chunk_size
        self._read_timeout        = read_timeout
        self._connect_timeout     = connect_timeout
        self._max_workers         = max(1, max_workers)
        self._max_retries         = max(0, max_retries)
        self._external_downloader = external_downloader.strip()
        self._naming_template     = naming_template
        self._dev                 = dev
        self._connections_per_track = max(1, connections_per_track)
        self._chunk_size_mb = max(1, chunk_size_mb)
        self._rate_limiter = RateLimiter(rate_limit_kbps) if rate_limit_kbps > 0 else None
        self._http = http_client or self._make_client()

    def _make_client(self) -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(self._read_timeout, connect=self._connect_timeout),
            follow_redirects=True,
        )

    # ── Public interface ───────────────────────────────────────────────────

    def download_track(
        self,
        track: Track,
        url_info: dict,
        dest_dir: str | Path,
        album: Optional[Album] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
        playlist_name: Optional[str] = None,
        playlist_index: Optional[int] = None,
        connections: Optional[int] = None,
        no_chunks: bool = False,
    ) -> DownloadResult:
        """
        Download a single track.

        Returns a DownloadResult whose .path is:
          · the final path                  when skipped=True or dev_stub=True
          · the .part path (needs rename)   for all other cases

        session._post_download() is responsible for tagging the .part file
        and renaming it to the final path on success.

        Parameters:
            track:          Full Track object (not TrackSummary).
            url_info:       Dict from client.get_track_url(). Must have "url";
                            optionally "bit_depth", "sampling_rate", "mime_type".
            dest_dir:       Root directory.
            album:          Album context for folder structure and naming.
            on_progress:    Callback(bytes_done, total_bytes).
            playlist_name:  Passed to naming template as {playlist}.
            playlist_index: Passed to naming template as {index}.
        """
        dest_dir = Path(dest_dir)
        url  = url_info["url"]
        mime = url_info.get("mime_type", "").lower()

        # If the URL contains 'mp3' or MIME is mpeg, it's an MP3. Period.
        if "mpeg" in mime or "mp3" in mime or ".mp3" in url.lower():
            extension = ".mp3"
        else:
            extension = ".flac"

        bit_depth     = url_info.get("bit_depth")
        sampling_rate = url_info.get("sampling_rate")

        is_multi_disc = (
            album is not None
            and album.media_count is not None
            and album.media_count > 1
        )

        dest_path = resolve_track_path(
            track=track,
            dest_dir=dest_dir,
            extension=extension,
            album=album,
            is_multi_disc=is_multi_disc,
            bit_depth=bit_depth,
            sampling_rate=sampling_rate,
            template=self._naming_template,
            playlist_name=playlist_name,
            playlist_index=playlist_index,
        )

        from ..dev import dev_log
        dev_log(f"resolved path → {dest_path}")

        if self._external_downloader:
            return self._external_download(url, dest_path, on_progress)

        n_conn = connections if connections is not None else self._connections_per_track
        if n_conn > 1 and not no_chunks and not self._dev:
            try:
                return self._download_chunked(url, dest_path, on_progress, n_conn)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (400, 416):
                    from ..dev import dev_log
                    dev_log(f"[yellow]chunked: {exc.response.status_code}, fallback[/yellow]")
                    self._cleanup_chunks(dest_path)
                    return self._download_to_path(url, dest_path, on_progress)
                raise

        return self._download_to_path(url, dest_path, on_progress)

    def download_album(
        self,
        tracks: list[tuple[Track, dict]],
        dest_dir: str | Path,
        album: Optional[Album] = None,
        on_track_start: Optional[Callable[[Track, int, int], None]] = None,
        on_track_done: Optional[Callable[[Track, DownloadResult], None]] = None,
        on_track_error: Optional[Callable[[Track, Exception], None]] = None,
        download_goodies: bool = True,
    ) -> AlbumDownloadResult:
        """
        Download multiple tracks, optionally in parallel.

        Callbacks receive the Track object so the caller can update a
        progress display without inspecting the result list mid-flight.

        When max_workers > 1 the callbacks may be called from worker
        threads — make them thread-safe (e.g. use rich's thread-safe
        Console rather than bare print).

        When download_goodies is True and album has goodies, they are
        downloaded sequentially after all tracks finish.

        Note: this method is not currently called by session.py, which
        manages its own loop to interleave tagging per-track. It is
        provided for callers that only need raw bytes (no tagging).
        """
        dest_dir = Path(dest_dir)
        result   = AlbumDownloadResult()
        total    = len(tracks)

        def _do(item: tuple[Track, dict], index: int) -> DownloadResult:
            track, url_info = item
            if on_track_start:
                on_track_start(track, index, total)
            return self.download_track(
                track=track,
                url_info=url_info,
                dest_dir=dest_dir,
                album=album,
            )

        if self._max_workers == 1:
            for i, item in enumerate(tracks, 1):
                track, _ = item
                try:
                    r = _do(item, i)
                    result.tracks.append(r)
                    if on_track_done:
                        on_track_done(track, r)
                except Exception as exc:
                    result.failed.append((track.id, str(exc)))
                    if on_track_error:
                        on_track_error(track, exc)
        else:
            futures = {}
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                for i, item in enumerate(tracks, 1):
                    f = pool.submit(_do, item, i)
                    futures[f] = item[0]
                for f in as_completed(futures):
                    track = futures[f]
                    try:
                        r = f.result()
                        result.tracks.append(r)
                        if on_track_done:
                            on_track_done(track, r)
                    except Exception as exc:
                        result.failed.append((track.id, str(exc)))
                        if on_track_error:
                            on_track_error(track, exc)

        # ── Goodies ───────────────────────────────────────────────────────
        if download_goodies and album and album.goodies:
            album_dir = dest_dir
            if result.tracks:
                candidate = result.tracks[0].path.parent
                if album.media_count and album.media_count > 1:
                    candidate = candidate.parent
                if candidate.is_dir():
                    album_dir = candidate

            for goodie in album.goodies:
                gr = self.download_goodie(goodie, album_dir)
                result.goodies.append(gr)

        return result

    def download_goodie(
        self,
        goodie: Goodie,
        dest_dir: Path,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> GoodieResult:
        """
        Download a single bonus file (booklet PDF, video, etc.).

        Goodies are non-audio files (PDFs, videos) — they don't go through
        the tagging pipeline, so we write directly to the final path using
        the same size-based skip/resume logic as before.
        """
        url = goodie.original_url or goodie.url
        if not url:
            return GoodieResult(
                path=dest_dir / sanitize(goodie.name),
                goodie=goodie,
                error="No URL available for this goodie",
            )

        url_filename = url.split("?")[0].rstrip("/").split("/")[-1]
        filename = sanitize(url_filename) if url_filename else sanitize(goodie.name)
        if not filename:
            filename = f"goodie_{goodie.id}"

        dest_path = dest_dir / filename

        from ..dev import dev_log
        dev_log(f"goodie '{goodie.name}' → {dest_path}")

        try:
            result = self._download_goodie_to_path(url, dest_path, on_progress)
            return GoodieResult(path=result.path, goodie=goodie, skipped=result.skipped)
        except Exception as exc:
            return GoodieResult(path=dest_path, goodie=goodie, error=str(exc))

    def download_to_file(
        self,
        url: str,
        dest: IO[bytes],
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> DownloadResult:
        """
        Low-level: stream a URL into any writable binary file-like object.
        No skip/resume logic — the caller controls the destination.
        """
        with self._http.stream("GET", url) as response:
            response.raise_for_status()
            total   = int(response.headers.get("content-length", 0))
            written = 0
            for chunk in response.iter_bytes(chunk_size=self._chunk_size):
                dest.write(chunk)
                written += len(chunk)
                if on_progress:
                    on_progress(written, total)

        return DownloadResult(
            path=Path(),
            bytes_written=written,
            total_bytes=total or written,
        )

    # ── Internal download logic ────────────────────────────────────────────

    def _head(self, url: str) -> int:
        """Return Content-Length from a HEAD request, or 0 on failure."""
        try:
            head = self._http.head(url)
            return int(head.headers.get("content-length", 0))
        except Exception:
            return 0

    def _download_to_path(
        self,
        url: str,
        path: Path,
        on_progress: Optional[Callable[[int, int], None]],
    ) -> DownloadResult:
        """
        Download url to path using the .part convention.

        State machine:
            path.exists()              → already fully done (skip)
            part_path size >= CDN len  → bytes done, tagging failed last run
                                         (return part_path for re-tagging)
            part_path size < CDN len   → partial, resume from offset
            no part_path               → fresh download
        """
        # ── Dev mode: write directly to final path, skip by existence ─────
        if self._dev:
            from ..dev import prepare_dev_audio, is_stub, DEV_STUB_BYTES, dev_log

            if path.exists():
                size = path.stat().st_size
                if on_progress:
                    on_progress(size, size)
                return DownloadResult(
                    path=path,
                    bytes_written=0,
                    total_bytes=size,
                    skipped=True,
                    dev_stub=is_stub(path),
                )

            is_real_audio = prepare_dev_audio(path)
            size = path.stat().st_size if path.exists() else len(DEV_STUB_BYTES)
            if on_progress:
                on_progress(size, size)
            return DownloadResult(
                path=path,
                bytes_written=size,
                total_bytes=size,
                dev_stub=not is_real_audio,
            )

        # ── Normal path ────────────────────────────────────────────────────
        from ..dev import dev_log

        # Final file exists → download + tagging both completed previously.
        if path.exists():
            size = path.stat().st_size
            if on_progress:
                on_progress(size, size)
            return DownloadResult(
                path=path, bytes_written=0, total_bytes=size, skipped=True,
            )

        part_path = Path(str(path) + ".part")
        total     = self._head(url)
        part_size = part_path.stat().st_size if part_path.exists() else 0

        # .part complete but tagging must have failed last run — return it
        # so session._post_download re-runs the pipeline without re-downloading.
        if total > 0 and part_size >= total:
            dev_log(f"part complete, re-tagging → {part_path.name}")
            if on_progress:
                on_progress(total, total)
            return DownloadResult(
                path=part_path,
                bytes_written=0,
                total_bytes=total,
                resumed=False,
            )


        # ── NEW: retry wrapper ─────────────────────────────────
        for attempt in range(self._max_retries + 1):
            try:
                return self._stream_to_part(url, part_path, total, on_progress)
            except httpx.TransportError as exc:
                if attempt < self._max_retries:
                    from ..dev import dev_log
                    dev_log(f"[yellow]retry {attempt+1}/{self._max_retries}: {exc}[/yellow]")
                    continue
                raise


    def _stream_to_part(self, url, part_path, total, on_progress):
        """The streaming loop — extracted from _download_to_path so it
        can be called repeatedly by the retry wrapper above."""
        part_size = part_path.stat().st_size if part_path.exists() else 0

        resumed = total > 0 and part_size > 0 and part_size < total
        headers = {"Range": f"bytes={part_size}-"} if resumed else {}
        written = 0
        mode    = "ab" if resumed else "wb"

        part_path.parent.mkdir(parents=True, exist_ok=True)
        with open(part_path, mode) as f:
            with self._http.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes(chunk_size=self._chunk_size):
                    f.write(chunk)
                    written += len(chunk)
                    if self._rate_limiter is not None:
                        self._rate_limiter.consume(len(chunk))
                    if on_progress:
                        on_progress(part_size + written, total or written)

        return DownloadResult(
            path=part_path, bytes_written=written,
            total_bytes=total or written, resumed=resumed,
        )

    def _cleanup_chunks(self, dest_path: Path) -> None:
        part_path = Path(str(dest_path) + ".part")
        for i in range(64):
            try:
                Path(f"{part_path}.{i}").unlink()
            except FileNotFoundError:
                pass

    def _download_chunked(
        self, url: str, path: Path,
        on_progress: Optional[Callable[[int, int], None]], n_conn: int,
    ) -> DownloadResult:
        from ..dev import dev_log
        part_path = Path(str(path) + ".part")
        if path.exists():
            size = path.stat().st_size
            if on_progress:
                on_progress(size, size)
            return DownloadResult(path=path, bytes_written=0, total_bytes=size, skipped=True)
        total = self._head(url)
        if total == 0:
            dev_log("[yellow]chunked: no Content-Length, falling back[/yellow]")
            return self._download_to_path(url, path, on_progress)
        if part_path.exists() and part_path.stat().st_size == total:
            return DownloadResult(path=part_path, bytes_written=0, total_bytes=total)
        ranges = _plan_chunks(total, n_conn)
        n = len(ranges)
        chunk_paths = [Path(f"{part_path}.{i}") for i in range(n)]
        done: set[int] = set()
        bytes_at_start = 0
        for i, (start, end) in enumerate(ranges):
            expected = end - start + 1
            cp = chunk_paths[i]
            if cp.exists() and cp.stat().st_size == expected:
                done.add(i)
                bytes_at_start += expected
        dev_log(f"chunked: {len(done)}/{n} pre-complete, {n - len(done)} to download ({n_conn} workers)")
        chunk_bytes = [0] * n
        for i in done:
            start, end = ranges[i]
            chunk_bytes[i] = end - start + 1
        progress_lock = threading.Lock()

        def _download_one(idx: int) -> None:
            start, end = ranges[idx]
            cp = chunk_paths[idx]
            expected = end - start + 1
            existing = cp.stat().st_size if cp.exists() else 0
            if existing >= expected:
                return
            req_start = start + existing
            headers = {"Range": f"bytes={req_start}-{end}"}
            mode = "ab" if existing > 0 else "wb"
            cp.parent.mkdir(parents=True, exist_ok=True)
            with open(cp, mode) as f:
                with self._http.stream("GET", url, headers=headers) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes(chunk_size=self._chunk_size):
                        f.write(chunk)
                        if self._rate_limiter is not None:
                            self._rate_limiter.consume(len(chunk))
                        with progress_lock:
                            chunk_bytes[idx] += len(chunk)
                            if on_progress:
                                on_progress(sum(chunk_bytes), total)

        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            failed: list[int] = []
            with ThreadPoolExecutor(max_workers=min(n, n_conn)) as pool:
                futures = {pool.submit(_download_one, i): i for i in range(n) if i not in done}
                for fut in as_completed(futures):
                    idx = futures[fut]
                    try:
                        fut.result()
                        done.add(idx)
                    except httpx.HTTPStatusError:
                        raise
                    except Exception as exc:
                        last_exc = exc
                        failed.append(idx)
            if not failed:
                break
            if attempt < self._max_retries:
                dev_log(f"[yellow]chunked retry {attempt+1}/{self._max_retries}: {len(failed)} failed[/yellow]")
            else:
                raise last_exc or httpx.TransportError("chunked download failed")
        _assemble_chunks(chunk_paths, part_path)
        return DownloadResult(
            path=part_path, bytes_written=total - bytes_at_start,
            total_bytes=total, resumed=bool(done),
        )

    def _external_download(
        self,
        url: str,
        path: Path,
        on_progress: Optional[Callable[[int, int], None]],
    ) -> DownloadResult:
        """
        Invoke an external downloader instead of the built-in one.

        The {output} and {filename} placeholders resolve to the .part path.
        session._post_download() renames it to the final path after tagging.

        Placeholders in the template:
            {url}      — the CDN URL
            {output}   — .part destination path (str)
            {dir}      — parent directory of {output}
            {filename} — basename of the .part path
        """
        from ..dev import dev_log

        # Final file exists → fully done.
        if path.exists():
            size = path.stat().st_size
            if on_progress:
                on_progress(size, size)
            return DownloadResult(
                path=path, bytes_written=0, total_bytes=size, skipped=True,
            )

        part_path = Path(str(path) + ".part")
        total     = self._head(url)
        part_size = part_path.stat().st_size if part_path.exists() else 0

        # .part complete — re-tag only.
        if total > 0 and part_size >= total:
            dev_log(f"part complete (external), re-tagging → {part_path.name}")
            if on_progress:
                on_progress(total, total)
            return DownloadResult(
                path=part_path, bytes_written=0, total_bytes=total,
            )

        part_path.parent.mkdir(parents=True, exist_ok=True)

        cmd_str = self._external_downloader.format(
            url      = url,
            output   = str(part_path),
            dir      = str(part_path.parent),
            filename = part_path.name,
        )

        try:
            subprocess.run(
                shlex.split(cmd_str),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace").strip()
            raise RuntimeError(
                f"External downloader failed (exit {exc.returncode}): {stderr}"
            ) from exc

        written = part_path.stat().st_size if part_path.exists() else 0
        if on_progress:
            on_progress(written, written)

        return DownloadResult(
            path=part_path,
            bytes_written=written,
            total_bytes=written,
        )

    def _download_goodie_to_path(self, url, path, on_progress):
        """Download a goodie directly to its final path (no .part convention),
        with bounded retry on TransportError."""
        total = self._head(url)                     # called once
        existing_size = path.stat().st_size if path.exists() else 0

        if total > 0 and existing_size >= total:
            if on_progress:
                on_progress(total, total)
            return DownloadResult(
                path=path, bytes_written=0, total_bytes=total, skipped=True,
            )

        for attempt in range(self._max_retries + 1):
            try:
                return self._stream_goodie(url, path, total, on_progress)
            except httpx.TransportError as exc:
                if attempt < self._max_retries:
                    from ..dev import dev_log
                    dev_log(f"[yellow]goodie retry {attempt+1}/{self._max_retries}: {exc}[/yellow]")
                    continue
                raise

    def _stream_goodie(self, url, path, total, on_progress):
        """The goodie streaming loop — extracted so the retry wrapper above
        can call it repeatedly. Reads existing_size fresh from disk each
        attempt so partial bytes from a prior failed attempt are resumed
        with a Range header, not re-fetched."""
        existing_size = path.stat().st_size if path.exists() else 0

        resumed = total > 0 and existing_size > 0 and existing_size < total
        headers = {"Range": f"bytes={existing_size}-"} if resumed else {}
        written = 0
        mode    = "ab" if resumed else "wb"

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, mode) as f:
            with self._http.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes(chunk_size=self._chunk_size):
                    f.write(chunk)
                    written += len(chunk)
                    if self._rate_limiter is not None:
                        self._rate_limiter.consume(len(chunk))
                    if on_progress:
                        on_progress(existing_size + written, total or written)

        return DownloadResult(
            path=path,
            bytes_written=written,
            total_bytes=total or written,
            resumed=resumed,
        )

    # ── Resource management ────────────────────────────────────────────────

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Downloader:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
