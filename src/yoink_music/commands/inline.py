"""Inline handler for music links: @bot <music_url>."""
from __future__ import annotations

import hashlib
import logging

from telegram import (
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultsButton,
    InputTextMessageContent,
    LinkPreviewOptions,
)
from telegram.ext import ContextTypes

from yoink_music.emoji_ids import _PLATFORM_NAMES, format_artist_entities, format_track_entities
from yoink_music.parsers.artist import SPOTIFY_ARTIST_RE, resolve_spotify_artist
from yoink_music.parsers.youtube import TRACK_RE as YOUTUBE_RE
from yoink_music.platforms import MUSIC_URL_RE, extract_music_urls
from yoink_music.resolver import MusicResolver, ResolverError
from yoink_music.types import ArtistInfo, TrackInfo

logger = logging.getLogger(__name__)


def _result_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


async def handle_inline(
    inline_query: InlineQuery,
    context: ContextTypes.DEFAULT_TYPE,
    query_text: str,
) -> bool:
    if not query_text:
        await inline_query.answer(
            [],
            cache_time=0,
            is_personal=True,
            button=InlineQueryResultsButton(
                text="Paste a music link (Spotify, YM, Deezer, ...)",
                start_parameter="music_help",
            ),
        )
        return True

    if MUSIC_URL_RE.search(query_text):
        return await _handle_music_url(inline_query, context, query_text)

    if YOUTUBE_RE.search(query_text):
        return await _handle_youtube_url(inline_query, context, query_text)

    return False


async def _handle_music_url(
    inline_query: InlineQuery,
    context: ContextTypes.DEFAULT_TYPE,
    query_text: str,
) -> bool:
    found = extract_music_urls(query_text)
    if not found:
        return False

    cfg = context.bot_data.get("music_config")
    resolver: MusicResolver | None = context.bot_data.get("music_resolver")
    if resolver is None:
        return False

    results = []
    for url, platform in found:
        if SPOTIFY_ARTIST_RE.search(url):
            try:
                artist_info = await resolve_spotify_artist(
                    url,
                    resolver._client,
                    client_id=cfg.spotify_client_id if cfg else None,
                    client_secret=cfg.spotify_client_secret if cfg else None,
                    proxy=cfg.proxy_for("spotify") if cfg else None,
                )
                results.append(_make_artist_article(url, artist_info))
            except ResolverError as exc:
                logger.warning("Artist resolve failed for %s: %s", url, exc)
            continue

        try:
            info = await resolver.resolve(url)
        except ResolverError as exc:
            logger.warning("Resolve failed for %s: %s", url, exc)
            await inline_query.answer(
                [],
                cache_time=0,
                is_personal=True,
                button=InlineQueryResultsButton(
                    text="Could not fetch track info, try again",
                    start_parameter="music_help",
                ),
            )
            return True

        if not info.links:
            continue

        results.append(_make_track_article(url, info))

    if not results:
        await inline_query.answer(
            [],
            cache_time=30,
            is_personal=True,
            button=InlineQueryResultsButton(
                text="No platform links found for this track",
                start_parameter="music_help",
            ),
        )
        return True

    await inline_query.answer(results, cache_time=300, is_personal=True)
    return True


async def _handle_youtube_url(
    inline_query: InlineQuery,
    context: ContextTypes.DEFAULT_TYPE,
    query_text: str,
) -> bool:
    resolver: MusicResolver | None = context.bot_data.get("music_resolver")
    if resolver is None:
        return False

    m = YOUTUBE_RE.search(query_text)
    if not m:
        return False
    url_str = m.group(0)

    try:
        info = await resolver.resolve(url_str)
    except ResolverError as exc:
        logger.debug("YouTube URL not a music track (%s): %s", url_str, exc)
        return False

    if not info.links:
        return False

    await inline_query.answer(
        [_make_track_article(url_str, info)],
        cache_time=300,
        is_personal=True,
    )
    return True


def _make_track_article(url: str, info: TrackInfo) -> InlineQueryResultArticle:
    text, entities = format_track_entities(info, with_icons=False)
    card_title = f"{info.artist} - {info.title}" if info.artist else info.title
    platform_names = " | ".join(_PLATFORM_NAMES.get(k, n) for k, n, _ in info.links)
    preview = None
    if info.thumbnail_url:
        preview = LinkPreviewOptions(
            url=info.thumbnail_url,
            show_above_text=True,
            prefer_large_media=True,
        )
    return InlineQueryResultArticle(
        id=_result_id(url),
        title=card_title,
        description=platform_names,
        thumbnail_url=info.thumbnail_url,
        input_message_content=InputTextMessageContent(
            message_text=text,
            entities=entities,
            link_preview_options=preview,
        ),
    )


def _make_artist_article(url: str, info: ArtistInfo) -> InlineQueryResultArticle:
    text, entities = format_artist_entities(info, with_icons=False)
    platform_names = " | ".join(_PLATFORM_NAMES.get(k, n) for k, n, _ in info.platform_links)
    genres_str = ", ".join(g.title() for g in info.genres[:2])
    description = f"{genres_str}  {platform_names}" if genres_str else platform_names
    preview = None
    if info.thumbnail_url:
        preview = LinkPreviewOptions(
            url=info.thumbnail_url,
            show_above_text=True,
            prefer_large_media=True,
        )
    return InlineQueryResultArticle(
        id=_result_id(url),
        title=info.name,
        description=description or "Artist",
        thumbnail_url=info.thumbnail_url,
        input_message_content=InputTextMessageContent(
            message_text=text,
            entities=entities,
            link_preview_options=preview,
        ),
    )
