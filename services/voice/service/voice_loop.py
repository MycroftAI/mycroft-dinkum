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
import audioop
import itertools
import logging
import time
import wave
from collections import deque
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any, Dict, Optional
from uuid import uuid4

import alsaaudio
import numpy as np
from mycroft.hotword import HotWordEngine
from mycroft.stt import MycroftSTT, StreamingSTT
from mycroft.util.file_utils import get_cache_directory
from mycroft.util.plugins import load_plugin
from mycroft_bus_client import Message, MessageBusClient

from .silero_vad import SileroVoiceActivityDetector
from .vad_command import VadCommand

LOG = logging.getLogger("voice")

AUDIO_DEVICE = "default"

# Seconds to wait for an audio chunk before erroring out
AUDIO_TIMEOUT = 5
AUDIO_THREAD_RETRIES = 3
AUDIO_THREAD_RETRY_SEC = 1

# Bytes to read from microphone at a time
AUDIO_CHUNK_SIZE = 4096

AUDIO_LOUDNESS_FACTOR = 1.0
"""Factor to multiply incoming audio by"""

# Onnx model path for Silero VAD
VAD_MODEL = Path(__file__).parent / "models" / "silero_vad.onnx"

# Threshold for silence detection (end of STT voice command)
VAD_THRESHOLD = 0.2

# Number of audio chunks to store for saving hotword WAV examples
HOTWORD_CHUNKS_TO_BUFFER = 15

# Number of audio chunks to use before hotword activation for STT.
# Increasing this number will start to include the end of the hotword in the STT
# voice command.
STT_CHUNKS_TO_BUFFER = 2

# Number of empty audio chunks to prepend to STT audio.
AUTO_SILENCE_CHUNKS = 5

SAMPLE_RATE = 16000  # hertz
SAMPLE_WIDTH = 2  # bytes
SAMPLE_CHANNELS = 1


class VoiceLoop:
    def __init__(
        self,
        config: Dict[str, Any],
        bus: MessageBusClient,
        hotword: HotWordEngine,
        vad: SileroVoiceActivityDetector,
        stt: StreamingSTT,
    ):
        self.config = config
        self.bus = bus
        self.hotword = hotword
        self.vad = vad
        self.stt = stt

        # TODO: Use config
        self.command = VadCommand(speech_begin=0.3, silence_end=0.8, timeout=10.0)

        self.log = logging.getLogger("voice.loop")

        # True if recording voice command for STT
        self.is_recording = False

        # True if mic is muted
        self.muted = False

        # True if we should treat the hotword as detected once (for get_response)
        self.listen_once = False

        # Current session id
        self.mycroft_session_id: Optional[str] = None

        # Name reported in recognizer_loop:wakeword
        self.wake_word_name = config.get("listener", {}).get("wake_word", "hey mycroft")

        # Audio chunks from arecord
        self.queue: "Queue[bytes]" = Queue()

        # Buffered audio that's used to store hotword samples
        self.hotword_audio_chunks = deque(maxlen=HOTWORD_CHUNKS_TO_BUFFER)

        # Directory to cache hotword recordings
        self.hotword_audio_dir = Path(get_cache_directory("hotword_recordings"))

        # Buffered audio that's sent to STT after wake
        self.stt_audio_chunks = deque(maxlen=STT_CHUNKS_TO_BUFFER)

        # Contains the audio from the last spoken voice command
        self.stt_audio = bytes()

        # Directory to cache STT recordings
        self.stt_audio_dir = Path(get_cache_directory("stt_recordings"))

        # Thread recording audio chunks
        self._audio_input_running = False
        self._audio_input_thread: Optional[Thread] = None

    def start(self):
        # Start arecord in separate thread
        # TODO: Use configurable command
        self._audio_input_running = True
        self._audio_input_thread = Thread(target=self._audio_input, daemon=True)
        self._audio_input_thread.start()

        self.bus.on("mycroft.mic.mute", self.handle_mute)
        self.bus.on("mycroft.mic.unmute", self.handle_unmute)
        self.bus.on("mycroft.mic.listen", self.handle_listen)

    def stop(self):
        """Gracefully"""
        if self._audio_input_thread is not None:
            self._audio_input_running = False
            self._audio_input_thread.join()
            self._audio_input_thread = None

    def run(self):
        while True:
            chunk = self.queue.get(timeout=AUDIO_TIMEOUT)
            assert chunk, "Empty audio chunk"

            if self.muted:
                self.stt_audio_chunks.clear()
                chunk = bytes(len(chunk))

            self.stt_audio_chunks.append(chunk)
            if not self.is_recording:
                self.hotword_audio_chunks.append(chunk)
                self.hotword.update(chunk)
                if self.listen_once:
                    # Fake detection for get_response
                    self.listen_once = False
                    hotword_detected = True
                else:
                    # Normal hotword detection
                    self.mycroft_session_id = None
                    hotword_detected = self.hotword.found_wake_word(None) and (
                        not self.muted
                    )

                if hotword_detected:
                    self.log.info("Hotword detected!")

                    # Save audio example
                    self._save_hotword_audio()
                    self.hotword_audio_chunks.clear()

                    # Wake up
                    self.do_listen()

                    # Reset state of hotword
                    self.hotword.reset()
            else:
                # In voice command
                self.stt.update(chunk)
                self.stt_audio += chunk
                seconds = _chunk_seconds(
                    len(chunk),
                    sample_rate=SAMPLE_RATE,
                    sample_width=SAMPLE_WIDTH,
                    channels=SAMPLE_CHANNELS,
                )

                # Check for end of voice command
                chunk_array = np.frombuffer(chunk, dtype=np.int16)
                is_speech = self.vad(chunk_array) >= VAD_THRESHOLD
                if self.command.process(is_speech, seconds):
                    self.is_recording = False
                    text = self.stt.stop() or ""
                    self.log.info("STT: %s", text)

                    self.bus.emit(
                        Message(
                            "recognizer_loop:record_end",
                            {
                                "mycroft_session_id": self.mycroft_session_id,
                            },
                        )
                    )

                    if text:
                        self.bus.emit(
                            Message(
                                "recognizer_loop:utterance",
                                {
                                    "utterances": [text],
                                    "mycroft_session_id": self.mycroft_session_id,
                                },
                            )
                        )
                    else:
                        self.bus.emit(
                            Message("recognizer_loop:speech.recognition.unknown")
                        )

                    self._save_stt_audio()

    def do_listen(self):
        if self.muted:
            self.log.warning("Not waking up since we're muted")
            return

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
                    "utterance": self.wake_word_name,
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

        # Begin voice command
        self.stt_audio = bytes()
        self.command.reset()
        self.stt.start()
        self.is_recording = True

        # Push audio buffer into STT
        buffered_chunks = [
            [bytes(AUDIO_CHUNK_SIZE)] * AUTO_SILENCE_CHUNKS,
            self.stt_audio_chunks,
        ]
        for buffered_chunk in itertools.chain.from_iterable(buffered_chunks):
            seconds = _chunk_seconds(
                len(buffered_chunk),
                sample_rate=SAMPLE_RATE,
                sample_width=SAMPLE_WIDTH,
                channels=SAMPLE_CHANNELS,
            )

            self.stt.update(buffered_chunk)
            self.stt_audio += buffered_chunk
            chunk_array = np.frombuffer(buffered_chunk, dtype=np.int16)
            is_speech = self.vad(chunk_array) >= VAD_THRESHOLD
            self.command.process(is_speech, seconds)

        self.stt_audio_chunks.clear()

    def handle_mute(self, _message):
        self.muted = True
        self.log.info("Muted microphone")

    def handle_unmute(self, _message):
        self.muted = False
        self.log.info("Unmuted microphone")

    def handle_listen(self, message):
        self.mycroft_session_id = message.data.get("mycroft_session_id")
        self.listen_once = True

    def _save_hotword_audio(self):
        try:
            wav_path = self.hotword_audio_dir / f"{time.monotonic_ns()}.wav"
            with open(wav_path, "wb") as wav_io, wave.open(wav_io, "wb") as wav_file:
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.setsampwidth(SAMPLE_WIDTH)
                wav_file.setnchannels(SAMPLE_CHANNELS)

                for chunk in self.hotword_audio_chunks:
                    wav_file.writeframes(chunk)

            self.log.debug("Wrote %s", wav_path)
        except Exception:
            self.log.exception("Error while saving STT audio")

    def _save_stt_audio(self):
        try:
            wav_path = self.stt_audio_dir / f"{time.monotonic_ns()}.wav"
            with open(wav_path, "wb") as wav_io, wave.open(wav_io, "wb") as wav_file:
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.setsampwidth(SAMPLE_WIDTH)
                wav_file.setnchannels(SAMPLE_CHANNELS)
                wav_file.writeframes(self.stt_audio)

            self.log.debug("Wrote %s", wav_path)
        except Exception:
            self.log.exception("Error while saving STT audio")

    def _audio_input(self):
        for _ in range(AUDIO_THREAD_RETRIES):
            try:
                # TODO: Use config
                mic = alsaaudio.PCM(
                    type=alsaaudio.PCM_CAPTURE,
                    rate=SAMPLE_RATE,
                    channels=SAMPLE_CHANNELS,
                    format=alsaaudio.PCM_FORMAT_S32_LE
                    if SAMPLE_WIDTH == 4
                    else alsaaudio.PCM_FORMAT_S16_LE,
                    device=AUDIO_DEVICE,
                    periodsize=AUDIO_CHUNK_SIZE // SAMPLE_WIDTH,
                )
                try:
                    while self._audio_input_running:
                        chunk_length, chunk = mic.read()
                        if chunk_length <= 0:
                            LOG.warning("Bad chunk length: %s", chunk_length)
                            continue

                        # Increase loudness of audio
                        if AUDIO_LOUDNESS_FACTOR != 1.0:
                            chunk = audioop.mul(
                                chunk, SAMPLE_WIDTH, AUDIO_LOUDNESS_FACTOR
                            )

                        self.queue.put_nowait(chunk)
                finally:
                    mic.close()
            except Exception:
                LOG.exception("Unexpected error in audio input thread")

            if not self._audio_input_running:
                break

            LOG.debug("Retrying audio input in %s second(s)", AUDIO_THREAD_RETRY_SEC)
            time.sleep(AUDIO_THREAD_RETRY_SEC)


def load_hotword_module(config: Dict[str, Any]) -> HotWordEngine:
    wake_word = config["listener"]["wake_word"]
    hotword_config = config["hotwords"][wake_word]
    module_name = hotword_config["module"]

    LOG.debug("Loading wake word module: %s", module_name)
    module = load_plugin("mycroft.plugin.wake_word", module_name)
    assert module, f"Failed to load {module_name}"
    hotword = module(config=hotword_config)
    LOG.info("Loaded wake word module: %s", module_name)

    return hotword


def load_stt_module(config: Dict[str, Any], bus: MessageBusClient) -> StreamingSTT:
    stt_config = config["stt"]
    module_name = stt_config["module"]
    if module_name == "mycroft":
        LOG.debug("Using Mycroft STT")
        return MycroftSTT(bus, config)

    LOG.debug("Loading speech to text module: %s", module_name)
    module = load_plugin("mycroft.plugin.stt", module_name)
    assert module, f"Failed to load {module_name}"
    module_config = stt_config.get(module_name, {})
    stt = module(bus=bus, config=module_config)
    LOG.info("Loaded speech to text module: %s", module_name)

    return stt


def load_vad_detector() -> SileroVoiceActivityDetector:
    return SileroVoiceActivityDetector(str(VAD_MODEL))


def _chunk_seconds(
    chunk_length: int, sample_rate: int, sample_width: int, channels: int
):
    """Returns the number of seconds in an audio chunk"""
    num_samples = chunk_length / (sample_width * channels)
    seconds = num_samples / sample_rate

    return seconds
