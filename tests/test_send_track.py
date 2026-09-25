from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest
from telegram import MessageEntity, User
from yoink_music import downloader
from yoink_music.types import TrackInfo


class _Bot:
    def __init__(self):
        self.calls = []

    async def send_audio(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            message_id=42,
            audio=SimpleNamespace(file_id="sent-file-id"),
        )


class _Cache:
    def __init__(self, cached):
        self.cached = cached
        self.put_calls = []

    async def get(self, key):
        return self.cached

    async def put(self, *args, **kwargs):
        self.put_calls.append((args, kwargs))


class _Config:
    def proxy_for(self, _platform):
        return None


def _install_download_module(monkeypatch, *, result=None):
    module = ModuleType("yoink_dl.download.music")
    module.MusicDownloadError = type("MusicDownloadError", (Exception,), {})
    module.TrackTooLargeError = type("TrackTooLargeError", (Exception,), {})
    module.make_music_cache_key = lambda artist, title: artist + ":" + title
    module.embed_tags = lambda *args, **kwargs: None

    async def download_track(_url, *, proxy=None):
        return result

    module.download_track = download_track
    root = ModuleType("yoink_dl")
    root.__path__ = []
    download_package = ModuleType("yoink_dl.download")
    download_package.__path__ = []
    monkeypatch.setitem(sys.modules, "yoink_dl", root)
    monkeypatch.setitem(sys.modules, "yoink_dl.download", download_package)
    monkeypatch.setitem(sys.modules, "yoink_dl.download.music", module)


def _info():
    return TrackInfo(
        title="Song",
        artist="Artist",
        thumbnail_url=None,
        source_url="https://open.spotify.com/track/1",
        links=[("ytmusic", "YouTube Music", "https://music.youtube.com/watch?v=1")],
    )


@pytest.mark.asyncio
async def test_send_track_cached_audio_mentions_requester_and_preserves_reply_topic(monkeypatch):
    _install_download_module(monkeypatch)
    cached = SimpleNamespace(file_id="cached-file-id", duration=180, file_size=123)
    cache = _Cache([cached])
    bot = _Bot()
    requester = User(12, "Listener", False, username="listener")

    sent = await downloader.send_track(
        bot,
        -1001,
        _info(),
        _Config(),
        reply_to_message_id=77,
        file_cache=cache,
        thread_id=88,
        requester=requester,
    )

    assert sent
    call = bot.calls[0]
    assert call["audio"] == "cached-file-id"
    assert call["reply_to_message_id"] == 77
    assert call["message_thread_id"] == 88
    assert call["caption"] == "Requested by @listener"
    entity = call["caption_entities"][0]
    assert entity.type == MessageEntity.MENTION
    assert call["caption"][entity.offset:entity.offset + entity.length] == "@listener"


@pytest.mark.asyncio
async def test_send_track_fresh_audio_mentions_requester_and_preserves_reply_topic(monkeypatch, tmp_path):
    download_dir = tmp_path / "download"
    download_dir.mkdir()
    audio_path = download_dir / "song.mp3"
    audio_path.write_bytes(b"audio")
    result = SimpleNamespace(path=audio_path, duration=180, file_size=123)
    _install_download_module(monkeypatch, result=result)
    cache = _Cache(None)
    bot = _Bot()
    requester = User(13, "Listener", False)

    sent = await downloader.send_track(
        bot,
        -1002,
        _info(),
        _Config(),
        reply_to_message_id=78,
        file_cache=cache,
        thread_id=89,
        requester=requester,
    )

    assert sent
    call = bot.calls[0]
    assert call["reply_to_message_id"] == 78
    assert call["message_thread_id"] == 89
    assert call["caption"] == "Requested by Listener"
    entity = call["caption_entities"][0]
    assert entity.type == MessageEntity.TEXT_MENTION
    assert entity.user.id == requester.id
    assert call["caption"][entity.offset:entity.offset + entity.length] == "Listener"
