# yoink-music

Music platform link resolver plugin for [yoink-core](https://github.com/AdamsGH/yoink-core).

Converts music URLs (Spotify, Yandex Music, Deezer, YouTube Music, Apple Music, SoundCloud) into cross-platform cards with links to all available services. Supports artist cards with top tracks, inline mode, and optional MP3 download.

Included in yoink-core as a git submodule at `plugins/yoink-music`.

## Usage

**In a group or private chat:** paste any music URL - the bot replies with a platform card.

**Artist URLs (Spotify):** paste a Spotify artist URL - the bot replies with an artist card showing platform links and top 5 tracks.

**Inline mode:** `@bot <music_url>` - pick the result to share a card with platform links and album art preview. If downloads are enabled, audio follows automatically.

**YouTube links:** `@bot https://youtube.com/watch?v=...` - if the video is in the Music category, the bot resolves it as a track.

## Supported platforms

| Platform | Parse | Cross-link search |
|---|---|---|
| Spotify | embed scrape → official API → oEmbed | Deezer API, Yandex Music library, YTMusic |
| Deezer | public API | Spotify API, Yandex, YTMusic |
| Yandex Music | yandex-music library | Spotify API, Deezer API, YTMusic |
| YouTube Music | ytmusicapi | Deezer API, Yandex, Spotify |
| Apple Music | og-tag scrape | Deezer API, Yandex, YTMusic |
| SoundCloud | og-tag scrape | Deezer API, Yandex, YTMusic |
| YouTube | yt-dlp metadata (Music category only) | - |

## RBAC

`FeatureSpec(music:inline, default_min_role=user)` controls inline access. The message handler uses `AccessPolicy(min_role=user, check_group_enabled=True, check_thread_policy=True)`. No explicit grant required - accessible to all `user+` by default.

## Platform icons

Cards sent directly by the bot use custom emoji from the `MusicServicesIcons` pack. Inline results use plain text links (Telegram does not render custom emoji in inline-sent messages).

## Music download

When `MUSIC_DOWNLOAD_ENABLED=true`:

1. Checks `file_id` cache (shared with yoink-dl) - instant re-send if cached
2. Resolves canonical source URL - prefers Spotify or YouTube Music links from the resolved track
3. Downloads at 192 kbps MP3 via yt-dlp
4. Embeds ID3 tags (title, artist, cover art via mutagen)
5. Sends as Telegram audio with thumbnail and caches `file_id`
6. Writes a `download_log` entry on every outcome (ok, cached, and all error paths) with `user_id`, `group_id`, and `thread_id`

Download is async - card is sent first, audio follows without blocking. Requires `yoink-dl` with `mutagen>=1.47`.

## Configuration

All variables use the `MUSIC_` prefix.

| Variable | Default | Description |
|---|---|---|
| `MUSIC_SPOTIFY_CLIENT_ID` | - | Spotify Web API client ID (enables full artist metadata) |
| `MUSIC_SPOTIFY_CLIENT_SECRET` | - | Spotify Web API client secret |
| `MUSIC_PROXY_URL` | - | Proxy for platforms that block direct requests |
| `MUSIC_PROXY_PLATFORMS` | - | Comma-separated platform keys to route through proxy (e.g. `spotify,soundcloud`) |
| `MUSIC_REQUEST_TIMEOUT` | `10.0` | HTTP timeout for platform API calls, seconds |
| `MUSIC_CACHE_TTL` | `3600` | In-memory resolved track cache TTL, seconds |
| `MUSIC_DOWNLOAD_ENABLED` | `false` | Send MP3 after each card |

Without Spotify credentials the plugin scrapes the embed page (requires proxy) or falls back to oEmbed (title only), then recovers the artist from a Deezer track lookup by ID.

## Package structure

```
src/yoink_music/
  plugin.py              # entry point (MusicPlugin)
  resolver.py            # orchestrates parser + parallel adapter searches
  types.py               # TrackInfo, ArtistInfo, ArtistTrack, ResolverError
  config.py              # MusicConfig (pydantic-settings)
  platforms.py           # URL regexes, extract_music_urls()
  emoji_ids.py           # PLATFORM_EMOJI map, format_track_entities(),
                         # format_artist_entities(), build_entities_text()
  downloader.py          # optional: find YT URL, download, embed tags, send audio
  parsers/
    spotify.py           # embed scrape -> official API -> oEmbed fallback chain
    deezer.py            # public Deezer API
    yandex.py            # yandex-music library
    ytmusic.py           # ytmusicapi
    soundcloud.py        # og-tag scrape
    apple_music.py       # og-tag scrape
    youtube.py           # yt-dlp metadata; Music category gate; title regex
    artist.py            # resolve_spotify_artist() with parallel enrichment
  adapters/
    spotify.py           # Spotify Web API search; DuckDuckGo + oEmbed fallback
    deezer.py            # public Deezer API search
    yandex.py            # yandex-music library search
    ytmusic.py           # ytmusicapi search
    soundcloud.py        # soundcloud.com/search scrape
    apple_music.py       # music.apple.com/search scrape
  commands/
    link.py              # MessageHandler: music URL in chat -> card + optional audio
    inline.py            # InlineHandlerSpec: @bot <url> inline card
  i18n/locales/          # translations (en.yml, ru.yml)
```
