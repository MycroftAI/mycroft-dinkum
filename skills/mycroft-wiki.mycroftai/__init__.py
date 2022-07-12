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

import typing
from collections import namedtuple
from urllib3.exceptions import HTTPError

from requests.exceptions import ConnectionError, ReadTimeout

from mycroft.skills import AdaptIntent, intent_handler
from mycroft.skills.common_query_skill import CommonQuerySkill, CQSMatchLevel

from .wiki import Wiki, DisambiguationError, MediaWikiPage


CONNECTION_ERRORS = (ConnectionError, HTTPError, ReadTimeout)


Article = namedtuple(
    "Article", ["title", "page", "summary", "num_lines_spoken", "image"]
)
# Set default values to None.
# Once Python3.7 is min version, we can switch to:
# Article = namedtuple('Article', fields, defaults=(None,) * len(fields))
Article.__new__.__defaults__ = (None,) * len(Article._fields)


class WikipediaSkill(CommonQuerySkill):
    def __init__(self):
        """Constructor for WikipediaSkill.

        Attributes:
            _match (PageMatch): current match in case user requests more info
            _lines_spoken_already (int): number of lines already spoken from _match.summary
            translated_question_words (list[str]): used in cleaning queries
            translated_question_verbs (list[str]): used in cleaning queries
            translated_articles (list[str]): used in cleaning queries
        """
        super(WikipediaSkill, self).__init__(name="WikipediaSkill")
        self._match = self._cqs_match = Article()
        self.platform = self.config_core["enclosure"].get("platform", "unknown")
        self.max_image_width = 416 if self.platform == "mycroft_mark_ii" else 1920
        self.translated_question_words = self.translate_list("question_words")
        self.translated_question_verbs = self.translate_list("question_verbs")
        self.translated_articles = self.translate_list("articles")
        self.wiki: typing.Optional[Wiki] = None

    def initialize(self):
        """Wait for internet connection before connecting to Wikipedia"""
        self.add_event("mycroft.internet-ready", self.handle_internet_ready)

    def handle_internet_ready(self, _):
        """Attempt connection to Wikipedia"""
        self._connect_to_wikipedia()

    def _connect_to_wikipedia(self):
        if self.wiki is None:
            # Try to connect now
            self.init_wikipedia()

            if self.wiki is None:
                # Failed to connect
                self.log.error("not connected to wikipedia")
                return False

        return True

    def init_wikipedia(self):
        """Initialize the Wikipedia connection.

        If unable to connect it will retry every 10 minutes for up to 1 hour
        """
        try:
            wikipedia_lang_code = self.translate_namedvalues("wikipedia_lang")["code"]
            auto_more = self.config_core.get("cq_auto_more", False)
            self.wiki = Wiki(wikipedia_lang_code, auto_more)
        except CONNECTION_ERRORS:
            self.wiki = None

    @intent_handler(AdaptIntent().require("Wikipedia").require("ArticleTitle"))
    def handle_direct_wiki_query(self, message):
        """Primary intent handler for direct wikipedia queries.

        Requires utterance to directly ask for Wikipedia's answer.
        """
        with self.activity():
            query = self.extract_topic(message.data.get("ArticleTitle"))
            # Talk to the user, as this can take a little time...
            # self.speak_dialog("searching", {"query": query})
            try:
                page, disambiguation_page = self.search_wikipedia(query)
                if page is None:
                    self.report_no_match(query)
                    return
                self.log.info(f"Best result from Wikipedia is: {page.title}")
                self.handle_result(page, query)
                # TODO determine intended disambiguation behaviour
                # disabling disambiguation for now.
                if False and disambiguation_page is not None:
                    self.log.info(
                        f"Disambiguation page available: {disambiguation_page}"
                    )
                    if self.translate("disambiguate-exists") != "disambiguate-exists":
                        # Dialog file exists and can be spoken
                        correct_topic = self.ask_yesno("disambiguate-exists")
                        if correct_topic != "no":
                            return
                    new_page = self.handle_disambiguation(disambiguation_page)
                    if new_page is not None:
                        self.handle_result(new_page, query)
            except CONNECTION_ERRORS:
                self.speak_dialog("connection-error", wait=True)

    @intent_handler("Random.intent")
    def handle_random_intent(self, _):
        """ Get a random wiki page.

        Uses the Special:Random page of wikipedia
        """
        with self.activity():
            if self.wiki is None:
                self.log.error("not connected to wikipedia")
                return

            self.log.info("Fetching random Wikipedia page")
            lang = self.translate_namedvalues("wikipedia_lang")["code"]
            page = self.wiki.get_random_page(lang=lang)
            self.log.info("Random page selected: %s", page.title)
            self.handle_result(page, "random page")

    @intent_handler(AdaptIntent().require("More").require("wiki_article"))
    def handle_tell_more(self, _):
        """Follow up query handler, "tell me more".

        If a "spoken_lines" entry exists in the active contexts
        this can be triggered.
        """
        # Read more of the last article queried
        with self.activity():
            if not self._match:
                self.log.error("handle_tell_more called without previous match")
                return

            if self.wiki is None:
                self.log.error("not connected to wikipedia")
                return

            summary_to_read, new_lines_spoken = self.wiki.get_summary_next_lines(
                self._match.page, self._match.num_lines_spoken
            )

            if self._match.image is None:
                # TODO consider showing next image on page instead of same image each time.
                image = self.wiki.get_best_image_url(
                    self._match.page, self.max_image_width
                )
                article = self._match._replace(image=image)

            if summary_to_read:
                article = self._match._replace(
                    summary=summary_to_read, num_lines_spoken=new_lines_spoken
                )
                self.display_article(article)
                self.speak(summary_to_read, wait=True)
                self.gui.release()

                # Update context
                self._match = article
                self.set_context("wiki_article", "")
            else:
                self.speak_dialog("thats all")

    def CQS_match_query_phrase(
        self, query: str
    ) -> tuple([str, CQSMatchLevel, str, dict]):
        """Respond to Common Query framework with best possible answer.

        Args:
            query: question to answer

        Returns:
            Tuple(
                question being answered,
                CQS Match Level confidence,
                answer to question,
                callback dict available to CQS_action method
            )
        """
        if not self._connect_to_wikipedia():
            return

        answer = None
        callback_data = dict()
        cleaned_query = self.extract_topic(query)

        if cleaned_query is not None:
            try:
                page, _ = self.search_wikipedia(cleaned_query)
            except CONNECTION_ERRORS:
                return

        if page:
            callback_data = {"title": page.title}
            answer, num_lines = self.wiki.get_summary_intro(page)
            self._cqs_match = Article(page.title, page, answer, num_lines)
        if answer:
            self.schedule_event(self.get_cqs_match_image, 0)
            return (query, CQSMatchLevel.GENERAL, answer, callback_data)
        return answer

    def CQS_action(self, phrase: str, data: dict):
        """Display result if selected by Common Query to answer.

        Note common query will speak the response.

        Args:
            phrase: User utterance of original question
            data: Callback data specified in CQS_match_query_phrase()
        """
        if not self._connect_to_wikipedia():
            return

        title = data.get("title")
        if title is None:
            self.log.error("No title returned from CQS match")
            return

        with self.activity():
            if self._cqs_match.title == title:
                title, page, summary, num_lines, image = self._cqs_match
            else:
                # This should never get called, but just in case.
                self.log.warning(
                    "CQS match data was not saved. " "Please report this to Mycroft."
                )
                page = self.wiki.get_page(title)
                summary, num_lines = self.wiki.get_summary_intro(page)

            if image is None:
                image = self.wiki.get_best_image_url(page, self.max_image_width)
            article = Article(title, page, summary, num_lines, image)
            self.display_article(article)
            self.speak(summary, wait=True)
            # Wait for the summary to finish, then remove skill from GUI
            self.gui.release()
            # Set context for follow up queries - "tell me more"
            self._match = article
            self.set_context("wiki_article", "")

    def extract_topic(self, query: str) -> str:
        """Extract the topic of a query.

        Args:
            query: user utterance eg 'what is the earth'
        Returns:
            topic of question eg 'earth' or original query
        """
        for noun in self.translated_question_words:
            for verb in self.translated_question_verbs:
                for article in [i + " " for i in self.translated_articles] + [""]:
                    test = noun + verb + " " + article
                    if query[: len(test)] == test:
                        return query[len(test) :]
        return query

    def search_wikipedia(self, query: str) -> tuple([MediaWikiPage, str]):
        """Handle Wikipedia query on topic.

        Args:
            query: search term to use
        Returns:
            wiki page for best result,
            disambiguation page title or None
        """
        if not self._connect_to_wikipedia():
            return

        self.log.info(f"Searching wikipedia for {query}")
        lang = self.translate_namedvalues("wikipedia_lang")["code"]
        try:
            results = self.wiki.search(query, lang=lang)
            if len(results) < 1:
                return None, None
            try:
                wiki_page = self.wiki.get_page(results[0])
                disambiguation = self.wiki.get_disambiguation_page(results)
            except DisambiguationError:
                # Some disambiguation pages aren't explicitly labelled.
                # The only guaranteed way to know is to fetch the page.
                # Eg "George Church"
                disambiguation, wiki_page = self.wiki.handle_disambiguation_error(
                    results
                )
                self.log.error(disambiguation)
                self.log.error(wiki_page)
        except CONNECTION_ERRORS as error:
            self.log.exception(error)
            raise error
        return wiki_page, disambiguation

    def get_cqs_match_image(self):
        """Fetch the image for a CQS answer.

        This is called from a scheduled event to run in its own thread,
        preventing delays in Common Query answer selection.
        """
        if not self._connect_to_wikipedia():
            return

        page = self._cqs_match.page
        image = self.wiki.get_best_image_url(page, self.max_image_width)
        self._cqs_match = self._cqs_match._replace(image=image)

    def handle_disambiguation(self, disambiguation_title: str) -> MediaWikiPage:
        """Ask user which of the different matches should be used.

        Args:
            disambiguation_title: name of disambiguation page
        Returns:
            wikipedia page selected by the user
        """
        try:
            self.wiki.get_page(disambiguation_title)
        except DisambiguationError as disambiguation:
            self.log.debug(disambiguation.options)
            self.log.debug(disambiguation.details)
            options = disambiguation.options[:3]
            self.speak_dialog("disambiguate-intro", wait=True)
            choice = self.ask_selection(options)
            self.log.debug("Disambiguation choice is {}".format(choice))
            try:
                wiki_page = self.wiki.get_page(choice)
            except CONNECTION_ERRORS as error:
                self.log.exception(error)
                raise error
            except DisambiguationError:
                self.handle_disambiguation(choice)
            return wiki_page

    def handle_result(self, page: MediaWikiPage, query: str):
        """Handle result depending on result type.

        Speaks appropriate feedback to user depending of the result type.
        Arguments:
            page: wiki page for search result
        """
        if page is None:
            self.report_no_match(query)
        else:
            self.report_match(page)

    def report_no_match(self, query: str):
        """Answer no match found."""
        self.speak_dialog("no entry found", data={"topic": query}, wait=True)

    def report_match(self, page: MediaWikiPage):
        """Read short summary to user."""
        if self.wiki is None:
            self.log.error("not connected to wikipedia")
            return

        summary, num_lines = self.wiki.get_summary_intro(page)
        # wait for the "just a minute while I look for that" dialog to finish
        article = Article(page.title, page, summary, num_lines)
        self.display_article(article)
        self.speak(summary)
        image = self.wiki.get_best_image_url(page, self.max_image_width)
        article = article._replace(image=image)
        self.update_display_data(article)
        # Wait for the summary to finish, then remove skill from GUI
        # TODO
        # wait_while_speaking()
        self.gui.release()
        # Remember context and speak results
        self._match = article
        # TODO improve context handling
        self.set_context("wiki_article", "")

    def display_article(self, article: Article):
        """Display the match page on a GUI if connected.

        Arguments:
            article: Article containing necessary fields
        """
        self.update_display_data(article)
        self.gui.show_page("feature_image.qml", override_idle=True)

    def update_display_data(self, article: Article):
        """Update the GUI display data when a page is already being shown.

        Arguments:
            article: Article containing necessary fields
        """
        title = article.title or ""

        self.gui["title"] = title
        self.gui["summary"] = article.summary or ""
        self.gui["imgLink"] = article.image or ""

    def stop(self):
        self.log.debug("wiki stop() hit")
        self.CQS_release_output_focus()


def create_skill():
    return WikipediaSkill()
