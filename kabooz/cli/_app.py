# kabooz/cli/_app.py
"""
Typer app instances and shared CLI state.

Holds the main app and the five sub-apps (library, lpl, export,
account, remote), plus the _dev module flag and the _session
factory function.

Both __init__.py and downloads.py import from here, avoiding the
circular dependency that would arise if download commands needed
_session from __init__.py.

main() in __init__.py sets _app._dev when --dev is passed.
"""
from __future__ import annotations

from typing import Optional

import typer

from ..config import QobuzConfig
from ..session import QobuzSession


app         = typer.Typer(name="qobuz", add_completion=False,
                          invoke_without_command=True,
                          help="Unofficial Qobuz CLI.")
library_app = typer.Typer(help="Manage local and remote favourites.")
lpl_app     = typer.Typer(help="Create, manage, and share local playlists.")
export_app  = typer.Typer(help="Export, import, and back up your library.")
account_app = typer.Typer(help="View and update your Qobuz account profile.")
remote_app  = typer.Typer(help="Manage playlists on your Qobuz account.")

app.add_typer(library_app, name="library")
app.add_typer(lpl_app,     name="lpl")
app.add_typer(export_app,  name="export")
app.add_typer(account_app, name="account")
app.add_typer(remote_app,  name="remote")

_dev: bool  = False


def _session(cfg: Optional[QobuzConfig] = None) -> QobuzSession:
    return QobuzSession.from_config(dev=_dev)
