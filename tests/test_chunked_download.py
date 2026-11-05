import re
import httpx
import respx
from kabooz.download.downloader import Downloader, _plan_chunks, _assemble_chunks


def make_track():
    from kabooz.models.track import Track
    return Track.from_dict({"id": 1, "title": "T", "duration": 100,
                            "track_number": 1, "media_number": 1})


def test_plan_chunks_even():
    r = _plan_chunks(1000, 4)
    assert len(r) == 4 and r[0] == (0, 249) and r[3] == (750, 999)

def test_plan_chunks_uneven():
    r = _plan_chunks(1001, 4)
    assert r[-1][1] == 1000
    for i in range(len(r) - 1):
        assert r[i][1] + 1 == r[i + 1][0]

def test_plan_chunks_cap():
    assert len(_plan_chunks(3, 10)) == 3

def test_plan_chunks_single():
    assert _plan_chunks(500, 1) == [(0, 499)]

def test_plan_chunks_zero():
    assert _plan_chunks(0, 4) == [(0, 0)]

def test_assemble(tmp_path):
    c1 = tmp_path / "c.0"; c1.write_bytes(b"AAA")
    c2 = tmp_path / "c.1"; c2.write_bytes(b"BBB")
    dest = tmp_path / "out"
    _assemble_chunks([c1, c2], dest)
    assert dest.read_bytes() == b"AAABBB"
    assert not c1.exists()

def test_assemble_large(tmp_path):
    c1 = tmp_path / "c.0"; c1.write_bytes(b"X" * (3 * 1024 * 1024))
    c2 = tmp_path / "c.1"; c2.write_bytes(b"Y" * (2 * 1024 * 1024))
    dest = tmp_path / "out"
    _assemble_chunks([c1, c2], dest)
    assert dest.read_bytes() == b"X" * (3 * 1024 * 1024) + b"Y" * (2 * 1024 * 1024)

@respx.mock
def test_chunked_basic(tmp_path):
    url = "https://cdn.qobuz.com/f.flac"
    content = b"0123456789" * 1000
    respx.head(url).mock(return_value=httpx.Response(200, headers={"content-length": str(len(content))}))
    def handler(request):
        rh = request.headers.get("range", "")
        m = re.match(r"bytes=(\d+)-(\d+)$", rh)
        if m:
            s, e = int(m.group(1)), int(m.group(2))
            body = content[s:e+1]
            return httpx.Response(206, content=body, headers={"content-length": str(len(body))})
        return httpx.Response(200, content=content, headers={"content-length": str(len(content))})
    respx.get(url).mock(side_effect=handler)
    dl = Downloader()
    result = dl.download_track(track=make_track(), url_info={"url": url},
                               dest_dir=tmp_path, connections=4)
    assert result.path.read_bytes() == content

@respx.mock
def test_fallback_no_content_length(tmp_path):
    url = "https://cdn.qobuz.com/f.flac"
    content = b"Y" * 3000
    respx.head(url).mock(return_value=httpx.Response(200))
    respx.get(url).mock(return_value=httpx.Response(200, content=content,
                                                     headers={"content-length": str(len(content))}))
    dl = Downloader()
    result = dl.download_track(track=make_track(), url_info={"url": url},
                               dest_dir=tmp_path, connections=4)
    assert result.path.read_bytes() == content
