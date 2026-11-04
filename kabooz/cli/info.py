# kabooz/cli/info.py
"""
info command and its display helpers.

Fetches metadata for an album, track, or artist and renders a
formatted view — tracklist table, format/quality panel, ISRC codes.
No download.

Extracted from cli/__init__.py. Uses app from ._app for registration
and helpers (console, err_console, _fmt_dur, _handle_auth_error)
from .helpers.

Public import path unchanged — @app.command() registration runs at
import time.
"""
from __future__ import annotations

import dataclasses
import json
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from ._app import app, _session
from .helpers import (
    console, err_console, _fmt_dur, _handle_auth_error,
)

from ..download.naming import quality_tag
from ..exceptions import (
    APIError, NotFoundError,
    TokenExpiredError, InvalidCredentialsError, NoAuthError,
)
from ..url import parse_url


@app.command()
def info(
    url_or_id:   str           = typer.Argument(..., help="Qobuz URL or bare ID"),
    info_type:   Optional[str] = typer.Option(
        None, "--type", "-t",
        help="Entity type when passing a bare ID: album | track | artist",
    ),
    json_output: bool          = typer.Option(False, "--json", help="Output raw JSON"),
) -> None:
    """
    Display metadata for an album, track, or artist — no download.

    Entity type is auto-detected from Qobuz URLs. When passing a bare
    numeric ID, use --type to specify album, track, or artist.

    Examples
    ────────
      kabooz info https://open.qobuz.com/album/0093046758769
      kabooz info 0093046758769 --type album
      kabooz info https://open.qobuz.com/track/12345
    """
    from rich.panel import Panel

    # ── Resolve entity type and ID ─────────────────────────────────────────
    if url_or_id.startswith("http"):
        try:
            entity_type, entity_id = parse_url(url_or_id)
        except ValueError as exc:
            err_console.print(f"[red]Invalid URL:[/red] {exc}")
            raise typer.Exit(code=1)
    else:
        if not info_type:
            err_console.print(
                "[red]Bare IDs require --type.[/red]  "
                "Use: --type album | track | artist"
            )
            raise typer.Exit(code=1)
        entity_type = info_type.lower()
        entity_id   = url_or_id

    sess = _session()

    # ── Fetch ──────────────────────────────────────────────────────────────
    try:
        if entity_type == "album":
            obj = sess.get_album(entity_id, limit=500)
        elif entity_type == "track":
            obj = sess.get_track(entity_id)
        elif entity_type == "artist":
            obj = sess.get_artist(entity_id, extras="albums", limit=50)
        else:
            err_console.print(
                f"[red]Unknown type:[/red] {entity_type!r}. "
                "Use album, track, or artist."
            )
            raise typer.Exit(code=1)
    except (TokenExpiredError, InvalidCredentialsError, NoAuthError) as exc:
        _handle_auth_error(exc)
    except NotFoundError:
        err_console.print(f"[red]Not found:[/red] {entity_id}")
        raise typer.Exit(code=1)
    except APIError as exc:
        err_console.print(f"[red]API error:[/red] {exc}")
        raise typer.Exit(code=1)

    if json_output:
        import json, dataclasses
        console.print_json(json.dumps(dataclasses.asdict(obj), indent=2, default=str))
        return

    # ── Display ────────────────────────────────────────────────────────────
    if entity_type == "album":
        _display_album_info(obj)
    elif entity_type == "track":
        _display_track_info(obj)
    elif entity_type == "artist":
        _display_artist_info(obj)

def _display_album_info(album) -> None:
    from rich.panel import Panel
    from rich.text  import Text

    # ── Header panel ───────────────────────────────────────────────────────
    artist = album.artist.name if album.artist else ""
    label  = album.label.name  if album.label  else ""
    genre  = album.genre.name  if album.genre  else (
        album.genres_list[0] if album.genres_list else ""
    )
    year   = album.release_date_original[:4] if album.release_date_original else ""

    from ..download.naming import quality_tag
    fmt = quality_tag(album.maximum_bit_depth, album.maximum_sampling_rate)

    # Build subtitle line: artist · genre · year · label
    meta_parts = [p for p in [artist, genre, year, label] if p]
    meta_line  = "  ·  ".join(meta_parts)

    flags = []
    if album.hires:            flags.append("Hi-Res")
    if album.hires_streamable: flags.append("Hi-Res Stream")
    if album.downloadable:     flags.append("DL")
    if album.parental_warning: flags.append("Explicit")
    flag_line = "  ".join(f"[dim]{f}[/dim]" for f in flags)

    goodies_line = ""
    if album.goodies:
        names = ", ".join(g.name or "file" for g in album.goodies)
        goodies_line = f"\n  [bold]Goodies:[/bold] {len(album.goodies)} — {names}"

    upc_line = f"  UPC [dim]{album.upc}[/dim]" if album.upc else ""

    header = (
        f"[bold]{album.display_title}[/bold]\n"
        f"  {meta_line}\n"
        f"  [cyan]{fmt}[/cyan]  ·  "
        f"{album.tracks_count} track{'s' if album.tracks_count != 1 else ''}  ·  "
        f"{_fmt_dur(album.duration)}"
        + (f"\n  {flag_line}" if flag_line else "")
        + (f"\n{upc_line}" if upc_line else "")
        + goodies_line
    )
    console.print(Panel(header, expand=False, border_style="cyan"))

    # ── Track listing ──────────────────────────────────────────────────────
    if not album.tracks or not album.tracks.items:
        console.print("[dim]No track data available.[/dim]")
        return

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("#",      style="dim",  no_wrap=True, width=4)
    table.add_column("Title",  style="bold", ratio=4)
    table.add_column("Dur",    style="dim",  no_wrap=True, width=6)
    table.add_column("ISRC",   style="dim",  no_wrap=True, width=14)

    for t in album.tracks.items:
        num  = f"{t.track_number:02d}"
        if album.media_count and album.media_count > 1:
            num = f"{t.media_number}-{t.track_number:02d}"
        table.add_row(
            num,
            t.display_title,
            _fmt_dur(t.duration),
            t.isrc or "",
        )

    console.print(table)
    console.print(
        f"\n[dim]ID: {album.id}"
        + (f"  ·  Released: {album.release_date_original}" if album.release_date_original else "")
        + "[/dim]"
    )

def _display_track_info(track) -> None:
    from rich.panel import Panel
    from ..download.naming import quality_tag

    artist  = track.performer.name if track.performer else ""
    composer = track.composer.name if track.composer  else ""
    album_t = ""
    fmt     = ""
    if track.album:
        album_t = track.album.display_title
        fmt = quality_tag(track.album.maximum_bit_depth, track.album.maximum_sampling_rate)

    lines = [f"[bold]{track.display_title}[/bold]"]
    if artist:
        lines.append(f"  {artist}")
    if composer and composer != artist:
        lines.append(f"  [dim]Composer:[/dim] {composer}")
    if track.work:
        lines.append(f"  [dim]Work:[/dim] {track.work}")
    if album_t:
        lines.append(f"  [dim]Album:[/dim] {album_t}")

    detail_parts = []
    if track.track_number:
        disc = f"Disc {track.media_number}  " if track.media_number and track.media_number > 1 else ""
        detail_parts.append(f"{disc}Track {track.track_number}")
    detail_parts.append(_fmt_dur(track.duration or 0))
    if fmt:
        detail_parts.append(f"[cyan]{fmt}[/cyan]")
    if track.isrc:
        detail_parts.append(f"ISRC [dim]{track.isrc}[/dim]")
    lines.append("  " + "  ·  ".join(detail_parts))

    flags = []
    if track.hires:        flags.append("Hi-Res")
    if track.downloadable: flags.append("DL")
    if track.streamable:   flags.append("Stream")
    if track.parental_warning: flags.append("Explicit")
    if flags:
        lines.append("  " + "  ".join(f"[dim]{f}[/dim]" for f in flags))

    console.print(Panel("\n".join(lines), expand=False, border_style="cyan"))
    console.print(f"[dim]ID: {track.id}[/dim]")

def _display_artist_info(artist) -> None:
    from rich.panel import Panel

    header = f"[bold]{artist.name}[/bold]"
    if artist.albums_count:
        header += f"\n  {artist.albums_count} albums"

    console.print(Panel(header, expand=False, border_style="cyan"))

    if not artist.albums or not artist.albums.items:
        console.print("[dim]No album data.[/dim]")
        return

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("ID",    style="dim",  no_wrap=True, width=14)
    table.add_column("Title", style="bold", ratio=4)
    table.add_column("Year",  style="dim",  no_wrap=True, width=6)
    table.add_column("Type",  style="dim",  no_wrap=True, width=12)

    for a in artist.albums.items:
        year = (a.release_date_original or "")[:4] if hasattr(a, "release_date_original") else ""
        rtype = (getattr(a, "release_type", None) or "").capitalize()
        table.add_row(str(a.id), a.display_title, year, rtype)

    console.print(table)
    console.print(f"[dim]ID: {artist.id}[/dim]")
