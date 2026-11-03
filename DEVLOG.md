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


## 2026-11-03
**Author**: [sherlockholmesat221b]
**Commits Made**: 214f9c1..
### DONE
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

- [x] **Tests.** 7 new tests total: 3 for `{disc}` segment dropping
      (monodisc, multidisc, `album=None`), 3 for `{track_all}`
      (monodisc, multidisc, `album=None`), 1 for MB User-Agent format
      (`tests/test_musicbrainz.py`). Suite: **234 passed**.

- [x] **Docs.** `docs/naming.md` gained `{disc}` drop-behaviour note,
      the `{track_all}` row, and a `{track}` vs `{track_all}`
      explanation. `docs/configuration.md` gained a note on the
      network requirement for `musicbrainz.org`.

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

- **TUI `AlbumPane` crash on classical albums.**
  `tui.py::AlbumPane._load` iterates `album.tracks.items` and reads
  `t.performer.name`, but `album.tracks.items` are `TrackSummary`
  objects, which do not have a `performer` attribute. Crashes for
  every album browsed in the TUI. Matches the DEVLOG entry from
  2026-03-17.
  Fix: fetch full `Track` via `sess.get_track()` per summary, or
  guard with `getattr(t, "performer", None)` and fall back to the
  album-level artist name.

- **Duplicate `work` prefix in `display_title`.**
  For albums where Qobuz returns the work name inside the `title`
  field *and* in the `work` field (very common in classical),
  `Track.display_title` prepends `work` unconditionally, producing
  `"Symphony No. 6 in A Minor - Mahler: Symphony No. 6 in A Minor:
  1. Allegro…"`. Visible in every classical filename and TITLE tag
  downloaded this session. Fix: only prepend `work` when
  `work.lower() not in title.lower()`. Non-classical tracks are
  unaffected.

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

- **`httpx.RemoteProtocolError` aborts entire album.** No retry
  anywhere. A single `RemoteProtocolError` (peer closed connection
  mid-stream) aborts the whole album because the per-track
  `except` in `session.download_album` only catches `APIError`, not
  `httpx.TransportError`. `.part` resume works across runs but not
  within a run.

- **`lookup_isrc` logs 404 as `error`.** Cosmetic: a `404 Not Found`
  from MusicBrainz means "no coverage", not "error". Only visible
  in `--dev` mode. Fix: distinguish `httpx.HTTPStatusError` with
  `status_code == 404` from other exceptions in the log message.

- **Network TLS block for `musicbrainz.org` on mobile data.**
  Not a Kabooz bug — confirmed at four client layers (see NOTES).
  Users on mobile without VPN will not get MB enrichment. VPN
  resolves it. Optional `proxy` config for MB could help users
  without VPN, deferred (VPN already covers the case).

#### IDEAS

- Optional `--refresh-secret` on `kabooz login`: fetch the current
  Qobuz web-player `app_secret` from the JS bundle. Would fix Issue
  #1 automatically if the root cause is a stale secret. Pure
  scraping; users who supply their own secret are unaffected. Not
  started;
- Cache album-level cover art between tracks within a single
  `download_album` run. Currently re-downloads the cover art per
  track when `--cover` is used. For a 14-track album that is 14
  identical HTTP GETs to the CDN. Low-impact on wired networks,
  noticeable on mobile.
