# tests/test_session_streaming.py
"""Tests for StreamingMixin.resolve_stream (#2)."""
import httpx
import respx
from kabooz.quality import Quality


BASE = "https://www.qobuz.com/api.json/0.2"
FAKE_URL = "https://cdn.qobuz.com/some/signed/url.flac"


def _make_session():
    from kabooz.client import QobuzClient
    from kabooz.config import QobuzConfig
    from kabooz.session import QobuzSession
    client = QobuzClient.from_credentials(app_id="123", app_secret="abc")
    client.login(token="TEST_TOKEN", user_id="42")
    return QobuzSession(client=client, config=QobuzConfig())


@respx.mock
def test_resolve_stream_returns_stream_info():
    respx.get(f"{BASE}/track/getFileUrl").mock(
        return_value=httpx.Response(200, json={
            "url": FAKE_URL, "format_id": 6,
            "bit_depth": 16, "sampling_rate": 44.1,
            "mime_type": "audio/flac",
        })
    )
    info = _make_session().resolve_stream("12345", quality=Quality.FLAC_16)
    assert info.url == FAKE_URL
    assert info.format_id == 6
    assert info.bit_depth == 16
    assert info.sampling_rate == 44.1


@respx.mock
def test_resolve_stream_silent_by_default():
    respx.get(f"{BASE}/track/getFileUrl").mock(
        return_value=httpx.Response(200, json={
            "url": FAKE_URL, "format_id": 27,
            "bit_depth": 24, "sampling_rate": 96.0,
            "mime_type": "audio/flac",
        })
    )
    report_route = respx.get(f"{BASE}/track/reportStreamingStart").mock(
        return_value=httpx.Response(200, json={})
    )
    _make_session().resolve_stream("12345", quality=Quality.HI_RES)
    assert not report_route.called


@respx.mock
def test_resolve_stream_reports_when_asked():
    respx.get(f"{BASE}/track/getFileUrl").mock(
        return_value=httpx.Response(200, json={
            "url": FAKE_URL, "format_id": 27,
            "bit_depth": 24, "sampling_rate": 96.0,
            "mime_type": "audio/flac",
        })
    )
    report_route = respx.get(f"{BASE}/track/reportStreamingStart").mock(
        return_value=httpx.Response(200, json={})
    )
    _make_session().resolve_stream("12345", quality=Quality.HI_RES, report=True)
    assert report_route.called
