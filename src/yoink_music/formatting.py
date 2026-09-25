"""Plain-text formatting and Telegram entities for music service cards."""
from __future__ import annotations

from typing import TYPE_CHECKING

from telegram import MessageEntity, User

if TYPE_CHECKING:
    from yoink_music.types import ArtistInfo, TrackInfo

_PLATFORM_NAMES: dict[str, str] = {
    "spotify": "Spotify",
    "yandex": "Yandex Music",
    "deezer": "Deezer",
    "youtubeMusic": "YouTube Music",
    "youtube": "YouTube",
    "ytmusic": "YouTube Music",
    "appleMusic": "Apple Music",
    "soundcloud": "SoundCloud",
}


def build_entities_text(
    segments: list[tuple[str, str | None, str | User | None]],
) -> tuple[str, list[MessageEntity]]:
    """Build text and Telegram entities with offsets measured in UTF-16 units."""
    text_parts: list[str] = []
    entities: list[MessageEntity] = []
    offset_utf16 = 0

    for seg_text, etype, extra in segments:
        length_utf16 = len(seg_text.encode("utf-16-le")) // 2
        if etype == "bold":
            entities.append(MessageEntity(type=MessageEntity.BOLD, offset=offset_utf16, length=length_utf16))
        elif etype == "italic":
            entities.append(MessageEntity(type=MessageEntity.ITALIC, offset=offset_utf16, length=length_utf16))
        elif etype == "text_link":
            assert isinstance(extra, str)
            entities.append(MessageEntity(type=MessageEntity.TEXT_LINK, offset=offset_utf16, length=length_utf16, url=extra))
        elif etype == "mention":
            entities.append(MessageEntity(type=MessageEntity.MENTION, offset=offset_utf16, length=length_utf16))
        elif etype == "text_mention":
            assert isinstance(extra, User)
            entities.append(MessageEntity(type=MessageEntity.TEXT_MENTION, offset=offset_utf16, length=length_utf16, user=extra))
        text_parts.append(seg_text)
        offset_utf16 += length_utf16

    return "".join(text_parts), entities


def add_requester_mention(
    text: str,
    entities: list[MessageEntity],
    requester: User | None,
) -> tuple[str, list[MessageEntity]]:
    """Append a mention of the actual requester, without guessing for anonymous users."""
    if requester is None:
        return text, entities

    if requester.username:
        mention_text = f"@{requester.username}"
        mention_type, mention_extra = "mention", None
    else:
        mention_text = requester.first_name or "Requester"
        mention_type, mention_extra = "text_mention", requester

    prefix = "\nRequested by " if text else "Requested by "
    suffix = f"{prefix}{mention_text}"
    mention_offset = len((text + prefix).encode("utf-16-le")) // 2
    mention_length = len(mention_text.encode("utf-16-le")) // 2
    mention = MessageEntity(
        type=MessageEntity.MENTION if mention_type == "mention" else MessageEntity.TEXT_MENTION,
        offset=mention_offset,
        length=mention_length,
        **({"user": mention_extra} if mention_type == "text_mention" else {}),
    )
    return text + suffix, [*entities, mention]


def _platform_segments(
    links: list[tuple[str, str, str]],
    separator: str = " | ",
) -> list[tuple[str, str | None, str | User | None]]:
    segments: list[tuple[str, str | None, str | User | None]] = []
    for index, (key, name, url) in enumerate(links):
        if index:
            segments.append((separator, None, None))
        segments.append((_PLATFORM_NAMES.get(key, name), "text_link", url))
    return segments


def format_track_entities(info: TrackInfo) -> tuple[str, list[MessageEntity]]:
    """Build a track card with clickable service names separated by pipes."""
    segments: list[tuple[str, str | None, str | User | None]] = []
    title = f"{info.artist} - {info.title}" if info.artist else info.title
    segments.append((title, "bold", None))
    if info.links:
        segments.append(("\n", None, None))
        segments.extend(_platform_segments(info.links))
    return build_entities_text(segments)


def format_artist_entities(info: ArtistInfo) -> tuple[str, list[MessageEntity]]:
    """Build an artist card with genres, top tracks, and clickable service links."""
    segments: list[tuple[str, str | None, str | User | None]] = [(info.name, "bold", None)]
    if info.genres:
        segments.append(("\n" + ", ".join(genre.title() for genre in info.genres), None, None))
    if info.platform_links:
        segments.append(("\n", None, None))
        segments.extend(_platform_segments(info.platform_links, separator="\n"))
    if info.top_tracks:
        segments.append(("\n", None, None))
        for index, track in enumerate(info.top_tracks, 1):
            if not track.title:
                continue
            segments.append(("\n", None, None))
            segments.append((f"{index}. {track.title}", None, None))
            if track.links:
                segments.append(("  ", None, None))
                segments.extend(_platform_segments(track.links))
    return build_entities_text(segments)
