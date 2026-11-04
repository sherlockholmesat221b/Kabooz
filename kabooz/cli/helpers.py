# kabooz/cli/helpers.py
"""
Shared presentation helpers for the CLI.

Small utilities used by multiple commands: quality parsing, cover
size validation, ID resolution, progress bar construction, callback
functions, error handling. Extracted from cli/__init__.py to keep
command modules focused on argument handling.

console and err_console live here so helpers and commands share the
same output destination. All helpers write through these instances;
none create their own Console.

Public import path unchanged — cli/__init__.py re-imports these.
"""
from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn, DownloadColumn, Progress,
    TextColumn, TimeRemainingColumn, TransferSpeedColumn,
)

from ..config import QobuzConfig, load_config
from ..exceptions import ConfigError
from ..session import _parse_quality
from ..url import parse_url


console     = Console()

err_console = Console(stderr=True)

def _quality(s: Optional[str]) -> Optional[Quality]:
    """
    Parse a quality flag string. Exits with a helpful error on bad input.
    Single source of truth — never duplicate this try/except in commands.
    """
    if not s:
        return None
    try:
        return _parse_quality(s)
    except (ValueError, ConfigError) as exc:
        err_console.print(f"[red]Invalid quality:[/red] {exc}")
        raise typer.Exit(code=1)

_VALID_COVER_SIZES = {"thumbnail", "small", "large", "original"}

def _cover_size(s: Optional[str]) -> Optional[str]:
    """Validate a --cover-size / --save-cover-size argument."""
    if s is None:
        return None
    if s not in _VALID_COVER_SIZES:
        err_console.print(
            f"[red]Invalid cover size:[/red] {s!r}. "
            f"Valid: {', '.join(sorted(_VALID_COVER_SIZES))}"
        )
        raise typer.Exit(code=1)
    return s

def _resolve_id(url_or_id: str, expected_type: Optional[str] = None) -> str:
    """Parse a Qobuz URL or bare ID and return the entity ID string."""
    if url_or_id.startswith("http"):
        try:
            entity_type, entity_id = parse_url(url_or_id)
        except ValueError as exc:
            err_console.print(f"[red]Invalid URL:[/red] {exc}")
            raise typer.Exit(code=1)
        if expected_type and entity_type != expected_type:
            err_console.print(
                f"[red]Expected a {expected_type} URL but got {entity_type}.[/red]"
            )
            raise typer.Exit(code=1)
        return entity_id
    return url_or_id

def _make_progress() -> Progress:
    return Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(), DownloadColumn(),
        TransferSpeedColumn(), TimeRemainingColumn(),
        console=console, transient=True,
    )

def _yn(v: bool) -> str:
    return "[green]yes[/green]" if v else "[dim]no[/dim]"

def _on_track_start(title: str, index: int, total: int) -> None:
    pad = f"/{total}" if total else ""
    console.print(f"  [{index}{pad}] {title}")

def _on_track_done(result) -> None:
    if result.download.skipped and not result.download.dev_stub:
        console.print("    [yellow]Already complete — skipped.[/yellow]")

def _on_album_start(title: str, index: int, total: int) -> None:
    console.print(
        f"\n[bold cyan][{index}/{total}][/bold cyan]  [bold]{title}[/bold]"
    )

def _print_failed(failed: list[str], label: str = "Failed") -> None:
    if not failed:
        return
    err_console.print(f"\n[red]{label} ({len(failed)}):[/red]")
    for item in failed:
        err_console.print(f"  [dim]·[/dim] {item}")

def _version_callback(value: bool) -> None:
    if value:
        try:
            from importlib.metadata import version
            v = version("kabooz")
        except Exception:
            v = "0.1.0"
        console.print(f"[bold]Kabooz[/bold] v{v}")
        raise typer.Exit()

def _credits_callback(value: bool) -> None:
    if not value:
        return
    from rich.panel import Panel
    lines = [
        "[bold]Kabooz[/bold] — unofficial Qobuz client\n",

        "[bold cyan]A word on Qobuz[/bold cyan]",
        "  This tool exists because Qobuz is genuinely one of the best",
        "  things to happen to music. Hi-res lossless, a serious catalog,",
        "  no ads, fair artist payouts — it deserves your subscription.",
        "  [dim]https://www.qobuz.com[/dim]\n",

        "[bold cyan]Technical thanks[/bold cyan]",
        "  [bold]tmxkwpn[/bold]  (@tmxkwpn on Telegram) — technical help and guidance\n",

        "[bold cyan]Services used[/bold cyan]",
        "  [bold]MusicBrainz[/bold]   musicbrainz.org — open music encyclopedia,",
        "                    used for ISRC lookup and tag enrichment",
        "  [bold]LRCLIB[/bold]        lrclib.net — free, open synced lyrics database\n",

        "[bold cyan]Built with[/bold cyan]",
        "  [bold]httpx[/bold]         HTTP client            github.com/encode/httpx",
        "  [bold]mutagen[/bold]       audio metadata         github.com/quodlibet/mutagen",
        "  [bold]Typer[/bold]         CLI framework          github.com/tiangolo/typer",
        "  [bold]Rich[/bold]          terminal formatting    github.com/Textualize/rich",
        "  [bold]tomli-w[/bold]       TOML writer            github.com/hukkin/tomli-w\n",

        "[bold cyan]Tinker, extend, improve[/bold cyan]",
        "  Kabooz is intentionally designed to be hackable. The business",
        "  logic lives entirely in session.py, models are plain dataclasses,",
        "  and the CLI is a thin presentation layer over the library.",
        "  If something is missing, slow, or broken — please add it.",
        "  PRs, forks, and feature branches are all welcome.\n",

        "[bold cyan]License[/bold cyan]",
        "  AGPL-3.0-or-later\n",

        "[dim]Kabooz is not affiliated with, endorsed by, or connected",
        "to Qobuz or any of the services listed above.[/dim]",
    ]
    console.print(Panel("\n".join(lines), expand=False, border_style="cyan"))
    raise typer.Exit()

def _cfg() -> QobuzConfig:
    return load_config()

def _handle_auth_error(exc: Exception) -> None:
    err_console.print(
        f"[red]Authentication error:[/red] {exc}\n"
        "Run [bold]kabooz login[/bold] to refresh your session."
    )
    raise typer.Exit(code=1)

def _fmt_dur(seconds: int) -> str:
    """Format an integer number of seconds as m:ss or h:mm:ss."""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
