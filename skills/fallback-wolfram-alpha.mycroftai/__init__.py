# Copyright 2017 Mycroft AI Inc.
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
#

from collections import namedtuple

from mtranslate import translate
from mycroft.messagebus.message import Message
from mycroft.skills import AdaptIntent, intent_handler
from mycroft.skills.common_query_skill import CommonQuerySkill, CQSMatchLevel
from mycroft.util import get_cache_directory
from mycroft.util.parse import normalize
from requests import HTTPError

from .skill.parse import EnglishQuestionParser
from .skill.util import clear_cache, process_wolfram_string
from .skill.wolfram_client import WolframAlphaClient

Query = namedtuple("Query", ["query", "spoken_answer", "display_text", "image"])
# Set default values to None.
# Once Python3.7 is min version, we can switch to:
# Query = namedtuple('Query', fields, defaults=(None,) * len(fields))
Query.__new__.__defaults__ = (None,) * len(Query._fields)


class WolframAlphaSkill(CommonQuerySkill):
    def __init__(self):
        super().__init__()
        self._last_query = self._cqs_match = Query()
        self.question_parser = EnglishQuestionParser()
        self.autotranslate = False
        self.cache_dir = get_cache_directory(self.__class__.__name__)
        # Whether the Skill is actively fetching an image
        self.fetching_image = False

    def initialize(self):
        self.on_settings_changed()
        self.settings_change_callback = self.on_settings_changed

    def on_settings_changed(self):
        self.log.debug("Settings changed")
        self.autotranslate = self.settings.get("autotranslate", True)
        for setting in self.settings.keys():
            self.log.debug("%s: %s", setting, self.settings[setting])
        self.__init_client()

    def __init_client(self):
        # Attempt to get an AppID skill settings instead (normally this
        # doesn't exist, but privacy-conscious might want to do this)
        appID = self.settings.get("appID", None)
        if appID == "":
            appID = None

        self.client = WolframAlphaClient(cache_dir=self.cache_dir, app_id=appID)

    def _clear_previous_data(self):
        # Clear any previous match query data
        self._last_query = self._cqs_match = Query()
        # Clear the display and any prior session data
        # Clear the cache directory of old files
        clear_cache(self.cache_dir)

    def CQS_match_query_phrase(self, utt):
        self.log.info("WolframAlpha query: " + utt)
        self._clear_previous_data()
        # TODO: Localization.  Wolfram only allows queries in English,
        #       so perhaps autotranslation or other languages?  That
        #       would also involve auto-translation of the result,
        #       which is a lot of room for introducting translation
        #       issues.

        # Automatic translation to English
        orig_utt = utt
        if self.autotranslate and self.lang[:2] != "en":
            utt = translate(utt, from_language=self.lang[:2], to_language="en")
            self.log.debug("translation: {}".format(utt))
        utterance = normalize(utt, self.lang, remove_articles=False)
        parsed_question = self.question_parser.parse(utterance)

        query = utterance
        if parsed_question:
            # Try to store pieces of utterance (None if not parsed_question)
            utt_word = parsed_question.get("QuestionWord")
            utt_verb = parsed_question.get("QuestionVerb")
            utt_query = parsed_question.get("Query")
            query = "%s %s %s" % (utt_word, utt_verb, utt_query)
            self.log.debug("Querying WolframAlpha: " + query)
        else:
            # This utterance doesn't look like a question, don't waste
            # time with WolframAlpha.
            self.log.info("Non-question, ignoring: %s", utterance)
            return None

        try:
            response = self.client.get_spoken_answer(
                utt,
                (
                    self.location["coordinate"]["latitude"],
                    self.location["coordinate"]["longitude"],
                ),
                self.config_core["system_unit"],
            )
            if response:
                if response == "No spoken result available":
                    # Wolfram's Spoken API returns a non-result as a speakable string
                    # Helpful I guess...
                    return None
                response = process_wolfram_string(
                    response, {"lang": self.lang, "root_dir": self.root_dir}
                )
                # Automatic re-translation to 'self.lang'
                if self.autotranslate and self.lang[:2] != "en":
                    response = translate(
                        response, from_language="en", to_language=self.lang[:2]
                    )
                    utt = orig_utt

                self.log.info("Answer: %s" % (response))
                self._cqs_match = Query(query=utt, spoken_answer=response)

                # Don't bother with images
                # self.schedule_event(self._get_cqs_match_image, 0)
                return (
                    utt,
                    CQSMatchLevel.GENERAL,
                    response,
                    {"query": utt, "answer": response},
                )
            else:
                return None
        except HTTPError as e:
            if e.response.status_code == 401:
                self.bus.emit(Message("mycroft.not.paired"))
        except Exception as e:
            self.log.exception(e)

        return None

    def CQS_action(self, phrase, data):
        """Display result if selected by Common Query to answer.

        Note common query will speak the response.

        Args:
            phrase: User utterance of original question
            data: Callback data specified in CQS_match_query_phrase()
        """
        """If selected to answer prepare data for follow up queries.

        Currently this includes detail on the source of the answer.
        """
        if data.get("query") != self._cqs_match.query:
            # This should never get called, but just in case.
            self.log.warning(
                "CQS match data was not saved. " "Please report this to Mycroft."
            )
            return

        speak, gui = self._display_answer(
            self._cqs_match.display_text, self._cqs_match.image
        )
        self.log.debug("Setting information for follow up query")
        self._last_query = self._cqs_match

        return self.end_session(speak=speak, gui=gui)

    def _get_cqs_match_image(self):
        """Fetch the image for a CQS answer.

        This is called from a scheduled event to run in its own thread,
        preventing delays in Common Query answer selection.
        """
        self.fetching_image = True
        display_text, image = self.client.get_visual_answer(
            self._cqs_match.query,
            (
                self.location["coordinate"]["latitude"],
                self.location["coordinate"]["longitude"],
            ),
            self.config_core["system_unit"],
        )
        self._cqs_match = self._cqs_match._replace(
            display_text=display_text, image=image
        )
        self.bus.emit(Message("skill.wolfram-alpha.image-fetch.ended"))
        self.fetching_image = False

    def _display_answer(self, text, image=None):
        """Display the answer."""
        speak = None
        gui = None

        if self.fetching_image:
            self.bus.once("skill.wolfram-alpha.image-fetch.ended", self._display_answer)

        # Don't bother with images
        gui = ("answer_only.qml", {"answer": self._cqs_match.spoken_answer})
        speak = self._cqs_match.spoken_answer

        return speak, gui

    def shutdown(self):
        super(WolframAlphaSkill, self).shutdown()

    def __translate(self, template, data=None):
        return self.dialog_renderer.render(template, data)

    def stop(self):
        self.log.debug("Wolfy stop() hit")
        self.CQS_release_output_focus()


def create_skill():
    return WolframAlphaSkill()
