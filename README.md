# yoink-music

Music link aggregator plugin for [yoink-core](https://github.com/AdamsGH/yoink-core). Detects music platform URLs in group chats and inline queries, fetches track metadata, and replies with a card containing links to the same track on all supported platforms. Optionally downloads and sends the track as an MP3 audio message.

Included in yoink-core as a git submodule at `plugins/yoink-music`.

## Supported platforms

| Platform | Parser | Adapter |
|---|---|---|
| Spotify | Official Web API (if credentials set); falls back to `open.spotify.com/embed` scrape (`__NEXT_DATA__` JSON, requires proxy); last resort oEmbed (title only) | Official Web API search with scoring (if credentials set); falls back to DuckDuckGo HTML search + oEmbed scoring |
| Deezer | Public API (`api.deezer.com/track/{id}`) | Public API search with scoring |
| Yandex Music | Unofficial `yandex-music` Python library | Library search (`"artist - title"` query) |
| YouTube Music | `ytmusicapi` (no key needed) | Library search |
| SoundCloud | og-tag scrape | HTML scrape of `soundcloud.com/search` |
| Apple Music | og-tag scrape | HTML scrape of `music.apple.com/search` |
| YouTube | `yt-dlp` metadata (Music category only); parses `Artist - Track (suffix)` title pattern | - (source only, no cross-search) |

## Usage

**In a group chat:** paste any Spotify / Deezer / YM / YTM link - the bot replies with a card and optional MP3.

**Inline mode:** `@bot <music_url>` - pick the result to send a card with platform links and album art preview. If downloads are enabled, audio follows the card automatically.

**Inline mode with plain YouTube:** `@bot https://youtube.com/watch?v=...` - if the video is in the Music category, the bot resolves it as a track and returns a music card (Deezer, YouTube Music, Apple Music links). Non-music videos fall through to the regular `yoink-dl` download flow.

Access is controlled by the core RBAC system. The message handler checks `user` role, group enabled flag, and thread policy. The inline handler is guarded at the dispatcher level via `access_policy` on the `InlineHandlerSpec` - users below `user` role get no response from the inline handler.

## Configuration

All variables use the `MUSIC_` prefix.

| Variable | Default | Description |
|---|---|---|
| `MUSIC_REQUEST_TIMEOUT` | `10.0` | HTTP timeout for platform API calls, seconds |
| `MUSIC_CACHE_TTL` | `3600` | In-memory cache TTL for resolved tracks, seconds |
| `MUSIC_SPOTIFY_CLIENT_ID` | - | Enables official Spotify Web API (full artist metadata without proxy) |
| `MUSIC_SPOTIFY_CLIENT_SECRET` | - | Spotify Client Credentials secret |
| `MUSIC_PROXY_URL` | - | Proxy URL for platforms that block direct requests (e.g. `socks5://host:1080`) |
| `MUSIC_PROXY_PLATFORMS` | - | Comma-separated platform keys to route through `MUSIC_PROXY_URL` (e.g. `spotify,soundcloud`) |
| `MUSIC_DOWNLOAD_ENABLED` | `false` | Send MP3 audio after each card (requires `yoink-dl` with `mutagen`) |

Without Spotify credentials the plugin scrapes the embed page (requires proxy) or falls back to oEmbed (title only), then recovers the artist from a Deezer track lookup by ID.

## Music download

When `MUSIC_DOWNLOAD_ENABLED=true` the plugin:

1. Checks a `file_id` cache (shared with `yoink-dl`) - instant re-send if cached
2. Searches YouTube Music via `ytmusicapi`, falls back to `yt-dlp ytsearch:`
3. Downloads at 192 kbps MP3 via `yt-dlp`
4. Embeds ID3 tags (title, artist, cover art) via `mutagen`
5. Sends as a Telegram `audio` message and caches the `file_id`

Download is async - the card is sent first, audio follows without blocking the handler. Requires `yoink-dl` with `mutagen>=1.47` installed.

## Architecture

```
src/yoink_music/
  plugin.py              # entry point (MusicPlugin)
  resolver.py            # orchestrates parser + parallel adapter searches
  types.py               # TrackInfo, ResolverError
  utils.py               # URL normalization, string similarity scoring
  config.py              # MusicConfig (pydantic-settings)
  platforms.py           # URL regexes + extract_music_urls()
  downloader.py          # optional: find YT URL, download, embed tags, send audio
  parsers/
    spotify.py           # embed scrape -> official API -> oEmbed fallback chain
    deezer.py            # public Deezer API
    yandex.py            # yandex-music library
    ytmusic.py           # ytmusicapi
    soundcloud.py        # og-tag scrape
    apple_music.py       # og-tag scrape
    youtube.py           # yt-dlp metadata; Music category gate; title regex parsing
  adapters/
    spotify.py           # Spotify Web API search (primary, if creds set); DuckDuckGo + oEmbed scoring (fallback)
    deezer.py            # public Deezer API search
    yandex.py            # yandex-music library search
    ytmusic.py           # ytmusicapi search
    soundcloud.py        # soundcloud.com/search scrape
    apple_music.py       # music.apple.com/search scrape
  commands/
    link.py              # MessageHandler - music URL in chat or via_bot card -> card + optional audio
    inline.py            # InlineHandlerSpec - @bot <url> inline card
  i18n/locales/          # translations (en.yml, ru.yml)
```

Parsers extract `(title, artist, thumbnail)` from the source URL. Adapters search for the same track on other platforms using `"artist title"` as query (Yandex uses `"artist - title"` for better precision). All adapter searches run in parallel. Results scored by geometric mean of title and artist similarity - wrong artist tanks the score even with a matching title. Results cached in memory per resolver instance.
