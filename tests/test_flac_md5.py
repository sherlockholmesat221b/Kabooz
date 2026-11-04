# tests/test_flac_md5.py
"""Tests for FLAC MD5 fix (feature #6)."""
from unittest.mock import MagicMock, patch

import pytest

import kabooz.session.downloads as sd


@pytest.fixture(autouse=True)
def reset_version_cache():
    sd._flac_version_cache = None
    yield
    sd._flac_version_cache = None


def test_skips_non_flac(tmp_path):
    p = tmp_path / "track.mp3"
    p.write_bytes(b"x")
    with patch("kabooz.session.downloads.subprocess.run") as r:
        assert sd._maybe_fix_flac_md5(p) is False
        r.assert_not_called()


def test_applies_to_flac_part(tmp_path):
    p = tmp_path / "track.flac.part"
    p.write_bytes(b"x")
    with patch("kabooz.session.downloads.subprocess.run") as r:
        r.side_effect = [
            MagicMock(returncode=0, stdout=b"metaflac 1.4.3\n"),
            MagicMock(returncode=0, stderr=b""),
        ]
        assert sd._maybe_fix_flac_md5(p) is True
        assert r.call_args_list[0][0][0] == ["metaflac", "--version"]
        assert r.call_args_list[1][0][0] == ["metaflac", "--set-md5sum", str(p)]


def test_skips_old_metaflac(tmp_path):
    p = tmp_path / "track.flac"
    p.write_bytes(b"x")
    with patch("kabooz.session.downloads.subprocess.run") as r:
        r.return_value = MagicMock(returncode=0, stdout=b"metaflac 1.3.4\n")
        assert sd._maybe_fix_flac_md5(p) is False
        assert r.call_count == 1


def test_skips_missing_metaflac(tmp_path):
    p = tmp_path / "track.flac"
    p.write_bytes(b"x")
    with patch("kabooz.session.downloads.subprocess.run", side_effect=FileNotFoundError):
        assert sd._maybe_fix_flac_md5(p) is False


def test_false_on_metaflac_error(tmp_path):
    p = tmp_path / "track.flac"
    p.write_bytes(b"x")
    with patch("kabooz.session.downloads.subprocess.run") as r:
        r.side_effect = [
            MagicMock(returncode=0, stdout=b"metaflac 1.4.3\n"),
            MagicMock(returncode=1, stderr=b"corrupt"),
        ]
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


def test_load_config_reads_max_retries():
    """Regression: feature #3 added max_retries to DownloadConfig but
    forgot to wire it into load_config, so user overrides were ignored."""
    import inspect
    from kabooz import config as cfg_mod
    src = inspect.getsource(cfg_mod.load_config)
    assert 'd.get("max_retries"' in src, "load_config must read max_retries"


def test_load_config_reads_fix_flac_md5():
    import inspect
    from kabooz import config as cfg_mod
    src = inspect.getsource(cfg_mod.load_config)
    assert 'd.get("fix_flac_md5"' in src, "load_config must read fix_flac_md5"
