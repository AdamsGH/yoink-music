"""SoundCloud parser - og-tags scrape."""
from __future__ import annotations

import re
import logging

import httpx

from yoink_music.types import ResolverError

logger = logging.getLogger(__name__)

# soundcloud.com/<artist>/<track>
TRACK_RE = re.compile(r"soundcloud\.com/([\w-]+)/([\w-]+)(?:[?#]|$)")


async def parse(url: str, client: httpx.AsyncClient) -> tuple[str, str, str | None]:
    """Return (title, artist, thumbnail_url) by scraping og-tags."""
    resp = await client.get(url)
    resp.raise_for_status()
    html = resp.text

    def og(prop: str) -> str | None:
        m = re.search(
            rf'<meta[^>]+property=["\']og:{prop}["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE,
        ) or re.search(
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:{prop}["\']',
            html, re.IGNORECASE,
        )
        return m.group(1) if m else None

    title_raw = og("title") or ""
    description = og("description") or ""
    thumbnail = og("image")

    if not title_raw:
        raise ResolverError(f"SoundCloud: could not extract og:title from {url}")

    # og:title format: "Artist - Track Title" or just "Track Title"
    if " - " in title_raw:
        artist, _, title = title_raw.partition(" - ")
    else:
        title = title_raw
        # Try to extract artist from description: "Listen to Artist · ..."
        m = re.match(r"Listen to (.+?)\s*[·|]", description)
        artist = m.group(1) if m else ""

    return title.strip(), artist.strip(), thumbnail
