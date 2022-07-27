# Copyright 2021, Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest

from wiki import DisambiguationError, MediaWikiPage, Wiki


class TestWiki(unittest.TestCase):
    def setUp(self):
        self.wiki = Wiki("en", auto_more=False)
        self.test_pages = {}
        test_titles = ["Elon Musk", "Lemur", "Car", "Nike, Inc."]
        for title in test_titles:
            self.test_pages[title] = self.wiki.get_page(title)

    def test_wiki_search(self):
        results = self.wiki.search("cars")
        self.assertIsInstance(results, list)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0], "Car")

    def test_wiki_search_returns_disambiguation(self):
        results = self.wiki.search("george church")
        with self.assertRaises(DisambiguationError):
            _ = self.wiki.get_page(results[0])

    def test_get_best_image(self):
        for page in self.test_pages.values():
            image = self.wiki.get_best_image_url(page, 50)
            self.assertIsInstance(image, str)
            self.assertEqual(image[:5], "https")
            self.assertEqual(image[-4:], ".jpg")

    # def test_get_disambiguation_from_results(self):
    #     results = self.wiki.search('george church')
    #     title = self.wiki.get_disambiguation_page(results)
    #     self.assertIsInstance(title, str)
    #     self.assertTrue(len(title) > 0)
    #     with self.assertRaises(DisambiguationError):
    #         _ = self.wiki.get_page(title)

    def test_get_page(self):
        bitcoin_page = self.wiki.get_page("bitcoin")
        self.assertIsInstance(bitcoin_page, MediaWikiPage)
        self.assertEqual(bitcoin_page.title, "Bitcoin")
        self.assertTrue("crypto" in bitcoin_page.summarize())

    def test_get_random_page(self):
        random_page = self.wiki.get_random_page()
        self.assertIsInstance(random_page, MediaWikiPage)
        self.assertIsInstance(random_page.title, str)
        self.assertTrue(len(random_page.title) > 0)

    def test_set_language(self):
        changed = self.wiki.set_language("es")
        self.assertTrue(changed)
        self.assertEqual(self.wiki.wiki.language, "es")
        page = self.wiki.get_page("barcelona")
        self.assertEqual(page.title, "Barcelona")
        summary = page.summarize(sentences=1)
        expected_start = "Barcelona es una ciudad española"
        self.assertEqual(summary[: len(expected_start)], expected_start)

        # Try to change to unsupported language
        changed = self.wiki.set_language("notlang")
        self.assertTrue(not changed)
        self.assertEqual(self.wiki.wiki.language, "es")

        # Change to same language
        changed = self.wiki.set_language("es")
        self.assertTrue(not changed)
        self.assertEqual(self.wiki.wiki.language, "es")

        # Change to default
        changed = self.wiki.set_language("en")
        self.assertTrue(changed)
        self.assertEqual(self.wiki.wiki.language, "en")

        # Set to default language
        self.wiki.set_language("fr")
        self.assertEqual(self.wiki.wiki.language, "fr")
        self.wiki.set_language()
        self.assertEqual(self.wiki.wiki.language, "en")

    def test_summarize_page(self):
        for page in self.test_pages.values():
            summary = self.wiki.summarize_page(page, sentences=2)
            self.assertIsInstance(summary, str)
            self.assertTrue("(" not in summary)
            self.assertTrue(")" not in summary)
            self.assertTrue("  " not in summary)
            self.assertTrue(0 < len(summary) < 500)

    def test_summary_next_lines(self):
        for page in self.test_pages.values():
            summary_intro, intro_length = self.wiki.get_summary_intro(page)
            new_lines = 2
            summary_follow_up, total_lines = self.wiki.get_summary_next_lines(
                page, intro_length, new_lines
            )
            self.assertIsInstance(summary_follow_up, str)
            self.assertTrue("(" not in summary_follow_up)
            self.assertTrue(")" not in summary_follow_up)
            self.assertTrue("  " not in summary_follow_up)
            self.assertTrue(summary_intro not in summary_follow_up)
            self.assertEqual(total_lines, intro_length + new_lines)
