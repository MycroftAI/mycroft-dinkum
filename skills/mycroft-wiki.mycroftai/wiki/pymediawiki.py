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

from urllib3.exceptions import HTTPError

import requests
from mediawiki import (
    MediaWiki,
    MediaWikiPage,
    PageError,
    DisambiguationError
)

from mycroft.util.log import LOG
from .util import clean_text


DEFAULT_IMAGE = 'ui/default-images/wikipedia-logo.svg'
EXCLUDED_IMAGES = [
    'Blue_pencil.svg',
    'OOjs_UI_icon_edit-ltr-progressive.svg',
    'Edit-clear.svg'
]


class Wiki():
    """Interface to Wikipedia using pymediawiki."""

    def __init__(self, lang, auto_more) -> None:
        self.default_lang = lang
        self.auto_more = auto_more
        try:
            self.wiki = MediaWiki(lang=lang)
        except HTTPError:
            raise

    def get_best_image_url(self, page: MediaWikiPage, max_width: int) -> str:
        """Get url of the best image from an existing Wiki page.

        Preference is given to the page thumbnail, otherwise we get the first
        image on the page that is not intentionally excluded.
        eg the pencil/edit icon

        Note: Calling `page.logos` is a parsing operation and not part of the
              standard API. It is not accessing existing data on the
              MediaWikiPage object and it is a slower operation.

        Args:
            page: target wikipedia page
        Returns:
            url of best image
        """
        LOG.debug("Fetching best image for %s", page.title)
        image = None

        # try direct API call
        api_url = (
            "https://en.wikipedia.org/w/api.php?action=query&"
            "formatversion=2&prop=pageimages&format=json&"
            f"pithumbsize={max_width}&titles={page.title}"
        )
        response = requests.get(api_url)
        if response.status_code < 300:
            page_image_data = response.json().get(
                'query', {}).get('pages', [False])[0]
            if page_image_data:
                image = page_image_data.get('thumbnail', {}).get('source')

        # Else fallback to pymediawiki page scraping
        if image is None:
            thumbnails = page.logos
            if len(thumbnails) > 0:
                thumbnail = thumbnails[0]
                # Get hi-res image if available.
                # This translates image urls between the following two formats
                # https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Sialyl_lewis_a.svg/200px-Sialyl_lewis_a.svg.png
                # https://upload.wikimedia.org/wikipedia/commons/d/d4/Sialyl_lewis_a.svg
                full_image = '/'.join(thumbnail.replace('/thumb/',
                                                        '/').split('/')[:-1])
                image = full_image if full_image in page.images else thumbnail
            elif len(page.images) > 0:
                try:
                    image = next(img for img in page.images if img.split(
                        '/')[-1] not in EXCLUDED_IMAGES)
                except StopIteration:
                    LOG.warning('Could not find an image for %s', page.title)

        LOG.debug('Image selected: %s', image)
        return image or DEFAULT_IMAGE

    @staticmethod
    def get_disambiguation_page(results: list([str])) -> str:
        """Get the disambiguation page title from a set of results.

        Note that some disambiguation pages aren't explicitly labelled as one.
        The only guaranteed way to know is to fetch the page and catch a
        DisambiguationError eg "George Church"

        Args:
            results: list of wikipedia pages
        Returns:
            disambiguation page title or None
        """
        try:
            page_title = next(
                page for page in results if "(disambiguation)" in page)
        except StopIteration:
            page_title = None
        return page_title

    def get_page(self, title: str) -> MediaWikiPage:
        """Get the specified wiki page."""
        try:
            page = self.wiki.page(title)
        except PageError:
            page = None
        return page

    def get_random_page(self, lang: str = 'en') -> MediaWikiPage:
        """Get a random wikipedia page.

        Uses the Special:Random page of Wikipedia
        """
        self.set_language('en')
        random_page = self.wiki.random(pages=1)
        return self.get_page(random_page)

    def get_summary_intro(self, page: MediaWikiPage) -> tuple([str, int]):
        """Get a short summary of the page.

        About auto_more (bool): default False
            Set by cq_auto_more attribute in mycroft.conf
            If true will read 20 sentences of abstract for any query.
            If false will read first 2 sentences and wait for request to read more.

        Args:
            page: wiki page containing a summary
        Returns:
            trimmed answer, number of sentences
        """
        length = 20 if self.auto_more else 2
        answer = self.summarize_page(page, sentences=length)
        if not self.auto_more and len(answer) > 300:
            length = 1
            answer = self.summarize_page(page, sentences=length)
        return answer, length

    def get_summary_next_lines(self, page: MediaWikiPage, previous_lines: int = 2, num_lines: int = 5) -> tuple([str, int]):
        """Get the next summary lines to be read.

        Args:
            page: wiki page containing a summary
            previous_lines: number of sentences already read
            num_lines: number of new lines to return
        Returns:
            next lines of summary,
            total length of summary read so far ie previous_lines + num_lines
        """
        total_summary_read = previous_lines + num_lines
        previously_read = self.summarize_page(page, sentences=previous_lines)
        next_summary_section = self.summarize_page(
            page, sentences=total_summary_read).replace(previously_read, '')
        return next_summary_section, total_summary_read

    def handle_disambiguation_error(self, search_results: list, prev_disambiguation_title: str = None) -> list([MediaWikiPage, str]):
        """Attempt to get valid MediaWikiPage from a DisambiguationError.

        This is a recursive method because a Disambiguation Page may refer to
        another Disambiguation Page.

        Args:
            err: DisambiguationError raised by pymediawiki
            previous_disambiguation_title: top level disambiguation page title
        Returns:
            Top level disambiguation page title,
            MediaWikiPage of most likely result OR None
        """
        if len(search_results) <= 0:
            return None, None
        disambiguation_title = search_results[0]

        if len(search_results) <= 1:
            return disambiguation_title, None

        try:
            wiki_page = self.get_page(search_results[1])
        except DisambiguationError:
            _, wiki_page = self.handle_disambiguation_error([
                disambiguation_title,
                *search_results[2:]
            ])
        
        return disambiguation_title, wiki_page


    def search(self, query: str, lang: str = 'en') -> list([str]):
        """Search wikipedia for the given query.

        Args:
            query: search term to use
            lang: language of the request

        Returns:
            list of results
        """
        self.set_language(lang)
        return self.wiki.search(query)

    def set_language(self, lang: str = None) -> bool:
        """Set the language for Wikipedia lookups.

        If the provided language cannot be found. The language used when
        instantiating the Wiki class will be used.

        Args:
            lang: BCP-47 language code to use
        Returns:
            True if language changed successfully else False
        """
        if lang is None:
            lang = self.default_lang
        if lang == self.wiki.language:
            is_changed = False
        elif lang not in self.wiki.supported_languages.keys():
            LOG.warning('Unable to set Wikipedia language to "%s"', lang)
            is_changed = False
        else:
            LOG.info('Setting Wikipedia language to "%s"', lang)
            self.wiki.language = lang
            is_changed = True
        return is_changed

    def summarize_page(self, page: MediaWikiPage, sentences: int) -> str:
        """Get a summary of a Wikipedia page.

        The summary is also cleaned for better spoken output.

        Args:
            page: Wiki page to get a summary of.
            sentences: Number of sentences to return.
        """
        # TODO consider splitting out each step to its own function
        # will enable detailed testing of each step and the whole.
        pymediawiki_summary = page.summarize(sentences=sentences)
        cleaned_text = clean_text(pymediawiki_summary)

        return cleaned_text
