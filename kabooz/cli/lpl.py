# kabooz/cli/lpl.py
"""lpl sub-app commands (local playlists)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.table import Table

from ._app import lpl_app, _session
from .helpers import console, err_console, _resolve_id, _handle_auth_error

from ..exceptions import TokenExpiredError, InvalidCredentialsError, NoAuthError


@lpl_app.command("list")
def lpl_list() -> None:
    """List all local playlists."""
    store = _session().store
    pls   = store.list_playlists()
    if not pls:
        console.print("[dim]No local playlists yet.[/dim]"); return
    table = Table(title="Local playlists", show_lines=False)
    table.add_column("ID",      style="dim", no_wrap=True, max_width=10)
    table.add_column("Name",    style="bold")
    table.add_column("Tracks",  style="dim")
    table.add_column("Updated", style="dim")
    for pl in pls:
        table.add_row(pl["id"][:8], pl["name"],
                      str(pl.get("track_count", 0)), pl.get("updated_at", "")[:10])
    console.print(table)

@lpl_app.command("create")
def lpl_create(
    name: str = typer.Argument(...),
    desc: str = typer.Option("", "--desc", "-d"),
) -> None:
    """Create a new local playlist."""
    store = _session().store
    pl_id = store.create_playlist(name, desc)
    console.print(f"[green]Created[/green] [bold]{name}[/bold] (id: {pl_id[:8]})")

@lpl_app.command("show")
def lpl_show(name: str = typer.Argument(...)) -> None:
    """Show tracks in a local playlist."""
    sess  = _session()
    pl    = sess._find_local_playlist(name)
    if not pl:
        err_console.print(f"[red]Playlist not found:[/red] {name}")
        raise typer.Exit(code=1)
    tracks = sess.store.get_playlist_tracks(pl["id"])
    console.print(f"[bold]{pl['name']}[/bold]  [dim]{pl.get('description', '')}[/dim]")
    if not tracks:
        console.print("[dim]Empty.[/dim]"); return
    table = Table(show_lines=False)
    table.add_column("#",      style="dim", width=4)
    table.add_column("ID",     style="dim", no_wrap=True)
    table.add_column("Title",  style="bold")
    table.add_column("Artist")
    for t in tracks:
        table.add_row(str(t["position"] + 1), str(t["track_id"]),
                      t.get("title", ""), t.get("artist", ""))
    console.print(table)

@lpl_app.command("add")
def lpl_add(
    playlist: str = typer.Argument(..., help="Playlist name or ID prefix"),
    track_arg: str = typer.Argument(..., help="Track ID or Qobuz URL"),
) -> None:
    """Add a track to a local playlist."""
    sess     = _session()
    track_id = _resolve_id(track_arg, "track")
    pl       = sess._find_local_playlist(playlist)
    if not pl:
        err_console.print(f"[red]Playlist not found:[/red] {playlist}")
        raise typer.Exit(code=1)

    title = artist = album = isrc = ""
    duration = 0
    try:
        obj      = sess.get_track(track_id)
        title    = obj.display_title
        artist   = obj.performer.name if obj.performer else ""
        album    = obj.album.title if obj.album else ""
        duration = obj.duration or 0
        isrc     = obj.isrc or ""
    except Exception:
        pass

    sess.store.add_track_to_playlist(
        pl["id"], track_id,
        title=title, artist=artist, album=album, duration=duration, isrc=isrc,
    )
    console.print(f"[green]Added[/green] {title or track_id} → [bold]{pl['name']}[/bold]")

@lpl_app.command("remove")
def lpl_remove(
    playlist:  str = typer.Argument(...),
    track_arg: str = typer.Argument(...),
) -> None:
    """Remove a track from a local playlist."""
    sess  = _session()
    pl    = sess._find_local_playlist(playlist)
    if not pl:
        err_console.print(f"[red]Playlist not found:[/red] {playlist}")
        raise typer.Exit(code=1)
    if sess.store.remove_track_from_playlist(pl["id"], track_arg):
        console.print(f"[green]Removed[/green] track {track_arg} from [bold]{pl['name']}[/bold].")
    else:
        console.print(f"[yellow]Track {track_arg} was not in that playlist.[/yellow]")

@lpl_app.command("delete")
def lpl_delete(
    name:    str  = typer.Argument(...),
    confirm: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Delete a local playlist."""
    sess = _session()
    pl   = sess._find_local_playlist(name)
    if not pl:
        err_console.print(f"[red]Playlist not found:[/red] {name}")
        raise typer.Exit(code=1)
    if not confirm:
        typer.confirm(f"Delete playlist '{pl['name']}'?", abort=True)
    sess.store.delete_playlist(pl["id"])
    console.print(f"[green]Deleted[/green] [bold]{pl['name']}[/bold].")

@lpl_app.command("clone")
def lpl_clone(
    url_or_id: str           = typer.Argument(...),
    name:      Optional[str] = typer.Option(None, "--name", "-n"),
) -> None:
    """Clone a Qobuz playlist into the local store."""
    sess = _session()
    try:
        pl_id = sess.clone_playlist(url_or_id, name=name)
    except (TokenExpiredError, InvalidCredentialsError, NoAuthError) as exc:
        _handle_auth_error(exc)
    except Exception as exc:
        err_console.print(f"[red]Clone failed:[/red] {exc}"); raise typer.Exit(code=1)

    pl     = sess.store.get_playlist(pl_id)
    tracks = sess.store.get_playlist_tracks(pl_id)
    console.print(
        f"[green]Cloned[/green] [bold]{pl['name']}[/bold] "
        f"({len(tracks)} tracks saved locally)."
    )

@lpl_app.command("share")
def lpl_share(
    name:   str            = typer.Argument(...),
    output: Optional[Path] = typer.Option(None, "-o"),
    author: str            = typer.Option("", "--author", "-a"),
) -> None:
    """Export a local playlist as a shareable TOML file."""
    sess = _session()
    try:
        path = sess.share_playlist(name, output=output, author=author)
    except ValueError as exc:
        err_console.print(f"[red]{exc}[/red]"); raise typer.Exit(code=1)
    console.print(f"[green]Exported[/green] → {path}")

@lpl_app.command("import")
def lpl_import(
    file:      Path = typer.Argument(...),
    overwrite: bool = typer.Option(False, "--overwrite/--no-overwrite"),
) -> None:
    """Import a shared TOML playlist file into the local store."""
    if not file.exists():
        err_console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(code=1)
    sess = _session()
    try:
        pl_id = sess.import_playlist(file, overwrite=overwrite)
    except Exception as exc:
        err_console.print(f"[red]Import failed:[/red] {exc}"); raise typer.Exit(code=1)
    pl     = sess.store.get_playlist(pl_id)
    tracks = sess.store.get_playlist_tracks(pl_id)
    console.print(f"[green]Imported[/green] [bold]{pl['name']}[/bold] ({len(tracks)} tracks)")
