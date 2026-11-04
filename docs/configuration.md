# Configuration

The configuration file lives at `~/.config/kabooz/config.toml`. It is created
automatically the first time you run `kabooz login`.

View the current configuration:

```bash
kabooz config --show
```

Set a value:

```bash
kabooz config --set section.key=value
```

Or edit the file directly in any text editor.

---

## Full reference

```toml
[credentials]
# Qobuz app ID. Also read from QOBUZ_APP_ID environment variable.
app_id = ""

# Qobuz app secret. Also read from QOBUZ_APP_SECRET environment variable.
app_secret = ""

# Path to a token pool file for pool mode. Leave empty for personal session.
pool = ""


[download]
# Default output directory for all downloads.
output_dir = "."

# Default quality level.
# Values: mp3_320 | flac_16 | flac_24_96 | hi_res
quality = "hi_res"

# Number of parallel track downloads within an album or playlist.
# 1 = sequential (default, safest). Higher values speed up multi-track
# downloads but increase API and CDN load.
max_workers = 1

# Number of retry attempts on httpx.TransportError (peer reset,
# read timeout, connect error) during a track or goodie download.
# 0 = fail on first error. 2 = two retries (three attempts total).
# No sleep between retries — immediate, cheap.
max_retries = 2

# Shell command template for an external downloader (e.g. aria2c).
# Leave empty to use the built-in httpx downloader.
# Placeholders: {url} {output} {dir} {filename}
# {output} and {filename} refer to the .part path.
# Example: "aria2c -x 16 -s 16 -d {dir} -o {filename} {url}"
external_downloader = ""

# Timeout in seconds for reading data from the CDN.
# Large hi-res files on slow connections may need this increased.
read_timeout = 300.0

# Timeout in seconds for establishing a connection.
connect_timeout = 10.0


[tagging]
# Master switch. Set to false to skip all tagging.
enabled = true

# Download and embed full-resolution cover art in each audio file.
embed_cover = true

# Save cover art as a separate cover.jpg file in the album folder.
# For single-track downloads, the file is named after the audio file.
save_cover_file = false

# ── Lyrics tag mapping ─────────────────────────────────────────────────
# Each output tag is controlled independently. Values:
#
#   "synced" — LRC text with [mm:ss.xx] timestamps; skipped if no
#              synced lyrics available
#   "plain"  — plain text with timestamps stripped; skipped if no
#              plain text available
#   "best"   — LRC if available, else plain; skipped if neither
#   "none"   — tag not written
#
# FLAC (Vorbis Comments — text-only, no format constraints)
flac_lyrics          = "best"   # LYRICS tag
flac_unsynced_lyrics = "none"   # UNSYNCEDLYRICS tag
flac_synced_lyrics   = "none"   # SYNCEDLYRICS tag

# MP3 (ID3v2.4)
mp3_uslt             = "best"   # USLT frame (unsynchronized lyrics)
mp3_txxx_unsynced    = "none"   # TXXX:UNSYNCEDLYRICS frame
mp3_sylt             = "none"   # SYLT frame — binary synced; accepts
                                # only "synced" or "none"

# Write <audio_stem>.lrc alongside each audio file when synced
# lyrics are available. Works for any player that reads external
# .lrc files, regardless of tag-reading behaviour.
save_lrc_file = false

# ── Empirical note (Musicolet, tested 2026-11-04) ─────────────────────
# These behaviours were measured with scripts/test_flac_lyrics.py
# and scripts/test_mp3_lyrics.py, 14 test files total:
#
#   FLAC:
#     · LYRICS=LRC only                → synced display ✓
#     · LYRICS=LRC + UNSYNCEDLYRICS≠∅  → static (UNSYNCED overrides
#                                          LYRICS; synced display
#                                          breaks)
#     · LYRICS=LRC + SYNCEDLYRICS=LRC  → synced display ✓
#     · SYNCEDLYRICS only              → nothing
#
#   MP3:
#     · USLT=LRC only                  → synced display ✓
#     · SYLT only                      → nothing
#     · TXXX:UNSYNCEDLYRICS only       → nothing
#     · TXXX:LYRICS only               → nothing
#
#   Implication for Musicolet users:
#     Keep flac_unsynced_lyrics="none" and flac_synced_lyrics="none"
#     when flac_lyrics contains LRC. Everything else is per-user.
#
#   Other players vary. foobar2000 and MusicBee, for example, read
#   SYNCEDLYRICS/SYLT; configure those fields as needed.

# Size tier to embed into the audio file's cover art frame.
#   "thumbnail" — 50px, ~10 KB
#   "small"     — 230px, ~50 KB
#   "large"     — 600px, ~150 KB   ← default
#   "original"  — _org.jpg, up to 3+ MB
# Override per-download with --cover-size.
embed_cover_size = "large"

# Size tier to save as the sidecar file (cover.jpg or <track_stem>.jpg).
# Same values as embed_cover_size.
# Override per-download with --save-cover-size.
sidecar_cover_size = "original"

[musicbrainz]
# Enrich tags with MusicBrainz data (recording IDs, release group IDs,
# additional relationships) using the track's ISRC code.
# Makes one extra HTTP request per track when enabled.
enabled = false

# Note: requires direct HTTPS access to musicbrainz.org. Some carriers
# block it at the TLS layer, in which case enrichment silently fails.
# Test with:
#   curl -v "https://musicbrainz.org/ws/2/isrc/TEST_ISRC?fmt=json"


[naming]
# Naming templates control where downloaded files are placed and what
# they are named. See docs/naming.md for all available placeholders.

# Used by: kabooz album
album = "{album} [{quality}] [{year}]/{track:02d}. {title}"

# Used by: kabooz track (standalone), kabooz favorites --type tracks
single = "{artist} - {title}"

# Used by: kabooz album when release_type is "ep"
ep = "{albumartist}/{album} [{quality}] [{year}]/{track:02d}. {title}"

# Used by: kabooz album when release_type is "compilation"
compilation = "{album} [{quality}] [{year}]/{track:02d}. {title}"

# Used by: kabooz playlist
playlist = "{playlist} [{quality}]/{index:02d}. {title}"

# Used by: kabooz artist (the artist folder itself is injected by the
# session layer, so this template must NOT start with {albumartist})
artist = "{album} [{quality}] [{year}]/{track:02d}. {title}"


[local_data]
# Root directory for the local SQLite database, playlist TOML files,
# and export archives.
data_dir = "~/.local/share/kabooz"

# Log every download to the history table in the local database.
track_history = true

# On login (personal session only), pull all Qobuz favorites into
# the local store automatically.
auto_sync_favorites = false

# Subdirectory under data_dir for exported playlist TOML files.
# Relative paths are resolved against data_dir.
playlists_subdir = "playlists"
```

---

## Environment variables

| Variable | Equivalent config key |
|----------|----------------------|
| `QOBUZ_APP_ID` | `credentials.app_id` |
| `QOBUZ_APP_SECRET` | `credentials.app_secret` |
| `KABOOZ_DEV` | `--dev` flag |

Environment variables take precedence over config file values for credentials.

---

## Per-command overrides

Most config values can be overridden per-command without editing the file:

```bash
# Override quality for this run only
kabooz album 0093046758769 -q cd

# Override output directory
kabooz album 0093046758769 -o /external/drive/Music

# Override naming template
kabooz album 0093046758769 --template "{albumartist}/{album}/{track:02d}. {title}"

# Override worker count
kabooz album 0093046758769 -j 4
```

