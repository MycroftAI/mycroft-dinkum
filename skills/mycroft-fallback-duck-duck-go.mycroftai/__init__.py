# Copyright 2017 Mycroft AI, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import itertools
import re
from collections import namedtuple
from xml.etree import ElementTree

import ddg3 as ddg
import requests
from mycroft.skills import AdaptIntent, intent_handler
from mycroft.skills.common_query_skill import CommonQuerySkill, CQSMatchLevel

Answer = namedtuple("Answer", ["query", "response", "text", "image"])
# Set default values to None.
# Once Python3.7 is min version, we can switch to:
# Answer = namedtuple('Answer', fields, defaults=(None,) * len(fields))
Answer.__new__.__defaults__ = (None,) * len(Answer._fields)


def split_sentences(text):
    """
    Turns a string of multiple sentences into a list of separate ones
    handling the edge case of names with initials
    As a side effect, .?! at the end of a sentence are removed
    """
    text = re.sub(r" ([^ .])\.", r" \1~.~", text)
    text = text.replace("Inc.", "Inc~.~")
    for c in "!?":
        text = text.replace(c + " ", ". ")
    sents = text.split(". ")
    sents = [i.replace("~.~", ".") for i in sents]
    if sents[-1][-1] in ".!?":
        sents[-1] = sents[-1][:-1]
    return sents


class DuckduckgoSkill(CommonQuerySkill):
    def __init__(self):
        super(DuckduckgoSkill, self).__init__()
        self._match = self._cqs_match = Answer()
        self.is_verb = " is "
        self.in_word = "in "

        # get ddg specific vocab for intent match
        vocab = set(
            itertools.chain.from_iterable(
                self.resources.load_vocabulary_file("DuckDuckGo")
            )
        )

        self.sorted_vocab = sorted(vocab, key=lambda x: (-len(x), x))

        self.translated_question_words = self.translate_list("question_words")
        self.translated_question_verbs = self.translate_list("question_verbs")
        self.translated_articles = self.translate_list("articles")
        self.translated_start_words = self.translate_list("start_words")

    def format_related(self, abstract: str, query: str) -> str:
        """Extract answer from a related topic abstract.

        When a disambiguation result is returned. The options are called
        'RelatedTopics'. Each of these has an abstract but they require
        cleaning before use.

        Args:
            abstract: text abstract from a Related Topic.
            query: original search term.
        Returns:
            Speakable response about the query.
        """
        self.log.debug("Original abstract: " + abstract)
        ans = abstract

        if ans[-2:] == "..":
            while ans[-1] == ".":
                ans = ans[:-1]

            phrases = ans.split(", ")
            first = ", ".join(phrases[:-1])
            last = phrases[-1]
            if last.split()[0] in self.translated_start_words:
                ans = first
            last_word = ans.split(" ")[-1]
            while last_word in self.translated_start_words or last_word[-3:] == "ing":
                ans = ans.replace(" " + last_word, "")
                last_word = ans.split(" ")[-1]

        category = None
        match = re.search(r"\(([a-z ]+)\)", ans)
        if match:
            start, end = match.span(1)
            if start <= len(query) * 2:
                category = match.group(1)
                ans = ans.replace("(" + category + ")", "()")

        words = ans.split()
        for article in self.translated_articles:
            article = article.title()
            if article in words:
                index = words.index(article)
                if index <= 2 * len(query.split()):
                    name, desc = words[:index], words[index:]
                    desc[0] = desc[0].lower()
                    ans = " ".join(name) + self.is_verb + " ".join(desc)
                    break

        if category:
            ans = ans.replace("()", self.in_word + category)

        if ans[-1] not in ".?!":
            ans += "."
        return ans

    def query_ddg(self, query: str) -> Answer:
        """Query DuckDuckGo about the search term.

        Args:
            query: search term to use.
        Returns:
            Answer namedtuple: (
                Query,
                DDG response object,
                Short text summary about the query,
                image url
            )
        """
        ret = Answer()
        self.log.debug("Query: %s" % (str(query),))
        # Apparently DDG prefers title case for queries
        query = query.title()

        if len(query) == 0:
            return
        else:
            ret = ret._replace(query=query)

        # note: '1+1' throws an exception
        try:
            response = ddg.query(query)
        except Exception as e:
            self.log.warning("DDG exception %s" % (e,))
            return ret

        self.log.debug("Type: %s" % (response.type,))

        # if disambiguation, save old result for fallback
        # but try to get the real abstract
        if response.type == "disambiguation":
            if response.related:
                detailed_url = response.related[0].url + "?o=x"
                self.log.debug("DDG: disambiguating %s" % (detailed_url,))
                request = requests.get(detailed_url)
                detailed_response = request.content
                if detailed_response:
                    xml = ElementTree.fromstring(detailed_response)
                    response = ddg.Results(xml)

        text_answer = None

        if (
            response.answer is not None
            and response.answer.text
            and "HASH" not in response.answer.text
        ):
            text_answer = query + self.is_verb + response.answer.text + "."
        elif len(response.abstract.text) > 0:
            sents = split_sentences(response.abstract.text)
            # return sents[0]  # what it is
            # return sents     # what it should be
            text_answer = ". ".join(sents)  # what works for now
        elif len(response.related) > 0 and len(response.related[0].text) > 0:
            related = split_sentences(response.related[0].text)[0]
            text_answer = self.format_related(related, query)

        if text_answer is not None:
            ret = ret._replace(response=response, text=text_answer)
        if response.image is not None and len(response.image.url) > 0:
            image_url = "https://duckduckgo.com/" + response.image.url
            ret = ret._replace(image=image_url)
        return ret

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
                    test = " ".join(s.strip() for s in (noun, verb, article))
                    test_query = query[: len(test)]
                    if test_query == test:
                        query_topic = query[len(test) :]
                        return query_topic
        return query

    def CQS_match_query_phrase(self, query: str):
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
        answer = None
        query_topic = self.extract_topic(query)
        self.log.info("Search DuckDuckGo for %s", query_topic)
        answer = self.query_ddg(query_topic)
        if answer and answer.text:
            self._cqs_match = answer
            callback_data = {"answer": answer.text}
            return (query, CQSMatchLevel.GENERAL, answer.text, callback_data)
        else:
            self.log.info("DDG has no answer")
            return None

    def CQS_action(self, query: str, data: dict):
        """Display result if selected by Common Query to answer.

        Note common query will speak the response.

        Args:
            query: User utterance of original question
            data: Callback data specified in CQS_match_query_phrase()
        """
        if self._cqs_match.text != data.get("answer"):
            self.log.warning("CQS match data does not match. " "Cannot display result.")
            return

        with self.activity():
            self.display_answer(self._cqs_match)
            self.speak(self._cqs_match.text, wait=True)

    @intent_handler(AdaptIntent("AskDucky").require("DuckDuckGo"))
    def handle_ask_ducky(self, message):
        """Intent handler to request information specifically from DDG."""
        with self.activity():
            utt = message.data["utterance"]

            if utt is None:
                self.log.warning("no utterance received")
                return

            for voc in self.sorted_vocab:
                utt = utt.replace(voc, "")

            utt = utt.strip()
            utt = self.extract_topic(utt)
            # TODO - improve method of cleaning input
            for article in self.translated_articles:
                utt = utt.replace(f"{article} ", "")

            if utt is not None:
                answer = self.query_ddg(utt)
                if answer.text is not None:
                    self.display_answer(answer)
                    self.speak(answer.text, wait=True)
                    self.gui.release()
                else:
                    self.speak_dialog("no-answer", data={"query": utt}, wait=True)

    def display_answer(self, answer: Answer):
        """Display the result page on a GUI if connected.

        Arguments:
            answer: Answer containing necessary fields
        """
        self.gui["title"] = answer.query.title() or ""
        self.gui["summary"] = answer.text or ""
        self.gui["imgLink"] = answer.image or ""
        # TODO - Duration of article display currently fixed at 60 seconds.
        # This should be more closely tied with the speech of the summary.
        self.gui.show_page("feature_image.qml", override_idle=True)

    def stop(self):
        self.log.debug("Ducky stop() hit")
        self.CQS_release_output_focus()


def create_skill():
    return DuckduckgoSkill()
