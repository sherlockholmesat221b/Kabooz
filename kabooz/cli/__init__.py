# kabooz/cli/__init__.py
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

try:
    import typer
    from rich.console import Console
    from rich.progress import (
        BarColumn, DownloadColumn, Progress,
        TextColumn, TimeRemainingColumn, TransferSpeedColumn,
    )
    from rich.table import Table
except ImportError:
    print(
        "CLI dependencies are not installed.\n"
        "Run: pip install 'kabooz[cli]'",
        file=sys.stderr,
    )
    sys.exit(1)

from ..config import (
    QobuzConfig, _CONFIG_PATH, _SESSION_PATH,
    load_config, save_config, update_config,
)
from ..exceptions import (
    APIError, ConfigError, InvalidCredentialsError,
    NoAuthError, NotFoundError, NotStreamableError,
    PoolModeError, TokenExpiredError,
)
from ..quality import Quality
from ..session import QobuzSession, _parse_quality
from ..url import parse_url

from ._app import (
    app, library_app, lpl_app, export_app,
    account_app, remote_app, _session,
)

from . import downloads  # noqa: F401 (registers commands)
from . import info       # noqa: F401 (registers command)
from . import auth       # noqa: F401 (registers commands)
from . import search     # noqa: F401 (registers commands)
from . import library  # noqa: F401 (registers commands)
from . import lpl  # noqa: F401 (registers commands)
from . import account  # noqa: F401 (registers commands)
from . import remote  # noqa: F401 (registers commands)
from . import export  # noqa: F401 (registers commands)

from .helpers import (
    _cfg,
    _cover_size,
    _credits_callback,
    _fmt_dur,
    _handle_auth_error,
    _make_progress,
    _on_album_start,
    _on_track_done,
    _on_track_start,
    _print_failed,
    _quality,
    _resolve_id,
    _version_callback,
    _yn,
    console,
    err_console,
)

# ── Sub-apps ───────────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════
# Presentation helpers — display concerns only, no business logic
# ══════════════════════════════════════════════════════════════════════════


# ── Global callback ────────────────────────────────────────────────────────


@app.callback()
def main(
    ctx: typer.Context,
    dev: bool = typer.Option(
        False, "--dev", envvar="KABOOZ_DEV", is_eager=True,
        help="Developer mode: cache API responses, write dev audio.",
    ),
    version: bool = typer.Option(
        False, "--version", "-V", is_eager=True,
        callback=_version_callback, expose_value=False,
        help="Show version and exit.",
    ),
    credits: bool = typer.Option(
        False, "--credits", is_eager=True,
        callback=_credits_callback, expose_value=False,
        help="Show credits and exit.",
    ),
) -> None:
    """Unofficial Qobuz CLI."""
    from . import _app as _app_mod
    _app_mod._dev = dev
    if dev:
        from .. import dev as _dev_module
        _dev_module.enable()
        err_console.print(
            "[yellow bold][DEV MODE][/yellow bold] "
            "API responses cached · Dev audio enabled · "
            f"Cache: [dim]{_dev_module.CACHE_DIR}[/dim]"
        )

    if ctx.invoked_subcommand is None:
        try:
            from importlib.metadata import version
            v = version("kabooz")
        except Exception:
            v = "0.1.0"

        from rich.panel import Panel
        from rich.columns import Columns
        from rich.text import Text

        console.print()
        console.print(
            f"  [bold cyan]Kabooz[/bold cyan] [dim]v{v}[/dim]  "
            "· Unofficial Qobuz client"
        )
        console.print()

        commands = [
            ("track",        "Download a single track"),
            ("album",        "Download a full album"),
            ("artist",       "Download a full discography"),
            ("playlist",     "Download a playlist"),
            ("goodies",      "Download bonus files only"),
            ("info",         "View metadata without downloading"),
            ("search",       "Search the catalog"),
            ("favorites",    "Download your favorites"),
            ("new-releases", "Browse new releases"),
            ("login",        "Authenticate"),
            ("config",       "View or edit configuration"),
            ("library",      "Local favorites and history"),
            ("lpl",          "Local playlists"),
            ("remote",       "Qobuz account playlists"),
            ("account",      "Account profile"),
            ("export",       "Backup and restore"),
        ]

        table = Table(box=None, show_header=False, padding=(0, 2, 0, 0))
        table.add_column(style="bold cyan",  no_wrap=True)
        table.add_column(style="dim")
        for cmd, desc in commands:
            table.add_row(cmd, desc)

        console.print(table)
        console.print()
        console.print(
            "  [dim]kabooz --help        full help[/dim]  "
            "  [dim]kabooz --version     version[/dim]  "
            "  [dim]kabooz --credits     credits[/dim]"
        )
        console.print()


# ── Shared session factory ─────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════
# Core commands
# ══════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════
# Download commands
# ══════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════
# Metadata and goodies
# ══════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════
# Discovery commands
# ══════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════
# library subcommands
# ══════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════
# lpl subcommands
# ══════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════
# export subcommands
# ══════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════
# account subcommands
# ══════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════
# remote subcommands
# ══════════════════════════════════════════════════════════════════════════


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
