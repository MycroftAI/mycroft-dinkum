import io
import logging
import os
import subprocess
import tempfile
import wave
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Any, Dict, Optional, Iterable, IO

from mycroft_bus_client import MessageBusClient
from mycroft.stt import StreamingSTT
from mycroft.util.log import LOG

from .utils import decode_output, make_wav_header

_DIR = Path(__file__).parent
_DEFAULT_GROKOTRON_DIR = Path("/opt/grokotron")
_DEFAULT_OUTPUT_DIR = _DEFAULT_GROKOTRON_DIR / "output"
_DEFAULT_KALDI_BIN_DIR = _DEFAULT_GROKOTRON_DIR / "kaldi" / "bin"

_LOGGER = logging.getLogger("grokotron")
_WAV_HEADER = make_wav_header()

_KALDI_TIMEOUT = 10  # seconds to wait for Kaldi process to stop


class GrokotronStreamingSTT(StreamingSTT):
    def __init__(self, bus: MessageBusClient, config: Dict[str, Any]):
        super().__init__(bus, config)

        # Directory with trained artifacts (from train.sh)
        self._output_dir = Path(self.config.get("output_dir", _DEFAULT_OUTPUT_DIR))

        # Directory with Kaldi executables (need online2-wav-nnet3-latgen-faster)
        self._kaldi_bin_dir = Path(
            self.config.get("kaldi_bin_dir", _DEFAULT_KALDI_BIN_DIR)
        )

        # Queue shared with Kaldi thread to pass audio chunks.
        # A "None" signals to the thread that the voice command is finished.
        self._audio_queue: "Optional[Queue[Optional[bytes]]]" = None

        # Queue shared with Kaldi thread to receive transcription.
        self._text_queue: "Optional[Queue[Optional[str]]]" = None

        # Always keep a fresh thread ready
        self._start_kaldi_thread()

    def start(self):
        """Called when voice command starts"""
        # Kaldi thread should already be started
        assert self._audio_queue is not None
        assert self._text_queue is not None

    def update(self, chunk: bytes):
        """Called during voice command"""
        assert self._audio_queue is not None
        self._audio_queue.put(chunk)

    def stop(self) -> Optional[str]:
        """Called when voice command ends"""
        assert self._audio_queue is not None
        assert self._text_queue is not None

        # Drain queue
        while not self._audio_queue.empty():
            self._audio_queue.get()

        # Signal stop
        self._audio_queue.put(None)

        text: Optional[str] = None
        try:
            text = self._text_queue.get(timeout=_KALDI_TIMEOUT)
        except subprocess.TimeoutExpired:
            _LOGGER.warning("Kaldi timeout")

        # Always keep a fresh thread ready
        self._start_kaldi_thread()

        return text

    def shutdown(self):
        """Called during Mycroft shut down"""
        if self._audio_queue is None:
            # Signal thread to shut down
            self._audio_queue.put(None)

        self._audio_queue = None
        self._text_queue = None

    def _start_kaldi_thread(self):
        self._audio_queue = Queue()
        self._text_queue = Queue()

        Thread(
            target=self._kaldi_thread_proc, args=(self._audio_queue, self._text_queue)
        ).start()

    def _make_kaldi_command(self, fifo_path: str):
        return [
            f"{self._kaldi_bin_dir}/online2-wav-nnet3-latgen-faster",
            "--online=true",
            "--do-endpointing=false",
            f"--config={self._output_dir}/acoustic_model/online/conf/online.conf",
            "--max-active=7000",
            "--lattice-beam=8.0",
            "--acoustic-scale=1.0",
            "--beam=24.0",
            f"--word-symbol-table={self._output_dir}/graph/words.txt",
            f"{self._output_dir}/acoustic_model/model/final.mdl",
            f"{self._output_dir}/graph/HCLG.fst",
            "ark:echo utt1 utt1|",
            f"scp:echo utt1 {fifo_path}|",
            "ark:/dev/null",
        ]

    def _kaldi_thread_proc(
        self, audio_queue: "Queue[Optional[bytes]]", text_queue: "Queue[Optional[str]]"
    ):
        try:
            # Create a FIFO in a temporary directory to share with the Kaldi
            # process. This allows us to stream audio into a "WAV" file with
            # Kaldi none the wiser.
            with tempfile.TemporaryDirectory() as temp_dir:
                fifo_path = os.path.join(temp_dir, "chunk.fifo")
                os.mkfifo(fifo_path)

                kaldi_cmd = self._make_kaldi_command(fifo_path)
                _LOGGER.debug(kaldi_cmd)

                with subprocess.Popen(
                    kaldi_cmd,
                    stderr=subprocess.STDOUT,
                    stdout=subprocess.PIPE,
                    universal_newlines=True,
                ) as proc:
                    # It's critical that the FIFO is opened *after* the Kaldi
                    # process starts. In other words, the order MUST be:
                    #
                    # 1. FIFO is created
                    # 2. Kaldi process is started, opens FIFO in read mode
                    # 3. Python process opens FIFO in write mode
                    with open(fifo_path, "wb") as fifo_file:
                        chunk: Optional[bytes] = audio_queue.get()
                        is_first_chunk = True

                        while chunk is not None:
                            if is_first_chunk:
                                fifo_file.write(_WAV_HEADER)

                            fifo_file.write(chunk)
                            chunk = self._audio_queue.get()

                    # Get stdout from Kaldi (stderr is redirected to stdout)
                    kaldi_stdout, _stderr = proc.communicate()

                # Extract transcription
                lines = kaldi_stdout.splitlines()
                text: Optional[str] = None
                for line in lines:
                    if line.startswith("utt1 "):
                        parts = line.split(maxsplit=1)
                        if len(parts) > 1:
                            text = decode_output(parts[1])

                _LOGGER.debug(text)
                text_queue.put(text)
        except Exception:
            _LOGGER.exception("Unexpected error in Kaldi thread")
