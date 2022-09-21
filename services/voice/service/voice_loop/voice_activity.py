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
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union

import numpy as np
import onnxruntime

LOG = logging.getLogger("voice_activity")


@dataclass
class VoiceActivity:
    def start(self):
        raise NotImplementedError()

    def is_speech(self, chunk: bytes) -> Tuple[bool, float]:
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()


# -----------------------------------------------------------------------------


@dataclass
class SileroVoiceActivity(VoiceActivity):
    model: Union[str, Path]
    threshold: float
    _session: Optional[onnxruntime.InferenceSession] = None
    _h_array: Optional[np.ndarray] = None
    _c_array: Optional[np.ndarray] = None

    def start(self):
        LOG.debug("Loading VAD model: %s", self.model)
        self._session = onnxruntime.InferenceSession(str(self.model))
        self._session.intra_op_num_threads = 1
        self._session.inter_op_num_threads = 1

        self._h_array = np.zeros((2, 1, 64)).astype("float32")
        self._c_array = np.zeros((2, 1, 64)).astype("float32")

    def is_speech(self, chunk: bytes) -> bool:
        audio_array = np.frombuffer(chunk, dtype=np.int16)

        # Add batch dimension
        audio_array = np.expand_dims(audio_array, 0)

        ort_inputs = {
            "input": audio_array.astype(np.float32),
            "h0": self._h_array,
            "c0": self._c_array,
        }
        ort_outs = self._session.run(None, ort_inputs)
        out, self._h_array, self._c_array = ort_outs
        probability = out.squeeze(2)[:, 1].item()
        is_speech = probability >= self.threshold

        return (is_speech, probability)

    def stop(self):
        self._session = None
        self._h_array = None
        self._c_array = None
