from telegram import MessageEntity, User
from yoink_music.commands.inline import _make_artist_article, _make_track_article
from yoink_music.downloader import _requester_caption
from yoink_music.formatting import (
    add_requester_mention,
    format_artist_entities,
    format_track_entities,
)
from yoink_music.types import ArtistInfo, ArtistTrack, TrackInfo


def _assert_service_links(text, entities, expected):
    """Check the visible UTF-16 entity span, not just its hidden destination."""
    assert "https://" not in text
    assert " = " not in text
    assert all(entity.type != MessageEntity.CUSTOM_EMOJI for entity in entities)
    encoded = text.encode("utf-16-le")
    links = [entity for entity in entities if entity.type == MessageEntity.TEXT_LINK]
    assert [
        (encoded[entity.offset * 2:(entity.offset + entity.length) * 2].decode("utf-16-le"), entity.url)
        for entity in links
    ] == [(name, url) for _, name, url in expected]


def test_track_card_has_inline_clickable_platform_names_and_utf16_mentions():
    info = TrackInfo(
        title="Song",
        artist="🎵 Artist",
        thumbnail_url=None,
        source_url="https://open.spotify.com/track/1",
        links=[
            ("spotify", "Spotify", "https://open.spotify.com/track/1"),
            ("deezer", "Deezer", "https://deezer.com/track/1"),
        ],
    )

    text, entities = format_track_entities(info)
    text, entities = add_requester_mention(text, entities, User(7, "Actual", False, username="actual"))

    assert text == "🎵 Artist - Song\nSpotify | Deezer\nRequested by @actual"
    _assert_service_links(text, entities, info.links)
    links = [entity for entity in entities if entity.type == MessageEntity.TEXT_LINK]
    assert [(entity.offset, entity.url) for entity in links] == [
        (len("🎵 Artist - Song\n".encode("utf-16-le")) // 2, "https://open.spotify.com/track/1"),
        (len("🎵 Artist - Song\nSpotify | ".encode("utf-16-le")) // 2, "https://deezer.com/track/1"),
    ]
    mention = entities[-1]
    assert mention.type == MessageEntity.MENTION
    assert mention.offset == len("🎵 Artist - Song\nSpotify | Deezer\nRequested by ".encode("utf-16-le")) // 2


def test_track_service_row_matches_requested_layout_in_direct_and_inline_cards():
    platforms = [
        ("yandex", "Yandex Music"), ("spotify", "Spotify"), ("deezer", "Deezer"),
        ("youtubeMusic", "YouTube Music"), ("soundcloud", "SoundCloud"),
        ("appleMusic", "Apple Music"), ("qobuz", "Qobuz"),
    ]
    info = TrackInfo(
        title="Притча о шмеле", artist="Тот Самый", thumbnail_url=None,
        source_url="https://music.yandex.ru/track/example",
        links=[(key, name, f"https://example.com/{key}?a=1&b=2") for key, name in platforms],
    )
    expected = (
        "Тот Самый - Притча о шмеле\n"
        "Yandex Music | Spotify | Deezer | YouTube Music | SoundCloud | Apple Music | Qobuz"
    )
    text, entities = format_track_entities(info)
    assert text == expected
    _assert_service_links(text, entities, info.links)
    content = _make_track_article(info.source_url, info).input_message_content
    assert content.message_text == expected
    _assert_service_links(content.message_text, content.entities, info.links)


def test_artist_card_uses_one_platform_link_per_line_and_text_mention_fallback():
    info = ArtistInfo(
        name="Artist",
        genres=["indie pop", "dream pop"],
        thumbnail_url=None,
        source_url="https://open.spotify.com/artist/1",
        platform_links=[
            ("spotify", "Spotify", "https://open.spotify.com/artist/1"),
            ("yandex", "Yandex", "https://music.yandex.com/artist/1"),
        ],
        top_tracks=[ArtistTrack("Top Song", [("spotify", "Spotify", "https://open.spotify.com/track/2")])],
    )

    text, entities = format_artist_entities(info)
    requester = User(8, "Actual", False)
    text, entities = add_requester_mention(text, entities, requester)

    assert text == "Artist\nIndie Pop, Dream Pop\nSpotify\nYandex Music\n\n1. Top Song  Spotify\nRequested by Actual"
    _assert_service_links(text, entities, [
        info.platform_links[0],
        ("yandex", "Yandex Music", info.platform_links[1][2]),
        *info.top_tracks[0].links,
    ])
    mention = entities[-1]
    assert mention.type == MessageEntity.TEXT_MENTION
    assert mention.user.id == requester.id
    assert mention.offset == len("Artist\nIndie Pop, Dream Pop\nSpotify\nYandex Music\n\n1. Top Song  Spotify\nRequested by ".encode("utf-16-le")) // 2


def test_inline_track_article_mentions_the_querying_user():
    info = TrackInfo(
        title="Song",
        artist="Artist",
        thumbnail_url=None,
        source_url="https://open.spotify.com/track/1",
        links=[("spotify", "Spotify", "https://open.spotify.com/track/1")],
    )
    requester = User(10, "Query user", False, username="query_user")

    content = _make_track_article(info.source_url, info, requester).input_message_content

    assert content.message_text.endswith("Requested by @query_user")
    assert content.entities[-1].type == MessageEntity.MENTION
    _assert_service_links(content.message_text, content.entities, info.links)


def test_inline_artist_article_mentions_the_querying_user():
    info = ArtistInfo(
        name="Artist",
        genres=["indie pop"],
        thumbnail_url=None,
        source_url="https://open.spotify.com/artist/1",
        platform_links=[("qobuz", "Qobuz", "https://www.qobuz.com/artist/example")],
    )
    requester = User(11, "Query user", False, username="query_user")

    content = _make_artist_article(info.source_url, info, requester).input_message_content

    assert content.message_text.endswith("Requested by @query_user")
    _assert_service_links(content.message_text, content.entities, info.platform_links)
    mention = content.entities[-1]
    assert mention.type == MessageEntity.MENTION
    assert content.message_text[mention.offset:mention.offset + mention.length] == "@query_user"


def test_anonymous_requester_does_not_add_a_guessed_mention():
    assert add_requester_mention("Track", [], None) == ("Track", [])
    assert _requester_caption(None) == {}


def test_audio_caption_has_valid_requester_entity_offset():
    requester = User(9, "Listener", False, username="listener")
    caption = _requester_caption(requester)

    assert caption["caption"] == "Requested by @listener"
    mention = caption["caption_entities"][0]
    assert mention.offset == len("Requested by ".encode("utf-16-le")) // 2
    assert mention.type == MessageEntity.MENTION
    assert caption["caption"][mention.offset:mention.offset + mention.length] == "@listener"
