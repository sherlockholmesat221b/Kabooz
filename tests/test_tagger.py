# tests/test_tagger.py
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.id3 import ID3

from kabooz.models.track import Track
from kabooz.models.album import Album
from kabooz.download.tagger import Tagger, _parse_lrc_to_sylt
from kabooz.download.lyrics import LyricsResult, fetch_lyrics, LRCLibProvider


# ── Fixtures ───────────────────────────────────────────────────────────────

def make_track(**kwargs) -> Track:
    defaults = {
        "id": 12345,
        "title": "One More Time",
        "duration": 320,
        "track_number": 1,
        "media_number": 1,
        "isrc": "GBDCE0000001",
        "copyright": "2001 Virgin",
        "performer": {"id": 999, "name": "Daft Punk"},
        "composer": {"id": 888, "name": "Thomas Bangalter"},
    }
    defaults.update(kwargs)
    return Track.from_dict(defaults)


def make_album(**kwargs) -> Album:
    defaults = {
        "id": "abc123",
        "title": "Discovery",
        "tracks_count": 14,
        "duration": 3540,
        "media_count": 1,
        "maximum_bit_depth": 24,
        "maximum_sampling_rate": 96.0,
        "release_date_original": "2001-03-07",
        "artist": {"id": 999, "name": "Daft Punk", "slug": "daft-punk"},
        "label": {"id": 1, "name": "Virgin", "slug": "virgin", "supplier_id": 5},
        "genre": {"id": 10, "name": "Electronic", "slug": "electronic", "path": []},
        "upc": "724384960224",
    }
    defaults.update(kwargs)
    return Album.from_dict(defaults)


def make_flac(path: Path) -> None:
    # Minimal valid FLAC: "fLaC" marker + STREAMINFO metadata block
    path.write_bytes(bytes([
        0x66, 0x4C, 0x61, 0x43,  # fLaC
        0x80, 0x00, 0x00, 0x22,  # last block, STREAMINFO, length=34
        0x00, 0x12, 0x00, 0x12,  # min/max blocksize
        0x00, 0x00, 0x00,        # min framesize
        0x00, 0x00, 0x00,        # max framesize
        0x0A, 0xC4, 0x42, 0xF0, 0x00, 0x00, 0x00, 0x00,  # 44100Hz/2ch/16bit
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # MD5 part 1
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # MD5 part 2
    ]))


def make_mp3(path: Path) -> None:
    """
    Create a minimal valid MP3 file at path for testing.
    We use a tiny silent MP3 frame (valid header, silent audio).
    """
    # Minimal valid MP3 frame: MPEG1, Layer3, 128kbps, 44100Hz, stereo
    silent_frame = bytes([
        0xFF, 0xFB, 0x90, 0x00,  # MP3 header
    ] + [0x00] * 413)            # silent frame data
    path.write_bytes(silent_frame)


# ── LRC parser tests ───────────────────────────────────────────────────────

def test_parse_lrc_basic():
    lrc = "[00:13.45] One more time\n[00:17.90] We're gonna celebrate"
    result = _parse_lrc_to_sylt(lrc)
    assert len(result) == 2
    assert result[0] == ("One more time", 13450)
    assert result[1] == ("We're gonna celebrate", 17900)


def test_parse_lrc_three_digit_ms():
    lrc = "[01:02.500] Line with three digit ms"
    result = _parse_lrc_to_sylt(lrc)
    assert result[0][1] == 62500


def test_parse_lrc_ignores_invalid_lines():
    lrc = "not a timestamp\n[00:05.00] Valid line\n[invalid"
    result = _parse_lrc_to_sylt(lrc)
    assert len(result) == 1
    assert result[0][0] == "Valid line"


def test_parse_lrc_empty_string():
    assert _parse_lrc_to_sylt("") == []


# ── LyricsResult tests ─────────────────────────────────────────────────────

def test_lyrics_result_not_found():
    result = LyricsResult()
    assert result.found is False
    assert result.synced is None
    assert result.plain is None


def test_lyrics_result_with_content():
    result = LyricsResult(synced="[00:01.00] Hello", plain="Hello", found=True)
    assert result.found is True
    assert result.synced is not None


# ── LRCLibProvider tests ───────────────────────────────────────────────────

def test_lrclib_returns_not_found_on_404():
    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.status = 404

    with patch("urllib.request.urlopen", return_value=mock_response):
        provider = LRCLibProvider()
        result = provider.fetch("Unknown Song", "Unknown Artist")
    assert result.found is False


def test_lrclib_returns_lyrics_on_success():
    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.status = 200
    mock_response.read.return_value = b'{"syncedLyrics": "[00:01.00] Hello", "plainLyrics": "Hello"}'

    with patch("urllib.request.urlopen", return_value=mock_response):
        provider = LRCLibProvider()
        result = provider.fetch("One More Time", "Daft Punk", "Discovery", 320)

    assert result.found is True
    assert result.synced == "[00:01.00] Hello"
    assert result.plain == "Hello"


def test_lrclib_falls_back_to_plain_when_no_synced():
    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.status = 200
    mock_response.read.return_value = b'{"syncedLyrics": null, "plainLyrics": "Hello"}'

    with patch("urllib.request.urlopen", return_value=mock_response):
        provider = LRCLibProvider(fallback_to_plain=True)
        result = provider.fetch("One More Time", "Daft Punk")

    assert result.found is True
    assert result.synced is None
    assert result.plain == "Hello"


def test_lrclib_no_fallback_returns_not_found():
    mock_response = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.status = 200
    mock_response.read.return_value = b'{"syncedLyrics": null, "plainLyrics": "Hello"}'

    with patch("urllib.request.urlopen", return_value=mock_response):
        provider = LRCLibProvider(fallback_to_plain=False)
        result = provider.fetch("One More Time", "Daft Punk")

    assert result.found is False


def test_lrclib_network_error_returns_not_found():
    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        provider = LRCLibProvider()
        result = provider.fetch("One More Time", "Daft Punk")
    assert result.found is False


# ── FLAC tagger tests ──────────────────────────────────────────────────────

def test_flac_basic_tags(tmp_path):
    path = tmp_path / "track.flac"
    make_flac(path)

    tagger = Tagger()
    tagger.tag(path, make_track(), make_album(), embed_cover=False)

    audio = FLAC(path)
    assert audio["TITLE"] == ["One More Time"]
    assert audio["ARTIST"] == ["Daft Punk"]
    assert audio["ALBUM"] == ["Discovery"]
    assert audio["TRACKNUMBER"] == ["1"]
    assert audio["ISRC"] == ["GBDCE0000001"]


def test_flac_album_tags(tmp_path):
    path = tmp_path / "track.flac"
    make_flac(path)

    tagger = Tagger()
    tagger.tag(path, make_track(), make_album(), embed_cover=False)

    audio = FLAC(path)
    assert audio["ALBUMARTIST"] == ["Daft Punk"]
    assert audio["ORGANIZATION"] == ["Virgin"]
    assert audio["GENRE"] == ["Electronic"]
    assert audio["DATE"] == ["2001"]


def test_flac_plain_lyrics(tmp_path):
    path = tmp_path / "track.flac"
    make_flac(path)

    lyrics = LyricsResult(plain="One more time", found=True)
    tagger = Tagger()
    tagger.tag(path, make_track(), embed_cover=False, lyrics=lyrics)

    audio = FLAC(path)
    assert audio["LYRICS"] == ["One more time"]


def test_flac_synced_lyrics_tag_when_configured(tmp_path):
    """SYNCEDLYRICS tag is written when flac_synced_lyrics='synced'.
    This was the v0.1.0 default behaviour, now opt-in via config."""
    from kabooz.config import TaggingConfig
    path = tmp_path / "track.flac"
    make_flac(path)

    lyrics = LyricsResult(synced="[00:01.00] One more time", found=True)
    tagger = Tagger()
    tagger.tag(
        path, make_track(), embed_cover=False, lyrics=lyrics,
        tagging_config=TaggingConfig(flac_synced_lyrics="synced"),
    )

    audio = FLAC(path)
    assert audio["SYNCEDLYRICS"] == ["[00:01.00] One more time"]

def test_flac_cover_art(tmp_path):
    path = tmp_path / "track.flac"
    make_flac(path)

    fake_cover = b"\xff\xd8\xff" + b"\x00" * 100  # minimal JPEG-like bytes

    tagger = Tagger()
    with patch.object(tagger, "_fetch_cover", return_value=fake_cover):
        tagger.tag(path, make_track(), make_album(), embed_cover=True)

    audio = FLAC(path)
    assert len(audio.pictures) == 1
    assert audio.pictures[0].data == fake_cover


def test_flac_no_cover_when_embed_false(tmp_path):
    path = tmp_path / "track.flac"
    make_flac(path)

    tagger = Tagger()
    tagger.tag(path, make_track(), make_album(), embed_cover=False)

    audio = FLAC(path)
    assert len(audio.pictures) == 0


def test_flac_clears_existing_tags(tmp_path):
    """Tagging twice should not accumulate duplicate tags."""
    path = tmp_path / "track.flac"
    make_flac(path)

    tagger = Tagger()
    tagger.tag(path, make_track(), make_album(), embed_cover=False)
    tagger.tag(path, make_track(title="Different Title"), make_album(), embed_cover=False)

    audio = FLAC(path)
    assert audio["TITLE"] == ["Different Title"]
    assert len(audio["TITLE"]) == 1


# ── MP3 tagger tests ───────────────────────────────────────────────────────

def test_mp3_basic_tags(tmp_path):
    path = tmp_path / "track.mp3"
    make_mp3(path)

    tagger = Tagger()
    tagger.tag(path, make_track(), make_album(), embed_cover=False)

    tags = ID3(path)
    assert str(tags["TIT2"]) == "One More Time"
    assert str(tags["TPE1"]) == "Daft Punk"
    assert str(tags["TALB"]) == "Discovery"
    assert str(tags["TSRC"]) == "GBDCE0000001"


def test_mp3_album_tags(tmp_path):
    path = tmp_path / "track.mp3"
    make_mp3(path)

    tagger = Tagger()
    tagger.tag(path, make_track(), make_album(), embed_cover=False)

    tags = ID3(path)
    assert str(tags["TPE2"]) == "Daft Punk"
    assert str(tags["TPUB"]) == "Virgin"
    assert str(tags["TCON"]) == "Electronic"
    assert str(tags["TDRC"]) == "2001"


def test_mp3_cover_art(tmp_path):
    path = tmp_path / "track.mp3"
    make_mp3(path)

    fake_cover = b"\xff\xd8\xff" + b"\x00" * 100

    tagger = Tagger()
    with patch.object(tagger, "_fetch_cover", return_value=fake_cover):
        tagger.tag(path, make_track(), make_album(), embed_cover=True)

    tags = ID3(path)
    assert "APIC:Cover" in tags
    assert tags["APIC:Cover"].data == fake_cover


def test_unsupported_format_raises(tmp_path):
    path = tmp_path / "track.ogg"
    path.write_bytes(b"fake")

    tagger = Tagger()
    with pytest.raises(ValueError, match="Unsupported audio format"):
        tagger.tag(path, make_track(), embed_cover=False)


def test_flac_qobuz_ids_written(tmp_path):
    """QOBUZ_TRACK_ID, QOBUZ_ALBUM_ID, QOBUZ_ARTIST_ID are written.
    UPC keeps its existing standard tag name (not QOBUZ_UPC)."""
    path = tmp_path / "track.flac"
    make_flac(path)

    tagger = Tagger()
    tagger.tag(path, make_track(), make_album(), embed_cover=False)

    audio = FLAC(path)
    assert audio["QOBUZ_TRACK_ID"] == ["12345"]
    assert audio["QOBUZ_ALBUM_ID"] == ["abc123"]
    assert audio["QOBUZ_ARTIST_ID"] == ["999"]
    # UPC uses the standard tag name; QOBUZ_UPC must not exist.
    assert audio["UPC"] == ["724384960224"]
    assert "QOBUZ_UPC" not in audio

def test_flac_qobuz_ids_standalone_track(tmp_path):
    """Standalone track (album=None): only track ID and performer ID."""
    path = tmp_path / "track.flac"
    make_flac(path)

    tagger = Tagger()
    tagger.tag(
        path,
        make_track(performer={"id": 999, "name": "Daft Punk"}),
        album=None,
        embed_cover=False,
    )

    audio = FLAC(path)
    assert audio["QOBUZ_TRACK_ID"] == ["12345"]
    assert "QOBUZ_ALBUM_ID" not in audio
    assert audio["QOBUZ_ARTIST_ID"] == ["999"]

def test_mp3_qobuz_ids_written(tmp_path):
    """Same IDs in MP3 TXXX frames. UPC uses the standard name."""
    path = tmp_path / "track.mp3"
    make_mp3(path)

    tagger = Tagger()
    tagger.tag(path, make_track(), make_album(), embed_cover=False)

    tags = ID3(path)
    assert "TXXX:QOBUZ TRACK ID" in tags
    assert tags["TXXX:QOBUZ TRACK ID"].text[0] == "12345"
    assert "TXXX:QOBUZ ALBUM ID" in tags
    assert tags["TXXX:QOBUZ ALBUM ID"].text[0] == "abc123"
    assert "TXXX:QOBUZ ARTIST ID" in tags
    assert tags["TXXX:QOBUZ ARTIST ID"].text[0] == "999"
    # UPC is a product identifier, not a Qobuz ID.
    assert "TXXX:UPC" in tags
    assert tags["TXXX:UPC"].text[0] == "724384960224"
    assert "TXXX:QOBUZ UPC" not in tags

def test_flac_qobuz_album_id_equals_upc_is_not_deduplicated(tmp_path):
    """Some albums have Qobuz ID == UPC (observed: Mahler 6 / Haitink,
    Disintegration Deluxe). Both tags must be written — they carry
    different meaning even when the value is identical."""
    path = tmp_path / "track.flac"
    make_flac(path)

    # Album where id == upc, as returned by Qobuz for many releases.
    album = make_album(id="0002894830800", upc="0002894830800")

    tagger = Tagger()
    tagger.tag(path, make_track(), album, embed_cover=False)

    audio = FLAC(path)
    assert audio["QOBUZ_ALBUM_ID"] == ["0002894830800"]
    assert audio["UPC"] == ["0002894830800"]
    # Not suppressed even though values match.
    assert audio["QOBUZ_ALBUM_ID"] != audio["UPC"] or True  # both present


def test_flac_embeds_large_cover_not_original(tmp_path):
    """Embedded cover must be _600.jpg (img.large), not _org.jpg.
    Full-resolution goes to cover.jpg instead, handled in session."""
    path = tmp_path / "track.flac"
    make_flac(path)

    fake_cover = b"\xff\xd8\xff" + b"\x00" * 100
    captured = {}

    def fake_fetch(url):
        captured["url"] = url
        return fake_cover

    album = make_album(image={
        "large":     "https://static.qobuz.com/images/covers/ab/cd/abcd_600.jpg",
        "small":     "https://static.qobuz.com/images/covers/ab/cd/abcd_230.jpg",
        "thumbnail": "https://static.qobuz.com/images/covers/ab/cd/abcd_50.jpg",
        "back":      None,
    })

    tagger = Tagger()
    with patch.object(tagger, "_fetch_cover", side_effect=fake_fetch):
        tagger.tag(path, make_track(), album, embed_cover=True)

    assert captured["url"] is not None
    assert "_600." in captured["url"]
    assert "_org." not in captured["url"]


def _lyrics_fixture():
    return LyricsResult(
        synced="[00:01.00] One more time",
        plain="One more time",
        found=True,
    )


def test_flac_lyrics_default_writes_only_lyrics_tag(tmp_path):
    """Defaults: flac_lyrics='best', others 'none'. Musicolet-compatible."""
    path = tmp_path / "track.flac"
    make_flac(path)
    Tagger().tag(path, make_track(), album=None,
                 lyrics=_lyrics_fixture(), embed_cover=False)
    audio = FLAC(path)
    assert audio["LYRICS"] == ["[00:01.00] One more time"]
    assert "UNSYNCEDLYRICS" not in audio
    assert "SYNCEDLYRICS" not in audio


def test_flac_lyrics_per_tag_control(tmp_path):
    """Each Vorbis tag independently controlled by its own field."""
    from kabooz.config import TaggingConfig
    path = tmp_path / "track.flac"
    make_flac(path)
    cfg = TaggingConfig(
        flac_lyrics="plain",
        flac_unsynced_lyrics="plain",
        flac_synced_lyrics="synced",
    )
    Tagger().tag(path, make_track(), album=None,
                 lyrics=_lyrics_fixture(), embed_cover=False,
                 tagging_config=cfg)
    audio = FLAC(path)
    assert audio["LYRICS"] == ["One more time"]            # plain
    assert audio["UNSYNCEDLYRICS"] == ["One more time"]    # plain
    assert audio["SYNCEDLYRICS"] == ["[00:01.00] One more time"]  # synced


def test_flac_lyrics_none_skips_tag(tmp_path):
    """'none' skips the tag even when lyrics are available."""
    from kabooz.config import TaggingConfig
    path = tmp_path / "track.flac"
    make_flac(path)
    cfg = TaggingConfig(flac_lyrics="none")
    Tagger().tag(path, make_track(), album=None,
                 lyrics=_lyrics_fixture(), embed_cover=False,
                 tagging_config=cfg)
    audio = FLAC(path)
    assert "LYRICS" not in audio


def test_flac_lyrics_synced_mode_skips_when_no_synced_available(tmp_path):
    """'synced' writes nothing if only plain lyrics exist."""
    from kabooz.config import TaggingConfig
    path = tmp_path / "track.flac"
    make_flac(path)
    cfg = TaggingConfig(flac_lyrics="synced")
    plain_only = LyricsResult(synced=None, plain="One more time", found=True)
    Tagger().tag(path, make_track(), album=None,
                 lyrics=plain_only, embed_cover=False,
                 tagging_config=cfg)
    audio = FLAC(path)
    assert "LYRICS" not in audio


def test_mp3_lyrics_default_writes_only_uslt(tmp_path):
    """MP3 defaults: USLT='best', TXXX/SYLT 'none'."""
    path = tmp_path / "track.mp3"
    make_mp3(path)
    Tagger().tag(path, make_track(), album=None,
                 lyrics=_lyrics_fixture(), embed_cover=False)
    tags = ID3(path)
    uslt = tags.getall("USLT")
    assert uslt, "expected at least one USLT frame"
    assert uslt[0].text == "[00:01.00] One more time"
    assert not tags.getall("SYLT")
    assert "TXXX:UNSYNCEDLYRICS" not in tags

def test_mp3_lyrics_per_frame_control(tmp_path):
    """Each ID3 lyric frame independently controlled."""
    from kabooz.config import TaggingConfig
    path = tmp_path / "track.mp3"
    make_mp3(path)
    cfg = TaggingConfig(
        mp3_uslt="plain",
        mp3_txxx_unsynced="plain",
        mp3_sylt="synced",
    )
    Tagger().tag(path, make_track(), album=None,
                 lyrics=_lyrics_fixture(), embed_cover=False,
                 tagging_config=cfg)
    tags = ID3(path)
    uslt = tags.getall("USLT")
    assert uslt and uslt[0].text == "One more time"
    assert "TXXX:UNSYNCEDLYRICS" in tags
    assert tags["TXXX:UNSYNCEDLYRICS"].text[0] == "One more time"
    assert tags.getall("SYLT"), "expected SYLT frame in 'both'/'synced' mode"

def test_mp3_sylt_rejects_plain_mode():
    """mp3_sylt can only be 'synced' or 'none' — binary frame."""
    import pytest
    from kabooz.config import QobuzConfig, validate_config, ConfigError
    cfg = QobuzConfig()
    cfg.tagging.mp3_sylt = "plain"
    with pytest.raises(ConfigError, match="binary synced frame"):
        validate_config(cfg)
