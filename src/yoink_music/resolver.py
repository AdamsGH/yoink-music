"""Central resolver: detect platform, parse metadata, search on others."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from yoink_music.types import ResolverError, TrackInfo
from yoink_music.utils import normalize_url

from yoink_music.parsers import apple_music as apple_music_parser
from yoink_music.parsers import deezer as deezer_parser
from yoink_music.parsers import soundcloud as soundcloud_parser
from yoink_music.parsers import spotify as spotify_parser
from yoink_music.parsers import yandex as yandex_parser
from yoink_music.parsers import ytmusic as ytmusic_parser
from yoink_music.parsers import youtube as youtube_parser

from yoink_music.adapters import apple_music as apple_music_adapter
from yoink_music.adapters import deezer as deezer_adapter
from yoink_music.adapters import soundcloud as soundcloud_adapter
from yoink_music.adapters import spotify as spotify_adapter
from yoink_music.adapters import yandex as yandex_adapter
from yoink_music.adapters import ytmusic as ytmusic_adapter

if TYPE_CHECKING:
    from yoink_music.config import MusicConfig

logger = logging.getLogger(__name__)

_DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


@dataclass
class _PlatformDef:
    key: str
    name: str
    url_re: object
    parser: object   # async (url, client) -> (title, artist, thumbnail)
    adapter: object  # async (query, client) -> url | None


def _build_platforms(cfg: "MusicConfig") -> list[_PlatformDef]:
    spotify_proxy = cfg.proxy_for("spotify")
    soundcloud_proxy = cfg.proxy_for("soundcloud")

    return [
        _PlatformDef(
            key="spotify",
            name="Spotify",
            url_re=spotify_parser.TRACK_RE,
            parser=lambda url, client: spotify_parser.parse(
                url, client,
                client_id=cfg.spotify_client_id,
                client_secret=cfg.spotify_client_secret,
                proxy=spotify_proxy,
            ),
            adapter=lambda query, client, **kw: spotify_adapter.search(
                query, client, proxy=spotify_proxy,
                client_id=cfg.spotify_client_id,
                client_secret=cfg.spotify_client_secret,
                **kw
            ),
        ),
        _PlatformDef(
            key="deezer",
            name="Deezer",
            url_re=deezer_parser.TRACK_RE,
            parser=deezer_parser.parse,
            adapter=deezer_adapter.search,
        ),
        _PlatformDef(
            key="yandex",
            name="Yandex Music",
            url_re=yandex_parser.TRACK_RE,
            parser=yandex_parser.parse,
            adapter=yandex_adapter.search,
        ),
        _PlatformDef(
            key="ytmusic",
            name="YouTube Music",
            url_re=ytmusic_parser.TRACK_RE,
            parser=ytmusic_parser.parse,
            adapter=ytmusic_adapter.search,
        ),
        _PlatformDef(
            key="soundcloud",
            name="SoundCloud",
            url_re=soundcloud_parser.TRACK_RE,
            parser=lambda url, client: soundcloud_parser.parse(
                url, _client_with_proxy(client, soundcloud_proxy),
            ),
            adapter=lambda query, client, **kw: soundcloud_adapter.search(
                query, _client_with_proxy(client, soundcloud_proxy), **kw
            ),
        ),
        _PlatformDef(
            key="apple_music",
            name="Apple Music",
            url_re=apple_music_parser.TRACK_RE,
            parser=apple_music_parser.parse,
            adapter=apple_music_adapter.search,
        ),
        # Regular YouTube - must come after ytmusic so music.youtube.com is
        # matched first. Parser uses yt-dlp and requires Music category.
        # No adapter: we don't want to add YouTube links in cross-platform search
        # results when the source is Spotify/Deezer/etc.
        _PlatformDef(
            key="youtube",
            name="YouTube",
            url_re=youtube_parser.TRACK_RE,
            parser=lambda url, client: youtube_parser.parse(
                url, client,
                proxy=cfg.proxy_for("youtube"),
            ),
            adapter=None,
        ),
    ]


def _client_with_proxy(base: httpx.AsyncClient, proxy: str | None) -> httpx.AsyncClient:
    """Return base client if no proxy needed, else a new client with proxy set."""
    if not proxy:
        return base
    return httpx.AsyncClient(
        proxy=proxy,
        timeout=base.timeout,
        follow_redirects=True,
        headers=dict(base.headers),
    )


class MusicResolver:
    def __init__(self, cfg: "MusicConfig") -> None:
        self._cfg = cfg
        self._platforms: list[_PlatformDef] = []
        self._cache: dict[str, tuple[TrackInfo, float]] = {}
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._platforms = _build_platforms(self._cfg)
        self._client = httpx.AsyncClient(
            timeout=self._cfg.request_timeout,
            follow_redirects=True,
            headers={"User-Agent": _DEFAULT_UA, "Accept-Language": "en-US,en;q=0.9"},
        )

    async def stop(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _detect(self, url: str) -> _PlatformDef | None:
        for p in self._platforms:
            if p.url_re.search(url):
                return p
        return None

    async def resolve(self, url: str) -> TrackInfo:
        norm = normalize_url(url)
        cached = self._cache.get(norm)
        if cached and time.monotonic() - cached[1] < self._cfg.cache_ttl:
            return cached[0]

        assert self._client is not None

        source = self._detect(norm)
        if source is None:
            raise ResolverError(f"Unsupported platform URL: {norm}")

        try:
            title, artist, thumbnail = await source.parser(norm, self._client)
        except ResolverError:
            raise
        except Exception as exc:
            raise ResolverError(f"Parser failed for {source.key}: {exc}") from exc

        # When artist is missing (Spotify oEmbed fallback), run adapters with
        # title-only query first, then recover artist from the best Deezer result.
        # This avoids _get_artist_hint which searches blindly and returns garbage.
        query = f"{artist} {title}".strip() if artist else title

        logger.info("Resolved %s: query=%r artist=%r", source.key, query, artist)

        other = [p for p in self._platforms if p.key != source.key and p.adapter is not None]
        tasks = {
            p.key: asyncio.create_task(
                p.adapter(query, self._client, title=title, artist=artist)
            )
            for p in other
        }
        results: dict[str, str | None] = {}
        for key, task in tasks.items():
            try:
                results[key] = await task
            except Exception as exc:
                logger.debug("Adapter %s failed: %s", key, exc)
                results[key] = None

        # If artist was unknown, recover it from a Deezer result found above.
        # Deezer public API lets us look up the track by ID from the URL.
        if not artist:
            deezer_url = results.get("deezer")
            if deezer_url:
                artist = await _artist_from_deezer_url(deezer_url, self._client)
                logger.debug("Recovered artist from Deezer result: %r", artist)

        links: list[tuple[str, str, str]] = [(source.key, source.name, url)]
        for p in self._platforms:
            if p.key == source.key:
                continue
            found = results.get(p.key)
            if found:
                links.append((p.key, p.name, found))

        info = TrackInfo(
            title=title,
            artist=artist,
            thumbnail_url=thumbnail,
            source_url=url,
            links=links,
        )
        self._cache[norm] = (info, time.monotonic())
        return info


async def _artist_from_deezer_url(deezer_url: str, client: httpx.AsyncClient) -> str:
    """Extract artist name by looking up the Deezer track ID from a found URL.

    Much more reliable than searching by title alone - we already know this is
    the correct track because the adapter matched it by title similarity.
    """
    m = re.search(r"/track/(\d+)", deezer_url)
    if not m:
        return ""
    try:
        resp = await client.get(
            f"https://api.deezer.com/track/{m.group(1)}",
            timeout=5,
        )
        data = resp.json()
        return data.get("artist", {}).get("name", "")
    except Exception:
        return ""
