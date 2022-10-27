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
"""Logic to load a configured TTS plugin and manage speech playback."""
import hashlib
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

import pysbd
from mycroft_bus_client import Message, MessageBusClient

from mycroft.tts import TTS
from mycroft.tts.dummy_tts import DummyTTS
from mycroft.util.file_utils import get_cache_directory
from mycroft.util.log import get_mycroft_logger
from mycroft.util.plugins import load_plugin

_log = get_mycroft_logger(__name__)


class SpeakHandler:
    """Synthesizes text into speech using the configured TTS engine."""

    def __init__(self, config: Dict[str, Any], bus: MessageBusClient, tts: TTS):
        self.config = config
        self.bus = bus
        self.tts = tts

        tts_name = self.config["tts"]["module"]
        cache_dir = Path(get_cache_directory(), "tts", tts_name)
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_dirs = [cache_dir]

        self._speak_lock = RLock()
        self._mycroft_session_id: Optional[str] = None

        self._segmenter: Optional[pysbd.Segmenter] = None
        self._load_segmenter()

    def start(self):
        """Defines the event handlers, effectively starting the ability to speak."""
        self.bus.on("speak", self._handle_speak)
        self.bus.on("speak.cache", self._handle_speak)
        self.bus.on("mycroft.tts.stop", self._handle_tts_stop)

    def stop(self):
        """Defines the logic needed to shut down the speech handler."""
        pass

    def _handle_speak(self, message: Message):
        """Synthesize speech for the text in the event message.

        Args:
            message: a "speak" or "speach.cache" event message.
        """
        try:
            cache_only = message.msg_type == "speak.cache"
            utterance = message.data["utterance"]
            mycroft_session_id = message.data.get("mycroft_session_id")

            if mycroft_session_id is not None:
                _log.info("Starting TTS for session %s", mycroft_session_id)
            if cache_only:
                _log.info("Caching speech synthesis for text '%s'", utterance)
            else:
                _log.info("Speaking text '%s'", utterance)

            with self._speak_lock:
                # Begin TTS session
                self._mycroft_session_id = mycroft_session_id

                if not cache_only:
                    self.bus.emit(
                        Message(
                            "mycroft.tts.session.start",
                            data={"mycroft_session_id": mycroft_session_id},
                        )
                    )

                # Segment utterance into sentences using pysbd (Python Sentence Boundary Detector).
                # NOTE: Segmentation is not thread safe
                segments = self._segment(utterance)

                # Synthesize and cache each segment/chunk independently.
                for i, sentence in enumerate(segments):
                    if self._mycroft_session_id != mycroft_session_id:
                        # New session has started
                        break

                    cache_path = self._synthesize(sentence)
                    if cache_only:
                        continue

                    # Ask audio service to play the chunk
                    audio_uri = "file://" + str(cache_path)
                    self.bus.emit(
                        Message(
                            "mycroft.tts.chunk.start",
                            data={
                                "uri": audio_uri,
                                "chunk_index": i,
                                "num_chunks": len(segments),
                                "mycroft_session_id": mycroft_session_id,
                                "text": sentence,
                            },
                        )
                    )
                    _log.debug(
                        "Submitted TTS chunk %s/%s: %s",
                        i + 1,
                        len(segments),
                        sentence,
                    )
            if mycroft_session_id is not None:
                _log.info("Completed TTS for session %s", mycroft_session_id)
        except Exception:
            _log.exception("Unexpected error handling speak")

    def _handle_tts_stop(self, _: Message):
        """Cancels any active TTS session."""
        _log.info("Speech synthesis stopped for session %s", self._mycroft_session_id)
        self._mycroft_session_id = None

    def _synthesize(self, text: str) -> Path:
        """Synthesizes audio from text.

        Before submitting text for synthesis, the TTS cache is searched.  If the
        text is found in the cache, use cached .wav file.

        Args:
            text: the text to synthesize

        Returns:
            the path to the cache file
        """
        text_hash = hash_sentence(text)

        # Check preloaded static cache
        if text_hash in self.tts.cache:
            audio_file, _phonemes_file = self.tts.cache.cached_sentences[text_hash]
            return audio_file.path

        # Check temporary dynamic cache
        for cache_dir in self._cache_dirs:
            cache_path = Path.joinpath(cache_dir, f"{text_hash}.wav")
            if cache_path.is_file():
                _log.info("Using cached synthesis")
                return cache_path

        # Not in cache, need to synthesize
        _log.info("Synthesizing speech")
        self.tts.get_tts(text, str(cache_path))
        return cache_path

    def _segment(self, utterance: str) -> List[str]:
        """Split an utterance into sentences"""
        if self._segmenter is not None:
            # Split into sentences intelligently
            segments = self._segmenter.segment(utterance)
            _log.info("Segmentation results: %s", segments)
        else:
            # No segmenter available, synthesize entire utterance as one chunk
            segments = [utterance]

        return segments

    def _load_segmenter(self):
        """Load a pysbd segmenter for the TTS language"""
        module_name = self.config["tts"]["module"]
        tts_config = self.config["tts"].get(module_name, {})
        lang = self.config.get("lang", "en-us")
        tts_lang = tts_config.get("lang", lang)

        # en-us -> en
        seg_lang = tts_lang[:2]
        if seg_lang in pysbd.languages.LANGUAGE_CODES:
            self._segmenter = pysbd.Segmenter(language=seg_lang, clean=False)
            _log.info("Loaded sentence segmenter for language %s", seg_lang)


def load_tts_module(config: Dict[str, Any]) -> TTS:
    """Load text to speech module as a plugin.

    Args:
        config: full Mycroft configuration

    Returns:
        Instance of a speech synthesis plugin.
    """
    module_name = config["tts"]["module"]
    if module_name == "dummy":
        _log.info("Using dummy TTS")
        return DummyTTS("", {})

    tts_config = config["tts"].get(module_name, {})
    lang = config.get("lang", "en-us")
    tts_lang = tts_config.get("lang", lang)

    _log.info("Loading text to speech module: %s", module_name)
    module = load_plugin("mycroft.plugin.tts", module_name)
    assert module, f"Failed to load {module_name}"
    tts = module(tts_lang, tts_config)
    _log.info("Text to speech module loaded")

    return tts


def hash_sentence(sentence: str):
    """Converts the sentence into a hash value used for the cache file name.

    Args:
        sentence: The sentence to be cached

    Returns:
        Hash value to be used as cache file name
    """
    encoded_sentence = sentence.encode("utf-8", "ignore")
    sentence_hash = hashlib.md5(encoded_sentence).hexdigest()

    return sentence_hash
