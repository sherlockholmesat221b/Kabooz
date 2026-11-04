# kabooz/cli/export.py
"""export sub-app commands (backup/restore)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from ._app import export_app, _session
from .helpers import console, err_console
from .lpl import lpl_share


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
