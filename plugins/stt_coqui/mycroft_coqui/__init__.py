from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from mycroft_bus_client import MessageBusClient
from mycroft.stt import StreamingSTT
from mycroft.util.log import LOG
from stt import Model

_DEFAULT_MODEL = (
    Path(__file__).parent / "models" / "english_v1.0.0-large-vocab" / "model.tflite"
)


class CoquiStreamingSTT(StreamingSTT):
    def __init__(self, bus: MessageBusClient, config: Dict[str, Any]):
        super().__init__(bus, config)

        model_path = Path(self.config.get("model", _DEFAULT_MODEL))
        scorer_path_str = self.config.get("scorer")
        if scorer_path_str:
            scorer_path = Path(scorer_path_str)
        else:
            model_dir = model_path.parent
            scorer_path = next(model_dir.glob("*.scorer"))

        LOG.debug("Loading model: %s, scorer: %s", model_path, scorer_path)
        self._model = Model(str(model_path))
        self._model.enableExternalScorer(str(scorer_path))

        scorer_alpha_beta = self.config.get("scorer_alpha_beta")
        if scorer_alpha_beta is not None:
            alpha, beta = float(scorer_alpha_beta[0]), float(scorer_alpha_beta[1])
            model.setScorerAlphaBeta(alpha, beta)

        self._model_stream = None

    def start(self):
        self._model_stream = self._model.createStream()

    def update(self, chunk: bytes):
        assert self._model_stream is not None, "Not started"
        chunk_array = np.frombuffer(chunk, dtype=np.int16)
        self._model_stream.feedAudioContent(chunk_array)

    def stop(self) -> Optional[str]:
        assert self._model_stream is not None, "Not started"
        text = self._model_stream.finishStream()
        return text

    def shutdown(self):
        self._model = None
        self._model_stream = None
