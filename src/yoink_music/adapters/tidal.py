"""Tidal search adapter - official API with OAuth2 client_credentials."""
from __future__ import annotations

import asyncio
import logging
import time

import httpx

from yoink_music.utils import track_score

logger = logging.getLogger(__name__)

_MIN_SCORE = 0.6

_token_cache: tuple[str, float] = ("", 0.0)
_token_lock = asyncio.Lock()


async def get_access_token(client: httpx.AsyncClient, client_id: str, client_secret: str) -> str:
    global _token_cache
    token, expires_at = _token_cache
    if token and time.monotonic() < expires_at - 60:
        return token

    async with _token_lock:
        token, expires_at = _token_cache
        if token and time.monotonic() < expires_at - 60:
            return token

        resp = await client.post(
            "https://auth.tidal.com/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        data = resp.json()
        token = data["access_token"]
        expires_at = time.monotonic() + data.get("expires_in", 86400)
        _token_cache = (token, expires_at)
        logger.debug("Tidal: fetched new access token (expires_in=%s)", data.get("expires_in"))
        return token


async def search(
    query: str,
    client: httpx.AsyncClient,
    title: str = "",
    artist: str = "",
    client_id: str = "",
    client_secret: str = "",
) -> str | None:
    if not client_id or not client_secret:
        return None
    try:
        token = await get_access_token(client, client_id, client_secret)

        import urllib.parse
        encoded_query = urllib.parse.quote(query, safe="")
        resp = await client.get(
            f"https://openapi.tidal.com/v2/searchResults/{encoded_query}/relationships/tracks",
            params={"countryCode": "US", "include": "tracks"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        data = resp.json()

        # data[] has id+type refs, included[] has attributes
        refs = data.get("data", [])
        included = data.get("included", [])
        if not refs or not included:
            return None

        best_url: str | None = None
        best_score = 0.0
        for ref, item in zip(refs[:5], included[:5]):
            attrs = item.get("attributes", {})
            c_title = (attrs.get("title") or "").strip()
            c_artist = (attrs.get("artistName") or attrs.get("artist") or "").strip()
            track_id = ref.get("id", "")
            url = f"https://listen.tidal.com/track/{track_id}"
            s = track_score(c_artist, c_title, artist, title)
            logger.debug("Tidal score=%.2f artist=%r title=%r", s, c_artist, c_title)
            if s > best_score:
                best_score, best_url = s, url

        return best_url if best_score >= _MIN_SCORE else None
    except Exception as exc:
        logger.debug("Tidal search failed: %s", exc)
        return None
