"""Yandex Music search adapter - unofficial yandex-music-api."""
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
        from yandex_music import ClientAsync
        yc = ClientAsync()
        await yc.init()
        # Yandex search quality is poor with freeform queries - "artist - title"
        # format significantly improves precision
        ym_query = f"{artist} - {title}" if artist and title else query
        results = await yc.search(ym_query, type_="track", page=0)
        if not results or not results.tracks or not results.tracks.results:
            return None
        for track in results.tracks.results[:5]:
            c_artist = ", ".join(a.name for a in (track.artists or []))
            c_title = track.title or ""
            s = track_score(c_artist, c_title, artist, title)
            logger.debug("Yandex score=%.2f artist=%r title=%r", s, c_artist, c_title)
            if s >= _MIN_SCORE and track.albums:
                return f"https://music.yandex.ru/album/{track.albums[0].id}/track/{track.id}"
        return None
    except ImportError:
        return None
    except Exception as exc:
        logger.debug("Yandex search failed: %s", exc)
        return None
