# DEV LOGS  

This file records logs written by the developer for future reference 
(self or collaborators). This is NOT user documentation; it exists 
purely for developer reference. Entries may be incomplete, outdated, 
or inaccurate.

## Format  
1. An entry should be made every session.
   A session usually corresponds to a single day.
2. All dates must be in UTC. Mentioning time is discouraged; if used, it must also be in UTC.
3. This file should be updated in the last commit of a session, and should be omitted in **Commits Made** list.
4. A single session entry must follow this format:

    ### YYYY-MM-DD  
    **Author**: [Your name / alias]  
    **Commits Made**: commit list or range  

    - Use bullet points.
    - Use explicit sub-headings (####) such as:
      - TODO
      - DONE 
      - NOTES
      - BUGS
      - IDEAS

---


### 2026-03-17
**Author**: [TchaikovskyCannonsAPI]
**Commits Made**: 6a88b36..c477381
#### DONE
- [x] Lets leave it, cuz it would be soo long
- [x] Fixed dev.py to be better in dev audio integrity. We don't wanna loose the rick roll in any case.
- [x] Made cover.jpg for singles copy the track file name instead of cover.jog
#### BUGS
- When downloading MP3, the template adds this in the folder name `Billie Jean [FLAC 16bit 44.1kHz] [2026]`
- When running TUI curses, and clicking on Mozart's Don Giovanni album by Carlo ... remastered 2016, it returns the error ` Overture  [24bit/96kHz] Philharmonia Orchestra  —  Mozart : Don Giovanni (2016 Remastered) █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0:18 / 6:18 ⏸ PAUSED  space=pause  n=next  p=prev  r=radio  [/]=vol 100%  ←/→=±10s  q=quit Loading: Mozart : Don Giovanni (2016 Remastered)… [DEV] GET /album/get params=['album_id', 'limit', 'offset'] → fetching…                                                                                                                          [DEV] GET /album/get params=['album_id', 'limit', 'offset'] → fetching…                [DEV] GET /album/get → HTTP 200 (cached) ✗ Load error: 'TrackSummary' object has no attribute 'performer' [DEV] GET /album/get → HTTP 200 (cached)`


---


### 2026-11-03
**Author**: [sherlockholmesat221b]
**Commits Made**: 214f9c1..cb219a7

#### DONE

- [x] **Issue #2 — `Disc {disc}/` folder created for monodisc albums.**
      Template segments containing `{disc}` are dropped when
      `album.media_count <= 1` or `album is None`. `{disc}` stays a
      plain integer. Auto path untouched — verified byte-for-byte
      identical. Root cause: `_build_context` set
      `"disc": track.media_number or 1` unconditionally; the template
      renderer had no equivalent of the `is_multi_disc` gate.

- [x] **`{track_all}` placeholder.** Continuous cross-disc track
      position. For monodisc equals `{track}`; for a 3-disc set with
      12 tracks on disc 1, disc 2 track 1 is `{track_all}` = `13`.
      Falls back to `track_number` when `album is None`. Registered
      in `_KNOWN_PLACEHOLDERS`.

- [x] **MusicBrainz User-Agent fix.** `kabooz/0.1 ( https://gitlab.com/kabooz )`
      → `Kabooz/0.1.0 ( https://github.com/sherlockholmesat221b/Kabooz )`.
      MB's WAF returns `403` for non-conforming UAs (confirmed:
      literal string `test` is rejected).

- [x] **Surface total MusicBrainz failure.** `AlbumDownloadResult`
      tracks `mb_attempted` / `mb_succeeded`. `cli.album` warns when
      every lookup returns nothing.

- [x] **Pre-existing stale test fix.**
      `test_load_playlist_magic_comment_stripped` asserted the old
      `# qobuz-playlist v1` header. Code writes `# kabooz-playlist v1`.

- [x] **`work` prefix dedupe.** `Track.display_title` no longer
      prepends `work` when `work.lower()` is already in
      `title.lower()`. Fixes doubled classical titles like
      `"Symphony No. 6 in A Minor - Mahler: Symphony No. 6 in A Minor: …"`.
      Commit: 4696c4c.

- [x] **Issue #3 — retry on `httpx.TransportError`.**
      `Downloader.max_retries` (default 2 = 3 attempts), immediate,
      uses `Range` to resume from `.part` each attempt.
      `_download_to_path` / `_stream_to_part` and
      `_download_goodie_to_path` / `_stream_goodie` split so retry
      wrapper and streaming loop are distinct. `_stream_*` reads
      `part_size`/`existing_size` fresh per attempt so transient HEAD
      failure on retry does not truncate. New
      `download.max_retries` config (0–10). Rationale for no backoff:
      transient peer resets need fast retry, not sleep; persistent
      failures escalate via `.part` resume across runs. Commit: 2809bea.

- [x] **Issue #1A — signature diagnostics.**
      `SignatureError(APIError)` raised on
      `"Invalid Request Signature"`, message points at `--app-secret`
      and clock check. `_sign_track_url_request` logs masked canonical
      string + timestamp in `--dev`.
      `_canonical_signature_string` extracted as module helper, locked
      in unit test. Confirmed against live API — canonical string and
      MD5 match qobuz-dl exactly. The failure mode is almost certainly
      a stale `app_secret` or clock skew, not a code bug — Issue #1B
      deferred until reproduced. Commit: c1298b6.

- [x] **TUI strategy: Textual shelved.**
      `tui_curses.py` is the supported, dependency-free TUI.
      `tui.py` marked EXPERIMENTAL in docstring;
      `docs/architecture.md` updated. Textual is not a shipped
      dependency and its async worker model produced bugs difficult
      to fix without local debugging. A full terminal player (audio
      engine, cover art rendering, edge cases) is a separate project.
      Commits: 76e84ce, a0fd83d, 186130f.

- [x] **TUI `TrackSummary` crash and search parsing.**
      `TrackSummary.artist_or()` / `Track.artist_or()` added;
      `SearchResults` attribute access replaces `.get()` in both
      TUI files. `tui_curses.py` verified end-to-end. `tui.py` search
      remains non-functional for a Textual-specific reason, out of
      scope.

- [x] **Feature #1 — Qobuz IDs in tagged metadata.**
      `QOBUZ_TRACK_ID`, `QOBUZ_ALBUM_ID`, `QOBUZ_ARTIST_ID` written
      to FLAC Vorbis Comments and MP3 TXXX frames. UPC is not a Qobuz
      ID — FLAC keeps its existing `UPC` tag; MP3 gains `TXXX:UPC`.
      Both `QOBUZ_ALBUM_ID` and `UPC` written even when values
      coincide. Standalone tracks (`album=None`) get TRACK_ID and
      ARTIST_ID only. Commit: bf8c380.

- [x] **Feature #4 — cover art embed/save swap.**
      Embedded art is now `img.large` (600px, ~150 KB) instead of
      `img.original` (`_org.jpg`, up to 3+ MB). Sidecar `cover.jpg` /
      `<track_stem>.jpg` is now `img.original` (archival). Verified
      on Mahler: embedded picture 141 KB (was 3.6 MB), sidecar 3.6 MB
      (was 150 KB). Commit: cb219a7.

#### NOTES

- **MusicBrainz — three-layer failure, fully characterised.**
  Four independent clients (`curl` TLS 1.2, `curl` TLS 1.3, `httpx`,
  `urllib`) on mobile data all fail at the TLS handshake with
  `UNEXPECTED_EOF_WHILE_READING`. Two different TLS versions, one
  failure signature → the blocker is not code, OpenSSL, or UA. It is
  a network-level filter to `musicbrainz.org` (very likely carrier
  DPI). On VPN the handshake succeeds; with correct UA, MB returns
  `404` for ISRCs it lacks and `200` with tags for ISRCs it has.
  Full Mahler 8-track run: `mb_attempted=8, mb_succeeded=4`.
  **Conclusion: the Kabooz MB code was correct all along.** The only
  fixable defects were UA and silent failure. Both fixed.

- **`{disc}` investigation.** Reproduced on Mahler (media_count=1),
  Don Giovanni (media_count=1), Disintegration Deluxe (media_count=3).
  Post-fix: monodisc has no `Disc/` folder; multidisc retains
  `Disc 1/`, `Disc 2/`, `Disc 3/`.

- **`_compute_track_all` design.** Lives in `download/naming.py`, not
  `models/track.py`, because it needs the album's full track list to
  sum prior discs.

- **Qobuz album ID sometimes equals UPC.** Confirmed on this
  session's downloads: Mahler 6 / Haitink `id == upc == "0002894830800"`;
  Disintegration Deluxe `id == upc == "0060075324566"`. Qobuz uses
  the UPC as album ID for releases without internal catalog numbers.
  Convention is inconsistent. Design: both tags written even when
  values coincide — they carry different meaning.

- **Qobuz album cover CDN pattern (observed, not relied upon).**
  Covers served at
  `https://static.qobuz.com/images/covers/{last2}/{prev2}/{id}_{size}.jpg`
  where `last2`/`prev2` are the last two and previous two characters
  of the album ID. Verified on all four albums used in this session.
  Not used in code — API's `image` object is primary source. Could be
  useful for a future library-store cover renderer or as a test-fixture
  helper. Does NOT apply to playlists (flat `images: list[str]`) or
  artists (single URL).


### 2026-11-04
**Author**: [sherlockholmesat221b]
**Commits Made**: 5fba195..75d5c7e

#### DONE

- [x] **Feature #3 — per-tag lyric mapping.**
      Six independent fields replace the originally proposed
      `synced_tag` preset: `flac_lyrics`, `flac_unsynced_lyrics`,
      `flac_synced_lyrics`, `mp3_uslt`, `mp3_txxx_unsynced`,
      `mp3_sylt`. Values: `synced` | `plain` | `best` | `none`
      (`mp3_sylt`: `synced` | `none` only — binary frame cannot
      carry plain). Users construct behaviour from primitives rather
      than choosing from presets. `save_lrc_file` writes
      `<audio_stem>.lrc` sidecar when synced lyrics are available.
      Commit: 5fba195.

- [x] **Feature #5 partial — cover art size tiers.**
      Added `embed_cover_size` and `sidecar_cover_size` config fields
      (`thumbnail` | `small` | `large` | `original`, matching Qobuz
      CDN tiers). New `Image.url_for_size()` helper with per-tier
      fallback (missing tier falls back to large, then small). CLI
      flags `--cover-size` and `--save-cover-size` on track, album,
      playlist, artist, favorites, purchases, and lpl download.
      Verified: `--cover-size small` embeds 15 KB (was 150 KB),
      `--save-cover-size large` writes 65 KB sidecar (was 3 MB),
      `--cover-size bogus` exits with clear error before download.
      Commit: 75d5c7e.

#### NOTES

- **Musicolet lyric tag testing — 14 test files across FLAC and MP3.
  Critical findings that changed the design:**

  FLAC (Vorbis Comments):
  - `LYRICS=LRC` only → synced ✓
  - `LYRICS=LRC` + `UNSYNCEDLYRICS=plain` → **static ✗**
    (`UNSYNCEDLYRICS` overrides `LYRICS`, breaking LRC parsing)
  - `LYRICS=LRC` + `SYNCEDLYRICS=LRC` → synced ✓
  - `SYNCEDLYRICS` only → nothing

  MP3 (ID3):
  - `USLT=LRC` only → synced ✓
  - `SYLT` only → nothing
  - `TXXX:UNSYNCEDLYRICS` only → nothing
  - `TXXX:LYRICS` only → nothing

  **Design consequences:**
  - `UNSYNCEDLYRICS` / `TXXX:UNSYNCEDLYRICS` are **never written**
    in any mode — writing them alongside `LYRICS=LRC` breaks synced
    display in Musicolet.
  - `SYNCEDLYRICS` / `SYLT` / `TXXX` variants are opt-in only, kept
    for players that specifically read them (foobar2000, MusicBee).
  - Defaults: `flac_lyrics=best`, `mp3_uslt=best`, all others
    `none` — Musicolet-compatible, constructed from primitives.
  - Verified end-to-end: Lovesong (The Cure) with `--lyrics` wrote
    `LYRICS=[00:28.08] Whenever I'm alone with you` (only), scrolls
    in Musicolet.

  Test scripts preserved at `scripts/test_flac_lyrics.py` and
  `scripts/test_mp3_lyrics.py` for re-running if a player updates.

- **Feature #5 cover size empirical verification.**
  `--cover-size small` → `_230.jpg` fetched, embedded `length: 15331`.
  `--save-cover-size large` → `_600.jpg` fetched, sidecar 65,473 bytes.
  `--cover-size bogus` → exits with `Invalid cover size: 'bogus'.
  Valid: large, original, small, thumbnail`.

- **Feature #5 refined design rule.** Flags for per-download toggles
  users may want to vary between runs (`--cover`, `--save-cover`,
  `--lyrics`, `--cover-size`, `--save-cover-size`). Config for
  collection-wide knobs (`flac_lyrics`, `mp3_sylt`, tag mappings
  generally). Only the size fields got flags; the six lyric tag
  mappings stayed config-only.

- **Session spanned two UTC days.** Commits from Nov 3 UTC through
  Nov 4 UTC are documented across two entries per the format rule
  ("an entry should be made every session" — session started Nov 3
  but continued past UTC midnight). The split point is between
  `cb219a7` (Nov 3 19:48 UTC) and `5fba195` (Nov 4 07:09 UTC).

- **Manual editing difficulties with session.py and cli.py.** During
  feature #5, `nano` on 1,500-line `session.py` produced partial or
  reverted edits multiple times — parameter additions lost, signatures
  duplicated, calls mangled. Recovery required a `git checkout` and
  two Python extraction scripts (`fix_session.py`, `fix_cli.py`) that
  asserted each anchor matched exactly once and aborted atomically on
  any mismatch. This is the direct motivation for the split TODO
  below.

#### BUGS

Open bugs remaining. All pre-existing from v0.1.0; none introduced
this session.

- **`max_workers` / `-j` is a no-op for all CLI download commands.**
  `session.download_album`, `download_playlist`,
  `download_artist_discography`, `download_favorites`,
  `download_purchases` each run their own sequential loop and never
  use `Downloader.download_album` (the only place that reads
  `self._max_workers`). `download.max_workers = 8` has no observable
  effect. `README.md` advertises parallel downloads — currently
  false. Larger fix, needs threading-safety review for mutagen writes.

- **`lookup_isrc` logs 404 as `error`.** Cosmetic. A `404 Not Found`
  from MusicBrainz means "no coverage", not "error". Only visible in
  `--dev` mode. Fix: distinguish `httpx.HTTPStatusError` with
  `status_code == 404` from other exceptions in the log message.

- **Network TLS block for `musicbrainz.org` on mobile data.**
  Not a Kabooz bug — confirmed at four client layers. Users on
  mobile without VPN will not get MB enrichment. VPN resolves it.

#### TODO

- [ ] **Refactor: split session.py and cli.py.** (elevated priority)

      session.py ~1,500 lines, cli.py ~1,000. Both became painful to
      edit this session — nano struggles with files this size,
      multi-site edits end up reverted or partial, verifying state
      requires grep after every change.

      Split session into mixins under `kabooz/session/`:
        _core.py     — __init__, from_config, resolve_id, resolve_quality
        downloads.py — download_*, _post_download, _save_cover_file,
                       _finalise
        catalog.py   — get_/search/iter_ methods
        streaming.py — prepare_stream, report_stream_*, _StreamReporter
        favorites.py — add/remove_favorite, sync_favorites
        playlists.py — clone/share/import + remote playlist methods
        account.py   — get/update_profile, change_password
        discovery.py — new_releases, featured, genres, radios, recs
        backup.py    — backup, export/import, restore

      Split cli.py into `kabooz/cli/` (one module per command group,
      Typer sub-apps wired in __init__.py).

      Public API unchanged. QobuzSession remains the single
      composition point. Users see no difference.

      Trigger: before feature #7 (ranged download — will touch
      download_album, download_playlist, download_artist_discography
      in session.py). Est. 2–3 hr. Use extraction scripts (Python
      read/split/write with per-anchor assertions), not nano.

- [ ] **Man page for kabooz.**
      Hand-written roff at `docs/man/kabooz.1`. Install script
      `scripts/install-man.sh` copies to `$PREFIX/share/man/man1/`
      (Termux) / `$(brew --prefix)/share/man/man1/` (macOS) /
      `/usr/local/share/man/man1/` (Linux). Wheel includes the man
      file; user runs the script once. `man kabooz` then works.

      Not auto-installed on `pip install` (would need root and be
      rude). Sequence: **after the session.py/cli.py split**, so the
      man page reflects the final CLI structure — no rework. Est.
      ~2 hr (man pages are hand-authored for good reason).

- [ ] **Issue #1B — `--refresh-secret` credential scraper.**
      Fetch the current Qobuz web-player `app_id` / `app_secret` from
      `play.qobuz.com`. Adapted from
      `QobuzDL/Qobuz-AppID-Secret-Tool/main.py` (uses `aiohttp`);
      port to `httpx` for consistency. Wire `--refresh-secret` into
      `kabooz login`. Fallback: prompt for manual `--app-secret`.
      **Deferred until Issue #1 reproduces** — the `--dev` signing
      log shipped in #1A will tell us whether it is stale secret or
      something else.

- [ ] **Consider** changing the default `naming.album` template to
      include `Disc {disc}/`:
      `"{albumartist}/{album} [{quality}] [{year}]/Disc {disc}/{track:02d}. {title}"`.
      Safe now that the `{disc}` segment is dropped for monodisc.
      Changes default for new users only. Deferred.

- [ ] **Cosmetic** — quiet first-run ffmpeg in `dev.py` with
      `-hide_banner -loglevel error`.

- [ ] **Cosmetic** — split `lookup_isrc`'s 404 case into a distinct
      dev log message.

#### IDEAS

- Cache album-level cover art between tracks within a single
  `download_album` run. Currently re-downloads the cover art per
  track when `--cover` is used. 14-track album = 14 identical HTTP
  GETs to the CDN. Low-impact on wired networks, noticeable on mobile.

#### FEATURES

Seven feature requests. Four done (#1, #3, #4 fully; #5 partially).
Remaining below.

- [ ] **#7: Ranged album/playlist download.**
      Two-tier syntax, unambiguous:
      ```bash
      # Global indices (1-based, inclusive)
      kabooz album <id> --start 3 --end 5
      kabooz album <id> --start 10

      # Per-disc
      kabooz album <id> --disc 2
      kabooz album <id> --disc 2 --start 3 --end 5

      # Playlists (no --disc)
      kabooz playlist <id> --start 50 --end 100
      ```
      Rules:
      · `--start`/`--end` are 1-based, inclusive.
      · Default `--start=1`, `--end=∞`.
      · `--disc N` alone — all tracks of disc N.
      · `--disc` given — `--start/--end` are per-disc indices.
      · `--disc` omitted — `--start/--end` are global indices.
      · `--disc` on a playlist — error, playlists have no disc
        structure.
      Files: `cli.py`, `session.py` (or their split successors).
      Effort: 1–2 hr on split files.

- [ ] **#2: Stream URL command.**
      ```bash
      kabooz url <track_id>                 # bare URL to stdout
      kabooz url <track_id> --json          # all fields
      kabooz url <track_id> --field url     # one field
      kabooz url <track_id> -q cd --report  # opt into reporting
      ```
      Design:
      · **Stream reporting OFF by default.** `--report` opts in.
        Rationale: `kabooz url … | xargs curl` in a script must not
        create false play events for Qobuz analytics.
      · Fast path (bare URL) resolves nothing beyond `get_track_url`.
      · All flags opt-in. Default output is one line.
      Files: `cli.py`, `session.py`. Effort: 1–2 hr.

- [ ] **#6: FLAC MD5 fix.**
      Qobuz zeroes the MD5 in STREAMINFO for downloaded FLACs.
      `metaflac --set-md5sum <file>` recomputes from decoded audio
      without re-encoding, ~1–2 s per hi-res track.
      **Requires `flac >= 1.4.0`.** Detect at startup, skip with
      one-line warning if absent. **No re-encode fallback** (`flac -0`)
      — rejected explicitly; users who want re-encode use
      `external_processor` from #5.
      NOTE: recomputed MD5 verifies local copy is intact at rest,
      not that it matches Qobuz's source (likely transcoded before
      delivery — hence the zeroed MD5).
      Config: `download.fix_flac_md5 = false` (default off).
      Files: `downloader.py`, `config.py`. Effort: 1–2 hr.

- [ ] **#5 remaining: config discipline + post-processing hooks.**
      · Quality fine-tuning — constrain maximum bit depth / sample
        rate (e.g. `download.max_bit_depth = 24`)
      · `external_processor` shell hook — runs **after** tagging,
        like `external_downloader` runs **instead of** downloading.
        Template: `"flac -0 --force {file}"` for re-encode, or
        anything a power user wants.
      · Audit of existing per-command overrides for tag/cover/lyrics
        flags; fill gaps.
      Files: `config.py`, `downloader.py`, `session.py`, `cli.py`.
      Effort: ongoing, per sub-feature.

- **Recommended order:** #7 → #2 → #6 → #5 remaining.
  · #7 and #2 both add CLI commands and touch the download path.
  · #6 is a single downloader hook.
  · #5 remaining is iterative.

### 2026-11-04 (addendum — feature #7 complete)

**Author**: [sherlockholmesat221b]
**Commits Made**: 03b7053..bfedada

#### DONE

- [x] **Feature #7 — ranged album/playlist/artist download.**
      Three new flags on album, playlist, and artist commands:
      - --start N / --end M — 1-based inclusive indices
      - --disc N — filter to a single disc (album only)
      - --no-warnings — suppress harmless range warnings

      Semantics:
      - Album without --disc: global track indices across the album
      - Album with --disc N: per-disc indices within disc N
      - Playlist: 1-based over playlist positions; {index} template
        preserves original positions in partial downloads
      - Artist: 1-based over the release list, NOT tracks

      Implementation:
      - _slice_range(items, *, start, end, disc, warnings_out) helper
        in session/downloads.py — pure function, tested in isolation
        in tests/test_session_downloads.py (19 cases)
      - Wired into download_album, download_playlist,
        download_artist_discography; on_warning callback threaded
        through from CLI to session
      - CLI validates via session-layer ValueError; displays
        "Invalid range: <detail>" before any API call

      Error rules (boring and predictable):
      - Empty result: ValueError with specific message
      - start > available count: error
      - end < start: error
      - end > available count: clamped silently, warns
      - disc 1 on monodisc album: valid, warns (no-op)
      - disc 2+ on monodisc album: error

      Warnings printed to stderr with "warning:" prefix, never stdout
      — piping output is safe. --no-warnings suppresses.

#### NOTES

- **Verification on real album** (Disintegration Deluxe, 3 discs,
  44 tracks):
      kabooz album 0060075324566 --disc 5
        → Invalid range: Cannot download album: disc 5 not found
      kabooz album 0060075324566 --end 999
        → warning: end=999 exceeded available count (44); using 44
      kabooz album 0060075324566 --end 999 --no-warnings
        → no warning printed
      kabooz --dev album 0060075324566 --disc 2 --start 1 --end 3
        → exactly 3 tracks from disc 2

- **Redundant prefix in error message.** The CLI prints
  "Invalid range: {exc}" where exc already includes
  "Cannot download album: disc N not found". Result is doubled
  context. Cosmetic — noted as a future cleanup: either strip the
  session-layer prefix or make the CLI print raw ValueError text.
  Not blocking.

- **Favorites / purchases ranged download deferred.** Two branches
  each (tracks vs albums) with different range-unit semantics.
  Doing it half-right would be worse than not doing it. The
  _slice_range helper is now in place; wiring favorites/purchases
  in later is small. Revisit if requested.

- **Artist range is over releases, not tracks.** Intentionally
  different from album's track range. Documented in --help and
  docs/cli.md.

- **Session split and CLI split complete.** This session also
  refactored session.py (1,500 lines → 10 mixin modules) and
  cli.py (1,000 lines → 12 modules). Feature #7 was the first
  work landed against the split codebase — the file-level
  isolation paid off, edits stayed small.

#### BUGS

No new bugs from feature #7.

Pre-existing, unchanged from the previous DEVLOG entry:
- max_workers / -j is a no-op for all CLI download commands
- lookup_isrc logs 404 as error
- Network TLS block for musicbrainz.org on mobile data (not Kabooz)

#### TODO

- [ ] Cosmetic: redundant "Invalid range: Cannot download X:" prefix
      in feature #7 error messages. Strip session-layer context from
      the ValueError message, OR have CLI print raw exc.
- [ ] Favorites / purchases ranged download. Deferred from feature #7.
- [ ] max_workers no-op fix. Larger change, needs threading review.
- [ ] Refactor: split client.py if editing becomes painful — not
      currently needed (untouched since v0.1.0).
- [ ] Man page for kabooz (after splits — both done, so this can
      proceed whenever).

#### FEATURES

Remaining from the original seven-feature queue:
- #2 stream URL command — not started
- #6 FLAC MD5 fix via metaflac --set-md5sum — not started
- #5 remaining: quality fine-tuning, external_processor hook

Completed: #1, #3, #4, #7, and #5 partial (cover art sizes).

### 2026-11-04
**Author**: [sherlockholmesat221b]
**Commits Made**: c0a65b5..22fe967

#### DONE

**Structural refactors (session split)**

- [x] **session.py split into a package.** Original 1,500-line
      monolith converted to 10 focused modules under
      kabooz/session/: \_types, downloads, catalog, streaming,
      favorites, playlists, account, discovery, backup, plus a thin
      \_\_init\_\_.py that composes them as mixins on QobuzSession.
      Each extraction was a script-driven byte-preserving move with
      pytest verification. Public import path unchanged: from
      kabooz.session import QobuzSession works identically.

- [x] **cli.py split into a package.** 1,000-line monolith
      converted to kabooz/cli/ with 12 modules: \_app (Typer app
      instances + shared state), helpers (console + utilities),
      downloads, info, auth, search, library, lpl, account, remote,
      export, plus \_\_init\_\_.py for the main callback and command
      registration. Same pattern; same verification.

**Feature #7 — ranged album/playlist/artist download**

- [x] `_slice_range(items, *, start=1, end=None, disc=None,
      warnings_out=None)` helper in session/downloads.py. Pure
      function, 19 tests in tests/test_session_downloads.py.

- [x] Wired into `download_album`, `download_playlist`, and
      `download_artist_discography`. on_warning callback threaded
      from CLI to session; warnings go to stderr.

- [x] CLI flags: `--start`, `--end`, `--disc` (album only),
      `--no-warnings` on album / playlist / artist.

- [x] Error rules: empty result → ValueError with specific message;
      start > available → error; end < start → error; end > available
      → clamped silently + warning; disc 1 on monodisc → warning (no-op);
      disc 2+ on monodisc → error.

- [x] Verified on real album (Disintegration Deluxe, 3 discs, 44
      tracks): --disc 5 errors, --end 999 warns then clamps,
      --disc 2 --start 1 --end 3 downloads exactly 3 tracks from disc 2.

**Feature #2 — stream URL command**

- [x] `StreamingMixin.resolve_stream(track_id, quality, report=False)`
      in session/streaming.py. Silent by default. report=True opts
      in to Qobuz reportStreamingStart.

- [x] `kabooz url <id>` command in cli/downloads.py.
      - Bare URL is default output (1 API call)
      - `--json` changes format only, not content
      - `--field NAME` (comma-separated) selects content:
        URL-only fields (1 call) or metadata fields (2 calls)
      - `--report` opts in to Qobuz reporting; off by default so
        scripted `kabooz url | xargs curl` does not pollute analytics

- [x] Verified: bare URL, `--json` (url only), `--field bit_depth`
      (16), `--field url,bit_depth` (two lines), `--field
      url,title --json` (JSON object), `--report` (silent success),
      `--field bogus` (error with field list).

**Feature #6 — FLAC MD5 fix (two attempts)**

- [x] **Attempt 1 (77d3c73, reverted):** called
      `metaflac --set-md5sum <path>` — WRONG. That flag *writes* an
      MD5 you supply; it does not *compute* one. The command failed
      every time. Mocked unit tests passed because they asserted only
      `returncode`, not the argv. Discovered via real download: MD5
      came back all zeros.

- [x] **Reverted (49ff1d6, 9417e34).**

- [x] **Salvaged max_retries load_config regression (b38115a).**
      Feature #3 added `max_retries` to DownloadConfig and
      validate_config, but never wired the corresponding
      `d.get("max_retries", ...)` call in load_config. Users
      setting `download.max_retries=N` in config.toml were silently
      ignored (always defaulted to 2). One-line fix + regression
      test in tests/test_downloader.py.

- [x] **Attempt 2 (f97b4a3, correct):** `flac -ds --stdout ... |
      hashlib.md5 | metaflac --set-md5sum=<hash>`. Fail-fast
      ConfigError if flac / metaflac missing (better than silent skip
      when the user has explicitly opted in). Verified on a real
      Lovesong FLAC: MD5 = a3dcc342..., `flac -t` passes.

**Testing infrastructure**

- [x] pytest integration marker added: `@pytest.mark.integration`.
      `pyproject.toml` `addopts = "-v -m 'not integration'"` so the
      default `pytest` run skips them. Opt in with
      `pytest -m integration` or run everything with `pytest -m ''`.

- [x] First integration test in tests/test_flac_md5.py
      (test_real_flac_md5_fix): generates a real FLAC, zeros its MD5,
      runs the fix, verifies MD5 is non-zero and `flac -t` passes.
      Skipped by default; requires flac + metaflac + ffmpeg.

**Performance**

- [x] Lazy imports: Tagger, lookup_isrc, apply_mb_tags, fetch_lyrics
      are now imported inside `_post_download` rather than at module
      top. LocalStore construction deferred to a `store` property.

- [x] Measured: small / no visible improvement because the remaining
      ~3.5s startup is dominated by Typer / Rich / httpx (structural,
      not fixable by lazy imports). Fix kept for hygiene — commands
      that never touch the store or the tagging pipeline no longer
      pay their cost.

**Cosmetic**

- [x] Error prefix cleanup: session layer no longer wraps
      `_slice_range` ValueError with `"Cannot download album: {exc}"`.
      CLI output is now `"Invalid range: disc 5 not found in collection"`
      instead of `"Invalid range: Cannot download album: disc 5 not found in collection"`.

#### NOTES

**Multi-attempt feature #6 lesson.** First attempt failed because I
assumed `metaflac --set-md5sum` computes the MD5. It does not — it
writes an arbitrary hex string. The mocked unit tests passed because
they asserted `returncode == 0`, not the actual argv passed to
subprocess. This is the exact class of bug that mocked tests miss.
Fix: for any external-tool invocation, tests must assert the argv
matches the tool's actual API (both shape and content), not just the
result. The correct attempt's unit tests do this: they assert
`argv[0] == "metaflac"`, `argv[1].startswith("--set-md5sum=")`,
the hex digest is 32 chars lowercase hex, and the file path is the
last argument. If that assertion had existed in attempt 1, the bug
would have been caught at test time instead of at download time.

**Fail-fast design principle.** If the user enables
`fix_flac_md5 = true` but flac / metaflac is missing, the download
now raises ConfigError rather than silently skipping. The user
opted in; they should know immediately that the tool cannot do what
they asked. Silent skip hides a broken feature — exactly what
happened with attempt 1.

**Session and CLI split paid off.** All of this session's feature
work — #7, #2, #6 — stayed confined to a single small file per
feature. Feature #7 edits touched session/downloads.py and
cli/downloads.py. Feature #2 added one method (session/streaming.py)
and one command (cli/downloads.py). Feature #6 touched config.py +
session/downloads.py. None of them required editing a >600 line file.
The splits were worth the day they took.

**Integration test infrastructure is the answer to the "mocks that
pass but the code is broken" problem.** First integration test
landed today (test_real_flac_md5_fix). Future integration tests
can cover: live Qobuz API (auth, get_track/album, signed URL),
real downloads with real tags, MusicBrainz enrichment against
the real API. Those go in tests/integration/ and are run with
`pytest -m integration`. Default `pytest` stays fast and hermetic.

#### BUGS

- **max_workers / -j is a no-op for all CLI download commands.**
  Same as before. This is the next priority.

  `session.download_album`, `download_playlist`,
  `download_artist_discography`, `download_favorites`,
  `download_purchases` each implement their own sequential for-loop
  and never call `Downloader.download_album` (the only method that
  reads `self._max_workers`). Setting `download.max_workers = 8` or
  `-j 8` has no observable effect.

  Fix scope: parallelise the per-track loop via ThreadPoolExecutor
  in each method. Rich progress and SQLite WAL are thread-safe;
  mutagen is per-file so no shared state. Estimated 60-90 minutes.
  Expected 3-5x speedup on multi-track albums.

- **lookup_isrc logs 404 as error.** Cosmetic, still deferred.

- **Network TLS block for musicbrainz.org on mobile data.** Not a
  Kabooz bug; VPN resolves.

#### TODO

- [ ] **max_workers / -j fix (Level 1 concurrency).** Highest
      priority. Parallel track downloads via ThreadPoolExecutor.
      Affects all 5 download commands. ~60-90 min.

- [ ] **Pipeline architecture (Level 2 concurrency).** After
      max_workers. Producer-consumer: metadata prefetch thread →
      downloader workers → tagger thread. Overlaps network I/O
      with tagging/MD5/lyrics/MB. ~3-4 hours.

- [ ] **Async rewrite (Level 3).** NOT RECOMMENDED. Async pays off
      for thousands of concurrent connections, not for 4-8 album
      tracks. Threading (Level 1 + 2) gives equivalent throughput
      with simpler code. Revisit only if profiling shows threading
      is the bottleneck.

- [ ] **Man page for kabooz.** Long-deferred. The CLI structure is
      now stable post-split, so this can proceed whenever.

- [ ] **Cosmetic: lookup_isrc 404 → "no coverage" log message.**

#### FEATURES remaining

- [ ] **#5 remaining:** quality fine-tuning (constrain max bit depth
      / sample rate), `external_processor` shell hook.

- **Dropped:** favorites / purchases ranged download. Users who
      need it can call `_slice_range` directly or wrap the returned
      list themselves. Adding CLI flags for these two commands adds
      surface area without proportionate value.

- **Deferred:** MP4-DASH lyrics discovery (Tampermonkey capture
      approach; needs a separate session).

### 2026-11-05
**Author**: [sherlockholmesat221b]
**Commits Made**: c0a65b5..e569dd0

**Note**: continuation of the 2026-11-04 session. The 11-04 entry
covers the session.py / cli.py package splits, feature #7 (ranged
download), and the perf investigation. This entry covers features
#2 and #6, chunked download, rate limiting, and the multiple
rounds of regressions and fixes that came with them.

#### DONE

- [x] **Feature #2 — stream URL command.**
      `kabooz url <id>` outputs the CDN stream URL to stdout.
      StreamingMixin.resolve_stream(track_id, quality, report=False)
      in session/streaming.py — silent by default. report=True opts
      in to Qobuz reportStreamingStart.

      CLI design (final):
        --json controls FORMAT only, not content
        --field controls CONTENT (comma-separated list)
        Bare URL default → 1 API call, no metadata fetch
        Metadata field requested → 2 API calls (adds get_track)

      `--report` is opt-in so scripted `kabooz url | xargs curl`
      does not create false play events. Downloads never report;
      TUI always reports; `kabooz url` is silent unless --report.

- [x] **Feature #6 — FLAC MD5 fix (correct implementation).**
      download.fix_flac_md5 = false (default off).
      Decodes via `flac -ds --stdout --force-raw-format
      --endian=little --sign=signed`, hashes PCM with hashlib.md5,
      then writes via `metaflac --set-md5sum=<hex>`. Runs after
      tagging and MB enrichment, before .part→final rename.

      Requires flac >= 1.4.0 and the `flac` binary. If enabled but
      binary missing → ConfigError immediately (fail-fast). --dev
      mode skips it. Caveat documented: recomputed MD5 proves the
      LOCAL copy is intact at rest, not source match.

- [x] **Chunked download (Phase A).**
      New DownloadConfig fields:
        connections_per_track = 1   byte-range chunks per track
        chunk_size_mb = 10          target chunk size
        rate_limit_kbps = 0         aggregate cap, kbps

      Downloader dispatches to _download_chunked when connections>1
      and not no_chunks. Splits file into N byte ranges, downloads
      each via ThreadPoolExecutor to <path>.part.{i}, then
      _assemble_chunks (pure Python — no `cat`, cross-platform)
      feeds the assembled .part file to the existing pipeline.

      Resume: complete .part.{i} files detected by size and
      skipped. Failed chunks persist so next run re-fetches only
      those. Falls back to single-connection on 400/416 (Range
      unsupported) or missing Content-Length.

      CLI: -x N / --connections N   (default from config)
           --no-chunks               (computes connections=1 at CLI
                                      layer; session signature
                                      unchanged)

- [x] **Rate limiting.**
      RateLimiter in kabooz/download/rate_limiter.py — thread-safe
      aggregate bandwidth cap. Consume called from every chunk
      write in both _download_chunked and existing _stream_*
      paths. Tracks cumulative bytes since start, sleeps to
      enforce target average. 0 = unlimited (default).
      8000 kbps = 1 MB/s = 8 Mbps.

- [x] **max_retries load_config regression fix.**
      Feature #3 added max_retries to DownloadConfig and
      validate_config but never wired it into load_config. Users
      setting download.max_retries=N were silently ignored
      (always defaulted to 2). One-line fix + regression test.

- [x] **-j to -x migration.**
      Old -j/--workers flag removed from all 7 download commands.
      It was documented as concurrency control but never
      implemented (silent no-op since v0.1.0). Users passing -j
      now get "no such option" — honest failure. Breaking change
      at v0.1.x scope; noted in commit message.

#### NOTES

**Chunked-download design decision.**

Rejected parallel-track model (multiple whole files simultaneously)
in favour of the conventional aria2c / yt-dlp approach: byte-range
parallelism WITHIN one file. Parallel tracks would be spotty in
CLI (N interleaved progress bars), unconventional, and would expose
lyrics/MB services to rate limits from N concurrent fetches.
Chunking within one file leaves lyrics/MB calls serialised and
keeps the progress display to a single bar.

Aggregate-limited networks see ~0% speedup from chunking (all
chunks share the same pipe). Per-connection-throttled networks see
2-4x per track. Both are correct; the knob is there for the latter
case. --dev mode bypasses chunking because dev audio is small
synthetic content — no benefit, adds assembly overhead.

**Pipeline (Level 2) deferred.**

Producer-consumer: metadata prefetch thread → downloader workers
→ tagger thread. Overlaps network (downloads) with disk (writes)
and CPU (tagging, MD5, lyrics parsing). ~5% wall-clock improvement
on aggregate-limited networks; larger benefit where tagging is a
meaningful fraction of total time. 3-4 hours, own session.

**Async rewrite not recommended.**

Threading with N chunks scales to 8-16 connections without a
second code path. Async pays off at 100+ concurrent connections;
for 4-8 album tracks it is overhead > benefit. Do not build.

**Session / CLI split paid off.**

Feature #2 touched session/streaming.py (one method) and
cli/downloads.py (one command). Feature #6 touched config.py,
session/downloads.py. Chunked download touched downloader.py,
session/downloads.py, cli/downloads.py, config.py, new
rate_limiter.py, docs. All small focused edits. The 1,500-line
session.py and 1,000-line cli.py that existed before the split
would have made each of those a 300+ line multi-site diff. The
split was worth the day it took.

#### LESSONS

Six-plus rounds of breakage during these features. Full
post-mortem so future-me does not repeat.

- **Mocked tests must validate ARGUMENTS, not just result.**
  First FLAC MD5 attempt called `metaflac --set-md5sum <path>` —
  WRONG, that flag writes an MD5 you supply, it does not compute
  one. Tests passed because they mocked subprocess.run and only
  asserted returncode. Real downloads always failed (MD5 came
  back zeros). Fix: assert on actual argv passed to subprocess
  matches the tool's real API. The corrected tests do this.
  Without that assertion, a mock never catches an API misuse.

- **`pipefail` masks `--help` exit codes.**
  Typer exits 2 for --help (Typer/Click convention).
  `kabooz track --help | grep -q -- --connections` under
  `set -o pipefail` returns pipeline exit 2, not grep's 0. Four
  separate scripts aborted on "missing --connections" while the
  flag was actually present. Fix: mask exit code explicitly
  (`output=$(kabooz ... 2>&1 || true)`) or strip pipefail around
  help checks.

- **`__pycache__` shadows fresh `.py` edits on some filesystems.**
  Termux ext4/FUSE sometimes has coarse mtime resolution. A
  freshly-written `.py` can be considered "same age" as an old
  `.pyc`; Python serves stale bytecode. Symptom is edits
  confirmed by grep not appearing in --help output. Fix: clear
  `__pycache__` at the start of every script that touches
  cli/ or session/. Do it reflexively; it costs 30 ms.

- **Sentinel checks must include `def ` or `class `.**
  `if "_download_chunked" not in src` returned False because
  the dispatch code (inserted earlier in the same script) already
  referenced the name. The method definition was missing. Fix:
  `"def _download_chunked("` (definition) not `"_download_chunked"`.
  Grep for the definition, not for the name.

- **Multi-indent regexes match across indents.**
  `for ind in [16-spaces, 12-spaces, 8-spaces]: re.sub(f'{ind}workers=...')`
  — the 12-space pattern matches the tail of 16-space lines.
  Doubled insertions. Fix: single regex with `^(\s+)` anchor,
  use `m.group(1)` for indent in replacement. One pass, one
  match per line, any indent.

- **AST-based patching beats regex for method edits.**
  Session/CLI split used `ast.parse` + method-name lookup +
  splice by lineno. First-try success every time. Regex failed
  repeatedly on whitespace/comment/adjacent-reference drift.
  For structural changes, use AST.

- **Orphan references from partial migrations.**
  Phase 3 added `connections` to session signatures. Phase 4
  replaced `workers` in CLI signatures with `connections` +
  `no_chunks`. But phase 4 also added `no_chunks=no_chunks,` to
  CLI calls without phase 3 having added `no_chunks` to session
  signatures. Every download command crashed with TypeError.
  Fix: two small edits — remove no_chunks from CLI calls,
  compute `connections=(1 if no_chunks else connections)` at CLI.
  Lesson: end-to-end design the feature; do not patch in phases
  where each phase assumes the other landed.

- **Do not commit until the smoke test passes.**
  Every phase of chunked download should have been followed by
  `kabooz --dev track <id>` before proceeding. It was not. Each
  regression would have been caught in seconds. Rule now: no
  commit until the command runs.

#### BUGS

- **lookup_isrc logs 404 as error.** Cosmetic, unchanged.
- **Network TLS block for musicbrainz.org on mobile data.** Not
  a Kabooz bug; VPN resolves.
- **max_workers no longer a CLI flag.** By design (see DONE).
  No alias planned. Users on older scripts may notice.

#### TODO

- [ ] **Man page (kabooz.1).** CLI surface stable post-split
      and post-features. Ready to write. ~2 hours, one commit.
      Install script for Termux / Linux / macOS.

- [ ] **Pipeline concurrency (Level 2).** Producer-consumer:
      prefetch → downloaders → tagger. Overlaps network, disk,
      CPU. 3-4 hours. Own session.

- [ ] **Chunked download docs polish.** Add explicit caveat that
      on aggregate-limited networks `-x 4` can be SLOWER than
      `-x 1` due to TCP slow-start × N.

- [ ] **Cosmetic: lookup_isrc 404 → "no coverage" log message.**

- [ ] **Feature #5 remaining:** quality fine-tuning (constrain
      max bit depth / sample rate), external_processor shell hook.
