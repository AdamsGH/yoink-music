"""Music download orchestration for yoink-music.

Bridges yoink-music (resolver, metadata) with yoink-dl (yt-dlp pipeline).
Import is optional - if yoink-dl is not installed, is_available() returns False
and the music plugin simply skips the download step.

Flow:
  1. Find a YouTube Music URL from TrackInfo.links, or search via ytmusicapi
  2. Fallback: YouTube search via yt-dlp ytsearch
  3. Check file_id cache (yoink-dl FileCacheRepo) - send instantly if hit
  4. Download MP3 via yoink-dl download/music.py
  5. Embed ID3 tags (title, artist, cover art)
  6. send_audio, store file_id in cache
  7. Cleanup tmpdir
"""
from __future__ import annotations

import logging
import shutil
from typing import TYPE_CHECKING

from telegram import Bot
from telegram.constants import ParseMode

if TYPE_CHECKING:
    from yoink_music.types import TrackInfo
    from yoink_music.config import MusicConfig

logger = logging.getLogger(__name__)


def is_available() -> bool:
    """Return True if yoink-dl download pipeline is available."""
    try:
        from yoink_dl.download.music import download_track  # noqa: F401
        return True
    except ImportError:
        return False


async def send_track(
    bot: Bot,
    chat_id: int,
    info: "TrackInfo",
    cfg: "MusicConfig",
    *,
    reply_to_message_id: int | None = None,
    file_cache=None,
) -> bool:
    """Download and send the track as an audio message.

    Returns True if the audio was sent, False on any failure.
    The link card is always sent first by the caller - this only handles audio.
    """
    try:
        from yoink_dl.download.music import (
            download_track,
            embed_tags,
            make_music_cache_key,
            MusicDownloadError,
            TrackTooLargeError,
        )
    except ImportError:
        logger.debug("yoink-dl not available, skipping music download")
        return False

    cache_key = make_music_cache_key(info.artist or "", info.title)

    # Check file_id cache first
    if file_cache is not None:
        cached = await file_cache.get(cache_key)
        if cached:
            logger.info("Music cache hit for %r by %r", info.title, info.artist)
            await bot.send_audio(
                chat_id=chat_id,
                audio=cached.file_id,
                reply_to_message_id=reply_to_message_id,
            )
            return True

    proxy = cfg.proxy_for("ytmusic") or cfg.proxy_for("spotify")

    direct = _find_youtube_url(info)
    searched: str | None = None

    # Build candidate list lazily - try direct first, search on failure
    direct_tried = set()
    candidates: list[str] = []
    if direct:
        candidates.append(direct)
        direct_tried.add(direct)

    if not candidates:
        # No direct link at all - search immediately
        found = await _search_ytsearch(info)
        if found:
            candidates.append(found)

    if not candidates:
        logger.info("No YouTube URL found for %r by %r, skipping download", info.title, info.artist)
        return False

    for yt_url in candidates:
        result = None
        try:
            logger.info("Downloading music: %r by %r from %s", info.title, info.artist, yt_url)
            result = await download_track(yt_url, proxy=proxy)
            embed_tags(
                result.path,
                title=info.title,
                artist=info.artist or "",
                thumbnail_url=info.thumbnail_url,
            )
            with result.path.open("rb") as f:
                msg = await bot.send_audio(
                    chat_id=chat_id,
                    audio=f,
                    title=info.title,
                    performer=info.artist or None,
                    duration=int(result.duration) if result.duration else None,
                    thumbnail=await _fetch_thumbnail(info.thumbnail_url) if info.thumbnail_url else None,
                    reply_to_message_id=reply_to_message_id,
                )
            if file_cache is not None and msg.audio:
                await file_cache.put(
                    cache_key,
                    file_id=msg.audio.file_id,
                    file_type="audio",
                    title=f"{info.artist} - {info.title}" if info.artist else info.title,
                    duration=result.duration,
                )
            return True
        except TrackTooLargeError:
            logger.info("Track too large: %r", info.title)
            return False
        except MusicDownloadError as exc:
            logger.warning("Music download failed for %r from %s: %s — trying next", info.title, yt_url, exc)
            # Append fallback search results on first failure
            if len(candidates) == 1:
                for url in await _search_all(info):
                    if url not in direct_tried:
                        candidates.append(url)
        except Exception as exc:
            logger.warning("Unexpected error for %r from %s: %s — trying next", info.title, yt_url, exc)
        finally:
            if result is not None:
                try:
                    shutil.rmtree(result.path.parent, ignore_errors=True)
                except Exception:
                    pass

    logger.info("All sources exhausted for %r by %r", info.title, info.artist)
    return False


def _find_youtube_url(info: "TrackInfo") -> str | None:
    """Return the first YouTube Music or YouTube URL from resolved links."""
    for key, _name, url in info.links:
        if key == "ytmusic":
            return url
    for _key, _name, url in info.links:
        if "youtube.com" in url or "youtu.be" in url:
            return url
    return None


async def _search_ytmusic(info: "TrackInfo") -> str | None:
    """Search YouTube Music via ytmusicapi."""
    query = f"{info.artist} {info.title}".strip() if info.artist else info.title
    try:
        from ytmusicapi import YTMusic
        import asyncio
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(
            None,
            lambda: YTMusic().search(query, filter="songs", limit=1),
        )
        if results:
            vid = results[0].get("videoId")
            if vid:
                return f"https://music.youtube.com/watch?v={vid}"
    except Exception as exc:
        logger.debug("YTMusic search failed: %s", exc)
    return None


async def _search_ytsearch(info: "TrackInfo") -> str | None:
    """Search regular YouTube via yt-dlp ytsearch."""
    query = f"{info.artist} {info.title}".strip() if info.artist else info.title
    try:
        import asyncio
        import yt_dlp
        loop = asyncio.get_running_loop()

        def _search():
            with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
                info_dict = ydl.extract_info(f"ytsearch1:{query}", download=False)
            entries = (info_dict or {}).get("entries") or []
            return entries[0].get("url") or entries[0].get("webpage_url") if entries else None

        return await loop.run_in_executor(None, _search)
    except Exception as exc:
        logger.debug("yt-dlp ytsearch failed: %s", exc)
    return None


async def _search_all(info: "TrackInfo") -> list[str]:
    """Return all search candidates: ytmusicapi result + ytsearch result."""
    results: list[str] = []
    ytm = await _search_ytmusic(info)
    if ytm:
        results.append(ytm)
    yts = await _search_ytsearch(info)
    if yts and yts not in results:
        results.append(yts)
    return results


async def _fetch_thumbnail(url: str):
    """Fetch thumbnail as InputFile for send_audio thumbnail param."""
    try:
        import io
        import httpx
        from telegram import InputFile
        resp = await httpx.AsyncClient().get(url, timeout=5, follow_redirects=True)
        if resp.status_code == 200:
            return InputFile(io.BytesIO(resp.content), filename="cover.jpg")
    except Exception:
        pass
    return None
