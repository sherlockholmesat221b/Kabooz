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
**Commits Made**: 214f9c1..c1298b6
#### DONE
- [x] **Issue #2 — `Disc {disc}/` folder created for monodisc albums.**
      Template segments containing `{disc}` are dropped when
      `album.media_count <= 1` or `album is None` (standalone track).
      `{disc}` stays a plain integer for callers that place it in a
      filename segment. Auto path (`resolve_track_path` without a
      custom template) untouched — verified byte-for-byte identical.
      Root cause: `_build_context` set `"disc": track.media_number or 1`
      unconditionally; the template renderer had no equivalent of the
      `is_multi_disc` gate that the auto path already used.

- [x] **`{track_all}` placeholder.** Position of a track counted
      continuously across all discs (1..N). For monodisc albums equals
      `{track}`; for a 3-disc set with 12 tracks on disc 1, disc 2
      track 1 is `{track_all}` = `13`. Falls back to `track_number`
      when `album is None` or `album.tracks` is empty. Registered in
      `_KNOWN_PLACEHOLDERS` so `validate_config` accepts it.

- [x] **MusicBrainz User-Agent.** Changed from
      `kabooz/0.1 ( https://gitlab.com/kabooz )` to
      `Kabooz/0.1.0 ( https://github.com/sherlockholmesat221b/Kabooz )`.
      MB's WAF returns `403` for non-conforming UAs (confirmed: the
      literal string `test` is rejected). The lowercase product name
      and stale gitlab URL were both non-compliant.

- [x] **Surface total MusicBrainz failure.** `AlbumDownloadResult`
      now tracks `mb_attempted` and `mb_succeeded`. `cli.album` prints
      a warning when `mb_attempted > 0 and mb_succeeded == 0`, listing
      the two realistic causes (network TLS block, or ISRCs not in MB).
      Previously silent outside `--dev`.

- [x] **Pre-existing stale test fix.**
      `test_load_playlist_magic_comment_stripped` asserted the old
      `# qobuz-playlist v1` header. The code has written
      `# kabooz-playlist v1` since the rename. Test updated.

- [x] **`work` prefix dedupe in classical titles.**
      `Track.display_title` no longer prepends `work` when
      `work.lower()` already appears inside `title.lower()`. Qobuz
      routinely returns the work name in both fields for classical
      albums, producing `"Symphony No. 6 in A Minor - Mahler: Symphony
      No. 6 in A Minor: 1. Allegro…"`. Non-classical tracks are
      unaffected (`work` is empty and the branch is skipped).
      Commit: 4696c4c.

- [x] **Issue #3 — retry on `httpx.TransportError`.**
      `Downloader` gains `max_retries` (default 2 = 3 total attempts).
      Retries are immediate (no sleep) and use the existing `Range`
      header, resuming from the `.part` file each attempt. The retry
      wrapper and streaming loop are split:
      `_download_to_path` / `_stream_to_part` and
      `_download_goodie_to_path` / `_stream_goodie`. `_stream_*` reads
      `part_size` / `existing_size` fresh per attempt, so a transient
      `HEAD` failure on retry does not truncate the `.part` file.
      `session.download_album` and `download_playlist` widen their
      per-track `except` to catch `httpx.TransportError` alongside
      `APIError`. New `download.max_retries` config with 0–10
      validation. Rationale for no backoff: the retry recovers
      transient peer resets, not rate limits. Persistent failures
      escalate via `.part` resume across runs.

- [x] **Issue #1A — signature diagnostics.**
      New `SignatureError(APIError)` raised when a response body
      contains "Invalid Request Signature", with a message pointing
      at `--app-secret` and clock check. `_sign_track_url_request`
      logs the masked canonical string and timestamp in `--dev` for
      comparison against a known-working client.
      `_canonical_signature_string` extracted as a module-level
      helper and locked in a unit test. **Confirmed against live
      API**: the canonical string and MD5 match qobuz-dl exactly.
      The failure mode is almost certainly a stale `app_secret` or
      clock skew, not a code bug — hence #1B (below) is the
      permanent fix, deferred until Issue #1 reproduces.

- [x] **Tests.** 14 new tests this session, bringing the suite from
      230 → **244 passing**:
      · 3 for `{disc}` segment dropping (monodisc, multidisc,
        `album=None`)
      · 3 for `{track_all}` (monodisc, multidisc, `album=None`)
      · 1 for MB User-Agent format
      · 3 for `artist_or()` on `TrackSummary` / `Track` (TUI crash
        guard)
      · 3 for download retry (track retry, goodie retry, bounded
        give-up)
      · 1 for canonical signature string stability

- [x] **Docs.** `docs/naming.md` gained `{disc}` drop-behaviour note,
      the `{track_all}` row, and a `{track}` vs `{track_all}`
      explanation. `docs/configuration.md` gained a note on the
      network requirement for `musicbrainz.org`.

- [x] **TUI strategy decision.** `tui.py` (Textual) shelved as
      experimental; `tui_curses.py` is the supported TUI. Rationale:
      Textual is not a shipped dependency (opt-in); its async worker
      model produces bugs that are difficult to fix without local
      debugging; a full terminal player (audio engine, cover art,
      caching, edge cases) is a separate project. `tui.py` retained
      as a reference for anyone who wants to build on it.

- [x] **TUI `TrackSummary` crash and search parsing.** Fixed in both
      TUI files — `TrackSummary.artist_or()` / `Track.artist_or()`
      added to models; `SearchResults` attribute access replaces
      `.get()`. `tui_curses.py` validated manually end-to-end
      (search → album view → playback). `tui.py` search remains
      non-functional for a Textual-specific reason, accepted as
      out of scope.

#### NOTES

- **MusicBrainz — three-layer failure, fully characterised.**
  Tested four independent clients (`curl` TLS 1.2, `curl` TLS 1.3,
  `httpx`, `urllib`) on mobile data: every one failed at the TLS
  handshake with `UNEXPECTED_EOF_WHILE_READING`. Four different
  clients, two different TLS versions, one failure signature → the
  blocker is not the code, not OpenSSL, not the User-Agent. It is a
  network-level filter to `musicbrainz.org` (very likely carrier DPI
  on mobile data).

  On VPN the handshake succeeds. With the correct User-Agent, MB
  responds normally: `404` for ISRCs it lacks (e.g. Norwegian Decca
  classical from 1987), `200` with tags written for ISRCs it has.
  Confirmed in a full Mahler 8-track run — `mb_attempted=8`,
  `mb_succeeded=4` (tracks 1–4 returned 404, tracks 5–8 succeeded
  and MB tags were written).

  Conclusion: **the Kabooz MB code was correct all along.** The
  only fixable defects were (a) the User-Agent and (b) silent
  failure. Both fixed.

- **`{disc}` investigation.** Reproduced on three albums:
  - Mahler 6 / Haitink, `media_count: 1` → `Disc 1/` created by
    template before fix. Post-fix: no `Disc/` folder.
  - Don Giovanni / Giulini, `media_count: 1` → same, post-fix no
    `Disc/`.
  - Disintegration Deluxe, `media_count: 3` → `Disc 1/`, `Disc 2/`,
    `Disc 3/` retained as expected. Confirmed discs 1 and 2 in the
    run; disc 3 has not been individually verified but the guard is
    album-level so if `1/` and `2/` appear, `3/` must too.

- **Default template still interleaves multidisc albums.** In the
  current v0.1.0 default (`{album} [{quality}] [{year}]/{track:02d}.
  {title}`), a 3-disc set with the same per-disc track numbers
  produces files where alphabetic sort interleaves discs. This was
  true in v0.1.0 before our work and remains true — users must opt
  into `{disc}/` or `{track_all}` explicitly. Candidate for a
  default-template change in a future release; not done now because
  it changes behaviour for new users only and we are still in the
  "small fixes" phase.

- **`_compute_track_all` design.** The helper lives in
  `download/naming.py`, not in `models/track.py`, because it needs
  the album's full track list to sum prior discs. `Track` alone does
  not carry enough information.

#### BUGS

Open bugs remaining, from both the v0.1.0 baseline and this session:

- **`max_workers` / `-j` is a no-op for all CLI download commands.**
  `session.download_album`, `download_playlist`,
  `download_artist_discography`, `download_favorites`, and
  `download_purchases` each run their own sequential loop and never
  use `Downloader.download_album` (the only place that reads
  `self._max_workers`). Setting `download.max_workers = 8` in
  config has no observable effect. `README.md` advertises "Parallel
  downloads with configurable worker count (`-j`)" — currently
  false. Larger fix, needs threading-safety review for mutagen
  writes.

- **`lookup_isrc` logs 404 as `error`.** Cosmetic: a `404 Not Found`
  from MusicBrainz means "no coverage", not "error". Only visible
  in `--dev` mode. Fix: distinguish `httpx.HTTPStatusError` with
  `status_code == 404` from other exceptions in the log message.

- **Network TLS block for `musicbrainz.org` on mobile data.**
  Not a Kabooz bug — confirmed at four client layers (see NOTES).
  Users on mobile without VPN will not get MB enrichment. VPN
  resolves it. Optional `proxy` config for MB could help users
  without VPN, deferred (VPN already covers the case).

#### TODO

- [ ] **Issue #1B — `--refresh-secret` credential scraper.**
      Fetch the current Qobuz web-player `app_id` and `app_secret`
      from `play.qobuz.com`. Adapted from
      `QobuzDL/Qobuz-AppID-Secret-Tool/main.py` (which uses
      `aiohttp`); port to `httpx` for consistency and to avoid a new
      dependency. Wire `--refresh-secret` flag into `kabooz login`.
      Fallback when scraping fails: prompt for manual `--app-secret`.
      **Deferred until Issue #1 reproduces in practice** — the
      `--dev` signing log shipped in #1A will tell us whether the
      failure is a stale secret (scraper needed) or something else
      (scraper is the wrong fix).

- [ ] **Consider** changing the default `naming.album` template to
      include `Disc {disc}/`:
      `"{albumartist}/{album} [{quality}] [{year}]/Disc {disc}/{track:02d}. {title}"`.
      Safe now that the `{disc}` segment is dropped for monodisc
      albums. Changes default for new users only. Deferred.

- [ ] **Cosmetic** — quiet first-run ffmpeg in `dev.py` with
      `-hide_banner -loglevel error`.

- [ ] **Cosmetic** — split `lookup_isrc`'s 404 case into a distinct
      dev log message.
      
#### IDEAS

- Cache album-level cover art between tracks within a single
  `download_album` run. Currently re-downloads the cover art per
  track when `--cover` is used. For a 14-track album that is 14
  identical HTTP GETs to the CDN. Low-impact on wired networks,
  noticeable on mobile.

#### FEATURES

Seven feature requests queued. No implementation started. Design
decisions captured here so the next session has full context.

- [ ] **#1: Qobuz IDs in tagged metadata.**
      Write `QOBUZ_TRACK_ID`, `QOBUZ_ALBUM_ID`, `QOBUZ_ARTIST_ID`,
      `QOBUZ_UPC` to FLAC Vorbis Comments and MP3 `TXXX` frames.
      Naming consistent with existing `MUSICBRAINZ_*` tags.
      Files: `tagger.py` only. Effort: ~30 min.

- [ ] **#4: Cover art swap.**
      Currently embeds full-res `_org.jpg` (up to 3+ MB for some
      albums) and saves 600×600 to `cover.jpg`. Intended: embed
      600×600 (UI read, smaller audio file), save full-res to
      `cover.jpg` (archival; user can inspect/extract). Files:
      `tagger.py`, `session._save_cover_file`. Effort: ~15 min.

- [ ] **#3: Lyrics tag mapping.**
      Target player: Musicolet. Musicolet reads `LYRICS` and parses
      LRC if present, falls back to plain text if not.
      Default mapping:
      · `LYRICS` — synced LRC when available; else plain (timestamps
        stripped)
      · `UNSYNCEDLYRICS` — plain, always (harmless; some players
        only read this tag)
      · `SYNCEDLYRICS` — not written by default
      Trade-off: players that read `LYRICS` but do not parse LRC
      (e.g. older desktop players) will show raw `[mm:ss.xx]`
      brackets. Config override to write to `SYNCEDLYRICS` instead
      for users of those players.
      Config additions:
      ```toml
      [tagging]
      # Where synced lyrics go.
      #   "lyrics"       — LYRICS gets synced LRC (Musicolet, some
      #                    Android players)
      #   "syncedlyrics" — SYNCEDLYRICS gets synced LRC, LYRICS
      #                    keeps plain (foobar2000, MusicBee)
      #   "both"         — write to both tags
      #   "none"         — do not write synced lyrics at all
      synced_tag = "lyrics"

      # Write a .lrc file alongside the audio file.
      save_lrc_file = false
      ```
      Files: `tagger.py`, `config.py`. Effort: ~30 min.

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
      · `--start` and `--end` are 1-based, inclusive.
      · Default `--start=1`, `--end=∞`.
      · `--disc N` alone — all tracks of disc N.
      · `--disc` given — `--start/--end` are per-disc indices.
      · `--disc` omitted — `--start/--end` are global indices.
      · `--disc` on a playlist — error, playlists have no disc
        structure.
      Files: `cli.py`, `session.py`. Effort: 1–2 hr.

- [ ] **#2: Stream URL command.**
      ```bash
      kabooz url <track_id>                 # bare URL to stdout
      kabooz url <track_id> --json          # all fields
      kabooz url <track_id> --field url     # one field
      kabooz url <track_id> -q cd --report  # opt into reporting
      ```
      Design:
      · **Stream reporting is OFF by default.** `--report` opts in.
        Rationale: `kabooz url … | xargs curl` in a script must not
        create false play events for Qobuz analytics.
      · Fast path (bare URL) resolves nothing beyond
        `get_track_url` — no album, no artist, no JSON beyond the
        one field.
      · All flags opt-in. Default output is one line, no fluff.
      Files: `cli.py`, `session.py` (thin wrapper preserving the
      "business logic in session" rule). Effort: 1–2 hr.

- [ ] **#6: FLAC MD5 fix.**
      Confirmed: Qobuz zeroes the MD5 in STREAMINFO for downloaded
      FLACs. `metaflac --set-md5sum <file>` recomputes from decoded
      audio without re-encoding, ~1–2 s per hi-res track.
      **Requires `flac >= 1.4.0`** for the flag. Detect at startup,
      skip with one-line warning if absent. **No re-encode fallback**
      (`flac -0`) — rejected explicitly by user as against the
      "boring and predictable" principle; users who want re-encode
      use the `external_processor` hook from #5.
      NOTE: the recomputed MD5 verifies the **local copy is intact
      at rest**, not that it matches Qobuz's source (which was
      likely transcoded before delivery — hence the zeroed MD5 in
      the first place).
      Config: `download.fix_flac_md5 = false` (default off, keeps
      downloads lean). Files: `downloader.py`, `config.py`.
      Effort: 1–2 hr.

- [ ] **#5: Config discipline + post-processing hooks.**
      Not one feature — a direction applied across #1, #3, #4, #6
      as they land. Concrete pieces, each its own commit:
      · Quality fine-tuning — constrain maximum bit depth / sample
        rate (e.g. `download.max_bit_depth = 24`)
      · `external_processor` shell hook — runs **after** tagging,
        like `external_downloader` runs **instead of** downloading.
        Template:
        `"flac -0 --force {file}"` for re-encode, or anything else
        a power user wants.
      · Audit of existing per-command overrides for tag/cover/
        lyrics flags; fill gaps.
      Files: `config.py`, `downloader.py`, `session.py`, `cli.py`.
      Effort: ongoing, spread across other features.

- **Recommended order:** 1 → 4 → 3 → 7 → 2 → 6 → 5.
  · 1 and 4 are tagger-only, small, independently verifiable by
    inspecting the output file.
  · 3 is tagger + config, follows naturally after 1 and 4.
  · 7 and 2 are session-layer changes with CLI surface.
  · 6 is one more downloader hook.
  · 5 is iterative; applied per-feature rather than as one commit.

#### NOTES
- **Qobuz album IDs sometimes equal UPCs.** Confirmed on this
  session's downloads: Mahler 6 / Haitink has `id == upc ==
  "0002894830800"`; Disintegration Deluxe has `id == upc ==
  "0060075324566"`. Both are valid — Qobuz uses the UPC as the
  album ID for releases that never had an internal catalog number
  assigned. The convention is inconsistent across the catalog.
  Design decision (feature #1): `QOBUZ_ALBUM_ID` and `UPC` are both
  written even when values coincide. They mean different things and
  neither can be derived from the other in the general case.
