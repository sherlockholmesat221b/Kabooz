# Changelog

## 0.2.0

### Breaking changes

- **`-j` / `--workers` removed.** Documented as a concurrency control
  but was silently a no-op in every download command since v0.1.0.
  Passing `-j` now errors with "no such option". Use `-x N` /
  `--connections N` for byte-range parallelism within one file, or
  `download.connections_per_track` in config.
- **Synced lyrics moved to `LYRICS` (FLAC) / `USLT` (MP3).** Most
  players read those tags; `SYNCEDLYRICS` / `SYLT` were largely
  ignored by players in practice. To restore v0.1.0 behaviour, set
  `tagging.flac_synced_lyrics = "synced"` and/or
  `tagging.mp3_sylt = "synced"` in config.
- **Cover art embed and sidecar swapped.** Embedded art is now
  600x600 (~150 KB) instead of up to 3+ MB. `cover.jpg` now holds
  the full-resolution image. Configurable via
  `tagging.embed_cover_size` / `tagging.sidecar_cover_size`.

### Added

- `kabooz url <id>` — resolve a track to its CDN stream URL.
  `--json` for JSON output, `--field NAME[,NAME...]` for selected
  fields, `--report` to opt in to Qobuz reporting. Off by default
  so `kabooz url | xargs curl` in scripts does not create false
  play events in Qobuz analytics.
- Ranged download: `--start`, `--end`, `--disc` on `album`,
  `playlist`, and `artist`. 1-based inclusive indices. See
  `kabooz album --help`.
- Chunked (byte-range parallel) downloads: `-x N` on all download
  commands, or `download.connections_per_track` in config. Parallel
  chunks within one file (aria2c / yt-dlp semantics), not parallel
  files. Falls back to single-connection if the server does not
  support HTTP Range.
- Rate limiting: `download.rate_limit_kbps` (kilobits/sec,
  0 = unlimited). 8000 kbps = 1 MB/s = 8 Mbps.
- `{track_all}` template placeholder — continuous track number
  across all discs (1..N). Useful for flat folder layouts without
  `{disc}/` on multidisc albums.
- Qobuz internal IDs in tags: `QOBUZ_TRACK_ID`, `QOBUZ_ALBUM_ID`,
  `QOBUZ_ARTIST_ID` on both FLAC and MP3. `UPC` written to MP3
  (FLAC already had it). Not added to the QOBUZ_* namespace — UPC
  is a product barcode, not a Qobuz identifier.
- Optional FLAC MD5 fix: `download.fix_flac_md5` (default off).
  Recomputes the STREAMINFO MD5 after tagging by decoding audio
  and hashing the PCM stream. Requires `flac >= 1.4.0`.
- Configurable cover art size tiers: `tagging.embed_cover_size`,
  `tagging.sidecar_cover_size`. Values: thumbnail | small | large
  | original.
- Per-tag lyrics control. Six independent fields:
  `tagging.flac_lyrics`, `tagging.flac_unsynced_lyrics`,
  `tagging.flac_synced_lyrics`, `tagging.mp3_uslt`,
  `tagging.mp3_txxx_unsynced`, `tagging.mp3_sylt`.
  Values: synced | plain | best | none.
- `tagging.save_lrc_file` — write a .lrc sidecar alongside each
  audio file when synced lyrics are available.

### Fixed

- `download.max_retries` was silently ignored. The field existed in
  `DownloadConfig` and `validate_config` but `load_config` never
  read it from the TOML file — every download used the hardcoded
  default of 2. Now respected.
- `{disc}` template segment no longer creates a pointless `Disc 1/`
  folder for monodisc albums. The segment is dropped entirely when
  `media_count <= 1`.
- Classical track titles no longer duplicate the work prefix
  ("Symphony No. 6 in A Minor - Mahler: Symphony No. 6 in A
  Minor: ..." now correctly rendered once).
- MusicBrainz User-Agent corrected; WAF-rejected requests no
  longer fail silently.
- MusicBrainz total-failure now surfaces a warning instead of
  remaining silent outside --dev mode.
- TUI crash on classical albums ('TrackSummary' object has no
  attribute 'performer').
- TUI search was broken (called `.get()` on a dataclass).
- Invalid Request Signature errors now raise a specific
  `SignatureError` with an actionable message.

### Internal

- `kabooz/session.py` (1,500 lines) split into 10 focused mixin
  modules under `kabooz/session/`. Public API unchanged.
- `kabooz/cli.py` (1,000 lines) split into 12 focused modules
  under `kabooz/cli/`. Public API unchanged.
- `pytest` integration test marker added. Opt in with
  `pytest -m integration`. Default `pytest` stays fast and hermetic.
- Lazy imports for tagger, musicbrainz, lyrics; lazy LocalStore
  construction. Small startup win for commands that do not touch
  the tagging pipeline or local database.
- CI publishes to PyPI and creates a GitHub release on tag push.
