# tests/test_musicbrainz.py
from kabooz.download import musicbrainz


def test_user_agent_references_project():
    """MusicBrainz requires a User-Agent that identifies the client
    and a contact URL. Anything else gets rate-limited or blocked."""
    ua = musicbrainz._USER_AGENT
    assert ua.startswith("Kabooz/"), f"Expected 'Kabooz/...' but got {ua!r}"
    assert "github.com" in ua.lower() or "gitlab.com" in ua.lower(), \
        f"User-Agent must contain a project URL: {ua!r}"
