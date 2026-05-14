"""SoundCloud search adapter - api-v2.soundcloud.com/search/tracks."""
from __future__ import annotations

import logging

import httpx

from yoink_music.parsers.soundcloud import _fetch_client_id, _make_session
from yoink_music.utils import track_score

logger = logging.getLogger(__name__)

_MIN_SCORE = 0.5


async def search(
    query: str,
    client: httpx.AsyncClient,
    title: str = "",
    artist: str = "",
    proxy: str | None = None,
) -> str | None:
    try:
        client_id = await _fetch_client_id(proxy)
        if not client_id:
            logger.debug("SoundCloud search: no client_id available")
            return None

        async with _make_session(proxy) as session:
            resp = await session.get(
                "https://api-v2.soundcloud.com/search/tracks",
                params={"q": query, "limit": "5", "client_id": client_id},
                allow_redirects=True,
                timeout=15,
            )
            if resp.status_code == 401:
                logger.debug("SoundCloud search: client_id expired")
                return None
            resp.raise_for_status()
            data = resp.json()

        items = data.get("collection", [])
        if not items:
            return None

        best_url: str | None = None
        best_score = 0.0
        for item in items:
            c_title = (item.get("title") or "").strip()
            c_artist = (item.get("user") or {}).get("username", "").strip()
            url = item.get("permalink_url", "")
            if not url:
                continue
            s = track_score(c_artist, c_title, artist, title)
            logger.debug("SoundCloud score=%.2f artist=%r title=%r", s, c_artist, c_title)
            if s > best_score:
                best_score, best_url = s, url

        return best_url if best_score >= _MIN_SCORE else None
    except Exception as exc:
        logger.debug("SoundCloud search failed: %s", exc)
        return None
