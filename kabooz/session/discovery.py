# kabooz/session/discovery.py
"""
Discovery and recommendation methods for QobuzSession.

Editorial content (new releases, featured playlists, genre tree),
radio queues built from a seed track or artist, and a combined
recommendations aggregator.

Extracted from session/__init__.py. Mixin composition — methods
operate on a QobuzSession instance with access to self.client.

Public import path unchanged.
"""
from __future__ import annotations

import random
from typing import Any, Optional

from ..models.track import Track


class DiscoveryMixin:
    """Mixin providing discovery, radio, and recommendations.
    Composed into QobuzSession via class inheritance."""

    def get_new_releases(
        self,
        release_type: str = "new-releases",
        genre_id: Optional[int] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict:
        return self.client.get_new_releases(
            type=release_type, genre_id=genre_id, limit=limit, offset=offset,
        )

    def get_featured_playlists(
        self,
        pl_type: str = "editor-picks",
        genre_id: Optional[int] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict:
        return self.client.get_featured_playlists(
            type=pl_type, genre_id=genre_id, limit=limit, offset=offset,
        )

    def get_genres(self, parent_id: Optional[int] = None) -> dict:
        return self.client.get_genres(parent_id=parent_id)

    def get_track_radio(
        self,
        track_id: str | int,
        limit: int = 25,
    ) -> list[Track]:
        """
        Build a radio queue seeded by a single track.

        Tries the official /track/getSuggestions endpoint first;
        falls back to similar-artist browsing if unavailable.
        """
        import random

        # Attempt 1 — official suggestions
        try:
            data  = self.client._request(
                "GET", "/track/getSuggestions",
                params={"track_id": str(track_id), "limit": limit},
            )
            items = (
                data.get("tracks", {}).get("items")
                or data.get("items")
                or []
            )
            if items:
                tracks = []
                for item in items[:limit]:
                    try:
                        tracks.append(Track.from_dict(item))
                    except Exception:
                        pass
                if tracks:
                    return tracks
        except Exception:
            pass

        # Attempt 2 — similar-artist fallback
        try:
            seed = self.client.get_track(str(track_id))
        except Exception:
            return []

        similar_ids: list[Any] = []
        if seed.performer:
            try:
                a = self.client.get_artist(
                    seed.performer.id, extras="", limit=1,
                )
                similar_ids = (a.similar_artist_ids or [])[:6]
            except Exception:
                pass

        tracks: list[Track] = []
        for sid in similar_ids:
            if len(tracks) >= limit:
                break
            try:
                artist = self.client.get_artist(sid, extras="albums", limit=5)
                if not artist.albums or not artist.albums.items:
                    continue
                alb = random.choice(artist.albums.items)
                full = self.client.get_album(alb.id, limit=20)
                if full.tracks and full.tracks.items:
                    for s in random.sample(
                        full.tracks.items, min(4, len(full.tracks.items))
                    ):
                        try:
                            tracks.append(self.client.get_track(str(s.id)))
                        except Exception:
                            pass
            except Exception:
                continue

        random.shuffle(tracks)
        return tracks[:limit]

    def get_artist_radio(
        self,
        artist_id: str | int,
        limit: int = 25,
    ) -> list[Track]:
        """
        Build a radio queue seeded by an artist.
        Picks tracks from the artist + their similar artists.
        """
        import random
        tracks: list[Track] = []

        # Artist's own releases
        try:
            for release in self.client.iter_releases(artist_id, page_size=10):
                if len(tracks) >= limit // 2 or not release.id:
                    break
                try:
                    alb = self.client.get_album(release.id, limit=10)
                    if alb.tracks and alb.tracks.items:
                        for s in alb.tracks.items[:3]:
                            tracks.append(self.client.get_track(str(s.id)))
                except Exception:
                    continue
        except Exception:
            pass

        # Fill from similar artists
        try:
            for sim in self.client.get_similar_artists(artist_id, limit=8):
                if len(tracks) >= limit:
                    break
                try:
                    for release in self.client.iter_releases(sim.id, page_size=3):
                        if not release.id:
                            continue
                        alb = self.client.get_album(release.id, limit=5)
                        if alb.tracks and alb.tracks.items:
                            tracks.append(
                                self.client.get_track(
                                    str(random.choice(alb.tracks.items).id)
                                )
                            )
                        break
                except Exception:
                    continue
        except Exception:
            pass

        random.shuffle(tracks)
        return tracks[:limit]

    def get_recommendations(self, limit: int = 20) -> dict[str, list]:
        """
        Return editorial and personalised recommendation lists.

        Keys:
            "new_releases"    — raw album dicts from the new-releases feed
            "press_awards"    — critic picks
            "featured"        — editorial playlist dicts
            "similar_artists" — Artist objects similar to your favourites
        """
        result: dict[str, list] = {
            "new_releases":    [],
            "press_awards":    [],
            "featured":        [],
            "similar_artists": [],
        }
        try:
            result["new_releases"] = (
                self.client.get_new_releases(type="new-releases", limit=limit)
                .get("albums", {}).get("items", [])
            )
        except Exception:
            pass
        try:
            result["press_awards"] = (
                self.client.get_new_releases(type="press-awards", limit=limit)
                .get("albums", {}).get("items", [])
            )
        except Exception:
            pass
        try:
            result["featured"] = (
                self.client.get_featured_playlists(type="editor-picks", limit=limit)
                .get("playlists", {}).get("items", [])
            )
        except Exception:
            pass
        try:
            fav_ids    = self.client.get_favorite_ids()
            artist_ids = (fav_ids.artist_ids or [])[:5]
            seen: set[str] = set()
            for aid in artist_ids:
                try:
                    for a in self.client.get_similar_artists(aid, limit=4):
                        if str(a.id) not in seen:
                            seen.add(str(a.id))
                            result["similar_artists"].append(a)
                except Exception:
                    continue
        except Exception:
            pass
        return result
