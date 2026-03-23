"""MessageHandler: music link posted in chat -> platform card reply + optional audio."""
from __future__ import annotations

import asyncio
import logging

from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from yoink.core.bot.access import AccessPolicy, require_access
from yoink.core.db.models import UserRole
from yoink_music.config import MusicConfig
from yoink_music.platforms import extract_music_urls, MUSIC_URL_RE
from yoink_music.resolver import MusicResolver, ResolverError
from yoink_music.types import TrackInfo

_MUSIC_POLICY = AccessPolicy(
    min_role=UserRole.user,
    check_group_enabled=True,
    check_thread_policy=True,
    silent_deny=True,
)

logger = logging.getLogger(__name__)


def _format_reply(info: TrackInfo) -> str:
    """odesli-bot style: Artist - Title\nPlatform | Platform | ...

    Hidden thumbnail anchor at the start triggers Telegram link preview.
    """
    header = f"<b>{info.artist}</b> - {info.title}" if info.artist else f"<b>{info.title}</b>"
    link_parts = [f'<a href="{url}">{name}</a>' for _, name, url in info.links]
    links_line = " | ".join(link_parts)
    if info.thumbnail_url:
        hidden = f'<a href="{info.thumbnail_url}">&#8203;</a>'
        return f"{hidden}{header}\n{links_line}"
    return f"{header}\n{links_line}"


def _source_url_from_entities(msg: Message) -> str | None:
    """Extract the first music platform URL from TEXT_LINK entities.

    Used for via_bot messages where the URL is not in msg.text but in entities.
    Returns the first URL that matches a known music platform.
    """
    for entity in msg.entities or []:
        if entity.type.name == "TEXT_LINK" and entity.url:
            if MUSIC_URL_RE.search(entity.url):
                return entity.url
    return None


@require_access(_MUSIC_POLICY)
async def _handle_music_link(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle music URLs pasted directly in chat - send card + optional download."""
    msg: Message | None = update.effective_message
    if not msg:
        return

    text = msg.text or msg.caption or ""
    found = extract_music_urls(text)
    if not found:
        return

    resolver: MusicResolver | None = context.bot_data.get("music_resolver")
    if resolver is None:
        return

    cfg: MusicConfig | None = context.bot_data.get("music_config")
    file_cache = context.bot_data.get("file_cache")

    for url, _platform in found:
        try:
            info = await resolver.resolve(url)
        except ResolverError as exc:
            logger.warning("Resolve failed for %s: %s", url, exc)
            continue

        if not info.links:
            continue

        await msg.reply_text(
            _format_reply(info),
            parse_mode=ParseMode.HTML,
        )

        if cfg and cfg.download_enabled:
            from yoink_music import downloader
            if downloader.is_available():
                asyncio.create_task(_download_and_log(
                    context.bot, msg.chat_id, info, cfg,
                    reply_to_message_id=msg.message_id,
                    file_cache=file_cache,
                ))


@require_access(_MUSIC_POLICY)
async def _handle_inline_card(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle music cards sent via inline mode - download only, card already sent.

    When a user picks a result from @bot inline, Telegram sends a message with
    via_bot set. The card is already in chat - we only need to send the audio.
    """
    msg: Message | None = update.effective_message
    if not msg or not msg.via_bot:
        return
    if msg.via_bot.id != context.bot.id:
        return

    cfg: MusicConfig | None = context.bot_data.get("music_config")
    if not cfg or not cfg.download_enabled:
        return

    from yoink_music import downloader
    if not downloader.is_available():
        return

    source_url = _source_url_from_entities(msg)
    if not source_url:
        return

    resolver: MusicResolver | None = context.bot_data.get("music_resolver")
    if resolver is None:
        return

    try:
        info = await resolver.resolve(source_url)
    except ResolverError as exc:
        logger.warning("Resolve failed for inline card %s: %s", source_url, exc)
        return

    if not info.links:
        return

    file_cache = context.bot_data.get("file_cache")
    asyncio.create_task(_download_and_log(
        context.bot, msg.chat_id, info, cfg,
        reply_to_message_id=msg.message_id,
        file_cache=file_cache,
    ))


async def _download_and_log(bot, chat_id, info, cfg, *, reply_to_message_id, file_cache):
    """Wrapper that logs any unhandled exception from the download task."""
    try:
        from yoink_music import downloader
        await downloader.send_track(
            bot, chat_id, info, cfg,
            reply_to_message_id=reply_to_message_id,
            file_cache=file_cache,
        )
    except Exception as exc:
        logger.exception("Unhandled error in music download task for %r: %s", info.title, exc)


def register(app: Application) -> None:
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            _handle_music_link,
        ),
        group=5,
    )
    # group=-1: run before all other handlers to catch via_bot music cards
    app.add_handler(
        MessageHandler(
            filters.VIA_BOT & filters.TEXT,
            _handle_inline_card,
        ),
        group=-1,
    )
