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
from typing import Optional

from mycroft.messagebus.message import Message
from mycroft.skills.fallback_skill import FallbackSkill

EXTENSION_TIME = 10


class QuestionsAnswersSkill(FallbackSkill):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()
        self.is_searching = False
        self.searching_event = threading.Event()
        self.answer_message: Optional[Message] = None
        self.action_event = threading.Event()
        self.query_done_event = threading.Event()

    def initialize(self):
        self.add_event("question:query.response", self.handle_query_response)
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

    def handle_question(self, message):
        """Send the phrase to the CommonQuerySkills and prepare for handling
        the replies.
        """
        utt = message.data.get("utterance")

        if not self.valid_question(utt):
            return False

        self.answer_message = None
        self.schedule_event(
            self._query_timeout,
            5,
            data={"phrase": utt, "mycroft_session_id": self._mycroft_session_id},
            name="QuestionQueryTimeout",
        )

        return True, self.continue_session(
            dialog="just.one.moment",
            speak_wait=False,
            message=Message("question:query", data={"phrase": utt}),
            gui="SearchingForAnswers.qml",
        )

    def handle_query_response(self, message):
        if message.data.get("mycroft_session_id") != self._mycroft_session_id:
            # Different session now
            return

        searching = message.data.get("searching")
        if searching:
            # No answer yet
            return

        answer = message.data.get("answer")

        if answer:
            skill_id = message.data["skill_id"]
            conf = message.data["conf"]

            if (not self.answer_message) or (conf > self.answer_message.data["conf"]):
                self.log.info(
                    "Answer from %s: %s (confidence=%s)", skill_id, answer, conf
                )
                self.answer_message = message

    def _query_timeout(self, message):
        if message.data.get("mycroft_session_id") != self._mycroft_session_id:
            # Different session now
            return

        if self.answer_message:
            # Engage action
            self.log.info("CQS action start (data=%s)", self.answer_message.data)
            self.bus.emit(
                message.forward(
                    "question:action",
                    data={
                        "mycroft_session_id": self._mycroft_session_id,
                        "skill_id": self.answer_message.data.get("skill_id"),
                        "phrase": message.data.get("phrase"),
                        "callback_data": self.answer_message.data.get("callback_data"),
                    },
                )
            )
        else:
            # No answers
            self.log.info("Search timeout")
            result = self.end_session(dialog="noAnswer")
            self.bus.emit(result)


def create_skill():
    return QuestionsAnswersSkill()
