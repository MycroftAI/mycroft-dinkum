import asyncio
import json
import logging
import subprocess
from collections import deque
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any, Dict, Optional
from uuid import uuid4

import numpy as np
from mycroft.hotword import HotWordEngine
from mycroft.stt import MycroftSTT, StreamingSTT
from mycroft.util.plugins import load_plugin
from mycroft_bus_client import Message, MessageBusClient

from .silero_vad import SileroVoiceActivityDetector
from .vad_command import VadCommand

LOG = logging.getLogger("voice")
AUDIO_TIMEOUT = 0.5
AUDIO_CHUNK_SIZE = 2048
VAD_MODEL = Path(__file__).parent / "models" / "silero_vad.onnx"
VAD_THRESHOLD = 0.2
CHUNKS_TO_BUFFER = 2


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
        self.command = VadCommand(speech_begin=0.3, silence_end=0.5, timeout=15.0)

        self.log = logging.getLogger("voice.loop")

        self.is_recording = False
        self.muted = False
        self.mycroft_session_id: Optional[str] = None

        # Name reported in recognizer_loop:wakeword
        self.wake_word_name = config.get("listener", {}).get("wake_word", "hey mycroft")

        # Audio chunks from arecord
        self.queue: "Queue[bytes]" = Queue()

        # Buffered audio that's sent to STT after wake
        self.chunk_buffer = deque(maxlen=CHUNKS_TO_BUFFER)

    def start(self):
        # Start arecord in separate thread
        # TODO: Use configurable command
        Thread(target=_audio_input, args=(self.queue,), daemon=True).start()

        self.bus.on("mycroft.mic.mute", self.handle_mute)
        self.bus.on("mycroft.mic.unmute", self.handle_unmute)
        self.bus.on("mycroft.mic.listen", self.handle_listen)

    def run(self):
        while True:
            chunk = self.queue.get(timeout=AUDIO_TIMEOUT)
            assert chunk, "Empty audio chunk"

            if self.muted:
                self.chunk_buffer.clear()
                chunk = bytes(len(chunk))

            self.chunk_buffer.append(chunk)
            if not self.is_recording:
                self.hotword.update(chunk)
                if self.hotword.found_wake_word(None) and (not self.muted):
                    self.log.info("Hotword detected!")
                    self.do_listen()
            else:
                # In voice command
                self.stt.update(chunk)
                seconds = _chunk_seconds(
                    len(chunk), sample_rate=16000, sample_width=2, channels=1
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
                    self.bus.emit(
                        Message(
                            "recognizer_loop:utterance",
                            {
                                "utterances": [text],
                                "mycroft_session_id": self.mycroft_session_id,
                            },
                        )
                    )

                    if not text:
                        self.bus.emit(
                            Message("recognizer_loop:speech.recognition.unknown")
                        )

    def do_listen(self, message: Optional[Message] = None):
        if self.muted:
            self.log.warning("Not waking up since we're muted")
            return

        if message:
            self.mycroft_session_id = message.data.get("mycroft_session_id")
        else:
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
        self.command.reset()
        self.stt.start()
        self.is_recording = True

        # Push audio buffer into STT
        self.command.reset()
        for buffered_chunk in self.chunk_buffer:
            seconds = _chunk_seconds(
                len(buffered_chunk), sample_rate=16000, sample_width=2, channels=1
            )

            self.stt.update(buffered_chunk)
            chunk_array = np.frombuffer(buffered_chunk, dtype=np.int16)
            is_speech = self.vad(chunk_array) >= VAD_THRESHOLD
            self.command.process(is_speech, seconds)

    def handle_mute(self, _message):
        self.muted = True
        self.log.info("Muted microphone")

    def handle_unmute(self, _message):
        self.muted = False
        self.log.info("Unmuted microphone")

    def handle_listen(self, message):
        self.do_listen(message)


def _audio_input(queue: "Queue[bytes]"):
    try:
        # TODO: Use config
        proc = subprocess.Popen(
            ["arecord", "-q", "-r", "16000", "-c", "1", "-f", "S16_LE", "-t", "raw"],
            stdout=subprocess.PIPE,
        )
        assert proc.stdout is not None

        while True:
            chunk = proc.stdout.read(AUDIO_CHUNK_SIZE)
            assert chunk, "Empty audio chunk"

            queue.put_nowait(chunk)
    except Exception:
        LOG.exception("Unexpected error in audio input thread")


def load_hotword_module(config: dict[str, Any]) -> HotWordEngine:
    wake_word = config["listener"]["wake_word"]
    hotword_config = config["hotwords"][wake_word]
    module_name = hotword_config["module"]

    LOG.debug("Loading wake word module: %s", module_name)
    module = load_plugin("mycroft.plugin.wake_word", module_name)
    assert module, f"Failed to load {module_name}"
    hotword = module(config=hotword_config)
    LOG.info("Loaded wake word module: %s", module_name)

    return hotword


def load_stt_module(config: dict[str, Any], bus: MessageBusClient) -> StreamingSTT:
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
