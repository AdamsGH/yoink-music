"""Supported music platforms: URL patterns and display metadata."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Platform:
    key: str          # Odesli platform key
    name: str         # Human-readable name for buttons/messages
    emoji: str        # Shown next to the name
    order: int        # Sort order in the link card
    url_re: re.Pattern


def _p(key: str, name: str, emoji: str, order: int, pattern: str) -> Platform:
    return Platform(key=key, name=name, emoji=emoji, order=order,
                    url_re=re.compile(pattern, re.IGNORECASE))


PLATFORMS: dict[str, Platform] = {p.key: p for p in [
    _p("yandex", "Yandex Music", "", 0,
       r"https?://(?:[\w-]+\.)*music\.yandex\.(?:com|ru|by|kz)/(?:album|track)/[^\s.,]+"),
    _p("spotify", "Spotify", "", 1,
       r"https?://(?:[\w-]+\.)*(?:spotify\.com/(?:intl-\w+/)?(?:album|track|artist|playlist)/[^\s.,]+"
       r"|tospotify\.com/[^\s.,]+|spotify\.link/[^\s]+)"),
    _p("deezer", "Deezer", "", 2,
       r"https?://(?:[\w-]+\.)*deezer\.com(?:/\w\w)?/(?:album|track)/[^\s.,]+"
       r"|https?://deezer\.page\.link/[^\s.,]+"
       r"|https?://link\.deezer\.com/[^\s.,]+"),
    _p("appleMusic", "Apple Music", "", 3,
       r"https?://(?:[\w-]+\.)*music\.apple\.com/.*?/album/[^\s,.]+"),
    _p("youtubeMusic", "YouTube Music", "", 4,
       r"https?://(?:[\w-]+\.)*music\.youtube\.com/(?:watch|playlist)\?(?:v|list)=[^\s.,]+"),
    _p("tidal", "Tidal", "", 5,
       r"https?://(?:www\.|listen\.)?tidal\.com(?:/browse)?/(?:track|album)/\d+(?:/track/\d+)?"),
    _p("soundcloud", "SoundCloud", "☁️", 6,
       r"https?://(?:[\w-]+\.)*soundcloud\.(?:com|app\.goo\.gl)/[^\s.,]+"),
    _p("bandcamp", "Bandcamp", "", 7,
       r"https?://[^\s.,]+\.bandcamp\.com/(?:album|track)/[^\s.,]+"),
]}

# Combined pattern to detect any supported music URL - used by the dispatcher
MUSIC_URL_RE = re.compile(
    "|".join(p.url_re.pattern for p in PLATFORMS.values()),
    re.IGNORECASE,
)


def extract_music_urls(text: str) -> list[tuple[str, Platform]]:
    """Return [(url, platform), ...] for every music URL found in text."""
    results: list[tuple[str, Platform]] = []
    for platform in sorted(PLATFORMS.values(), key=lambda p: p.order):
        for m in platform.url_re.finditer(text):
            results.append((m.group(0), platform))
    # Deduplicate by URL preserving order
    seen: set[str] = set()
    deduped = []
    for url, plat in results:
        if url not in seen:
            seen.add(url)
            deduped.append((url, plat))
    return deduped
