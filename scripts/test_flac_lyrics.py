#!/usr/bin/env python3
# scripts/test_flac_lyrics.py
"""
FLAC counterpart to test_mp3_lyrics.py.

FLAC uses Vorbis Comments, not ID3 frames. The candidate tags are:

    LYRICS            — most widely read, typically plain
    UNSYNCEDLYRICS    — plain, read by most players
    SYNCEDLYRICS      — synced LRC, read by foobar2000/MusicBee
    SYNCEDLYRICS_LRC  — some tools use this variant

Test whether Musicolet parses LRC in LYRICS, or only shows static
text, or requires SYNCEDLYRICS specifically. Distinct lyric strings
per file so the tester can identify which tag was read.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from mutagen.flac import FLAC


PLAIN = "PLAIN LINE ONE\nPLAIN LINE TWO\nPLAIN LINE THREE"
SYNCED_LRC = (
    "[00:00.00] SYNCED LRC LINE ONE\n"
    "[00:02.00] SYNCED LRC LINE TWO\n"
    "[00:04.00] SYNCED LRC LINE THREE"
)
SYNCED_LRC_ONLY = SYNCED_LRC  # alias for clarity in config below


CONFIGS: dict[str, dict] = {
    # tag map: {vorbis_key: value}
    "H_lyrics_lrc":         {"LYRICS": SYNCED_LRC},
    "I_lyrics_plain":       {"LYRICS": PLAIN},
    "J_unsynced_plain":     {"UNSYNCEDLYRICS": PLAIN},
    "K_lyrics_and_unsynced":{"LYRICS": SYNCED_LRC, "UNSYNCEDLYRICS": PLAIN},
    "L_syncedlyrics_only":  {"SYNCEDLYRICS": SYNCED_LRC},
    "M_lyrics_and_synced":  {"LYRICS": SYNCED_LRC, "SYNCEDLYRICS": SYNCED_LRC},
    "N_all_three":          {
        "LYRICS": SYNCED_LRC,
        "UNSYNCEDLYRICS": PLAIN,
        "SYNCEDLYRICS": SYNCED_LRC,
    },
}


def _make_flac(path: Path) -> None:
    """Generate an 8-second FLAC."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=8",
            "-c:a", "flac", "-compression_level", "0",
            str(path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def _write_tags(path: Path, config: dict) -> None:
    audio = FLAC(path)
    audio.clear()
    for key, value in config.items():
        audio[key] = value
    audio.save()


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./flac-lyrics-test")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating FLAC test files in: {out_dir.absolute()}\n")
    for name, config in CONFIGS.items():
        path = out_dir / f"{name}.flac"
        _make_flac(path)
        _write_tags(path, config)
        tags = ", ".join(sorted(config.keys()))
        print(f"  {name}.flac   [{tags}]")

    print(f"\n{len(CONFIGS)} files generated.\n")
    print(f"  cp -r {out_dir} /storage/emulated/0/Music/")
    print()
    print("  ┌─────────────────────────┬───────────┬────────┐")
    print("  │ File                    │ Lyrics?   │ Synced?│")
    print("  ├─────────────────────────┼───────────┼────────┤")
    for name in CONFIGS:
        print(f"  │ {name}.flac{' ' * (22 - len(name))}│           │        │")
    print("  └─────────────────────────┴───────────┴────────┘")


if __name__ == "__main__":
    main()
