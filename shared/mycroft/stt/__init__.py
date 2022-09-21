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
import subprocess
import tempfile
from abc import ABCMeta, abstractmethod
from typing import Any, BinaryIO, Dict, Optional

from mycroft.api import STTApi
from mycroft.util.log import LOG
from mycroft.util.plugins import load_plugin
from mycroft_bus_client import MessageBusClient


class StreamingSTT(metaclass=ABCMeta):
    def __init__(self, bus: MessageBusClient, config):
        self.bus = bus
        self.config = config

    def start(self):
        pass

    @abstractmethod
    def update(self, chunk: bytes):
        pass

    @abstractmethod
    def stop(self) -> Optional[str]:
        pass

    def shutdown(self):
        pass


class MycroftSTT(StreamingSTT):
    def __init__(self, bus: MessageBusClient, config):
        super().__init__(bus, config)

        self._api = STTApi("transcribe")
        self._flac_proc: Optional[subprocess.Popen] = None
        self._flac_file: Optional[BinaryIO] = None

    def start(self):
        self._start_flac()

    def update(self, chunk: bytes):
        # Stream chunks into FLAC encoder
        assert self._flac_proc is not None
        assert self._flac_proc.stdin is not None

        self._flac_proc.stdin.write(chunk)

    def stop(self) -> Optional[str]:
        try:
            assert self._flac_proc is not None
            assert self._flac_file is not None

            # Read contents of encoded file.
            #
            # A file is needed here so the encoder can seek back and write the
            # length.
            self._flac_proc.communicate()
            self._flac_file.seek(0)
            flac = self._flac_file.read()

            self._flac_file.close()
            self._flac_file = None

            self._flac_proc = None

            result = self._api.stt(flac, "en-US", 1)
            LOG.info(result)
            return result["transcription"]
        except Exception:
            LOG.exception("Error in Mycroft STT")

        return None

    def _start_flac(self):
        self._stop_flac()

        # pylint: disable=consider-using-with
        self._flac_file = tempfile.NamedTemporaryFile(suffix=".flac", mode="wb+")

        # Encode raw audio into temporary file
        self._flac_proc = subprocess.Popen(
            [
                "flac",
                "--totally-silent",
                "--best",
                "--endian=little",
                "--channels=1",
                "--bps=16",
                "--sample-rate=16000",
                "--sign=signed",
                "-f",
                "-o",
                self._flac_file.name,
                "-",
            ],
            stdin=subprocess.PIPE,
        )

    def _stop_flac(self):
        if self._flac_proc is not None:
            # Try to gracefully terminate
            self._flac_proc.terminate()
            self._flac_proc.wait(0.5)
            try:
                self._flac_proc.communicate()
            except subprocess.TimeoutExpired:
                self._flac_proc.kill()

            self._flac_proc = None


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
