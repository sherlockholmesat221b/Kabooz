#!/usr/bin/env python3
# scripts/test_mp3_lyrics.py
"""
Generate a set of MP3 files with different lyrics tag combinations,
to empirically determine which ID3 tags Musicolet (and other Android
players) actually read for lyrics display.

Why this exists: MP3 has two standard lyrics frames (USLT plain, SYLT
binary) plus several non-standard TXXX conventions. Players differ
wildly on which they honour. Rather than guess and ship a feature
that displays nothing in the target player, we generate one file per
candidate configuration and observe.

Usage:
    python scripts/test_mp3_lyrics.py [output_dir]

Default output dir: ./mp3-lyrics-test/

After running:
  1. Copy the output directory to your phone's music folder.
  2. Open each file in Musicolet (or any target player).
  3. Note for each file: (a) do lyrics display at all? (b) do they
     scroll in time with the audio?

The lyrics are distinct per tag so you can tell which one the player
is reading:

  SYNCED LRC  — "SYNCED LRC LINE ONE" / "... TWO" / "... THREE"
  SYNCED SYLT — "SYNCED SYLT LINE ONE" / "... TWO" / "... THREE"
  PLAIN       — "PLAIN LINE ONE" / "... TWO" / "... THREE"

Sync timings: line 1 at 0s, line 2 at 2s, line 3 at 4s.
Audio: 8 seconds of a soft sine tone.

Expected outcomes:

  If A (USLT=LRC) scrolls   → 'lyrics' default works.
  If A shows but static     → USLT works but LRC is not parsed.
                              Need SYLT or a TXXX fallback.
  If B (USLT=plain) works   → USLT is read at all; format question
                              is LRC parsing only.
  If only C or D works      → Musicolet ignores USLT entirely and
                              only reads TXXX.
  If E (SYLT only) works    → Musicolet reads SYLT; prefer 'syncedlyrics'.
  If nothing works          → Musicolet does not read any embedded
                              tag (only external .lrc sidecars).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from mutagen.id3 import ID3, SYLT, TXXX, USLT


# Distinct lyric strings so the tester can identify which tag was read.
PLAIN = (
    "PLAIN LINE ONE\n"
    "PLAIN LINE TWO\n"
    "PLAIN LINE THREE"
)

SYNCED_LRC = (
    "[00:00.00] SYNCED LRC LINE ONE\n"
    "[00:02.00] SYNCED LRC LINE TWO\n"
    "[00:04.00] SYNCED LRC LINE THREE"
)

SYLT_DATA: list[tuple[str, int]] = [
    ("SYNCED SYLT LINE ONE", 0),
    ("SYNCED SYLT LINE TWO", 2000),
    ("SYNCED SYLT LINE THREE", 4000),
]


CONFIGS: dict[str, dict] = {
    "A_uslt_lrc":        {"uslt": SYNCED_LRC},
    "B_uslt_plain":      {"uslt": PLAIN},
    "C_txxx_unsynced":   {"txxx_unsynced": PLAIN},
    "D_txxx_lyrics":     {"txxx_lyrics": SYNCED_LRC},
    "E_sylt_only":       {"sylt": True},
    "F_uslt_lrc_sylt":   {"uslt": SYNCED_LRC, "sylt": True},
    "G_uslt_lrc_txxx":   {"uslt": SYNCED_LRC, "txxx_unsynced": PLAIN},
}


def _make_mp3(path: Path) -> None:
    """Generate an 8-second soft sine tone MP3."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=8",
            "-q:a", "9", "-acodec", "libmp3lame",
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def _write_tags(path: Path, config: dict) -> None:
    tags = ID3()
    if "uslt" in config:
        tags["USLT"] = USLT(encoding=3, lang="eng", desc="", text=config["uslt"])
    if "sylt" in config:
        tags["SYLT"] = SYLT(
            encoding=3, lang="eng", format=2, type=1, text=SYLT_DATA,
        )
    if "txxx_lyrics" in config:
        tags.add(TXXX(encoding=3, desc="LYRICS", text=config["txxx_lyrics"]))
    if "txxx_unsynced" in config:
        tags.add(TXXX(encoding=3, desc="UNSYNCEDLYRICS", text=config["txxx_unsynced"]))
    tags.save(path, v2_version=4)


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./mp3-lyrics-test")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating test files in: {out_dir.absolute()}\n")
    for name, config in CONFIGS.items():
        path = out_dir / f"{name}.mp3"
        _make_mp3(path)
        _write_tags(path, config)
        tag_names = ", ".join(sorted(config.keys()))
        print(f"  {name}.mp3   [{tag_names}]")

    print(f"\n{len(CONFIGS)} files generated.")
    print()
    print("Next steps:")
    print("  1. Copy this directory to your phone's Music folder:")
    print(f"       cp -r {out_dir} /storage/emulated/0/Music/")
    print("     (or use any file-transfer method; Musicolet scans the")
    print("      standard Music directory.)")
    print("  2. Open each file in Musicolet.")
    print("  3. Fill in the results table:")
    print()
    print("     ┌───────────────────────┬───────────┬────────┐")
    print("     │ File                  │ Lyrics?   │ Synced?│")
    print("     ├───────────────────────┼───────────┼────────┤")
    for name in CONFIGS:
        print(f"     │ {name}.mp3{' ' * (20 - len(name))}│           │        │")
    print("     └───────────────────────┴───────────┴────────┘")
    print()
    print("  Report the results — we pick the implementation based on")
    print("  which combination actually displays in your player.")


if __name__ == "__main__":
    main()
