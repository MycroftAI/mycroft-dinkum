import logging
import subprocess
import tempfile
import typing
from abc import ABCMeta, abstractmethod

from mycroft_bus_client import MessageBusClient

from mycroft.api import STTApi

LOG = logging.getLogger(__package__)


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
    def stop(self) -> typing.Optional[str]:
        pass

    def shutdown(self):
        pass


class MycroftSTT(StreamingSTT):
    def __init__(self, bus: MessageBusClient, config):
        super().__init__(bus, config)

        self._api = STTApi("stt")
        self._flac_proc: typing.Optional[subprocess.Popen] = None
        self._flac_file: typing.Optional[typing.BinaryIO] = None

    def start(self):
        self._start_flac()

    def update(self, chunk: bytes):
        # Stream chunks into FLAC encoder
        assert self._flac_proc is not None
        assert self._flac_proc.stdin is not None

        self._flac_proc.stdin.write(chunk)

    def stop(self) -> typing.Optional[str]:
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

            return self._api.stt(flac, "en-US", 1)[0]
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
