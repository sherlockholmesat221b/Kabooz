# kabooz/cli/remote.py
"""remote sub-app commands (Qobuz account playlists)."""
from __future__ import annotations

from typing import Optional

import typer
from rich.table import Table

from ._app import remote_app, _session
from .helpers import console, err_console, _resolve_id


@remote_app.command("list")
def remote_list(limit: int = typer.Option(50, "-n")) -> None:
    """List playlists on your Qobuz account."""
    sess = _session()
    try:
        pls = list(sess.iter_user_playlists(page_size=limit))
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)
    if not pls:
        console.print("[dim]No playlists on your Qobuz account.[/dim]"); return
    table = Table(title="Remote playlists", show_lines=False)
    table.add_column("ID",     style="dim", no_wrap=True)
    table.add_column("Name",   style="bold")
    table.add_column("Tracks", style="dim")
    table.add_column("Public", style="dim")
    table.add_column("Owner",  style="dim")
    for pl in pls:
        table.add_row(str(pl.id), pl.name, str(pl.tracks_count),
                      "yes" if pl.is_public else "no",
                      pl.owner.name if pl.owner else "—")
    console.print(table)

@remote_app.command("show")
def remote_show(
    playlist_id: str = typer.Argument(...),
    limit:       int = typer.Option(50, "-n"),
) -> None:
    """Show tracks in a Qobuz account playlist."""
    sess = _session()
    try:
        pl = sess.get_playlist(playlist_id, limit=limit)
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)
    console.print(
        f"[bold]{pl.name}[/bold]  "
        f"[dim]{pl.tracks_count} tracks · "
        f"{'public' if pl.is_public else 'private'} · "
        f"owner: {pl.owner.name}[/dim]"
    )
    if not pl.tracks or not pl.tracks.items:
        console.print("[dim]Empty.[/dim]"); return
    table = Table(show_lines=False)
    table.add_column("Pos",      style="dim", width=4)
    table.add_column("PT-ID",    style="dim", no_wrap=True, width=10)
    table.add_column("Track ID", style="dim", no_wrap=True)
    table.add_column("Title",    style="bold")
    table.add_column("Artist")
    for t in pl.tracks.items:
        table.add_row(str(t.position or "—"), str(t.playlist_track_id or "—"),
                      str(t.id), t.title,
                      t.performer.name if t.performer else "—")
    console.print(table)

@remote_app.command("create")
def remote_create(
    name:          str  = typer.Argument(...),
    desc:          str  = typer.Option("",    "--desc",            "-d"),
    public:        bool = typer.Option(False, "--public/--private"),
    collaborative: bool = typer.Option(False, "--collaborative/--no-collaborative"),
    save_locally:  bool = typer.Option(True,  "--save-locally/--no-save-locally"),
) -> None:
    """Create a new playlist on your Qobuz account."""
    sess = _session()
    try:
        pl = sess.create_remote_playlist(
            name=name, description=desc,
            is_public=public, is_collaborative=collaborative,
            also_save_locally=save_locally,
        )
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)
    console.print(f"[green]Created[/green] remote playlist [bold]{pl.name}[/bold] (id: {pl.id})")

@remote_app.command("update")
def remote_update(
    playlist_id:   str            = typer.Argument(...),
    name:          Optional[str]  = typer.Option(None, "--name",  "-n"),
    desc:          Optional[str]  = typer.Option(None, "--desc",  "-d"),
    public:        Optional[bool] = typer.Option(None, "--public/--private"),
    collaborative: Optional[bool] = typer.Option(None, "--collaborative/--no-collaborative"),
) -> None:
    """Update a Qobuz playlist's metadata."""
    if not any([name, desc, public is not None, collaborative is not None]):
        err_console.print("[red]Provide at least one field to update.[/red]")
        raise typer.Exit(code=1)
    sess = _session()
    try:
        pl = sess.update_remote_playlist(
            playlist_id, name=name, description=desc,
            is_public=public, is_collaborative=collaborative,
        )
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)
    console.print(f"[green]Updated[/green] [bold]{pl.name}[/bold].")

@remote_app.command("delete")
def remote_delete(
    playlist_id: str  = typer.Argument(...),
    confirm:     bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Permanently delete a playlist from your Qobuz account."""
    if not confirm:
        typer.confirm(f"Delete remote playlist {playlist_id!r}?", abort=True)
    sess = _session()
    try:
        sess.delete_remote_playlist(playlist_id)
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)
    console.print(f"[green]Deleted[/green] remote playlist {playlist_id}.")

@remote_app.command("add")
def remote_add(
    playlist_id: str       = typer.Argument(...),
    track_ids:   list[str] = typer.Argument(...),
    duplicates:  bool      = typer.Option(False, "--allow-duplicates"),
) -> None:
    """Add one or more tracks to a Qobuz playlist."""
    resolved = [_resolve_id(t, "track") for t in track_ids]
    sess = _session()
    try:
        sess.add_tracks_to_remote_playlist(
            playlist_id, resolved, no_duplicate=not duplicates,
        )
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)
    console.print(f"[green]Added[/green] {len(resolved)} track(s) to playlist {playlist_id}.")

@remote_app.command("remove")
def remote_remove(
    playlist_id:        str       = typer.Argument(...),
    playlist_track_ids: list[int] = typer.Argument(...),
) -> None:
    """Remove tracks from a Qobuz playlist by playlist_track_id (PT-ID from 'remote show')."""
    sess = _session()
    try:
        sess.remove_tracks_from_remote_playlist(playlist_id, playlist_track_ids)
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)
    console.print(
        f"[green]Removed[/green] {len(playlist_track_ids)} track(s) "
        f"from playlist {playlist_id}."
    )

@remote_app.command("follow")
def remote_follow(playlist_id: str = typer.Argument(...)) -> None:
    """Follow a public Qobuz playlist."""
    sess = _session()
    try:
        sess.follow_playlist(playlist_id)
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)
    console.print(f"[green]Following[/green] playlist {playlist_id}.")

@remote_app.command("unfollow")
def remote_unfollow(
    playlist_id: str  = typer.Argument(...),
    confirm:     bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Unfollow a Qobuz playlist."""
    if not confirm:
        typer.confirm(f"Unfollow playlist {playlist_id!r}?", abort=True)
    sess = _session()
    try:
        sess.unfollow_playlist(playlist_id)
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)
    console.print(f"[green]Unfollowed[/green] playlist {playlist_id}.")
