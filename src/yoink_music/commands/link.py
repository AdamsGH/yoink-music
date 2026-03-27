"""MessageHandler: music link posted in chat -> platform card reply + optional audio."""
from __future__ import annotations

import asyncio
import logging
import re

from telegram import LinkPreviewOptions, Message, Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from yoink.core.bot.access import AccessPolicy, require_access
from yoink.core.db.models import UserRole
from yoink_music.emoji_ids import format_artist_entities, format_track_entities
from yoink_music.config import MusicConfig
from yoink_music.parsers.artist import SPOTIFY_ARTIST_RE, resolve_spotify_artist
from yoink_music.platforms import MUSIC_URL_RE, extract_music_urls
from yoink_music.resolver import MusicResolver, ResolverError
from yoink_music.types import ArtistInfo, TrackInfo

_MUSIC_POLICY = AccessPolicy(
    min_role=UserRole.user,
    check_group_enabled=True,
    check_thread_policy=True,
    silent_deny=True,
)

logger = logging.getLogger(__name__)

_PLAYLIST_RE = re.compile(
    r"spotify\.com/(?:intl-[a-z]+/)?playlist/", re.IGNORECASE
)


def _source_url_from_entities(msg: Message) -> str | None:
    """Extract the first music platform URL from TEXT_LINK entities."""
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
        if _PLAYLIST_RE.search(url):
            logger.debug("Skipping Spotify playlist URL: %s", url)
            continue

        if SPOTIFY_ARTIST_RE.search(url):
            await _handle_artist_url(msg, url, resolver, cfg)
            continue

        try:
            info = await resolver.resolve(url, user_id=update.effective_user.id if update.effective_user else None)
        except ResolverError as exc:
            logger.warning("Resolve failed for %s: %s", url, exc)
            continue

        if not info.links:
            continue

        text_out, entities = format_track_entities(info)
        preview = None
        if info.thumbnail_url:
            preview = LinkPreviewOptions(
                url=info.thumbnail_url,
                show_above_text=True,
                prefer_large_media=True,
            )
        await msg.reply_text(
            text_out,
            entities=entities,
            link_preview_options=preview,
        )

        if cfg and cfg.download_enabled:
            from yoink_music import downloader
            if downloader.is_available():
                asyncio.create_task(_download_and_log(
                    context.bot, msg.chat_id, info, cfg,
                    reply_to_message_id=msg.message_id,
                    file_cache=file_cache,
                ))


async def _handle_artist_url(
    msg: Message,
    url: str,
    resolver: MusicResolver,
    cfg: MusicConfig | None,
) -> None:
    try:
        info = await resolve_spotify_artist(
            url,
            resolver._client,
            client_id=cfg.spotify_client_id if cfg else None,
            client_secret=cfg.spotify_client_secret if cfg else None,
            proxy=cfg.proxy_for("spotify") if cfg else None,
        )
    except ResolverError as exc:
        logger.warning("Artist resolve failed for %s: %s", url, exc)
        return

    text_out, entities = format_artist_entities(info)
    preview = None
    if info.thumbnail_url:
        preview = LinkPreviewOptions(
            url=info.thumbnail_url,
            show_above_text=True,
            prefer_large_media=True,
        )
    await msg.reply_text(
        text_out,
        entities=entities,
        link_preview_options=preview,
    )


@require_access(_MUSIC_POLICY)
async def _handle_inline_card(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle music cards sent via inline mode - download only, card already sent."""
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

    if SPOTIFY_ARTIST_RE.search(source_url):
        return

    resolver: MusicResolver | None = context.bot_data.get("music_resolver")
    if resolver is None:
        return

    try:
        info = await resolver.resolve(source_url, user_id=update.effective_user.id if update.effective_user else None)
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
    app.add_handler(
        MessageHandler(
            filters.VIA_BOT & filters.TEXT,
            _handle_inline_card,
        ),
        group=-1,
    )
