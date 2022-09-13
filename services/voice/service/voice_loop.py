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

        # Load config values
        listener = self.config["listener"]
        self._device_name = listener["device_name"]
        self._sample_rate = listener["sample_rate"]
        self._sample_width = listener["sample_width"]
        self._sample_channels = listener["sample_channels"]
        self._multiplier = listener["multiplier"]
        self._vad_threshold = listener["vad_threshold"]
        self._chunk_size = listener["chunk_size"]
        self._audio_silence_chunks = listener["audio_silence_chunks"]

        self._audio_timeout = listener["audio_timeout"]
        self._audio_retries = listener["audio_retries"]
        self._audio_retry_delay = listener["audio_retry_delay"]

        self.command = VadCommand(
            speech_begin=listener["speech_begin"],
            silence_end=listener["silence_end"],
            timeout=listener["recording_timeout"],
        )

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
        self.hotword_audio_chunks = deque(maxlen=listener["wakeword_chunks_to_save"])

        save_path = listener.get("save_path")

        # Directory to cache hotword recordings
        if save_path:
            self.hotword_audio_dir = Path(save_path) / "mycroft_wake_words"
        else:
            self.hotword_audio_dir = Path(get_cache_directory("mycroft_wake_words"))
        self.hotword_audio_dir.mkdir(parents=True, exist_ok=True)

        # Buffered audio that's sent to STT after wake
        self.stt_audio_chunks = deque(maxlen=listener["utterance_chunks_to_rewind"])

        # Contains the audio from the last spoken voice command
        self.stt_audio = bytes()

        # Directory to cache STT recordings
        if save_path:
            self.stt_audio_dir = Path(save_path) / "mycroft_utterances"
        else:
            self.stt_audio_dir = Path(get_cache_directory("mycroft_utterances"))
        self.stt_audio_dir.mkdir(parents=True, exist_ok=True)

        # Thread recording audio chunks
        self._audio_input_running = False
        self._audio_input_thread: Optional[Thread] = None

        # True if diagnostic events should be sent out
        self._diagnostics_enabled = False

    def start(self):
        # Record audio in a separate thread to avoid overruns
        self._audio_input_running = True
        self._audio_input_thread = Thread(target=self._audio_input, daemon=True)
        self._audio_input_thread.start()

        self.bus.on("mycroft.mic.mute", self.handle_mute)
        self.bus.on("mycroft.mic.unmute", self.handle_unmute)
        self.bus.on("mycroft.mic.listen", self.handle_listen)
        self.bus.on("mycroft.mic.set-diagnostics", self.handle_set_diagnostics)

    def stop(self):
        """Gracefully"""
        if self._audio_input_thread is not None:
            self._audio_input_running = False
            self._audio_input_thread.join()
            self._audio_input_thread = None

    def run(self):
        while True:
            chunk = self.queue.get(timeout=self._audio_timeout)
            assert chunk, "Empty audio chunk"

            if self.muted:
                self.stt_audio_chunks.clear()
                chunk = bytes(len(chunk))

            is_speech: Optional[bool] = None
            diagnostics: Optional[Dict[str, Any]] = None
            if self._diagnostics_enabled:
                vad_probability = self.vad(np.frombuffer(chunk, dtype=np.int16)).item()
                is_speech = vad_probability >= self._vad_threshold
                diagnostics = {
                    "vad_probability": vad_probability,
                    "is_speech": is_speech,
                    "energy": _debiased_energy(chunk, self._sample_width),
                }

            self.stt_audio_chunks.append(chunk)
            if not self.is_recording:
                self.hotword_audio_chunks.append(chunk)
                self.hotword.update(chunk)

                if (diagnostics is not None) and hasattr(self.hotword, "probability"):
                    diagnostics["hotword_probability"] = self.hotword.probability

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

                    if self.config["listener"]["record_wake_words"]:
                        # Save audio example
                        self._save_hotword_audio()

                    self.hotword_audio_chunks.clear()

                    # Wake up
                    self.do_listen()

                    # Reset state of hotword
                    if hasattr(self.hotword, "reset"):
                        self.hotword.reset()
            else:
                # In voice command
                self.stt.update(chunk)
                self.stt_audio += chunk
                seconds = _chunk_seconds(
                    len(chunk),
                    sample_rate=self._sample_rate,
                    sample_width=self._sample_width,
                    channels=self._sample_channels,
                )

                # Check for end of voice command
                if is_speech is None:
                    is_speech = (
                        self.vad(np.frombuffer(chunk, dtype=np.int16))
                        >= self._vad_threshold
                    )

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

                    if self.config["listener"]["save_utterances"]:
                        self._save_stt_audio()

            if diagnostics is not None:
                self.bus.emit(Message("mycroft.mic.diagnostics", data=diagnostics))

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
            [bytes(self._chunk_size)] * self._audio_silence_chunks,
            self.stt_audio_chunks,
        ]
        for buffered_chunk in itertools.chain.from_iterable(buffered_chunks):
            seconds = _chunk_seconds(
                len(buffered_chunk),
                sample_rate=self._sample_rate,
                sample_width=self._sample_width,
                channels=self._sample_channels,
            )

            self.stt.update(buffered_chunk)
            self.stt_audio += buffered_chunk
            is_speech = (
                self.vad(np.frombuffer(buffered_chunk, dtype=np.int16))
                >= self._vad_threshold
            )
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

    def handle_set_diagnostics(self, message):
        self._diagnostics_enabled = message.data.get("enabled", True)
        self.log.debug("Diagnostics: enabled=%s", self._diagnostics_enabled)

    def _save_hotword_audio(self):
        try:
            wav_path = self.hotword_audio_dir / f"{time.monotonic_ns()}.wav"
            with open(wav_path, "wb") as wav_io, wave.open(wav_io, "wb") as wav_file:
                wav_file.setframerate(self._sample_rate)
                wav_file.setsampwidth(self._sample_width)
                wav_file.setnchannels(self._sample_channels)

                for chunk in self.hotword_audio_chunks:
                    wav_file.writeframes(chunk)

            self.log.debug("Wrote %s", wav_path)
        except Exception:
            self.log.exception("Error while saving STT audio")

    def _save_stt_audio(self):
        try:
            wav_path = self.stt_audio_dir / f"{time.monotonic_ns()}.wav"
            with open(wav_path, "wb") as wav_io, wave.open(wav_io, "wb") as wav_file:
                wav_file.setframerate(self._sample_rate)
                wav_file.setsampwidth(self._sample_width)
                wav_file.setnchannels(self._sample_channels)
                wav_file.writeframes(self.stt_audio)

            self.log.debug("Wrote %s", wav_path)
        except Exception:
            self.log.exception("Error while saving STT audio")

    def _audio_input(self):
        for _ in range(self._audio_retries):
            try:
                # TODO: Use config
                mic = alsaaudio.PCM(
                    type=alsaaudio.PCM_CAPTURE,
                    rate=self._sample_rate,
                    channels=self._sample_channels,
                    format=alsaaudio.PCM_FORMAT_S32_LE
                    if self._sample_width == 4
                    else alsaaudio.PCM_FORMAT_S16_LE,
                    device=self._device_name,
                    periodsize=self._chunk_size // self._sample_width,
                )
                try:
                    while self._audio_input_running:
                        chunk_length, chunk = mic.read()
                        if chunk_length <= 0:
                            LOG.warning("Bad chunk length: %s", chunk_length)
                            continue

                        # Increase loudness of audio
                        if self._multiplier != 1.0:
                            chunk = audioop.mul(
                                chunk, self._sample_width, self._multiplier
                            )

                        self.queue.put_nowait(chunk)
                finally:
                    mic.close()
            except Exception:
                LOG.exception("Unexpected error in audio input thread")

            if not self._audio_input_running:
                break

            LOG.debug("Retrying audio input in %s second(s)", self._audio_retry_delay)
            time.sleep(self._audio_retry_delay)


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


def load_vad_detector(model_path: str) -> SileroVoiceActivityDetector:
    return SileroVoiceActivityDetector(model_path)


def _chunk_seconds(
    chunk_length: int, sample_rate: int, sample_width: int, channels: int
):
    """Returns the number of seconds in an audio chunk"""
    num_samples = chunk_length / (sample_width * channels)
    seconds = num_samples / sample_rate

    return seconds


def _debiased_energy(audio_data: bytes, sample_width: int) -> float:
    """Compute RMS of debiased audio."""
    # Thanks to the speech_recognition library!
    # https://github.com/Uberi/speech_recognition/blob/master/speech_recognition/__init__.py
    energy = -audioop.rms(audio_data, sample_width)
    energy_bytes = bytes([energy & 0xFF, (energy >> 8) & 0xFF])
    debiased_energy = audioop.rms(
        audioop.add(
            audio_data, energy_bytes * (len(audio_data) // sample_width), sample_width
        ),
        sample_width,
    )

    return debiased_energy
