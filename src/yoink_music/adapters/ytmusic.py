"""YouTube Music search adapter - ytmusicapi, no API key."""
from __future__ import annotations

import logging

import httpx

from yoink_music.utils import track_score

logger = logging.getLogger(__name__)

_MIN_SCORE = 0.5


async def search(
    query: str,
    client: httpx.AsyncClient,
    title: str = "",
    artist: str = "",
) -> str | None:
    try:
        from ytmusicapi import YTMusic
        ytm = YTMusic()
        results = ytm.search(query, filter="songs", limit=5)
        if not results:
            return None
        for item in results:
            c_title = item.get("title", "")
            c_artist = " ".join(a.get("name", "") for a in item.get("artists", []))
            s = track_score(c_artist, c_title, artist, title)
            logger.debug("YTMusic score=%.2f artist=%r title=%r", s, c_artist, c_title)
            if s >= _MIN_SCORE:
                vid = item.get("videoId")
                if vid:
                    return f"https://music.youtube.com/watch?v={vid}"
        return None
    except ImportError:
        return None
    except Exception as exc:
        logger.debug("YTMusic search failed: %s", exc)
        return None
