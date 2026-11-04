# kabooz/session/_types.py
"""
Value objects, callback aliases, and helpers extracted from the
session layer.

These are the parts of session that do not depend on QobuzSession:
the quality parser, result dataclasses, callback type aliases, and
the internal stream reporter. Extracted so that feature work on the
session layer can modify QobuzSession without scrolling past 400
lines of dataclasses.

Public import path is unchanged — session/__init__.py re-exports
all of these names.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..client import QobuzClient
from ..download.downloader import DownloadResult
from ..models.album import Album
from ..models.track import Track
from ..quality import Quality


# ══════════════════════════════════════════════════════════════════════════
# Quality parsing helper
# ══════════════════════════════════════════════════════════════════════════

def _parse_quality(s: str) -> Quality:
    """
    Parse a quality string without requiring Quality.from_str().

    Accepts enum names (case-insensitive), common aliases, and raw
    format_id integers.  Raises ValueError on unknown input.
    """
    _ALIASES: dict[str, Quality] = {
        "mp3":        Quality.MP3_320,
        "320":        Quality.MP3_320,
        "cd":         Quality.FLAC_16,
        "lossless":   Quality.FLAC_16,
        "flac":       Quality.FLAC_16,
        "24bit":      Quality.FLAC_24_96,
        "24_96":      Quality.FLAC_24_96,
        "hires":      Quality.HI_RES,
        "hi_res":     Quality.HI_RES,
        "best":       Quality.HI_RES,
        "max":        Quality.HI_RES,
    }
    n = s.strip().lower().replace("-", "_")
    try:
        return Quality[n.upper()]
    except KeyError:
        pass
    if n in _ALIASES:
        return _ALIASES[n]
    try:
        return Quality(int(s))
    except (ValueError, KeyError):
        pass
    valid = ", ".join(m.name.lower() for m in Quality)
    raise ValueError(
        f"Unknown quality {s!r}. "
        f"Valid: {valid}. "
        f"Aliases: {', '.join(_ALIASES)}"
    )


# ══════════════════════════════════════════════════════════════════════════
# Public result types
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class StreamInfo:
    """
    Returned by prepare_stream(). Contains everything the TUI or any
    other player needs to start playback and report to Qobuz.
    """
    track_id:      str
    url:           str
    format_id:     int
    bit_depth:     Optional[int]   = None
    sampling_rate: Optional[float] = None
    mime_type:     str             = "audio/flac"


@dataclass
class TrackDownloadResult:
    download:     DownloadResult
    track:        Track
    album:        Optional[Album] = None
    tagged:       bool = False
    lyrics_found: bool = False
    mb_enriched:  bool = False


@dataclass
class AlbumDownloadResult:
    album: Album
    tracks: list[TrackDownloadResult] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    goodies_ok: int = 0
    goodies_failed: int = 0
    mb_attempted: int = 0
    mb_succeeded: int = 0
    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.tracks if not r.download.skipped)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.tracks if r.download.skipped)


@dataclass
class PlaylistDownloadResult:
    name:   str
    tracks: list[TrackDownloadResult] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.tracks if not r.download.skipped)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.tracks if r.download.skipped)


# Callback signatures
ProgressCallback   = Callable[[int, int], None]           # (bytes_done, total_bytes)
TrackStartCallback = Callable[[str, int, int], None]       # (title, index, total)
TrackDoneCallback  = Callable[[TrackDownloadResult], None]
TrackFailCallback  = Callable[[str, str], None]           # (title, reason)
AlbumStartCallback = Callable[[str, int, int], None]       # (title, index, total)


# ══════════════════════════════════════════════════════════════════════════
# Internal stream reporter
# ══════════════════════════════════════════════════════════════════════════

class _StreamReporter:
    """
    Sends stream start/end events to the Qobuz API.
    Access only through QobuzSession.report_stream_* methods.
    """

    def __init__(self, client: QobuzClient, enabled: bool = True) -> None:
        self._client  = client
        self._enabled = enabled
        self._lock    = threading.Lock()
        self._active: dict[str, float] = {}   # track_id → wall-clock start

    def start(self, track_id: str, format_id: int = 27) -> None:
        if not self._enabled:
            return
        with self._lock:
            self._active[track_id] = time.time()
        try:
            self._client._request(
                "GET", "/track/reportStreamingStart",
                params={"track_id": track_id, "format_id": format_id, "intent": "stream"},
            )
        except Exception:
            pass   # reporting is best-effort; never crash playback

    def end(self, track_id: str, duration_seconds: Optional[int] = None) -> None:
        if not self._enabled:
            return
        with self._lock:
            started = self._active.pop(track_id, None)
        elapsed = duration_seconds
        if elapsed is None and started is not None:
            elapsed = int(time.time() - started)
        try:
            params: dict[str, Any] = {"track_id": track_id}
            if elapsed is not None:
                params["duration"] = elapsed
            self._client._request("GET", "/track/reportStreamingEnd", params=params)
        except Exception:
            pass

    def cancel(self, track_id: str) -> None:
        """Cancel without reporting end (e.g. track skipped before 30 s)."""
        with self._lock:
            self._active.pop(track_id, None)


