# kabooz/session/favorites.py
"""
Favorites management for QobuzSession.

Adds/removes favourites locally (always) and optionally on the
Qobuz account (when the client is not in pool mode). Syncs Qobuz
favourites into the local SQLite store.

Extracted from session/__init__.py. Mixin composition — methods
operate on a QobuzSession instance with access to self.client,
self.store, and self.config.

Public import path unchanged.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Optional

from ..exceptions import PoolModeError


class FavoritesMixin:
    """Mixin providing favorite add/remove/sync.
    Composed into QobuzSession via class inheritance."""

    def add_favorite(
        self, entity_id: str, entity_type: str, remote: bool = False,
    ) -> None:
        title = artist = extra = ""
        try:
            if entity_type == "track":
                obj    = self.client.get_track(entity_id)
                title  = obj.display_title
                artist = obj.performer.name if obj.performer else ""
                extra  = obj.album.title if obj.album else ""
            elif entity_type == "album":
                obj    = self.client.get_album(entity_id)
                title  = obj.display_title
                artist = obj.artist.name if obj.artist else ""
                extra  = obj.genre.name if obj.genre else ""
            elif entity_type == "artist":
                obj   = self.client.get_artist(entity_id, extras="")
                title = obj.name
        except Exception:
            pass
        self.store.add_favorite(
            entity_id, entity_type, title=title, artist=artist, extra=extra,
        )
        if remote:
            kwargs: dict[str, Any] = {}
            if entity_type == "track":
                kwargs = {"track_ids":  [entity_id]}
            elif entity_type == "album":
                kwargs = {"album_ids":  [entity_id]}
            elif entity_type == "artist":
                kwargs = {"artist_ids": [entity_id]}
            self.client.add_favorite(**kwargs)

    def remove_favorite(
        self, entity_id: str, entity_type: str, remote: bool = False,
    ) -> bool:
        removed = self.store.remove_favorite(entity_id, entity_type)
        if remote:
            kwargs: dict[str, Any] = {}
            if entity_type == "track":
                kwargs = {"track_ids":  [entity_id]}
            elif entity_type == "album":
                kwargs = {"album_ids":  [entity_id]}
            elif entity_type == "artist":
                kwargs = {"artist_ids": [entity_id]}
            self.client.remove_favorite(**kwargs)
        return removed

    def sync_favorites(
        self, fav_type: Optional[str] = None, clear: bool = False,
    ) -> dict[str, int]:
        if self.client.is_pool_mode:
            raise PoolModeError("sync_favorites() requires a personal session.")
        types    = [fav_type] if fav_type else ["track", "album", "artist"]
        result   = {}
        fav      = self.client.get_user_favorites()
        type_map = {"track": fav.tracks, "album": fav.albums, "artist": fav.artists}
        for t in types:
            page = type_map.get(t)
            if not page or not page.items:
                result[t] = 0; continue
            raw = [dataclasses.asdict(i) for i in page.items]
            result[t] = self.store.sync_favorites_from_api(raw, t, clear_first=clear)
        return result
