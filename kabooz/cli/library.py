# kabooz/cli/library.py
"""library sub-app commands."""
from __future__ import annotations


import typer
from rich.table import Table

from ._app import library_app, _session
from .helpers import console, err_console, _resolve_id

from ..exceptions import PoolModeError


@library_app.command("show")
def library_show(
    show_type: str = typer.Option("all", "--type", "-t"),
    limit:     int = typer.Option(50, "-n"),
) -> None:
    """Show local favorites."""
    store = _session().store
    types = ["track", "album", "artist"] if show_type == "all" else [show_type]
    for t in types:
        items = store.get_favorites(t, limit=limit)
        if not items:
            continue
        table = Table(title=f"Favorite {t}s ({len(items)})", show_lines=False)
        table.add_column("ID",    style="dim", no_wrap=True)
        table.add_column("Title", style="bold")
        table.add_column("Artist")
        if t == "track":
            table.add_column("Album", style="dim")
        for item in items:
            row = [item.get("id", ""), item.get("title", ""), item.get("artist", "")]
            if t == "track":
                row.append(item.get("extra", ""))
            table.add_row(*row)
        console.print(table)

@library_app.command("add")
def library_add(
    url_or_id:   str  = typer.Argument(...),
    entity_type: str  = typer.Option("track", "--type", "-t"),
    remote:      bool = typer.Option(False, "--remote/--local-only"),
) -> None:
    """Add a track, album, or artist to local favorites."""
    sess      = _session()
    entity_id = _resolve_id(url_or_id)
    try:
        sess.add_favorite(entity_id, entity_type, remote=remote)
        console.print(f"[green]Added[/green] {entity_type} {entity_id}.")
        if remote:
            console.print("  [dim]Also added to Qobuz account.[/dim]")
    except PoolModeError:
        err_console.print("[red]--remote not available in pool mode.[/red]")
        raise typer.Exit(code=1)
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)

@library_app.command("remove")
def library_remove(
    url_or_id:   str  = typer.Argument(...),
    entity_type: str  = typer.Option("track", "--type", "-t"),
    remote:      bool = typer.Option(False, "--remote/--local-only"),
) -> None:
    """Remove a track, album, or artist from local favorites."""
    sess      = _session()
    entity_id = _resolve_id(url_or_id)
    try:
        removed = sess.remove_favorite(entity_id, entity_type, remote=remote)
        if removed:
            console.print(f"[green]Removed[/green] {entity_type} {entity_id}.")
        else:
            console.print(f"[yellow]{entity_type} {entity_id} was not in local favorites.[/yellow]")
        if remote:
            console.print("  [dim]Also removed from Qobuz account.[/dim]")
    except PoolModeError:
        err_console.print("[red]--remote not available in pool mode.[/red]")
        raise typer.Exit(code=1)
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)

@library_app.command("sync")
def library_sync(
    sync_type: str  = typer.Option("all", "--type", "-t"),
    clear:     bool = typer.Option(False, "--clear"),
) -> None:
    """Sync favorites from your Qobuz account into the local store."""
    sess = _session()
    try:
        counts = sess.sync_favorites(
            fav_type=None if sync_type == "all" else sync_type,
            clear=clear,
        )
        for t, n in counts.items():
            console.print(f"[green]Synced[/green] {n} {t}(s) → local store.")
    except PoolModeError:
        err_console.print("[red]sync requires a personal session (not pool mode).[/red]")
        raise typer.Exit(code=1)
    except Exception as exc:
        err_console.print(f"[red]Sync failed:[/red] {exc}"); raise typer.Exit(code=1)

@library_app.command("history")
def library_history(
    limit: int  = typer.Option(20, "-n"),
    clear: bool = typer.Option(False, "--clear"),
) -> None:
    """Show or clear the local download/play history."""
    store = _session().store
    if clear:
        console.print(f"[green]Cleared {store.clear_history()} history entries.[/green]")
        return
    rows = store.get_history(limit=limit)
    if not rows:
        console.print("[dim]No history yet.[/dim]"); return
    table = Table(title=f"Recent history (last {limit})", show_lines=False)
    table.add_column("Time",   style="dim", no_wrap=True)
    table.add_column("Title",  style="bold")
    table.add_column("Artist")
    table.add_column("Album",  style="dim")
    for row in rows:
        table.add_row(row.get("played_at", "")[:16], row.get("title", ""),
                      row.get("artist", ""), row.get("album", ""))
    console.print(table)
