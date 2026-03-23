"""Apple Music search adapter - HTML scrape of music.apple.com/search."""
from __future__ import annotations

import logging
import re

import httpx

from yoink_music.utils import track_score

logger = logging.getLogger(__name__)

_MIN_SCORE = 0.5
_SONG_LINK_RE = re.compile(r'href="(https://music\.apple\.com/[^"]+/album/[^"]+\?i=\d+)"')


async def search(
    query: str,
    client: httpx.AsyncClient,
    title: str = "",
    artist: str = "",
) -> str | None:
    try:
        resp = await client.get(
            "https://music.apple.com/ca/search",
            params={"term": query},
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
        )
        resp.raise_for_status()
        links = _SONG_LINK_RE.findall(resp.text)
        seen: set[str] = set()
        unique = [l for l in links if not (l in seen or seen.add(l))]  # type: ignore[func-returns-value]
        if not unique:
            return None
        best_url, best_score = unique[0], 0.0
        for url in unique[:5]:
            # URL slug encodes album name, not track - use title slug only for title match
            slug = re.search(r"/album/([^/?]+)", url)
            c_title = slug.group(1).replace("-", " ") if slug else ""
            # No artist in the URL slug - compare title only, use 0.0 for artist
            s = track_score("", c_title, "", title) if title else 0.0
            logger.debug("Apple Music score=%.2f title=%r", s, c_title)
            if s > best_score:
                best_score, best_url = s, url
        # Lower threshold for Apple Music since we can only match on title slug
        return best_url if best_score >= 0.4 else None
    except Exception as exc:
        logger.debug("Apple Music search failed: %s", exc)
        return None
