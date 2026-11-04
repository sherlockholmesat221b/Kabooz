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

@export_app.command("backup")
def export_backup(output: Optional[Path] = typer.Option(None, "-o")) -> None:
    """Create a full .tar.gz backup of your local library."""
    sess = _session()
    try:
        path = sess.backup(output)
    except Exception as exc:
        err_console.print(f"[red]Backup failed:[/red] {exc}"); raise typer.Exit(code=1)
    console.print(
        f"[green]Backup saved:[/green] {path}  "
        f"[dim]({path.stat().st_size / 1024:.1f} KB)[/dim]"
    )


@export_app.command("favorites")
def export_favorites_cmd(
    output:   Optional[Path] = typer.Option(None, "-o"),
    fav_type: str            = typer.Option("all", "--type", "-t"),
) -> None:
    """Export local favorites to a TOML file."""
    sess = _session()
    try:
        path = sess.export_favorites(output, fav_type=None if fav_type == "all" else fav_type)
    except Exception as exc:
        err_console.print(f"[red]Export failed:[/red] {exc}"); raise typer.Exit(code=1)
    console.print(f"[green]Favorites exported:[/green] {path}")


@export_app.command("playlist")
def export_playlist(
    name:   str            = typer.Argument(...),
    output: Optional[Path] = typer.Option(None, "-o"),
    author: str            = typer.Option("", "--author", "-a"),
) -> None:
    """Export a local playlist to a shareable TOML file."""
    lpl_share(name=name, output=output, author=author)


@export_app.command("import-favorites")
def export_import_favorites(
    file:     Path = typer.Argument(...),
    no_merge: bool = typer.Option(False, "--replace/--merge"),
) -> None:
    """Import favorites from a TOML file created by 'export favorites'."""
    if not file.exists():
        err_console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(code=1)
    sess = _session()
    try:
        n = sess.import_favorites(file, merge=not no_merge)
    except (ValueError, Exception) as exc:
        err_console.print(f"[red]Import failed:[/red] {exc}"); raise typer.Exit(code=1)
    console.print(f"[green]Imported[/green] {n} favorite(s) from {file.name}.")


@export_app.command("restore")
def export_restore(
    archive:       Path           = typer.Argument(...),
    do_favorites:  bool           = typer.Option(True,  "--favorites/--no-favorites"),
    do_playlists:  bool           = typer.Option(True,  "--playlists/--no-playlists"),
    db:            bool           = typer.Option(False, "--db"),
    replace:       bool           = typer.Option(False, "--replace/--merge"),
) -> None:
    """Restore from a backup archive created by 'export backup'."""
    if not archive.exists():
        err_console.print(f"[red]File not found:[/red] {archive}")
        raise typer.Exit(code=1)
    sess = _session()
    try:
        result = sess.restore(
            archive,
            restore_favorites=do_favorites,
            restore_playlists=do_playlists,
            restore_db=db,
            merge=not replace,
        )
    except Exception as exc:
        err_console.print(f"[red]Restore failed:[/red] {exc}"); raise typer.Exit(code=1)

    if result.db_restored:
        console.print("[green]Database restored.[/green] Please re-open the application.")
        return
    console.print(
        f"[green]Restore complete.[/green]  "
        f"Favorites: {result.favorites_imported}  "
        f"Playlists: {result.playlists_imported} imported, "
        f"{result.playlists_skipped} skipped."
    )
    for e in result.errors:
        err_console.print(f"  [dim yellow]{e}[/dim yellow]")


# ══════════════════════════════════════════════════════════════════════════
# account subcommands
# ══════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════
# remote subcommands
# ══════════════════════════════════════════════════════════════════════════


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
