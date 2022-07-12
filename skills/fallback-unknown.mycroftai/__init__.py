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
import time
import typing
from collections import deque

from mycroft.skills.fallback_skill import FallbackSkill
from mycroft.skills import AdaptIntent, intent_handler
from mycroft.util.log import LOG

MAX_DISPLAY_UTTERANCES = 4


class UnknownSkill(FallbackSkill):
    def __init__(self):
        super(UnknownSkill, self).__init__()
        self.last_utterances = deque(maxlen=MAX_DISPLAY_UTTERANCES + 1)
        self.question_vocab = dict()

    def initialize(self):
        self.register_fallback(self.handle_fallback, 100)
        self.add_event(
            "mycroft.speech.recognition.unknown", self.handle_unknown_recognition
        )
        self.add_event("complete_intent_failure", self.handle_unknown_recognition)
        self.add_event("recognizer_loop:utterance", self.handle_utterance)
        self.load_question_vocab()

    def load_question_vocab(self):
        """Load question marker vocabulary to provide more specific response."""
        for group in ["question", "who.is", "why.is"]:
            self.question_vocab[group] = [
                vocab[0] for vocab in self.resources.load_vocabulary_file(group)
            ]

    def handle_fallback(self, message):
        with self.activity():
            self.gui_show(self.last_utterances)

            utterance = message.data["utterance"].lower()
            try:
                self.report_metric("failed-intent", {"utterance": utterance})
            except Exception:
                self.log.exception("Error reporting metric")

            for key, vocab in self.question_vocab.items():
                for line in vocab:
                    if utterance.startswith(line):
                        self.log.info("Fallback type: " + line)
                        self.speak_dialog(
                            key, data={"remaining": line.replace(key, "")}, wait=True
                        )
                        return True

            self.log.info(utterance)
            self.speak_dialog("unknown", wait=True)
            time.sleep(5)
            self.gui.release()

            return True

    def handle_unknown_recognition(self, message):
        """Called when no transcription is returned from STT"""
        with self.activity():
            self.log.info("Unknown recognition")
            self.speak_dialog("unknown", wait=True)

    def handle_utterance(self, message):
        utterances = message.data.get("utterances")
        if utterances:
            self.last_utterances.append(utterances[0])

    @intent_handler(AdaptIntent().require("show").require("utterance"))
    def show_last_utterance(self, _):
        """Handles a user's request to show the most recent utterance."""
        with self.activity():
            self.gui_show(self.last_utterances)
            time.sleep(5)
            self.gui.release()

    def gui_show(self, utterances: typing.Iterable[str]):
        """Show speech to text utterance for debugging"""
        for utt_idx, utt in enumerate(reversed(utterances)):
            self.gui[f"utterance{utt_idx+1}"] = utt

        self.gui.replace_page("utterance.qml", override_idle=True)


def create_skill():
    return UnknownSkill()
