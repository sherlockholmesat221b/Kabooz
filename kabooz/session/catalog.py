# kabooz/session/catalog.py
"""
Catalog read methods for QobuzSession.

Thin passthroughs to QobuzClient for reading catalog entities
(tracks, albums, artists, playlists, labels), search results, and
user favorites. Extracted from session/__init__.py to keep
QobuzSession navigable.

Every method here is called as self.get_album() etc. — mixin
composition means they operate on a QobuzSession instance.

Public import path unchanged.
"""
from __future__ import annotations

from typing import Any, Generator, Optional

from ..models.album import Album
from ..models.artist import Artist
from ..models.favorites import LabelDetail, UserFavoriteIds, UserFavorites
from ..models.playlist import Playlist
from ..models.track import Track


class CatalogMixin:
    """Mixin providing catalog read passthroughs.
    Composed into QobuzSession via class inheritance."""

    def get_track(self, track_id: str | int) -> Track:
        return self.client.get_track(str(track_id))

    def get_album(
        self,
        album_id: str,
        extra: Optional[str] = None,
        limit: int = 1200,
        offset: int = 0,
    ) -> Album:
        return self.client.get_album(album_id, extra=extra, limit=limit, offset=offset)

    def get_artist(
        self,
        artist_id: str | int,
        extras: str = "albums",
        sort: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Artist:
        return self.client.get_artist(
            artist_id, extras=extras, sort=sort, limit=limit, offset=offset,
        )

    def get_playlist(
        self,
        playlist_id: str | int,
        limit: int = 500,
        offset: int = 0,
    ) -> Playlist:
        return self.client.get_playlist(playlist_id, limit=limit, offset=offset)

    def get_label(self, label_id: str | int, **kwargs) -> LabelDetail:
        return self.client.get_label(label_id, **kwargs)

    def search(
        self,
        query: str,
        search_type: str = "tracks",
        limit: int = 25,
        offset: int = 0,
    ) -> dict:
        """
        Search the Qobuz catalog.
        search_type: 'tracks', 'albums', 'artists', 'playlists'
        """
        return self.client.search(
            query=query, type=search_type, limit=limit, offset=offset,
        )

    def get_user_favorites(
        self,
        fav_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> UserFavorites:
        return self.client.get_user_favorites(
            type=fav_type, limit=limit, offset=offset,
        )

    def get_favorite_ids(self) -> UserFavoriteIds:
        return self.client.get_favorite_ids()

    def iter_user_playlists(self, page_size: int = 50) -> Generator[Playlist, None, None]:
        return self.client.iter_user_playlists(page_size=page_size)

    def iter_playlist_track_summaries(
        self, playlist_id: str | int, page_size: int = 500,
    ) -> Generator[Any, None, None]:
        return self.client.iter_playlist_track_summaries(playlist_id, page_size)

    def iter_releases(
        self,
        artist_id: str | int,
        release_type: Optional[str] = None,
        page_size: int = 50,
    ) -> Generator[Any, None, None]:
        return self.client.iter_releases(
            artist_id, release_type=release_type, page_size=page_size,
        )

    def get_similar_artists(
        self, artist_id: str | int, limit: int = 10,
    ) -> list[Artist]:
        return self.client.get_similar_artists(artist_id, limit=limit)
