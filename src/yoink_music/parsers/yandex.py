"""Yandex Music parser - uses unofficial yandex-music-api."""
from __future__ import annotations

import re
import logging

import httpx

from yoink_music.types import ResolverError

logger = logging.getLogger(__name__)

TRACK_RE = re.compile(r"music\.yandex\.[a-z]+/album/(\d+)/track/(\d+)")


async def parse(url: str, client: httpx.AsyncClient) -> tuple[str, str, str | None]:
    """Return (title, artist, thumbnail_url)."""
    m = TRACK_RE.search(url)
    if not m:
        raise ResolverError(f"Cannot extract Yandex Music track ID from {url}")
    album_id, track_id = m.group(1), m.group(2)

    try:
        from yandex_music import ClientAsync
        yc = ClientAsync()
        await yc.init()
        tracks = await yc.tracks([f"{track_id}:{album_id}"])
    except ImportError:
        raise ResolverError("yandex-music not installed")
    except Exception as exc:
        raise ResolverError(f"Yandex Music API failed: {exc}") from exc

    if not tracks:
        raise ResolverError("Yandex Music: track not found")

    track = tracks[0]
    title = track.title or ""
    artist = ", ".join(a.name for a in (track.artists or []))
    thumbnail: str | None = None
    if track.cover_uri:
        thumbnail = "https://" + track.cover_uri.replace("%%", "400x400")
    return title, artist, thumbnail
