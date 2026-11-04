# kabooz/session/streaming.py
"""
Streaming methods for QobuzSession.

Prepares CDN stream URLs and reports stream start/end/cancel events
back to Qobuz. Extracted from session/__init__.py to keep
QobuzSession navigable.

The internal _StreamReporter instance is created once in
QobuzSession.__init__ (as self._reporter) and lives in _types.py;
these methods delegate to it. Move is mechanical — no logic changes.

Public import path unchanged.
"""
from __future__ import annotations

from typing import Optional

from ..quality import Quality

from ._types import StreamInfo


class StreamingMixin:
    """Mixin providing streaming URL resolution and event reporting.
    Composed into QobuzSession via class inheritance. Methods assume
    self.client and self._reporter are available on the instance."""

    def prepare_stream(
        self,
        track_id: str | int,
        quality: Quality = Quality.HI_RES,
    ) -> StreamInfo:
        """
        Resolve a CDN stream URL and report stream start to Qobuz.

        This is the ONLY way the TUI (or any player) should get a stream
        URL. It bundles URL resolution and stream reporting so reporting
        can never be accidentally skipped.

        Call report_stream_end() when playback stops normally.
        Call report_stream_cancel() when the track is skipped.
        """
        url_info = self.client.get_track_url(str(track_id), quality=quality)
        fmt_id   = url_info.get("format_id", int(quality))
        self._reporter.start(str(track_id), format_id=int(fmt_id))
        return StreamInfo(
            track_id      = str(track_id),
            url           = url_info["url"],
            format_id     = int(fmt_id),
            bit_depth     = url_info.get("bit_depth"),
            sampling_rate = url_info.get("sampling_rate"),
            mime_type     = url_info.get("mime_type", "audio/flac"),
        )

    def report_stream_end(
        self,
        track_id: str | int,
        duration_seconds: Optional[int] = None,
    ) -> None:
        """Report that playback of track_id ended normally."""
        self._reporter.end(str(track_id), duration_seconds)

    def report_stream_cancel(self, track_id: str | int) -> None:
        """Report that track_id was cancelled/skipped before finishing."""
        self._reporter.cancel(str(track_id))
