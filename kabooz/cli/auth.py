# kabooz/cli/auth.py
"""Authentication and configuration commands."""
from __future__ import annotations

import os
from typing import Optional

import typer

from ._app import app
from .helpers import console, err_console, _cfg

from ..config import (
    _CONFIG_PATH, _SESSION_PATH, save_config, update_config,
)
from ..exceptions import ConfigError
from ..session import QobuzSession


@app.command()
def login(
    username:   Optional[str] = typer.Option(None, "--username", "-u"),
    password:   Optional[str] = typer.Option(None, "--password", "-p", hide_input=True),
    token:      Optional[str] = typer.Option(None, "--token"),
    user_id:    Optional[str] = typer.Option(None, "--user-id"),
    pool:       Optional[str] = typer.Option(None, "--pool"),
    app_id:     Optional[str] = typer.Option(None, "--app-id"),
    app_secret: Optional[str] = typer.Option(None, "--app-secret", hide_input=True),
) -> None:
    """
    Authenticate with Qobuz.

    \b
    1. Username + password:  kabooz login -u me@example.com -p secret
    2. Direct token:         kabooz login --token TOKEN --user-id 12345
    3. Token pool:           kabooz login --pool ~/.config/kabooz/pool.txt
    """
    from ..client import QobuzClient
    cfg = _cfg()

    if pool:
        try:
            QobuzClient.from_token_pool(pool)
        except Exception as exc:
            err_console.print(f"[red]Failed to load token pool:[/red] {exc}")
            raise typer.Exit(code=1)
        cfg.credentials.pool = pool
        save_config(cfg)
        console.print(f"[green]Token pool saved.[/green] Config: [bold]{_CONFIG_PATH}[/bold]")
        return

    resolved_app_id     = app_id     or os.environ.get("QOBUZ_APP_ID")     or cfg.credentials.app_id
    resolved_app_secret = app_secret or os.environ.get("QOBUZ_APP_SECRET") or cfg.credentials.app_secret
    if not resolved_app_id:
        resolved_app_id = typer.prompt("App ID")
    if not resolved_app_secret:
        resolved_app_secret = typer.prompt("App Secret", hide_input=True)

    cfg.credentials.app_id     = resolved_app_id
    cfg.credentials.app_secret = resolved_app_secret
    cfg.credentials.pool       = ""

    client = QobuzClient.from_credentials(
        app_id=resolved_app_id, app_secret=resolved_app_secret,
    )

    if token:
        if not user_id:
            user_id = typer.prompt("User ID")
        try:
            session = client.login(token=token, user_id=user_id)
        except Exception as exc:
            err_console.print(f"[red]Login failed:[/red] {exc}")
            raise typer.Exit(code=1)
    else:
        if not username:
            username = typer.prompt("Qobuz username (email)")
        if not password:
            password = typer.prompt("Password", hide_input=True)
        try:
            session = client.login(username=username, password=password)
        except Exception as exc:
            err_console.print(f"[red]Login failed:[/red] {exc}")
            raise typer.Exit(code=1)

    save_config(cfg)
    try:
        client.save_session(_SESSION_PATH)
    except Exception as exc:
        err_console.print(f"[red]Could not save session:[/red] {exc}")
        raise typer.Exit(code=1)

    if cfg.local_data.auto_sync_favorites and not cfg.credentials.pool:
        console.print("[dim]Syncing favorites to local store…[/dim]")
        try:
            s      = QobuzSession.from_client(client, cfg)
            counts = s.sync_favorites()
            for t, n in counts.items():
                if n:
                    console.print(f"  [dim]{n} {t}(s) synced[/dim]")
        except Exception as exc:
            err_console.print(f"[yellow]Auto-sync failed:[/yellow] {exc}")

    console.print(
        f"[green]Logged in as[/green] {session.user_email or session.user_id}. "
        f"Session saved to [bold]{_SESSION_PATH}[/bold]."
    )

@app.command()
def config(
    show: bool            = typer.Option(False, "--show"),
    set_: Optional[str]   = typer.Option(None, "--set",
        help="section.key=value  e.g. download.max_workers=4"),
) -> None:
    """
    View or update the configuration file.

    \b
    Examples:
        kabooz config --show
        kabooz config --set download.max_workers=4
        kabooz config --set streaming.report_streams=false
        kabooz config --set download.quality=flac_16
    """
    if show:
        import dataclasses, json
        console.print_json(json.dumps(dataclasses.asdict(_cfg()), indent=2))
        return

    if set_:
        if "=" not in set_:
            err_console.print("[red]Format must be section.key=value[/red]")
            raise typer.Exit(code=1)
        key_path, _, value = set_.partition("=")
        parts = key_path.strip().split(".")
        if len(parts) != 2:
            err_console.print("[red]Key must be in section.key format[/red]")
            raise typer.Exit(code=1)
        section, key = parts
        coerced: object = value
        if value.lower() in ("true", "yes", "1"):
            coerced = True
        elif value.lower() in ("false", "no", "0"):
            coerced = False
        else:
            try:
                coerced = int(value)
            except ValueError:
                try:
                    coerced = float(value)
                except ValueError:
                    coerced = value
        try:
            update_config({section: {key: coerced}})
        except ConfigError as exc:
            err_console.print(f"[red]Invalid config value:[/red] {exc}")
            raise typer.Exit(code=1)
        console.print(f"[green]Set[/green] {section}.{key} = {coerced!r}")
        return

    console.print("Use [bold]--show[/bold] or [bold]--set section.key=value[/bold].")
    console.print(f"Config: [bold]{_CONFIG_PATH}[/bold]")

@app.command("dev-cache")
def dev_cache(
    clear: bool = typer.Option(False, "--clear"),
    show:  bool = typer.Option(False, "--show"),
) -> None:
    """Manage the dev mode API response cache."""
    from ..dev import CACHE_DIR, clear_cache
    if clear:
        console.print(f"[green]Cleared {clear_cache()} cached response(s).[/green]")
        return
    files = list(CACHE_DIR.glob("*.json")) if CACHE_DIR.exists() else []
    console.print(
        f"Cache: [bold]{CACHE_DIR}[/bold]  ({len(files)} files"
        + (f", {sum(f.stat().st_size for f in files)/1024:.1f} KB)" if files else ")")
    )
