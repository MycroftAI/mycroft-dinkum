import json
from pathlib import Path
from typing import Any, Dict, Optional

from mycroft_bus_client import MessageBusClient
from mycroft.stt import StreamingSTT
from mycroft.util.log import LOG
from vosk import Model, KaldiRecognizer, SetLogLevel

_DEFAULT_MODEL_DIR = Path(__file__).parent / "models" / "small-en-us-0.15"


class VoskStreamingSTT(StreamingSTT):
    def __init__(self, bus: MessageBusClient, config: Dict[str, Any]):
        super().__init__(bus, config)

        SetLogLevel(0)

        model_path = self.config.get("model", _DEFAULT_MODEL_DIR)
        LOG.debug("Loading model: %s", model_path)
        self._model = Model(str(model_path))
        self._recognizer: Optional[KaldiRecognizer] = None

    def start(self):
        self._recognizer = KaldiRecognizer(self._model, 16000)

    def update(self, chunk: bytes):
        assert self._recognizer is not None
        self._recognizer.AcceptWaveform(chunk)

    def stop(self) -> Optional[str]:
        assert self._recognizer is not None
        result = json.loads(self._recognizer.FinalResult())
        LOG.debug(result)
        return result.get("text")

    def shutdown(self):
        self._recognizer = None
