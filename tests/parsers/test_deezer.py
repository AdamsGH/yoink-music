import unittest

import httpx

from yoink_music.parsers.deezer import _extract_track_id


class DeezerTrackIdExtractionTests(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_track_id_from_redirect_location_without_loading_track_page(self):
        for destination in (
            'https://www.deezer.com/track/123',
            '/?dest=https%3A%2F%2Fwww.deezer.com%2Ftrack%2F123',
        ):
            with self.subTest(destination=destination):
                calls = []

                def respond_to_redirect(request):
                    calls.append(str(request.url))
                    if request.url.path != '/s/example':
                        raise AssertionError('Track destination must not be requested')
                    return httpx.Response(302, headers={'location': destination})

                async with httpx.AsyncClient(transport=httpx.MockTransport(respond_to_redirect)) as client:
                    result = await _extract_track_id('https://link.deezer.com/s/example', client)
                self.assertEqual(result, '123')
                self.assertEqual(len(calls), 1)

    async def test_uses_get_after_head_is_rejected_and_resolves_relative_redirects(self):
        requests = []

        def respond_to_redirect(request):
            requests.append((request.method, request.url.path))
            if request.method == 'HEAD':
                # Deezer can reject HEAD requests; following the link still requires GET.
                return httpx.Response(405)
            if request.url.path == '/s/example':
                return httpx.Response(302, headers={'location': '/redirect'})
            return httpx.Response(302, headers={'location': 'https://www.deezer.com/track/123'})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond_to_redirect)) as client:
            result = await _extract_track_id('https://link.deezer.com/s/example', client)
        self.assertEqual(result, '123')
        self.assertEqual(requests, [('HEAD', '/s/example'), ('GET', '/s/example'), ('GET', '/redirect')])

    async def test_stops_after_client_redirect_limit_when_redirects_loop(self):
        request_methods = []

        def respond_with_loop(request):
            request_methods.append(request.method)
            return httpx.Response(302, headers={'location': '/s/example'})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond_with_loop), max_redirects=2,
        ) as client:
            result = await _extract_track_id('https://link.deezer.com/s/example', client)
        self.assertIsNone(result)
        self.assertEqual(request_methods, ['HEAD'] * 3 + ['GET'] * 3)

    async def test_returns_track_id_from_direct_deezer_url_without_http_request(self):
        def fail_on_request(request):
            raise AssertionError('Direct link must not make any requests')

        async with httpx.AsyncClient(transport=httpx.MockTransport(fail_on_request)) as client:
            result = await _extract_track_id('https://www.deezer.com/track/123', client)
        self.assertEqual(result, '123')
