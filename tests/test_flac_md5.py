# tests/test_flac_md5.py
"""Tests for FLAC MD5 fix (feature #6)."""
import os
import shutil
import subprocess
from unittest.mock import MagicMock, patch

import pytest

import kabooz.session.downloads as sd


# ── Unit tests — argument validation, not just returncode ────────

def test_skips_non_flac(tmp_path):
    p = tmp_path / "track.mp3"
    p.write_bytes(b"x")
    with patch("kabooz.session.downloads.subprocess.run") as r:
        assert sd._maybe_fix_flac_md5(p) is False
        r.assert_not_called()


def test_raises_when_flac_missing(tmp_path):
    """If the user enabled fix_flac_md5 but flac is not installed,
    raise ConfigError — fail-fast, do not silently skip."""
    from kabooz.exceptions import ConfigError
    p = tmp_path / "track.flac"
    p.write_bytes(b"x")
    with patch("kabooz.session.downloads.shutil.which", return_value=None):
        with pytest.raises(ConfigError, match="flac.*is not installed"):
            sd._maybe_fix_flac_md5(p)


def test_raises_when_metaflac_missing(tmp_path):
    from kabooz.exceptions import ConfigError
    p = tmp_path / "track.flac"
    p.write_bytes(b"x")

    def fake_which(name):
        return "/usr/bin/flac" if name == "flac" else None

    with patch("kabooz.session.downloads.shutil.which", side_effect=fake_which):
        with pytest.raises(ConfigError, match="metaflac.*is not installed"):
            sd._maybe_fix_flac_md5(p)


def test_metaflac_called_with_computed_hash(tmp_path):
    """Assert subprocess.run is invoked as
    `metaflac --set-md5sum=<32-hex-hash> <file>` — the critical
    behaviour the previous bug broke."""
    p = tmp_path / "track.flac"
    p.write_bytes(b"x")

    fake_popen = MagicMock()
    fake_popen.returncode = 0
    fake_popen.stdout.read.side_effect = [b"audio_chunk", b""]
    fake_popen.wait = MagicMock()

    with patch("kabooz.session.downloads.shutil.which", return_value="/usr/bin/x"), \
         patch("kabooz.session.downloads.subprocess.Popen", return_value=fake_popen), \
         patch("kabooz.session.downloads.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr=b"")
        result = sd._maybe_fix_flac_md5(p)

    assert result is True
    # subprocess.run must have been called exactly once
    assert mock_run.call_count == 1
    argv = mock_run.call_args[0][0]
    # arg[0] is metaflac
    assert argv[0] == "metaflac"
    # arg[1] is --set-md5sum=<hex>
    assert argv[1].startswith("--set-md5sum=")
    md5_hex = argv[1].split("=", 1)[1]
    assert len(md5_hex) == 32
    assert all(c in "0123456789abcdef" for c in md5_hex)
    # arg[2] is the file path
    assert argv[2] == str(p)


def test_popen_args_match_flac_decode(tmp_path):
    """Assert Popen decodes FLAC properly:
    flac -ds --stdout --force-raw-format --endian=little --sign=signed <file>"""
    p = tmp_path / "track.flac"
    p.write_bytes(b"x")

    fake_popen = MagicMock()
    fake_popen.returncode = 0
    fake_popen.stdout.read.side_effect = [b"x", b""]
    fake_popen.wait = MagicMock()

    with patch("kabooz.session.downloads.shutil.which", return_value="/usr/bin/x"), \
         patch("kabooz.session.downloads.subprocess.Popen", return_value=fake_popen) as mock_popen, \
         patch("kabooz.session.downloads.subprocess.run",
               return_value=MagicMock(returncode=0, stderr=b"")):
        sd._maybe_fix_flac_md5(p)

    argv = mock_popen.call_args[0][0]
    assert argv[0] == "flac"
    assert "-ds" in argv
    assert "--stdout" in argv
    assert "--force-raw-format" in argv
    assert "--endian=little" in argv
    assert "--sign=signed" in argv
    assert argv[-1] == str(p)


def test_false_on_decode_failure(tmp_path):
    p = tmp_path / "track.flac"
    p.write_bytes(b"x")
    fake_popen = MagicMock()
    fake_popen.returncode = 1
    fake_popen.stdout.read.side_effect = [b"", b""]
    fake_popen.wait = MagicMock()
    with patch("kabooz.session.downloads.shutil.which", return_value="/usr/bin/x"), \
         patch("kabooz.session.downloads.subprocess.Popen", return_value=fake_popen), \
         patch("kabooz.session.downloads.subprocess.run") as mock_run:
        assert sd._maybe_fix_flac_md5(p) is False
        mock_run.assert_not_called()


def test_false_on_metaflac_error(tmp_path):
    p = tmp_path / "track.flac"
    p.write_bytes(b"x")
    fake_popen = MagicMock()
    fake_popen.returncode = 0
    fake_popen.stdout.read.side_effect = [b"x", b""]
    fake_popen.wait = MagicMock()
    with patch("kabooz.session.downloads.shutil.which", return_value="/usr/bin/x"), \
         patch("kabooz.session.downloads.subprocess.Popen", return_value=fake_popen), \
         patch("kabooz.session.downloads.subprocess.run",
               return_value=MagicMock(returncode=1, stderr=b"corrupt")):
        assert sd._maybe_fix_flac_md5(p) is False


def test_config_default_false():
    from kabooz.config import DownloadConfig
    assert DownloadConfig().fix_flac_md5 is False


def test_config_rejects_non_bool():
    from kabooz.config import QobuzConfig, validate_config, ConfigError
    cfg = QobuzConfig()
    cfg.download.fix_flac_md5 = "yes"
    with pytest.raises(ConfigError, match="fix_flac_md5"):
        validate_config(cfg)


# ── Integration test — real flac + metaflac, opt-in ──────────────

@pytest.mark.integration
@pytest.mark.skipif(
    not (shutil.which("flac") and shutil.which("metaflac")
         and shutil.which("ffmpeg")),
    reason="requires flac, metaflac, ffmpeg",
)
def test_real_flac_md5_fix(tmp_path):
    """Generate a real FLAC, zero its MD5, run the fix, verify:
      1. MD5 is no longer zeroed
      2. `flac -t` (integrity test) passes
      3. The MD5 matches what a fresh `flac -ds` decode produces
    """
    import shutil as _sh

    wav = tmp_path / "silent.wav"
    flac_file = tmp_path / "silent.flac"

    # 1-second silent WAV via ffmpeg
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         "anullsrc=r=44100:cl=mono", "-t", "1",
         "-c:a", "pcm_s16le", str(wav)],
        check=True, capture_output=True,
    )
    # Encode to FLAC
    subprocess.run(
        ["flac", "-s", "-f", "-o", str(flac_file), str(wav)],
        check=True, capture_output=True,
    )
    # Zero the MD5
    subprocess.run(
        ["metaflac",
         "--set-md5sum=00000000000000000000000000000000",
         str(flac_file)],
        check=True, capture_output=True,
    )
    zero = subprocess.run(
        ["metaflac", "--show-md5sum", str(flac_file)],
        capture_output=True, text=True,
    ).stdout.strip()
    assert zero == "0" * 32, f"failed to zero MD5: got {zero!r}"

    # Run the fix
    assert sd._maybe_fix_flac_md5(flac_file) is True

    # Verify non-zero
    fixed = subprocess.run(
        ["metaflac", "--show-md5sum", str(flac_file)],
        capture_output=True, text=True,
    ).stdout.strip()
    assert fixed != "0" * 32
    assert len(fixed) == 32

    # Verify FLAC integrity (flac -t recomputes and compares)
    result = subprocess.run(
        ["flac", "-t", "-s", str(flac_file)],
        capture_output=True,
    )
    assert result.returncode == 0, (
        f"flac -t failed (MD5 mismatch): {result.stderr.decode()[:300]}"
    )
