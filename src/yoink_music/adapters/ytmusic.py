"""YouTube Music search adapter - ytmusicapi with ytsearch fallback."""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

import httpx

from yoink_music.utils import track_score

logger = logging.getLogger(__name__)

_MIN_SCORE = 0.6
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ytmusic")


async def search(
    query: str,
    client: httpx.AsyncClient,
    title: str = "",
    artist: str = "",
) -> str | None:
    result = await _search_ytmusicapi(query, title=title, artist=artist)
    if result:
        return result
    logger.info("YTMusic API found nothing for %r, falling back to ytsearch", query)
    return await _search_ytsearch(query, title=title, artist=artist)


async def _search_ytmusicapi(
    query: str,
    title: str = "",
    artist: str = "",
) -> str | None:
    try:
        from ytmusicapi import YTMusic
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            _executor,
            lambda: YTMusic().search(query, filter="songs", limit=10),
        )
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
        logger.debug("YTMusic API search failed: %s", exc)
        return None


async def _search_ytsearch(
    query: str,
    title: str = "",
    artist: str = "",
) -> str | None:
    """Fallback: yt-dlp ytsearch on regular YouTube, score candidates.

    Returns a music.youtube.com link so it still shows as YouTube Music
    in the card - the video is playable from either domain.
    """
    try:
        import yt_dlp
        loop = asyncio.get_running_loop()

        def _search():
            with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
                info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            return (info or {}).get("entries", [])

        entries = await loop.run_in_executor(_executor, _search)
        best_url, best_score = None, 0.0
        for entry in entries:
            vid = entry.get("id") or entry.get("url", "").split("v=")[-1].split("&")[0]
            raw_title = entry.get("title", "")
            c_channel = entry.get("channel") or entry.get("uploader", "")
            # YouTube video titles are often "Artist - Track Title (suffix)"
            # Try splitting on " - " and score both interpretations, take the best.
            c_title, c_artist = raw_title, c_channel
            if " - " in raw_title:
                parts = raw_title.split(" - ", 1)
                c_artist_from_title = parts[0].strip()
                c_title_from_title = parts[1].strip()
                s_split = track_score(c_artist_from_title, c_title_from_title, artist, title)
                s_raw = track_score(c_channel, raw_title, artist, title)
                if s_split >= s_raw:
                    c_artist, c_title = c_artist_from_title, c_title_from_title
            s = track_score(c_artist, c_title, artist, title)
            logger.debug("ytsearch score=%.2f artist=%r title=%r", s, c_artist, c_title)
            if s > best_score:
                best_score = s
                best_url = f"https://music.youtube.com/watch?v={vid}" if vid else None
        if best_score >= _MIN_SCORE and best_url:
            logger.info("ytsearch fallback hit: score=%.2f url=%s", best_score, best_url)
            return best_url
        logger.info("ytsearch fallback: best score %.2f below threshold", best_score)
        return None
    except Exception as exc:
        logger.warning("ytsearch fallback failed: %s", exc)
        return None
