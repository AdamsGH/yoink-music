"""Deezer parser - uses public Deezer API, no auth needed."""
from __future__ import annotations

import re
import logging

import httpx

from yoink_music.types import ResolverError

logger = logging.getLogger(__name__)

TRACK_RE = re.compile(r"deezer\.com/(?:[a-z]{2}/)?track/(\d+)")


async def parse(url: str, client: httpx.AsyncClient) -> tuple[str, str, str | None]:
    """Return (title, artist, thumbnail_url)."""
    m = TRACK_RE.search(url)
    if not m:
        raise ResolverError(f"Cannot extract Deezer track ID from {url}")
    track_id = m.group(1)

    resp = await client.get(f"https://api.deezer.com/track/{track_id}")
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise ResolverError(f"Deezer API error: {data['error']}")

    title = data.get("title") or ""
    artist = data.get("artist", {}).get("name") or ""
    thumbnail = data.get("album", {}).get("cover_medium")
    if not title:
        raise ResolverError("Deezer API returned empty title")
    return title, artist, thumbnail
