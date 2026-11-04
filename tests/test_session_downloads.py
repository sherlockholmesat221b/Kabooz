# tests/test_session_downloads.py
"""Tests for _slice_range — pure helper for ranged downloads (#7)."""
import pytest

from kabooz.session.downloads import _slice_range


class _Item:
    def __init__(self, id: int, media_number: int = 1):
        self.id = id
        self.media_number = media_number


def _tracks(n: int, media_count: int = 1) -> list[_Item]:
    per_disc = n // media_count
    out = []
    i = 0
    for d in range(1, media_count + 1):
        for _ in range(per_disc):
            out.append(_Item(i, media_number=d))
            i += 1
    return out


def test_full_range():
    items = _tracks(5)
    result = _slice_range(items)
    assert [r[1].id for r in result] == [0, 1, 2, 3, 4]
    assert [r[0] for r in result] == [1, 2, 3, 4, 5]


def test_start_only():
    items = _tracks(5)
    result = _slice_range(items, start=3)
    assert [r[1].id for r in result] == [2, 3, 4]


def test_end_only():
    items = _tracks(5)
    result = _slice_range(items, end=2)
    assert [r[1].id for r in result] == [0, 1]


def test_start_and_end():
    items = _tracks(10)
    result = _slice_range(items, start=3, end=5)
    assert [r[1].id for r in result] == [2, 3, 4]


def test_end_clamped_to_available():
    items = _tracks(5)
    result = _slice_range(items, start=2, end=100)
    assert [r[1].id for r in result] == [1, 2, 3, 4]


def test_start_exceeds_count_raises():
    items = _tracks(3)
    with pytest.raises(ValueError, match="start=5 exceeds available count \\(3\\)"):
        _slice_range(items, start=5)


def test_end_less_than_start_raises():
    items = _tracks(10)
    with pytest.raises(ValueError, match="end=2 is less than start=5"):
        _slice_range(items, start=5, end=2)


def test_disc_filter_selects_correct_tracks():
    items = _tracks(6, media_count=2)
    result = _slice_range(items, disc=2)
    assert [r[1].id for r in result] == [3, 4, 5]
    assert [r[0] for r in result] == [4, 5, 6]


def test_disc_within_disc_range():
    items = _tracks(6, media_count=2)
    result = _slice_range(items, disc=2, start=1, end=2)
    assert [r[1].id for r in result] == [3, 4]


def test_disc_1_on_monodisc_passes():
    items = _tracks(5, media_count=1)
    result = _slice_range(items, disc=1)
    assert [r[1].id for r in result] == [0, 1, 2, 3, 4]


def test_disc_not_found_raises():
    items = _tracks(6, media_count=2)
    with pytest.raises(ValueError, match="disc 3 not found in collection"):
        _slice_range(items, disc=3)


def test_disc_start_within_disc_exceeds_raises():
    items = _tracks(6, media_count=2)
    with pytest.raises(ValueError, match="start=5 exceeds available count \\(3\\)"):
        _slice_range(items, disc=2, start=5)


def test_empty_input():
    with pytest.raises(ValueError):
        _slice_range([], start=1)


def test_single_item():
    items = _tracks(1)
    result = _slice_range(items, start=1, end=1)
    assert len(result) == 1
    assert result[0][1].id == 0


def test_end_exceeds_count_warns():
    items = _tracks(5)
    warnings: list[str] = []
    result = _slice_range(items, end=100, warnings_out=warnings)
    assert len(result) == 5
    assert "end=100 exceeded available count (5)" in warnings[0]


def test_end_equals_count_no_warning():
    items = _tracks(5)
    warnings: list[str] = []
    _slice_range(items, end=5, warnings_out=warnings)
    assert warnings == []


def test_disc_1_on_monodisc_warns():
    items = _tracks(5, media_count=1)
    warnings: list[str] = []
    _slice_range(items, disc=1, warnings_out=warnings)
    assert len(warnings) == 1
    assert "--disc 1 had no effect" in warnings[0]


def test_disc_1_on_multidisc_no_warning():
    items = _tracks(6, media_count=2)
    warnings: list[str] = []
    _slice_range(items, disc=1, warnings_out=warnings)
    assert warnings == []


def test_no_warnings_out_silent():
    items = _tracks(5)
    result = _slice_range(items, end=100, warnings_out=None)
    assert len(result) == 5
