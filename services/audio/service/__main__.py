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

from .audio_ui import AudioUserInterface
from .tts import SpeakHandler, load_tts_module


class AudioService(DinkumService):
    """
    Service for playing audio and text to speech.

    Input messages:
    * speak
      * Speak "utterance" with text to speech system
    * speak.cache
      * Cache audio for "utterance" (don't speak)
    * mycroft.tts.stop
      * Stop text to speech
    * mycroft.audio.play-sound
      * Play "uri" on sound effect channel
    * mycroft.audio.service.play
      * Stream "tracks" on music channel
      * tracks - list of uris
    * mycroft.audio.service.{pause,resume,stop}
      * Pause/resume/stop music

    Output messages:
    * recognizer_loop:audio_output_start
      * Start of text to speech
    * recognizer_loop:audio_output_end
      * End of text to speech
    * mycroft.audio.service.position
      * Music stream "position_ms" (milliseconds)
      * Sent while music is playing
    * mycroft.audio.service.{playing,paused,resumed,stopped}
      * State changes of music stream

    Service messages:
    * audio.service.connected
    * audio.service.connected.response
    * audio.initialize.started
    * audio.initialize.ended

    """

    def __init__(self):
        super().__init__(service_id="audio")

    def start(self):
        # Text to speech plugin
        self._tts = load_tts_module(self.config)

        # Audio UI/HAL
        self._audio_ui = AudioUserInterface(self.config)
        self._audio_ui.initialize(self.bus)

        # Handle "speak" events
        self._speak_handler = SpeakHandler(self.config, self.bus, self._tts)
        self._speak_handler.start()

    def stop(self):
        self._speak_handler.stop()
        self._audio_ui.shutdown()


def main():
    """Service entry point"""
    AudioService().main()


if __name__ == "__main__":
    main()
