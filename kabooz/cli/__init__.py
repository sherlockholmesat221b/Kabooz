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

@account_app.command("show")
def account_show(json_output: bool = typer.Option(False, "--json")) -> None:
    """Show your Qobuz account profile and subscription tier."""
    sess = _session()
    try:
        profile = sess.get_profile()
    except Exception as exc:
        err_console.print(f"[red]Failed to fetch profile:[/red] {exc}")
        raise typer.Exit(code=1)

    if json_output:
        import json as _json
        console.print(_json.dumps(profile._raw, indent=2, ensure_ascii=False))
        return

    table = Table(title="Account profile", show_lines=False, box=None)
    table.add_column("Field", style="dim", width=20)
    table.add_column("Value", style="bold")
    for label, value in [
        ("ID",           str(profile.id)),
        ("Login",        profile.login),
        ("Email",        profile.email or "—"),
        ("Name",         profile.full_name),
        ("Display name", profile.display_name or "—"),
        ("Country",      profile.country_code or "—"),
        ("Language",     profile.language_code or "—"),
        ("Newsletter",   "yes" if profile.newsletter else "no"),
        ("Created",      profile.creation_date or "—"),
    ]:
        table.add_row(label, value)
    console.print(table)

    if profile.credential:
        cred = profile.credential
        sub  = Table(title="Subscription", show_lines=False, box=None)
        sub.add_column("Field", style="dim", width=20)
        sub.add_column("Value", style="bold")
        sub.add_row("Plan",              cred.label)
        sub.add_row("Description",       cred.description)
        sub.add_row("Max quality",       cred.max_audio_quality)
        sub.add_row("Hi-res streaming",  _yn(cred.hires_streaming))
        sub.add_row("Mobile streaming",  _yn(cred.mobile_streaming))
        sub.add_row("Offline listening", _yn(cred.offline_listening))
        console.print(sub)


@account_app.command("update")
def account_update(
    email:        Optional[str]  = typer.Option(None, "--email"),
    firstname:    Optional[str]  = typer.Option(None, "--firstname"),
    lastname:     Optional[str]  = typer.Option(None, "--lastname"),
    display_name: Optional[str]  = typer.Option(None, "--display-name"),
    country:      Optional[str]  = typer.Option(None, "--country"),
    language:     Optional[str]  = typer.Option(None, "--language"),
    newsletter:   Optional[bool] = typer.Option(None, "--newsletter/--no-newsletter"),
) -> None:
    """Update your Qobuz account profile fields."""
    if not any([email, firstname, lastname, display_name, country, language,
                newsletter is not None]):
        err_console.print("[red]Provide at least one field to update.[/red]")
        raise typer.Exit(code=1)
    sess = _session()
    try:
        profile = sess.update_profile(
            email=email, firstname=firstname, lastname=lastname,
            display_name=display_name, country_code=country,
            language_code=language, newsletter=newsletter,
        )
    except Exception as exc:
        err_console.print(f"[red]Update failed:[/red] {exc}"); raise typer.Exit(code=1)
    console.print(
        f"[green]Profile updated.[/green] "
        f"Name: {profile.full_name}  Email: {profile.email or '—'}"
    )


@account_app.command("password")
def account_password(
    current: Optional[str] = typer.Option(None, "--current", hide_input=True),
    new:     Optional[str] = typer.Option(None, "--new",     hide_input=True),
    confirm: Optional[str] = typer.Option(None, "--confirm", hide_input=True),
) -> None:
    """Change your Qobuz account password."""
    if current is None:
        current = typer.prompt("Current password", hide_input=True)
    if new is None:
        new = typer.prompt("New password", hide_input=True)
    if confirm is None:
        confirm = typer.prompt("Confirm new password", hide_input=True)
    if new != confirm:
        err_console.print("[red]New passwords do not match.[/red]")
        raise typer.Exit(code=1)
    sess = _session()
    try:
        sess.change_password(current, new)
    except Exception as exc:
        err_console.print(f"[red]Password change failed:[/red] {exc}")
        raise typer.Exit(code=1)
    console.print("[green]Password changed successfully.[/green]")


@account_app.command("subscription")
def account_subscription() -> None:
    """Show your current subscription tier and capabilities."""
    sess = _session()
    try:
        profile = sess.get_profile()
    except Exception as exc:
        err_console.print(f"[red]Failed:[/red] {exc}"); raise typer.Exit(code=1)
    if not profile.credential:
        console.print("[yellow]No subscription information available.[/yellow]"); return
    cred  = profile.credential
    table = Table(title="Subscription", show_lines=False, box=None)
    table.add_column("", style="dim", width=28)
    table.add_column("", style="bold")
    table.add_row("Plan",                   cred.label)
    table.add_row("Description",            cred.description)
    table.add_row("Max quality",            cred.max_audio_quality)
    table.add_row("Lossy streaming",        _yn(cred.lossy_streaming))
    table.add_row("Lossless streaming",     _yn(cred.lossless_streaming))
    table.add_row("Hi-res streaming",       _yn(cred.hires_streaming))
    table.add_row("Mobile streaming",       _yn(cred.mobile_streaming))
    table.add_row("Offline listening",      _yn(cred.offline_listening))
    console.print(table)


# ══════════════════════════════════════════════════════════════════════════
# remote subcommands
# ══════════════════════════════════════════════════════════════════════════

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


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
