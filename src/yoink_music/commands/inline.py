"""Inline handler for music links: @bot <music_url>."""
from __future__ import annotations

import hashlib
import logging

from telegram import (
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultsButton,
    InputTextMessageContent,
)
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from yoink_music.parsers.youtube import TRACK_RE as YOUTUBE_RE
from yoink_music.platforms import MUSIC_URL_RE, extract_music_urls
from yoink_music.resolver import MusicResolver, ResolverError
from yoink_music.types import TrackInfo

logger = logging.getLogger(__name__)


def _result_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _format_links(info: TrackInfo) -> tuple[str, str]:
    """Return (message_text, description) in odesli-bot style.

    message_text: Artist - Title\nPlatform | Platform | ...
    """
    header = f"<b>{info.artist}</b> - {info.title}" if info.artist else f"<b>{info.title}</b>"
    link_parts = [f'<a href="{url}">{name}</a>' for _, name, url in info.links]
    links_line = " | ".join(link_parts)
    if info.thumbnail_url:
        hidden = f'<a href="{info.thumbnail_url}">&#8203;</a>'
        message_text = f"{hidden}{header}\n{links_line}"
    else:
        message_text = f"{header}\n{links_line}"

    platform_names = " | ".join(name for _, name, _ in info.links)
    return message_text, platform_names


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

    # Try known music platform URLs first
    if MUSIC_URL_RE.search(query_text):
        return await _handle_music_url(inline_query, context, query_text)

    # Try plain YouTube URL - may be a music video; resolver will reject non-Music
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

    resolver: MusicResolver | None = context.bot_data.get("music_resolver")
    if resolver is None:
        return False

    results = []
    for url, platform in found:
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

        results.append(_make_article(url, info))

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
    """Try to resolve a plain YouTube URL as a music track.

    Returns False if the video is not in the Music category so yoink-dl
    can handle it as a regular video download.
    """
    resolver: MusicResolver | None = context.bot_data.get("music_resolver")
    if resolver is None:
        return False

    url = YOUTUBE_RE.search(query_text)
    if not url:
        return False
    url_str = url.group(0)

    try:
        info = await resolver.resolve(url_str)
    except ResolverError as exc:
        # Not a Music category video - let yoink-dl handle it
        logger.debug("YouTube URL not a music track (%s): %s", url_str, exc)
        return False

    if not info.links:
        return False

    await inline_query.answer(
        [_make_article(url_str, info)],
        cache_time=300,
        is_personal=True,
    )
    return True


def _make_article(url: str, info: TrackInfo) -> InlineQueryResultArticle:
    message_text, description = _format_links(info)
    card_title = f"{info.artist} - {info.title}" if info.artist else info.title
    return InlineQueryResultArticle(
        id=_result_id(url),
        title=card_title,
        description=description,
        thumbnail_url=info.thumbnail_url,
        input_message_content=InputTextMessageContent(
            message_text=message_text,
            parse_mode=ParseMode.HTML,
        ),
    )
