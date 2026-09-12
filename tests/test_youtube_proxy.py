import pytest
from yoink_music import downloader
from yoink_music.adapters import ytmusic
from yoink_music.types import TrackInfo


class _FakeYDL:
    seen_opts: list[dict] = []

    def __init__(self, opts):
        self.opts = opts
        self.seen_opts.append(opts)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def extract_info(self, query, download=False):
        return {
            "entries": [{
                "id": "video-id",
                "url": "https://www.youtube.com/watch?v=video-id",
                "title": "Artist - Title",
                "channel": "Artist",
            }]
        }


@pytest.fixture(autouse=True)
def _clear_seen_opts():
    _FakeYDL.seen_opts.clear()


@pytest.mark.asyncio
async def test_adapter_ytsearch_uses_configured_proxy(monkeypatch):
    # yt_dlp is imported inside the function, so patch the shared module.
    import yt_dlp

    monkeypatch.setattr(yt_dlp, "YoutubeDL", _FakeYDL)

    result = await ytmusic._search_ytsearch(
        "Artist Title",
        title="Title",
        artist="Artist",
        proxy="http://yoink-proxy:8080",
    )

    assert result == "https://music.youtube.com/watch?v=video-id"
    assert _FakeYDL.seen_opts[0]["proxy"] == "http://yoink-proxy:8080"


@pytest.mark.asyncio
async def test_download_fallback_search_uses_configured_proxy(monkeypatch):
    import yt_dlp

    monkeypatch.setattr(yt_dlp, "YoutubeDL", _FakeYDL)
    info = TrackInfo(
        title="Title",
        artist="Artist",
        thumbnail_url=None,
        source_url="https://www.deezer.com/track/1",
    )

    result = await downloader._search_ytsearch(
        info,
        proxy="http://yoink-proxy:8080",
    )

    assert result == "https://www.youtube.com/watch?v=video-id"
    assert _FakeYDL.seen_opts[0]["proxy"] == "http://yoink-proxy:8080"
