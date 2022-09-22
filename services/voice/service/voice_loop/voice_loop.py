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
import logging
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Deque, Optional

from mycroft.hotword import HotWordEngine
from mycroft.stt import StreamingSTT
from mycroft.util.audio import debiased_energy

from .microphone import Microphone
from .voice_activity import VoiceActivity

LOG = logging.getLogger("voice_loop")


@dataclass
class VoiceLoop:
    mic: Microphone
    hotword: HotWordEngine
    stt: StreamingSTT
    vad: VoiceActivity

    def start(self):
        raise NotImplementedError()

    def run(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()


# -----------------------------------------------------------------------------


@dataclass
class ChunkInfo:
    vad_probability: float = 0.0
    is_speech: bool = False
    energy: float = 0.0
    hotword_probability: Optional[float] = None


WakeCallback = Callable[[], None]
TextCallback = Callable[[str], None]
AudioCallback = Callable[[bytes], None]
ChunkCallback = Callable[[ChunkInfo], None]


class State(Enum):
    DETECT_WAKEWORD = auto()
    BEFORE_COMMAND = auto()
    IN_COMMAND = auto()
    AFTER_COMMAND = auto()


@dataclass
class MycroftVoiceLoop(VoiceLoop):
    speech_seconds: float
    silence_seconds: float
    timeout_seconds: float
    num_stt_rewind_chunks: int
    num_hotword_keep_chunks: int
    skip_next_wake: bool = False
    wake_callback: Optional[WakeCallback] = None
    text_callback: Optional[TextCallback] = None
    hotword_audio_callback: Optional[AudioCallback] = None
    stt_audio_callback: Optional[AudioCallback] = None
    chunk_callback: Optional[ChunkCallback] = None
    is_muted: bool = False
    _is_running: bool = False
    _chunk_info: ChunkInfo = field(default_factory=ChunkInfo)

    def start(self):
        self._is_running = True

    def run(self):
        # Voice command state
        speech_seconds_left = self.speech_seconds
        silence_seconds_left = self.silence_seconds
        timeout_seconds_left = self.timeout_seconds
        state = State.DETECT_WAKEWORD

        # Keep hotword/STT audio so they can (optionally) be saved to disk
        hotword_chunks = deque(maxlen=self.num_hotword_keep_chunks)
        stt_audio_bytes = bytes()

        # Audio from just before the wake word is detected is kept for STT.
        # This allows you to speak a command immediately after the wake word.
        stt_chunks: Deque[bytes] = deque(maxlen=self.num_stt_rewind_chunks + 1)

        has_probability = hasattr(self.hotword, "probability")

        while self._is_running:
            chunk = self.mic.read_chunk()
            assert chunk is not None, "No audio from microphone"

            if self.is_muted:
                # Soft mute
                chunk = bytes(self.mic.chunk_size)

            self._reset_diagnostics()

            # State machine:
            #
            # DETECT_HOTWORD -> BEFORE_COMMAND
            # BEFORE_COMMAND -> {IN_COMMAND, AFTER_COMMAND}
            # IN_COMMAND -> AFTER_COMMAND
            # AFTER_COMMAND -> DETECT_HOTWORD
            #
            if state == State.DETECT_WAKEWORD:
                hotword_chunks.append(chunk)
                stt_chunks.append(chunk)
                self.hotword.update(chunk)

                if has_probability:
                    # For diagnostics
                    self._chunk_info.hotword_probability = self.hotword.probability

                if self.chunk_callback is not None:
                    # Need to calculate VAD probability for diagnostics.
                    # This is usually not calculated until STT recording.
                    (
                        self._chunk_info.is_speech,
                        self._chunk_info.vad_probability,
                    ) = self.vad.is_speech(chunk)

                if self.hotword.found_wake_word(None) or self.skip_next_wake:

                    # Callback to handle recorded hotword audio
                    if (self.hotword_audio_callback is not None) and (
                        not self.skip_next_wake
                    ):
                        hotword_audio_bytes = bytes()
                        while hotword_chunks:
                            hotword_audio_bytes += hotword_chunks.popleft()

                        self.hotword_audio_callback(hotword_audio_bytes)

                    self.skip_next_wake = False
                    hotword_chunks.clear()

                    # Callback to handle wake up
                    if self.wake_callback is not None:
                        self.wake_callback()

                    # Wake word detected, begin recording voice command
                    state = State.BEFORE_COMMAND
                    speech_seconds_left = self.speech_seconds
                    timeout_seconds_left = self.timeout_seconds
                    stt_audio_bytes = bytes()
                    self.stt.start()

                    # Reset the VAD internal state to avoid the model getting
                    # into a degenerative state where it always reports silence.
                    self.vad.reset()

                self._send_diagnostics(chunk)
            elif state == State.BEFORE_COMMAND:
                # Recording voice command, but user has not spoken yet
                stt_audio_bytes += chunk
                stt_chunks.append(chunk)
                while stt_chunks:
                    stt_chunk = stt_chunks.popleft()
                    self.stt.update(stt_chunk)

                    timeout_seconds_left -= self.mic.seconds_per_chunk
                    if timeout_seconds_left <= 0:
                        # Recording has timed out
                        state = State.AFTER_COMMAND
                        break

                    # Wait for enough speech before looking for the end of the
                    # command (silence).
                    (
                        self._chunk_info.is_speech,
                        self._chunk_info.vad_probability,
                    ) = self.vad.is_speech(stt_chunk)
                    self._send_diagnostics(chunk)

                    if self._chunk_info.is_speech:
                        speech_seconds_left -= self.mic.seconds_per_chunk
                        if speech_seconds_left <= 0:
                            # Voice command has started, so start looking for the
                            # end.
                            state = State.IN_COMMAND
                            silence_seconds_left = self.silence_seconds
                            break
                    else:
                        # Reset
                        speech_seconds_left = self.speech_seconds
            elif state == State.IN_COMMAND:
                # Recording voice command until user stops speaking
                stt_audio_bytes += chunk
                stt_chunks.append(chunk)
                while stt_chunks:
                    stt_chunk = stt_chunks.popleft()
                    self.stt.update(stt_chunk)

                    timeout_seconds_left -= self.mic.seconds_per_chunk
                    if timeout_seconds_left <= 0:
                        # Recording has timed out
                        state = State.AFTER_COMMAND
                        break

                    # Wait for enough silence before considering the command to be
                    # ended.
                    (
                        self._chunk_info.is_speech,
                        self._chunk_info.vad_probability,
                    ) = self.vad.is_speech(stt_chunk)
                    self._send_diagnostics(chunk)

                    if not self._chunk_info.is_speech:
                        silence_seconds_left -= self.mic.seconds_per_chunk
                        if silence_seconds_left <= 0:
                            # End of voice command detected
                            state = State.AFTER_COMMAND
                            break
                    else:
                        # Reset
                        silence_seconds_left = self.silence_seconds
            elif state == State.AFTER_COMMAND:
                # Voice command has finished recording
                if self.stt_audio_callback is not None:
                    self.stt_audio_callback(stt_audio_bytes)

                stt_audio_bytes = bytes()

                # Command has ended, get text and trigger callback
                text = self.stt.stop() or ""

                # Callback to handle STT text
                if self.text_callback is not None:
                    self.text_callback(text)

                # Back to detecting wake word
                state = State.DETECT_WAKEWORD

                # Clear any buffered STT chunks
                stt_chunks.clear()

                self._send_diagnostics(chunk)

    def stop(self):
        self._is_running = False

    def _reset_diagnostics(self):
        self._chunk_info.vad_probability = 0.0
        self._chunk_info.is_speech = False
        self._chunk_info.hotword_probability = None
        self._chunk_info.energy = 0.0

    def _send_diagnostics(self, chunk: bytes):
        if self.chunk_callback is not None:
            self._chunk_info.energy = debiased_energy(chunk, self.mic.sample_width)
            self.chunk_callback(self._chunk_info)
