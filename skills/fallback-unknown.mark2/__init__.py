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
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional

from mycroft.messagebus.message import Message
from mycroft.skills import AdaptIntent, GuiClear, intent_handler
from mycroft.skills.fallback_skill import FallbackSkill

MAX_DISPLAY_UTTERANCES = 4


@dataclass
class Utterance:
    text: str
    mycroft_session_id: Optional[str] = None
    hotword_audio_uri: Optional[str] = None
    stt_audio_uri: Optional[str] = None


class UnknownSkill(FallbackSkill):
    def __init__(self, skill_id: str):
        super().__init__(skill_id=skill_id, name="Unknown Skill")
        self.last_utterances: Dequeue[Utterance] = deque(
            maxlen=MAX_DISPLAY_UTTERANCES + 1
        )
        self.question_vocab = dict()

    def initialize(self):
        self.register_fallback(self.handle_fallback, 100)
        self.add_event(
            "mycroft.speech.recognition.unknown", self.handle_unknown_recognition
        )
        self.add_event("complete_intent_failure", self.handle_unknown_recognition)
        self.add_event("recognizer_loop:utterance", self.handle_utterance)
        self.add_event(
            "mycroft.speech.recognition.unknown", self.handle_unknown_recognition
        )
        self.gui.register_handler(
            "play",
            "utterance.qml",
            self.handle_play,
        )
        self.gui.register_handler(
            "close",
            "utterance.qml",
            self.handle_close,
        )
        self.load_question_vocab()
        super().initialize()

    def load_question_vocab(self):
        """Load question marker vocabulary to provide more specific response."""
        for group in ["question", "who.is", "why.is"]:
            self.question_vocab[group] = [
                vocab[0] for vocab in self.resources.load_vocabulary_file(group)
            ]

    def handle_fallback(self, message):
        utterance = message.data["utterance"].lower()
        for key, vocab in self.question_vocab.items():
            for line in vocab:
                if utterance.startswith(line):
                    self.log.info("Fallback type: " + line)
                    return True, self.end_session(
                        dialog=(key, {"remaining": line.replace(key, "")})
                    )

        self.log.info(utterance)
        return True, self.end_session(dialog="unknown")

    def handle_unknown_recognition(self, message):
        """Called when no transcription is returned from STT"""
        self.log.info("Unknown recognition")
        return self.end_session(
            dialog="unknown", gui=self.gui_show(), gui_clear=GuiClear.ON_IDLE
        )

    def handle_utterance(self, message):
        utterances = message.data.get("utterances")
        if utterances:
            self.last_utterances.append(
                Utterance(
                    text=utterances[0],
                    mycroft_session_id=message.data.get("mycroft_session_id"),
                    hotword_audio_uri=message.data.get("hotword_audio_uri"),
                    stt_audio_uri=message.data.get("stt_audio_uri"),
                )
            )

    def handle_play(self, message):
        uri = message.data.get("uri")
        if uri:
            self.bus.emit(Message("mycroft.audio.play-sound", data={"uri": uri}))

    def handle_close(self, message):
        self.bus.emit(Message("mycroft.gui.idle"))

    @intent_handler(AdaptIntent().require("show").require("utterance"))
    def show_last_utterance(self, _):
        """Handles a user's request to show the most recent utterance."""
        return self.end_session(gui=self.gui_show(), gui_clear=GuiClear.NEVER)

    def gui_show(self):
        """Show speech to text utterance for debugging"""
        gui_data = {}
        for utt_idx, utt in enumerate(self.last_utterances):
            label = f"utterance{utt_idx+1}"
            gui_data[label] = utt.text
            gui_data[f"{label}_hotword_audio"] = utt.hotword_audio_uri
            gui_data[f"{label}_stt_audio"] = utt.stt_audio_uri

        return ("utterance.qml", gui_data)


def create_skill(skill_id: str):
    return UnknownSkill(skill_id=skill_id)
