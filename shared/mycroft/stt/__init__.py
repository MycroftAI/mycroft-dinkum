import logging
import subprocess
import tempfile
import time
from abc import ABCMeta, abstractmethod
from typing import Any, Optional, BinaryIO, Dict, List

import requests
from mycroft.api import STTApi
from mycroft_bus_client import MessageBusClient

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
    def stop(self) -> Optional[str]:
        pass

    def shutdown(self):
        pass


class MycroftSTT(StreamingSTT):
    def __init__(self, bus: MessageBusClient, config):
        super().__init__(bus, config)

        self._api = STTApi("stt")
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
            flac = self._get_flac()
            return self._api.stt(flac, "en-US", 1)[0]
        except Exception:
            LOG.exception("Error in Mycroft STT")

        return None

    def _get_flac(self) -> bytes:
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

        return flac

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


class AssemblyAISTT(MycroftSTT):
    API_KEY = "838fdde44cd54f1282ced7d075d094fd"
    UPLOAD_ENDPOINT = "https://api.assemblyai.com/v2/upload"
    TRANSCRIPT_ENDPOINT = "https://api.assemblyai.com/v2/transcript"

    MAX_POLLS = 10
    POLL_WAIT_SEC = 1

    def __init__(self, bus: MessageBusClient, config):
        super().__init__(bus, config)
        self._header: Dict[str, Any] = {
            "authorization": AssemblyAISTT.API_KEY,
            "content-type": "application/json",
        }

    def stop(self) -> Optional[str]:
        try:
            text: Optional[str] = None
            flac = self._get_flac()

            # https://github.com/AssemblyAI-Examples/assemblyai-and-python-in-5-minutes/
            LOG.debug("Uploading %s byte(s) to AAI", len(flac))
            upload_url = self._upload_file(flac)

            LOG.debug("Requesting transcript")
            transcript_response = self._request_transcript(upload_url)

            LOG.debug("Waiting for transcript")
            polling_endpoint = self._make_polling_endpoint(transcript_response)
            polling_response = self._wait_for_completion(polling_endpoint)
            if polling_response is not None:
                paragraphs = self._get_paragraphs(polling_endpoint)
                text = " ".join(p["text"] for p in paragraphs)
                LOG.debug(text)
            else:
                LOG.warning("AAI transcription did not complete")

            return text
        except Exception:
            LOG.exception("Error in Assembly AI STT")

        return None

    def _upload_file(self, flac: bytes) -> Dict[str, Any]:
        """Uploads a file to AAI servers"""
        upload_response = requests.post(
            AssemblyAISTT.UPLOAD_ENDPOINT, headers=self._header, data=flac
        )
        return upload_response.json()

    def _request_transcript(self, upload_url: Dict[str, Any]) -> Dict[str, Any]:
        """Request transcript for file uploaded to AAI servers"""
        transcript_request = {"audio_url": upload_url["upload_url"]}
        transcript_response = requests.post(
            AssemblyAISTT.TRANSCRIPT_ENDPOINT,
            json=transcript_request,
            headers=self._header,
        )
        return transcript_response.json()

    def _make_polling_endpoint(self, transcript_response: Dict[str, Any]) -> str:
        """Make a polling endpoint"""
        polling_endpoint = (
            self._ensure_slash(AssemblyAISTT.TRANSCRIPT_ENDPOINT)
            + transcript_response["id"]
        )
        return polling_endpoint

    def _wait_for_completion(self, polling_endpoint) -> Optional[Dict[str, Any]]:
        """Wait for the transcript to finish"""
        polling_response: Optional[Dict[str, Any]] = None
        for i in range(AssemblyAISTT.MAX_POLLS):
            polling_response = requests.get(polling_endpoint, headers=self._header)
            polling_response = polling_response.json()

            if polling_response["status"] == "completed":
                break

            time.sleep(AssemblyAISTT.POLL_WAIT_SEC)

        return polling_response

    def _get_paragraphs(self, polling_endpoint: str) -> List[str]:
        """Get the paragraphs of the transcript"""
        paragraphs_response = requests.get(
            self._ensure_slash(polling_endpoint) + "paragraphs", headers=self._header
        )
        paragraphs_response = paragraphs_response.json()
        paragraphs: List[str] = []
        for para in paragraphs_response["paragraphs"]:
            paragraphs.append(para)

        return paragraphs

    def _ensure_slash(self, uri: str) -> str:
        if not uri[-1] == "/":
            return f"{uri}/"

        return uri
