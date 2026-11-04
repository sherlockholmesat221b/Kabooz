# kabooz/cli/search.py
"""Search and discovery commands."""
from __future__ import annotations

import dataclasses
import json
from typing import Optional

import typer
from rich.table import Table

from ._app import app, _session
from .helpers import console, err_console, _handle_auth_error

from ..exceptions import (
    APIError, TokenExpiredError, InvalidCredentialsError, NoAuthError,
)


@app.command()
def search(
    query:       str  = typer.Argument(...),
    search_type: str  = typer.Option("tracks", "--type", "-t"),
    limit:       int  = typer.Option(10, "-n"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Search the Qobuz catalog."""
    valid = {"tracks", "albums", "artists", "playlists"}
    if search_type not in valid:
        err_console.print(
            f"[red]Invalid type.[/red] Choose from: {', '.join(sorted(valid))}"
        )
        raise typer.Exit(code=1)

    sess = _session()
    try:
        results = sess.search(query=query, search_type=search_type, limit=limit)
    except (TokenExpiredError, InvalidCredentialsError, NoAuthError) as exc:
        _handle_auth_error(exc)
    except APIError as exc:
        err_console.print(f"[red]Search failed:[/red] {exc}")
        raise typer.Exit(code=1)

    if json_output:
        import json, dataclasses
        console.print_json(json.dumps(dataclasses.asdict(results), indent=2, default=str))
        return

    # Pull items from the typed result object based on what was requested.
    if search_type == "tracks":
        page = results.tracks
    elif search_type == "albums":
        page = results.albums
    elif search_type == "artists":
        page = results.artists
    else:
        page = results.playlists

    items = page.items if page else []
    if not items:
        console.print(f"No results for [bold]{query!r}[/bold].")
        return

    table = Table(title=f'Search: "{query}" ({search_type})', show_lines=False)
    if search_type == "tracks":
        table.add_column("ID", style="dim", no_wrap=True)
        table.add_column("Title", style="bold")
        table.add_column("Artist")
        table.add_column("Album", style="dim")
        for t in items:
            table.add_row(
                str(t.id),
                t.display_title,
                t.performer.name if t.performer else "",
                t.album.display_title if t.album else "",
            )
    elif search_type == "albums":
        table.add_column("ID", style="dim", no_wrap=True)
        table.add_column("Title", style="bold")
        table.add_column("Artist")
        table.add_column("Year", style="dim")
        for a in items:
            table.add_row(
                str(a.id),
                a.display_title,
                a.artist.name if a.artist else "",
                (a.release_date_original or "")[:4],
            )
    elif search_type == "artists":
        table.add_column("ID", style="dim", no_wrap=True)
        table.add_column("Name", style="bold")
        table.add_column("Albums", style="dim")
        for a in items:
            table.add_row(str(a.id), a.name, str(a.albums_count or ""))
    elif search_type == "playlists":
        table.add_column("ID", style="dim", no_wrap=True)
        table.add_column("Name", style="bold")
        table.add_column("Tracks", style="dim")
        table.add_column("Owner")
        for p in items:
            table.add_row(
                str(p.id),
                p.name,
                str(p.tracks_count or ""),
                p.owner.get("name", "") if isinstance(p.owner, dict) else "",
            )
    console.print(table)

@app.command("new-releases")
def cmd_new_releases(
    release_type: str           = typer.Option("new-releases", "--type", "-t"),
    genre_id:     Optional[int] = typer.Option(None, "--genre"),
    limit:        int           = typer.Option(25, "-n"),
) -> None:
    """Browse new or featured album releases."""
    sess = _session()
    try:
        data = sess.get_new_releases(release_type=release_type,
                                     genre_id=genre_id, limit=limit)
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)

    albums = data.get("albums", {}).get("items", [])
    if not albums:
        console.print("[dim]No results.[/dim]"); return

    table = Table(title=f"New releases ({release_type})", show_lines=False)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Artist")
    table.add_column("Date", style="dim")
    for a in albums:
        table.add_row(str(a.get("id", "")), a.get("title", ""),
                      (a.get("artist") or {}).get("name", ""),
                      (a.get("release_date_original") or "")[:10])
    console.print(table)

@app.command("featured")
def cmd_featured(
    pl_type:  str           = typer.Option("editor-picks", "--type", "-t"),
    genre_id: Optional[int] = typer.Option(None, "--genre"),
    limit:    int           = typer.Option(25, "-n"),
) -> None:
    """Browse editorially curated playlists."""
    sess = _session()
    try:
        data = sess.get_featured_playlists(pl_type=pl_type,
                                           genre_id=genre_id, limit=limit)
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)

    pls = data.get("playlists", {}).get("items", [])
    if not pls:
        console.print("[dim]No results.[/dim]"); return

    table = Table(title=f"Featured playlists ({pl_type})", show_lines=False)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Tracks", style="dim")
    table.add_column("Owner")
    for p in pls:
        table.add_row(str(p.get("id", "")), p.get("name", ""),
                      str(p.get("tracks_count", "")),
                      (p.get("owner") or {}).get("name", ""))
    console.print(table)

@app.command("genres")
def cmd_genres(
    parent: Optional[int] = typer.Option(None, "--parent"),
) -> None:
    """List Qobuz genres (or sub-genres of a parent)."""
    sess = _session()
    try:
        data = sess.get_genres(parent_id=parent)
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)

    genres = data.get("genres", {}).get("items", [])
    if not genres:
        console.print("[dim]No genres found.[/dim]"); return

    table = Table(title="Genres", show_lines=False)
    table.add_column("ID",   style="dim", width=6)
    table.add_column("Name", style="bold")
    table.add_column("Slug", style="dim")
    for g in genres:
        table.add_row(str(g.get("id", "")), g.get("name", ""), g.get("slug", ""))
    console.print(table)
