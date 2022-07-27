# Copyright 2022 Mycroft AI Inc.
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
from mycroft.service import DinkumService

from .voice_loop import (
    load_hotword_module,
    load_stt_module,
    load_vad_detector,
    voice_loop,
)


class VoiceService(DinkumService):
    """
    Service for handling user voice input.

    Performs the following tasks:
    * Recording audio from microphone
    * Hotword detection
    * Voice activity detection (silence at end of voice command)
    * Speech to text

    Input messages:
    * mycroft.mic.mute
      * Produces empty audio stream
    * mycroft.mic.unmute
      * Uses real audio stream
    * mycroft.mic.listen
      * Wakes up mycroft and starts recording voice command

    Output messages:
    * recognizer_loop:awoken
      * Reports that mycroft is now awake
    * recognizer_loop:wake
      * Reports wake word used to wake up mycroft
    * recognizer_loop:record_begin
      * Reports that voice command recording has begun
    * recognizer_loop:record_end
      * Reports that voice command recording has ended
    * recognizer_loop:utterance
      * Result from speech to text of voice command
    * recognizer_loop:speech.recognition.unknown
      * Sent when empty result from speech to text is returned

    Service messages:
    * voice.service.connected
    * voice.service.connected.response
    * voice.initialize.started
    * voice.initialize.ended

    """

    def __init__(self):
        super().__init__(service_id="voice")

    def start(self):
        self.hotword = load_hotword_module(self.config)
        self.vad = load_vad_detector()
        self.stt = load_stt_module(self.config, self.bus)

    def run(self):
        self._wait_for_ready()
        voice_loop(
            config=self.config,
            bus=self.bus,
            hotword=self.hotword,
            vad=self.vad,
            stt=self.stt,
        )

    def stop(self):
        pass


def main():
    """Service entry point"""
    VoiceService().main()


if __name__ == "__main__":
    main()
