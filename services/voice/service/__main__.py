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
import dataclasses
import time
import wave
from pathlib import Path
from typing import Optional
from uuid import uuid4

from mycroft_bus_client import Message

from mycroft.hotword import load_hotword_module
from mycroft.service import DinkumService
from mycroft.stt import load_stt_module
from mycroft.util.file_utils import get_cache_directory, resolve_resource_file
from mycroft.util.log import configure_mycroft_logger
from .voice_loop import AlsaMicrophone, MycroftVoiceLoop, SileroVoiceActivity

configure_mycroft_logger("voice")


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
        self.mycroft_session_id: Optional[str] = None
        self._is_diagnostics_enabled = False
        self._last_hotword_audio_uri: Optional[str] = None
        self._last_stt_audio_uri: Optional[str] = None

    def start(self):
        listener = self.config["listener"]

        mic = AlsaMicrophone(
            device=listener["device_name"],
            sample_rate=listener["sample_rate"],
            sample_width=listener["sample_width"],
            sample_channels=listener["sample_channels"],
            chunk_size=listener["chunk_size"],
            period_size=listener["period_size"],
            #
            multiplier=listener["multiplier"],
            timeout=listener["audio_timeout"],
            audio_retries=listener["audio_retries"],
            audio_retry_delay=listener["audio_retry_delay"],
        )
        mic.start()

        hotword = load_hotword_module(self.config)

        vad = SileroVoiceActivity(
            model=resolve_resource_file(listener["vad_model"]),
            threshold=listener["vad_threshold"],
        )
        vad.start()

        stt = load_stt_module(self.config, self.bus)
        stt.start()

        self.voice_loop = MycroftVoiceLoop(
            mic=mic,
            hotword=hotword,
            stt=stt,
            vad=vad,
            #
            speech_seconds=listener["speech_begin"],
            silence_seconds=listener["silence_end"],
            timeout_seconds=listener["recording_timeout"],
            num_stt_rewind_chunks=listener["utterance_chunks_to_rewind"],
            num_hotword_keep_chunks=listener["wakeword_chunks_to_save"],
            #
            wake_callback=self._wake,
            text_callback=self._stt_text,
            hotword_audio_callback=self._hotword_audio,
            stt_audio_callback=self._stt_audio,
        )
        self.voice_loop.start()

        # Register events
        self.bus.on("mycroft.mic.mute", self._handle_mute)
        self.bus.on("mycroft.mic.unmute", self._handle_unmute)
        self.bus.on("mycroft.mic.listen", self._handle_listen)
        self.bus.on("mycroft.mic.set-diagnostics", self._handle_set_diagnostics)

    def run(self):
        self._wait_for_ready()
        self.voice_loop.run()

    def stop(self):
        self.voice_loop.stop()

        mic, hotword, vad, stt = (
            self.voice_loop.mic,
            self.voice_loop.hotword,
            self.voice_loop.vad,
            self.voice_loop.stt,
        )

        if hasattr(stt, "shutdown"):
            stt.shutdown()

        vad.stop()

        if hasattr(hotword, "shutdown"):
            hotword.shutdown()

        mic.stop()

    def _wake(self):
        self.log.debug("Awake!")

        if self.mycroft_session_id is None:
            self.mycroft_session_id = str(uuid4())

        self.bus.emit(
            Message(
                "recognizer_loop:awoken",
                data={"mycroft_session_id": self.mycroft_session_id},
            )
        )
        self.bus.emit(
            Message(
                "recognizer_loop:wakeword",
                data={
                    "utterance": self.config["listener"]["wake_word"],
                    "session": self.mycroft_session_id,
                },
            )
        )
        self.bus.emit(
            Message(
                "recognizer_loop:record_begin",
                {
                    "mycroft_session_id": self.mycroft_session_id,
                },
            )
        )

    def _hotword_audio(self, audio_bytes: bytes):
        try:
            listener = self.config["listener"]
            if listener["record_wake_words"]:
                save_path = listener.get("save_path")
                if save_path:
                    hotword_audio_dir = Path(save_path) / "mycroft_wake_words"
                else:
                    hotword_audio_dir = Path(get_cache_directory("mycroft_wake_words"))

                hotword_audio_dir.mkdir(parents=True, exist_ok=True)

                mic = self.voice_loop.mic
                wav_path = hotword_audio_dir / f"{time.monotonic_ns()}.wav"
                with open(wav_path, "wb") as wav_io, wave.open(
                    wav_io, "wb"
                ) as wav_file:
                    wav_file.setframerate(mic.sample_rate)
                    wav_file.setsampwidth(mic.sample_width)
                    wav_file.setnchannels(mic.sample_channels)
                    wav_file.writeframes(audio_bytes)

                self.log.debug("Wrote %s", wav_path)
                self._last_hotword_audio_uri = f"file://{wav_path.absolute()}"
        except Exception:
            self.log.exception("Error while saving STT audio")

    def _stt_text(self, text: str):
        self.bus.emit(
            Message(
                "recognizer_loop:record_end",
                {
                    "mycroft_session_id": self.mycroft_session_id,
                },
            )
        )

        if self._is_diagnostics_enabled:
            # Bypass intent service when diagnostics are enabled
            self.bus.emit(
                Message(
                    "mycroft.mic.diagnostics:utterance",
                    data={"utterance": text},
                )
            )
        else:
            # Report utterance to intent service
            if text:
                self.bus.emit(
                    Message(
                        "recognizer_loop:utterance",
                        {
                            "utterances": [text],
                            "mycroft_session_id": self.mycroft_session_id,
                            "hotword_audio_uri": self._last_hotword_audio_uri,
                            "stt_audio_uri": self._last_stt_audio_uri,
                        },
                    )
                )
            else:
                self.bus.emit(Message("recognizer_loop:speech.recognition.unknown"))

        self.log.debug("STT: %s", text)
        self.mycroft_session_id = None

    def _stt_audio(self, audio_bytes: bytes):
        try:
            listener = self.config["listener"]
            if listener["save_utterances"]:
                save_path = listener.get("save_path")
                if save_path:
                    stt_audio_dir = Path(save_path) / "mycroft_utterances"
                else:
                    stt_audio_dir = Path(get_cache_directory("mycroft_utterances"))

                stt_audio_dir.mkdir(parents=True, exist_ok=True)

                mic = self.voice_loop.mic
                wav_path = stt_audio_dir / f"{time.monotonic_ns()}.wav"
                with open(wav_path, "wb") as wav_io, wave.open(
                    wav_io, "wb"
                ) as wav_file:
                    wav_file.setframerate(mic.sample_rate)
                    wav_file.setsampwidth(mic.sample_width)
                    wav_file.setnchannels(mic.sample_channels)
                    wav_file.writeframes(audio_bytes)

                self.log.debug("Wrote %s", wav_path)
                self._last_stt_audio_uri = f"file://{wav_path.absolute()}"
        except Exception:
            self.log.exception("Error while saving STT audio")

    def _chunk_diagnostics(self, chunk_info):
        if self._is_diagnostics_enabled:
            self.bus.emit(
                Message("mycroft.mic.diagnostics", data=dataclasses.asdict(chunk_info))
            )

    def _handle_mute(self, _message: Message):
        self.voice_loop.is_muted = True

    def _handle_unmute(self, _message: Message):
        self.voice_loop.is_muted = False

    def _handle_listen(self, message: Message):
        self.mycroft_session_id = message.data.get("mycroft_session_id")
        self.voice_loop.skip_next_wake = True

    def _handle_set_diagnostics(self, message: Message):
        self._is_diagnostics_enabled = message.data.get("enabled", True)

        if self._is_diagnostics_enabled:
            self.voice_loop.chunk_callback = self._chunk_diagnostics
            self.log.debug("Diagnostics enabled")
        else:
            self.voice_loop.chunk_callback = None
            self.log.debug("Diagnostics disabled")


def main():
    """Service entry point"""
    VoiceService().main()


if __name__ == "__main__":
    main()
