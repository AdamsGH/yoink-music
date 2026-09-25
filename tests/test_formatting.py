from telegram import MessageEntity, User
from yoink_music.commands.inline import _make_artist_article, _make_track_article
from yoink_music.downloader import _requester_caption
from yoink_music.formatting import (
    add_requester_mention,
    format_artist_entities,
    format_track_entities,
)
from yoink_music.types import ArtistInfo, ArtistTrack, TrackInfo


def test_track_card_has_one_clickable_platform_per_line_and_utf16_mentions():
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

    assert text == "🎵 Artist - Song\nSpotify = https://open.spotify.com/track/1\nDeezer = https://deezer.com/track/1\nRequested by @actual"
    links = [entity for entity in entities if entity.type == MessageEntity.TEXT_LINK]
    assert [(entity.offset, entity.url) for entity in links] == [
        (len("🎵 Artist - Song\nSpotify = ".encode("utf-16-le")) // 2, "https://open.spotify.com/track/1"),
        (len("🎵 Artist - Song\nSpotify = https://open.spotify.com/track/1\nDeezer = ".encode("utf-16-le")) // 2, "https://deezer.com/track/1"),
    ]
    mention = entities[-1]
    assert mention.type == MessageEntity.MENTION
    assert mention.offset == len("🎵 Artist - Song\nSpotify = https://open.spotify.com/track/1\nDeezer = https://deezer.com/track/1\nRequested by ".encode("utf-16-le")) // 2


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

    assert text == "Artist\nIndie Pop, Dream Pop\nSpotify = https://open.spotify.com/artist/1\nYandex Music = https://music.yandex.com/artist/1\n1. Top Song\nSpotify = https://open.spotify.com/track/2\nRequested by Actual"
    mention = entities[-1]
    assert mention.type == MessageEntity.TEXT_MENTION
    assert mention.user.id == requester.id
    assert mention.offset == len("Artist\nIndie Pop, Dream Pop\nSpotify = https://open.spotify.com/artist/1\nYandex Music = https://music.yandex.com/artist/1\n1. Top Song\nSpotify = https://open.spotify.com/track/2\nRequested by ".encode("utf-16-le")) // 2


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


def test_inline_artist_article_mentions_the_querying_user():
    info = ArtistInfo(
        name="Artist",
        genres=["indie pop"],
        thumbnail_url=None,
        source_url="https://open.spotify.com/artist/1",
    )
    requester = User(11, "Query user", False, username="query_user")

    content = _make_artist_article(info.source_url, info, requester).input_message_content

    assert content.message_text.endswith("Requested by @query_user")
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
