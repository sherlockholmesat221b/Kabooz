# kabooz/download/rate_limiter.py
"""
Simple token-bucket-ish rate limiter for aggregate download bandwidth.

Thread-safe. Multiple concurrent callers share one budget. Tracks
cumulative bytes consumed since start and sleeps to enforce the
aggregate target rate. If actual bandwidth is below the target, no
sleep is added (max speed). If above, sleep brings the average down.
"""
from __future__ import annotations

import threading
import time


class RateLimiter:
    """
    kbps: kilobits per second (kbps * 1000 / 8 = bytes/sec). 0 = unlimited.
    """
    def __init__(self, kbps: int) -> None:
        self._bytes_per_sec = (kbps * 1000) / 8 if kbps > 0 else 0.0
        self._lock = threading.Lock()
        self._total_bytes = 0
        self._start = time.monotonic()

    @property
    def enabled(self) -> bool:
        return self._bytes_per_sec > 0

    def consume(self, n_bytes: int) -> None:
        if self._bytes_per_sec == 0 or n_bytes <= 0:
            return
        with self._lock:
            self._total_bytes += n_bytes
            expected = self._total_bytes / self._bytes_per_sec
            actual = time.monotonic() - self._start
            sleep_time = expected - actual
        if sleep_time > 0:
            time.sleep(sleep_time)
