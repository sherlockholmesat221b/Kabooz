# kabooz/cli/account.py
"""account sub-app commands."""
from __future__ import annotations

from typing import Optional

import typer
from rich.table import Table

from ._app import account_app, _session
from .helpers import console, err_console, _yn


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
