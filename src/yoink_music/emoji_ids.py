"""Custom emoji IDs for music platform icons (pack: MusicServicesIcons).

Two usage modes:

1. HTML (platform_link): decorative icon + linked name as separate entities.
   custom_emoji and text_link cannot overlap, so icon is non-clickable.
   Use for regular bot messages (reply_text with parse_mode=HTML).

2. Entities (build_platform_entities): returns (plain_text, [MessageEntity]).
   Pass to InputTextMessageContent(entities=...) for inline results.
   Avoids HTML parse_mode so custom_emoji entity is exact.
"""
from __future__ import annotations

# Maps platform key -> (custom_emoji_id, fallback_emoji, display_name)
# fallback_emoji must be a single valid emoji character (from the sticker's emoji field)
PLATFORM_EMOJI: dict[str, tuple[str, str, str]] = {
    "yandex":       ("5346035579622560518", "1\ufe0f\u20e3", "Yandex Music"),
    "spotify":      ("5346061014418888371", "0\ufe0f\u20e3", "Spotify"),
    "deezer":       ("5346255134055764960", "2\ufe0f\u20e3", "Deezer"),
    "youtubeMusic": ("5345918683497664823", "3\ufe0f\u20e3", "YouTube Music"),
    "youtube":      ("5345918683497664823", "3\ufe0f\u20e3", "YouTube Music"),
    "ytmusic":      ("5345918683497664823", "3\ufe0f\u20e3", "YouTube Music"),
    "appleMusic":   ("5345784955395934957", "4\ufe0f\u20e3", "Apple Music"),
    "soundcloud":   ("5346074603695410935", "5\ufe0f\u20e3", "SoundCloud"),
}

_PLATFORM_NAMES: dict[str, str] = {
    "spotify":      "Spotify",
    "yandex":       "Yandex Music",
    "deezer":       "Deezer",
    "youtubeMusic": "YouTube Music",
    "youtube":      "YouTube Music",
    "ytmusic":      "YouTube Music",
    "appleMusic":   "Apple Music",
    "soundcloud":   "SoundCloud",
}


def platform_link(key: str, url: str) -> str:
    """Return decorative icon + linked platform name.

    custom_emoji and text_link cannot overlap — icon is non-clickable,
    name is the clickable link. Renders as: [icon][linked name]
    """
    entry = PLATFORM_EMOJI.get(key)
    name = _PLATFORM_NAMES.get(key, key)
    link = f'<a href="{url}">{name}</a>'
    if entry:
        eid, fallback, _ = entry
        return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji> {link}'
    return link


def build_entities_text(
    segments: list[tuple[str, str | None, str | None]],
) -> tuple[str, list]:
    """Build (plain_text, MessageEntity list) from segments.

    Each segment is (text, entity_type, extra) where:
    - entity_type=None: plain text
    - entity_type='bold'/'italic': formatting, extra=None
    - entity_type='text_link': extra=url
    - entity_type='custom_emoji': extra=emoji_id

    UTF-16 offsets are computed automatically.
    """
    from telegram import MessageEntity

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
            entities.append(MessageEntity(type=MessageEntity.TEXT_LINK, offset=offset_utf16, length=length_utf16, url=extra))
        elif etype == "custom_emoji":
            entities.append(MessageEntity(type=MessageEntity.CUSTOM_EMOJI, offset=offset_utf16, length=length_utf16, custom_emoji_id=extra))
        text_parts.append(seg_text)
        offset_utf16 += length_utf16

    return "".join(text_parts), entities


def _platform_segments(
    links: list[tuple[str, str, str]],
    separator: str = " | ",
    with_icons: bool = True,
) -> list[tuple[str, str | None, str | None]]:
    """Build entity segments for a list of (key, name, url) platform links."""
    segs: list[tuple[str, str | None, str | None]] = []
    for i, (key, name, url) in enumerate(links):
        if i > 0:
            segs.append((separator, None, None))
        if with_icons:
            entry = PLATFORM_EMOJI.get(key)
            if entry:
                eid, fallback, _ = entry
                segs.append((fallback, "custom_emoji", eid))
                segs.append((" ", None, None))
        display = _PLATFORM_NAMES.get(key, name)
        segs.append((display, "text_link", url))
    return segs


def format_track_entities(
    info,
    with_icons: bool = True,
) -> tuple[str, list]:
    """Build (text, entities) for a track card.

    with_icons=False for inline results (Telegram does not render custom_emoji
    in messages sent via inline query, even with Premium owner).
    """
    segs: list[tuple[str, str | None, str | None]] = []

    if info.thumbnail_url:
        segs.append(("\u200b", "text_link", info.thumbnail_url))

    if info.artist:
        segs.append((info.artist, "bold", None))
        segs.append((" - ", None, None))
        segs.append((info.title, None, None))
    else:
        segs.append((info.title, "bold", None))
    segs.append(("\n", None, None))
    segs.extend(_platform_segments(info.links, with_icons=with_icons))

    return build_entities_text(segs)


def format_artist_entities(
    info,
    with_icons: bool = True,
) -> tuple[str, list]:
    """Build (text, entities) for an artist card.

    with_icons=False for inline results.
    """
    segs: list[tuple[str, str | None, str | None]] = []

    segs.append((info.name, "bold", None))

    if info.platform_links:
        segs.append(("\n", None, None))
        for i, (key, name, url) in enumerate(info.platform_links):
            if i > 0:
                segs.append(("\n", None, None))
            if with_icons:
                entry = PLATFORM_EMOJI.get(key)
                if entry:
                    eid, fallback, _ = entry
                    segs.append((fallback, "custom_emoji", eid))
                    segs.append((" ", None, None))
            display = _PLATFORM_NAMES.get(key, name)
            segs.append((display, "text_link", url))

    if info.top_tracks:
        segs.append(("\n", None, None))
        for i, track in enumerate(info.top_tracks, 1):
            if not track.title:
                continue
            segs.append(("\n", None, None))
            segs.append((f"{i}. {track.title}", None, None))
            if track.links:
                segs.append(("  ", None, None))
                segs.extend(_platform_segments(track.links, with_icons=with_icons))

    return build_entities_text(segs)


def platform_button(key: str, url: str) -> dict:
    """Return InlineKeyboardButton dict with custom emoji icon + url."""
    entry = PLATFORM_EMOJI.get(key)
    name = _PLATFORM_NAMES.get(key, key)
    btn: dict = {"text": name, "url": url}
    if entry:
        eid, _, _ = entry
        btn["icon_custom_emoji_id"] = eid
    return btn
