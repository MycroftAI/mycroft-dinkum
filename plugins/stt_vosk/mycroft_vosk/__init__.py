import json
from pathlib import Path
from typing import Optional

from mycroft_bus_client import MessageBusClient
from mycroft.stt import StreamingSTT
from vosk import Model, KaldiRecognizer, SetLogLevel

_DEFAULT_MODEL_DIR = Path(__file__).parent / "models" / "small-en-us-0.15"


class VoskStreamingSTT(StreamingSTT):
    def __init__(self, bus: MessageBusClient, config):
        super().__init__(bus, config)

        SetLogLevel(0)

        # TODO: Use config
        self._model = Model(str(_DEFAULT_MODEL_DIR))
        self._recognizer: Optional[KaldiRecognizer] = None

    def start(self):
        self._recognizer = KaldiRecognizer(self._model, 16000)

    def update(self, chunk: bytes):
        assert self._recognizer is not None
        self._recognizer.AcceptWaveform(chunk)

    def stop(self) -> Optional[str]:
        assert self._recognizer is not None
        result = json.loads(self._recognizer.FinalResult())
        return result.get("text")

    def shutdown(self):
        self._recognizer = None
