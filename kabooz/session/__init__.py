# kabooz/session.py
"""
QobuzSession — the ONLY place where business logic lives.

Architectural rule
──────────────────
cli.py  and  tui.py  are presentation layers.
They call methods on QobuzSession and render the results.
They NEVER:
  · import from kabooz.client directly
  · call sess.client.anything
  · duplicate quality-parsing, URL-resolution, or reporting logic

Every operation a user can trigger from the CLI or TUI is a method here,
so it is equally callable from a plain Python script.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Generator, Optional

from ..client import QobuzClient
from ..config import QobuzConfig, _CONFIG_PATH, _SESSION_PATH, load_config
from ..download.downloader import Downloader, DownloadResult, GoodieResult
from ..download.lyrics import fetch_lyrics
from ..download.musicbrainz import lookup_isrc, apply_mb_tags
from ..download.naming import sanitize
from ..download.tagger import Tagger
from ..exceptions import (
    APIError, ConfigError, NotFoundError, NotStreamableError,
    PoolModeError, TokenExpiredError, InvalidCredentialsError, NoAuthError,
)
from ..local.export import (
    ImportResult, backup_to_tar, export_favorites_toml,
    import_favorites_toml, import_playlist_toml, restore_from_tar,
)
from ..local.playlist import (
    LocalPlaylist, LocalPlaylistTrack,
    load_playlist, save_playlist, playlist_from_store_tracks,
)
from ..local.store import LocalStore
from ..models.album import Album
from ..models.artist import Artist
from ..models.favorites import UserFavorites, UserFavoriteIds, LabelDetail
from ..models.playlist import Playlist
from ..models.track import Track
from ..models.user import UserProfile
from ..quality import Quality, QUALITY_DESCENDING
from ..url import parse_url


# ══════════════════════════════════════════════════════════════════════════
# Public re-exports from _types
# ══════════════════════════════════════════════════════════════════════════

from ._types import (
    _parse_quality,
    StreamInfo,
    TrackDownloadResult,
    AlbumDownloadResult,
    PlaylistDownloadResult,
    ProgressCallback,
    TrackStartCallback,
    TrackDoneCallback,
    TrackFailCallback,
    AlbumStartCallback,
    _StreamReporter,
)
from .downloads import DownloadsMixin
from .catalog import CatalogMixin
from .streaming import StreamingMixin
from .favorites import FavoritesMixin
from .playlists import PlaylistsMixin
from .account import AccountMixin
from .discovery import DiscoveryMixin
from .backup import BackupMixin


# ══════════════════════════════════════════════════════════════════════════
# QobuzSession
# ══════════════════════════════════════════════════════════════════════════

class QobuzSession(
    DownloadsMixin,
    CatalogMixin,
    StreamingMixin,
    FavoritesMixin,
    PlaylistsMixin,
    AccountMixin,
    DiscoveryMixin,
    BackupMixin,
):

    def __init__(
        self,
        client: QobuzClient,
        config: QobuzConfig,
        store:  Optional[LocalStore] = None,
        dev:    bool = False,
    ) -> None:
        self.client  = client
        self.config  = config
        self.store   = store or LocalStore(config.local_data.db_path)
        self._dev    = dev
        self._reporter = _StreamReporter(client, enabled=True)

    # ── Construction ───────────────────────────────────────────────────────

    @classmethod
    def from_config(
        cls,
        config_path: Path = _CONFIG_PATH,
        dev: bool = False,
    ) -> "QobuzSession":
        cfg = load_config(config_path)
        if dev:
            from ..dev import enable as _dev_enable
            _dev_enable()
        if cfg.credentials.pool:
            client = QobuzClient.from_token_pool(cfg.credentials.pool, dev=dev)
        else:
            client = QobuzClient.from_credentials(
                app_id=cfg.credentials.app_id,
                app_secret=cfg.credentials.app_secret,
                dev=dev,
            )
            client.load_session(_SESSION_PATH)
        return cls(client=client, config=cfg, dev=dev)

    @classmethod
    def from_client(
        cls,
        client: QobuzClient,
        config: Optional[QobuzConfig] = None,
    ) -> "QobuzSession":
        cfg = config or load_config()
        return cls(client=client, config=cfg)

    # ══════════════════════════════════════════════════════════════════════
    # Helpers — used by CLI, TUI, and scripts; never duplicated elsewhere
    # ══════════════════════════════════════════════════════════════════════

    def resolve_id(
        self,
        url_or_id: str,
        expected_type: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Parse a Qobuz URL or bare numeric ID.

        Returns (entity_type, entity_id).
        For bare IDs entity_type is expected_type or 'unknown'.

        Raises ValueError if URL parses to a different type than expected.
        """
        if url_or_id.startswith("http"):
            entity_type, entity_id = parse_url(url_or_id)
            if expected_type and entity_type != expected_type:
                raise ValueError(
                    f"Expected a {expected_type} URL but got a {entity_type} URL."
                )
            return entity_type, entity_id
        return expected_type or "unknown", url_or_id

    def resolve_quality(
        self,
        s: Optional[str],
        default: Optional[Quality] = None,
    ) -> Quality:
        """
        Parse a quality string, falling back to config then HI_RES.

        Raises ConfigError (not ValueError) so callers get a consistent
        exception type regardless of where the bad string came from.
        """
        if not s:
            if default is not None:
                return default
            return _parse_quality(self.config.download.quality)
        try:
            return _parse_quality(s)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc

    # ══════════════════════════════════════════════════════════════════════
    # Stream reporting — public API for TUI/player
    # ══════════════════════════════════════════════════════════════════════




    # ══════════════════════════════════════════════════════════════════════
    # Catalog reads — thin wrappers so CLI/TUI never import from .client
    # ══════════════════════════════════════════════════════════════════════









    def get_user_info(self) -> UserProfile:
        return self.client.get_user_info()





    # ── Discovery ──────────────────────────────────────────────────────────




    # ══════════════════════════════════════════════════════════════════════
    # Radio and recommendations
    # ══════════════════════════════════════════════════════════════════════




    # ══════════════════════════════════════════════════════════════════════
    # Post-download pipeline (tagging, lyrics, MusicBrainz, history)
    # ══════════════════════════════════════════════════════════════════════



    # ══════════════════════════════════════════════════════════════════════
    # Downloads
    # ══════════════════════════════════════════════════════════════════════


        






    # ══════════════════════════════════════════════════════════════════════
    # Favourites
    # ══════════════════════════════════════════════════════════════════════




    # ══════════════════════════════════════════════════════════════════════
    # Remote playlist management
    # ══════════════════════════════════════════════════════════════════════











    # ══════════════════════════════════════════════════════════════════════
    # Account
    # ══════════════════════════════════════════════════════════════════════




    # ══════════════════════════════════════════════════════════════════════
    # Export / backup
    # ══════════════════════════════════════════════════════════════════════





    # ══════════════════════════════════════════════════════════════════════
    # Private helpers
    # ══════════════════════════════════════════════════════════════════════


