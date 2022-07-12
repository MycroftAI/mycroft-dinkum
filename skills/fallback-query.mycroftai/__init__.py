# Copyright 2018 Mycroft AI Inc.
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
import re
import threading
import time
import typing
from mycroft.messagebus.message import Message
from mycroft.skills.fallback_skill import FallbackSkill


EXTENSION_TIME = 10


class QuestionsAnswersSkill(FallbackSkill):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()
        self.is_searching = False
        self.searching_event = threading.Event()
        self.answer_message: typing.Optional[Message] = None
        self.action_event = threading.Event()

    def initialize(self):
        self.add_event("fallback-query.search", self.handle_query_search)
        self.add_event("question:query.response", self.handle_query_response)
        self.add_event("query:action-complete", self.handle_query_action_complete)
        self.register_fallback(self.handle_question, 5)
        self.qwords = [
            "tell me ",
            "answer ",
            "where ",
            "which ",
            "what ",
            "when ",
            "does ",
            "how ",
            "why ",
            "are ",
            "who ",
            "do ",
            "is ",
        ]
        super().initialize()

    def valid_question(self, utt):
        for word in self.qwords:
            if utt.startswith(word):
                return True
        return False

    # @intent_handler(AdaptIntent().require('Question'))
    def handle_question(self, message):
        """Send the phrase to the CommonQuerySkills and prepare for handling
        the replies.
        """
        utt = message.data.get("utterance")

        if not self.valid_question(utt):
            return False

        self.bus.emit(Message("fallback-query.search", data={"utterance": utt}))

        return True

    def handle_query_search(self, message):
        with self.activity():
            utt = message.data.get("utterance")

            if self.is_searching:
                self._stop_search()

            self.log.info("Searching for %s", utt)
            self._start_search()
            self.schedule_event(
                self._query_timeout,
                5,
                data={"phrase": utt},
                name="QuestionQueryTimeout",
            )

            self.bus.emit(message.forward("question:query", data={"phrase": utt}))

            self.gui.show_page("SearchingForAnswers.qml")
            self.speak_dialog("just.one.moment")
            self.searching_event.wait(timeout=6)

            if self.answer_message:
                self.log.info("CQS action start (data=%s)", self.answer_message.data)
                self.action_event.clear()
                self.bus.emit(
                    message.forward(
                        "question:action",
                        data={
                            "skill_id": self.answer_message.data["skill_id"],
                            "phrase": utt,
                            "callback_data": self.answer_message.data.get(
                                "callback_data"
                            ),
                        },
                    )
                )
                self.action_event.wait(timeout=60)
                self.log.info("CQS action complete")
            else:
                self.speak_dialog("noAnswer", wait=True)

    def handle_query_response(self, message):
        with self.lock:
            if not self.is_searching:
                return

            searching = message.data.get("searching")
            if searching:
                return

            answer = message.data.get("answer")

            if answer:
                skill_id = message.data["skill_id"]
                conf = message.data["conf"]

                if (not self.answer_message) or (
                    conf > self.answer_message.data["conf"]
                ):
                    self.log.info(
                        "Answer from %s: %s (confidence=%s)", skill_id, answer, conf
                    )
                    self.answer_message = message

    def _query_timeout(self, message):
        with self.lock:
            if not self.is_searching:
                return

            if self.answer_message:
                self._answer_found()
            else:
                self.log.info("Search timeout")
                self._stop_search()

    def handle_query_action_complete(self, message):
        self.action_event.set()

    def _start_search(self):
        self.is_searching = True
        self.answer_message = None
        self.searching_event.clear()

    def _stop_search(self):
        self.is_searching = False
        self.answer_message = None
        self.searching_event.set()

    def _answer_found(self):
        self.is_searching = False
        self.searching_event.set()


def create_skill():
    return QuestionsAnswersSkill()
