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
import logging
import time
from dataclasses import dataclass, field
from queue import Queue
from threading import Thread
from typing import Optional

import alsaaudio

LOG = logging.getLogger("microphone")


@dataclass
class Microphone:
    sample_rate: int
    sample_width: int
    sample_channels: int
    chunk_size: int

    @property
    def frames_per_chunk(self) -> int:
        return self.chunk_size // (self.sample_width * self.sample_channels)

    @property
    def seconds_per_chunk(self) -> float:
        return self.frames_per_chunk / self.sample_rate

    def start(self):
        raise NotImplementedError()

    def read_chunk(self) -> Optional[bytes]:
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()


# -------------------------------------------------------------------------------


@dataclass
class AlsaMicrophone(Microphone):
    device: str
    timeout: float
    period_size: int
    multiplier: float = 1.0
    audio_retries: int = 0
    audio_retry_delay: float = 0.0
    _thread: Optional[Thread] = None
    _queue: "Queue[Optional[bytes]]" = field(default_factory=Queue)
    _is_running: bool = False

    def start(self):
        assert self._thread is None, "Already started"
        self._is_running = True
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def read_chunk(self) -> Optional[bytes]:
        assert self._is_running, "Not running"
        return self._queue.get(timeout=self.timeout)

    def stop(self):
        assert self._thread is not None, "Not started"
        self._is_running = False
        while not self._queue.empty():
            self._queue.get()
        self._queue.put_nowait(None)
        self._thread.join()
        self._thread = None

    def _run(self):
        try:
            assert self.sample_width in {
                2,
                4,
            }, "Only 16-bit and 32-bit sample widths are supported"

            for _ in range(self.audio_retries + 1):
                try:
                    LOG.debug(
                        "Opening microphone (device=%s, rate=%s, width=%s, channels=%s)",
                        self.device,
                        self.sample_rate,
                        self.sample_width,
                        self.sample_channels,
                    )

                    mic = alsaaudio.PCM(
                        type=alsaaudio.PCM_CAPTURE,
                        rate=self.sample_rate,
                        channels=self.sample_channels,
                        format=alsaaudio.PCM_FORMAT_S32_LE
                        if self.sample_width == 4
                        else alsaaudio.PCM_FORMAT_S16_LE,
                        device=self.device,
                        periodsize=self.period_size,
                    )

                    try:
                        full_chunk = bytes()

                        while self._is_running:
                            mic_chunk_length, mic_chunk = mic.read()
                            if mic_chunk_length <= 0:
                                LOG.warning("Bad chunk length: %s", mic_chunk_length)
                                continue

                            # Increase loudness of audio
                            if self.multiplier != 1.0:
                                mic_chunk = audioop.mul(
                                    mic_chunk, self.sample_width, self.multiplier
                                )

                            full_chunk += mic_chunk
                            while len(full_chunk) >= self.chunk_size:
                                self._queue.put_nowait(full_chunk[: self.chunk_size])
                                full_chunk = full_chunk[self.chunk_size :]

                            time.sleep(0.0)
                    finally:
                        mic.close()
                except Exception:
                    LOG.exception("Failed to open microphone")
                    time.sleep(self.audio_retry_delay)
        except Exception:
            LOG.exception("Unexpected error in ALSA microphone thread")
