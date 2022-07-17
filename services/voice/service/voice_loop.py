import asyncio
import json
import logging
import subprocess
from collections import deque
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any, Optional
from uuid import uuid4

import numpy as np
# import websockets
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

# logging.getLogger("websockets.client").setLevel(logging.INFO)


def voice_loop(
    config: dict[str, Any],
    bus: MessageBusClient,
    hotword: HotWordEngine,
    vad: SileroVoiceActivityDetector,
    stt: StreamingSTT,
):
    queue: "Queue[bytes]" = Queue()
    Thread(target=_audio_input, args=(queue,), daemon=True).start()

    # TODO: Use config
    command = VadCommand(speech_begin=0.3, silence_end=0.5, timeout=15.0)
    chunk_buffer = deque(maxlen=CHUNKS_TO_BUFFER)
    is_recording = False
    mycroft_session_id: Optional[str] = None

    def do_listen(message: Optional[Message] = None):
        nonlocal is_recording, mycroft_session_id
        if message:
            mycroft_session_id = message.data.get("mycroft_session_id")
        else:
            mycroft_session_id = str(uuid4())

        bus.emit(
            Message(
                "recognizer_loop:awoken",
                data={"mycroft_session_id": mycroft_session_id},
            )
        )

        # Begin voice command
        command.reset()
        stt.start()
        is_recording = True

        # Push audio buffer into STT
        command.reset()
        for buffered_chunk in chunk_buffer:
            stt.update(buffered_chunk)
            chunk_array = np.frombuffer(chunk, dtype=np.int16)
            is_speech = vad(chunk_array) >= VAD_THRESHOLD
            command.process(is_speech, seconds)

    muted = False

    def handle_mute(_message):
        nonlocal muted
        muted = True
        LOG.info("Muted microphone")

    def handle_unmute(_message):
        nonlocal muted
        muted = False
        LOG.info("Unmuted microphone")

    def handle_listen(message):
        do_listen(message)

    bus.on("mycroft.mic.mute", handle_mute)
    bus.on("mycroft.mic.unmute", handle_unmute)
    bus.on("mycroft.mic.listen", handle_listen)

    while True:
        chunk = queue.get(timeout=AUDIO_TIMEOUT)
        assert chunk, "Empty audio chunk"

        if muted:
            chunk = bytes(len(chunk))

        # TODO: Use config
        seconds = _chunk_seconds(
            len(chunk), sample_rate=16000, sample_width=2, channels=1
        )

        chunk_buffer.append(chunk)
        if not is_recording:
            hotword.update(chunk)
            if hotword.found_wake_word(None):
                LOG.info("Hotword detected!")
                do_listen()
        else:
            # In voice command
            stt.update(chunk)

            # Check for end of voice command
            chunk_array = np.frombuffer(chunk, dtype=np.int16)
            is_speech = vad(chunk_array) >= VAD_THRESHOLD
            if command.process(is_speech, seconds):
                is_recording = False
                text = stt.stop()
                LOG.info("STT: %s", text)

                if text:
                    bus.emit(
                        Message(
                            "recognizer_loop:utterance",
                            {
                                "utterances": [text],
                                "mycroft_session_id": mycroft_session_id,
                            },
                        )
                    )
                else:
                    bus.emit(Message("recognizer_loop:speech.recognition.unknown"))


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
