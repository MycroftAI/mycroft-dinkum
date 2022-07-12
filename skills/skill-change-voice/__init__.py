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

import lingua_franca
from lingua_franca.parse import extract_number

from mycroft.messagebus.message import Message
from mycroft.skills.core import MycroftSkill, intent_handler
from mycroft.util.log import LOG

VOICE_NORM = {
    "alan": "apope",
    "pope": "apope",
    "alan pope": "apope",
    "british male": "apope",
    "american female": "amy",
    "american male": "kusal",
}


class ChangeVoiceSkill(MycroftSkill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def initialize(self):
        lingua_franca.load_language("en")
        self.register_entity_file("voice.entity")

    @intent_handler("change-voice.intent")
    def handle_change_voice(self, message):
        with self.activity():
            voice = message.data.get("voice")

            if not voice:
                self.speak("Please specify a voice", wait=True)
                return

            voice_norm = VOICE_NORM.get(voice, voice)
            speaker: typing.Optional[int] = None

            if voice_norm.startswith("speaker "):
                speaker_str = voice_norm.split(maxsplit=1)[1]
                speaker = int(extract_number(speaker_str))
                if speaker > 108:
                    voice_norm = "cmu"
                    speaker = min(17, speaker - 109)
                else:
                    voice_norm = "vctk"

                speaker = max(speaker, 0)
            elif voice_norm not in VOICE_NORM.values():
                voice_norm = ""

            if not voice_norm:
                self.speak("I don't recognize that voice", wait=True)
                return

            self.gui.show_page("ChangingVoice.qml")
            try:
                self._change_voice(voice, voice_norm, speaker=speaker)
            finally:
                self.gui.release()

    def _change_voice(
        self, voice_name: str, voice_norm: str, speaker: typing.Optional[int] = None
    ):
        LOG.info("Changing voice to %s (speaker=%s)", voice_norm, speaker)
        self.bus.wait_for_response(
            Message(
                "mycroft.tts.change-voice",
                data={"voice": voice_norm, "speaker": speaker},
            ),
            "mycroft.tts.change-voice.reply",
            timeout=120,
        )
        self.speak(f"Voice has now been changed to {voice_name}", wait=True)


def create_skill():
    return ChangeVoiceSkill()
