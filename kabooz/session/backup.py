# kabooz/session/backup.py
"""
Backup and restore methods for QobuzSession.

Full library backup (tar.gz including DB, config, playlists, and
favorites), favorites export/import to TOML, and restore-from-archive
with selective or full replacement.

Extracted from session/__init__.py. Mixin composition — methods
operate on a QobuzSession instance with access to self.store and
self.config.

Public import path unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..config import _CONFIG_PATH
from ..local.export import (
    ImportResult,
    backup_to_tar,
    export_favorites_toml,
    import_favorites_toml,
    restore_from_tar,
)


class BackupMixin:
    """Mixin providing backup, export, import, and restore.
    Composed into QobuzSession via class inheritance."""

    def backup(self, output: Optional[Path] = None) -> Path:
        if output is None:
            from datetime import datetime, timezone
            self.config.local_data.exports_dir.mkdir(parents=True, exist_ok=True)
            date   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            output = self.config.local_data.exports_dir / f"qobuz-backup-{date}.tar.gz"
        return backup_to_tar(
            store=self.store,
            config_path=_CONFIG_PATH,
            playlists_dir=self.config.local_data.playlists_dir,
            output_path=output,
        )

    def export_favorites(
        self, output: Optional[Path] = None, fav_type: Optional[str] = None,
    ) -> Path:
        if output is None:
            from datetime import datetime, timezone
            self.config.local_data.exports_dir.mkdir(parents=True, exist_ok=True)
            date   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            output = self.config.local_data.exports_dir / f"favorites-{date}.toml"
        return export_favorites_toml(self.store, output, type=fav_type)

    def import_favorites(self, file: Path, merge: bool = True) -> int:
        return import_favorites_toml(self.store, Path(file), merge=merge)

    def restore(
        self,
        archive_path:      Path,
        restore_favorites: bool = True,
        restore_playlists: bool = True,
        restore_db:        bool = False,
        merge:             bool = True,
    ) -> ImportResult:
        return restore_from_tar(
            self.store, Path(archive_path),
            restore_favorites=restore_favorites,
            restore_playlists=restore_playlists,
            restore_db=restore_db,
            merge=merge,
            playlists_dir=(
                self.config.local_data.playlists_dir if restore_playlists else None
            ),
        )
