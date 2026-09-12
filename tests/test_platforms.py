import unittest

from yoink_music.platforms import extract_music_urls


class MusicUrlExtractionTests(unittest.TestCase):
    def test_extracts_deezer_short_links(self):
        for url in (
            "https://link.deezer.com/s/example",
            "https://deezer.page.link/example",
        ):
            with self.subTest(url=url):
                self.assertEqual(extract_music_urls(url)[0][0], url)

    def test_strips_punctuation_after_url(self):
        url = "https://link.deezer.com/s/example"

        self.assertEqual(extract_music_urls(f"Listen: {url}.);")[0][0], url)
