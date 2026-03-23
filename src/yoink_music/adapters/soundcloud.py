"""SoundCloud search adapter - HTML scrape."""
from __future__ import annotations

import logging
import re

import httpx

from yoink_music.utils import track_score

logger = logging.getLogger(__name__)

_MIN_SCORE = 0.5
_TRACK_RE = re.compile(r'"permalink_url"\s*:\s*"(https://soundcloud\.com/[^"]+)"')


async def search(
    query: str,
    client: httpx.AsyncClient,
    title: str = "",
    artist: str = "",
) -> str | None:
    try:
        resp = await client.get(
            "https://soundcloud.com/search/sounds",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        urls = _TRACK_RE.findall(resp.text)
        if not urls:
            return None
        # SoundCloud URLs encode artist/title as /artist/title slugs
        best_url, best_score = urls[0], 0.0
        for url in urls[:5]:
            parts = url.rstrip("/").rsplit("/", 2)
            c_artist = parts[-2].replace("-", " ") if len(parts) >= 2 else ""
            c_title = parts[-1].replace("-", " ") if len(parts) >= 1 else ""
            s = track_score(c_artist, c_title, artist, title)
            logger.debug("SoundCloud score=%.2f artist=%r title=%r", s, c_artist, c_title)
            if s > best_score:
                best_score, best_url = s, url
        return best_url if best_score >= _MIN_SCORE else None
    except Exception as exc:
        logger.debug("SoundCloud search failed: %s", exc)
        return None
