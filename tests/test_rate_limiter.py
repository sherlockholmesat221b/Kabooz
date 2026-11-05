# tests/test_rate_limiter.py
"""Tests for RateLimiter (feature #5 aggression knob)."""
import time

from kabooz.download.rate_limiter import RateLimiter


def test_disabled_when_kbps_zero():
    rl = RateLimiter(0)
    assert not rl.enabled
    start = time.monotonic()
    rl.consume(100_000_000)   # huge amount
    elapsed = time.monotonic() - start
    assert elapsed < 0.1   # no sleep


def test_enabled_when_kbps_positive():
    rl = RateLimiter(100)
    assert rl.enabled


def test_small_consume_under_budget():
    """Very small consume should not sleep meaningfully at start."""
    rl = RateLimiter(1000000)   # 1 MB/s
    start = time.monotonic()
    rl.consume(1000)   # 1 KB
    elapsed = time.monotonic() - start
    assert elapsed < 0.05


def test_rate_is_enforced():
    """100 KB/s target; consume 50 KB should take ~0.4s.
    Allow generous slack for CI/mobile variance."""
    rl = RateLimiter(1000)   # 1000 kbps = 125000 bytes/sec
    # First 1 KB is 'free' (buffer starts at 0, but we do not enforce first)
    rl.consume(1000)   # 1 KB — should be fast
    start = time.monotonic()
    rl.consume(50_000)   # 50 KB
    elapsed = time.monotonic() - start
    # 50000 / 125000 = 0.4s; allow 0.2 to 2.0 s slack
    assert 0.2 <= elapsed <= 2.0, f"expected ~0.4s, got {elapsed:.3f}s"


def test_disabled_consume_is_noop():
    rl = RateLimiter(0)
    start = time.monotonic()
    for _ in range(100):
        rl.consume(8192)
    elapsed = time.monotonic() - start
    assert elapsed < 0.1
