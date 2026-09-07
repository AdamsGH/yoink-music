import re
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx

from yoink_music.resolver import MusicResolver, _PlatformDef


class MusicResolverCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_reuses_short_link_result_for_its_resolved_destination_until_cache_expires(self):
        short_url = 'https://spotify.link/example'
        destination = 'https://open.spotify.com/track/123'
        requests = []

        def respond_to_request(request):
            requests.append(str(request.url))
            if str(request.url) == short_url:
                return httpx.Response(302, headers={'location': destination})
            return httpx.Response(200)

        parser = AsyncMock(return_value=('Track', 'Artist', None))
        adapter = AsyncMock(return_value='https://www.deezer.com/track/123')
        cfg = SimpleNamespace(cache_ttl=3600)
        resolver = MusicResolver(cfg)
        resolver._platforms = [
            _PlatformDef('spotify', 'Spotify', re.compile(r'spotify\.com/track/'), parser, None),
            _PlatformDef('deezer', 'Deezer', re.compile(r'deezer\.com/track/'), parser, adapter),
        ]
        resolver._log_resolve = AsyncMock()
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond_to_request)) as client:
            resolver._client = client
            cached_result = await resolver.resolve(short_url, user_id=42)
            request_count = len(requests)
            self.assertIs(await resolver.resolve(short_url, user_id=42), cached_result)
            self.assertIs(await resolver.resolve(destination, user_id=42), cached_result)
            self.assertEqual(len(requests), request_count)
            parser.assert_awaited_once()
            adapter.assert_awaited_once()
            self.assertEqual(resolver._log_resolve.await_count, 3)
            self.assertIs(resolver._cache[short_url], resolver._cache[destination])

            cfg.cache_ttl = 0
            await resolver.resolve(short_url)
            self.assertEqual(parser.await_count, 2)
            self.assertEqual(adapter.await_count, 2)
