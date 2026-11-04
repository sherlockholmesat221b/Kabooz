# kabooz/session/playlists.py
"""
Playlist methods for QobuzSession.

Covers both local playlists (SQLite store, shareable TOML format)
and remote playlists on the user's Qobuz account. Extracted from
session/__init__.py. Mixin composition — methods operate on a
QobuzSession instance with access to self.client, self.store,
self.config.

Public import path unchanged.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..download.naming import sanitize
from ..local.export import import_playlist_toml
from ..local.playlist import (
    load_playlist, playlist_from_store_tracks, save_playlist,
)
from ..models.playlist import Playlist


class PlaylistsMixin:
    """Mixin providing local and remote playlist management.
    Composed into QobuzSession via class inheritance."""

    def clone_playlist(self, url_or_id: str, name: Optional[str] = None) -> str:
        _, playlist_id = self.resolve_id(url_or_id, "playlist")
        pl         = self.client.get_playlist(playlist_id, limit=1)
        local_name = name or pl.name
        if self.store.get_playlist_by_name(local_name):
            local_name = f"{local_name} (cloned)"
        local_id = self.store.create_playlist(local_name, pl.description or "")
        for i, t in enumerate(
            self.client.iter_playlist_track_summaries(playlist_id)
        ):
            self.store.add_track_to_playlist(
                local_id, str(t.id),
                title=t.title,
                artist=t.performer.name if t.performer else "",
                album=t.album.title if t.album else "",
                duration=t.duration or 0,
                isrc=getattr(t, "isrc", "") or "",
                position=i,
            )
        return local_id

    def share_playlist(
        self,
        playlist_name_or_id: str,
        output: Optional[Path] = None,
        author: str = "",
    ) -> Path:
        pl = self._find_local_playlist(playlist_name_or_id)
        if not pl:
            raise ValueError(f"Local playlist not found: {playlist_name_or_id!r}")
        tracks = self.store.get_playlist_tracks(pl["id"])
        lpl    = playlist_from_store_tracks(
            name=pl["name"], tracks=tracks,
            description=pl.get("description", ""), author=author,
        )
        if output is None:
            self.config.local_data.playlists_dir.mkdir(parents=True, exist_ok=True)
            output = (
                self.config.local_data.playlists_dir
                / f"{sanitize(pl['name'])}.toml"
            )
        save_playlist(lpl, output)
        return output

    def import_playlist(self, file: Path, overwrite: bool = False) -> str:
        pl_id = import_playlist_toml(self.store, file, overwrite=overwrite)
        if pl_id is not None:
            return pl_id
        lpl      = load_playlist(file)
        new_name = f"{lpl.name} (imported)"
        local_id = self.store.create_playlist(new_name, lpl.description)
        for i, t in enumerate(lpl.tracks):
            self.store.add_track_to_playlist(
                local_id, t.id,
                title=t.title, artist=t.artist, album=t.album,
                duration=t.duration, isrc=t.isrc, position=i,
            )
        return local_id

    def create_remote_playlist(
        self,
        name:               str,
        description:        str  = "",
        is_public:          bool = False,
        is_collaborative:   bool = False,
        also_save_locally:  bool = True,
    ) -> Playlist:
        pl = self.client.create_remote_playlist(
            name=name, description=description,
            is_public=is_public, is_collaborative=is_collaborative,
        )
        if also_save_locally:
            self.store.create_playlist(name, description)
        return pl

    def update_remote_playlist(
        self, playlist_id: str | int, **kwargs: Any,
    ) -> Playlist:
        return self.client.update_remote_playlist(
            playlist_id=playlist_id, **kwargs,
        )

    def delete_remote_playlist(self, playlist_id: str | int) -> None:
        self.client.delete_remote_playlist(playlist_id)

    def add_tracks_to_remote_playlist(
        self, playlist_id: str | int, track_ids: list[str | int],
        no_duplicate: bool = True,
    ) -> None:
        self.client.add_tracks_to_remote_playlist(
            playlist_id=playlist_id, track_ids=track_ids, no_duplicate=no_duplicate,
        )

    def remove_tracks_from_remote_playlist(
        self, playlist_id: str | int, playlist_track_ids: list[int],
    ) -> None:
        self.client.remove_tracks_from_remote_playlist(
            playlist_id=playlist_id, playlist_track_ids=playlist_track_ids,
        )

    def follow_playlist(self, playlist_id: str | int) -> None:
        self.client.subscribe_to_playlist(playlist_id)

    def unfollow_playlist(self, playlist_id: str | int) -> None:
        self.client.unsubscribe_from_playlist(playlist_id)

    def _find_local_playlist(self, name_or_id: str) -> Optional[dict]:
        pl = self.store.get_playlist_by_name(name_or_id)
        if pl:
            return pl
        for c in self.store.list_playlists():
            if c["id"].startswith(name_or_id):
                return c
        return None
