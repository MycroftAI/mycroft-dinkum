import hashlib
import logging
from pathlib import Path
from threading import RLock
from typing import Any, Optional
from uuid import uuid4

import pysbd
from mycroft.tts import TTS
from mycroft.tts.dummy_tts import DummyTTS
from mycroft.util.file_utils import get_cache_directory
from mycroft.util.plugins import load_plugin
from mycroft_bus_client import Message, MessageBusClient

LOG = logging.getLogger("audio")


class SpeakHandler:
    def __init__(self, config: dict[str, Any], bus: MessageBusClient, tts: TTS):
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
        self.bus.on("speak", self._handle_speak)
        self.bus.on("speak.cache", self._handle_speak)
        self.bus.on("mycroft.tts.stop", self._handle_tts_stop)

    def stop(self):
        pass

    def _handle_speak(self, message: Message):
        try:
            cache_only = message.msg_type == "speak.cache"
            utterance = message.data["utterance"]
            mycroft_session_id = message.data.get("mycroft_session_id")

            LOG.debug(
                "Speak for session '%s': %s (cache=%s)",
                mycroft_session_id,
                utterance,
                cache_only,
            )

            with self._speak_lock:
                # Begin TTS session
                self._mycroft_session_id = mycroft_session_id
                tts_session_id = message.data.get("tts_session_id") or str(uuid4())
                self.bus.emit(
                    Message(
                        "mycroft.tts.session.start",
                        data={
                            "tts_session_id": tts_session_id,
                            "mycroft_session_id": mycroft_session_id,
                        },
                    )
                )

                # Segment utterance into sentences using pysbd (Python Sentence Boundary Detector).
                # NOTE: Segmentation is not thread safe
                segments = self._segment(utterance)

                # Synthesize and cache each segment/chunk independently.
                for i, sentence in enumerate(segments):
                    if self._mycroft_session_id != mycroft_session_id:
                        # New session has started
                        LOG.debug("TTS session cancelled: %s", tts_session_id)

                        # Ensure TTS session is finished
                        self.bus.emit(
                            Message(
                                "mycroft.tts.session.end",
                                data={
                                    "tts_session_id": tts_session_id,
                                    "mycroft_session_id": mycroft_session_id,
                                },
                            )
                        )
                        break

                    cache_path = self._synthesize(sentence)
                    if cache_only:
                        # Don't speak, just cache the chunk
                        continue

                    # Ask audio service to play the chunk
                    audio_uri = "file://" + str(cache_path)
                    self.bus.emit(
                        Message(
                            "mycroft.tts.chunk.start",
                            data={
                                "uri": audio_uri,
                                "tts_session_id": tts_session_id,
                                "chunk_index": i,
                                "num_chunks": len(segments),
                                "mycroft_session_id": mycroft_session_id,
                            },
                        )
                    )
        except Exception:
            LOG.exception("Unexpected error handling speak")

    def _handle_tts_stop(self, message: Message):
        # Cancel any active TTS session
        self._mycroft_session_id = None

    def _synthesize(self, text: str) -> Path:
        """Synthesize audio from text or use cached WAV if available"""
        text_hash = hash_sentence(text)

        # Check preloaded static cache
        if text_hash in self.tts.cache:
            audio_file, _phonemes_file = self.tts.cache.cached_sentences[text_hash]
            return audio_file.path

        # Check temporary dynamic cache
        for cache_dir in self._cache_dirs:
            cache_path = Path.joinpath(cache_dir, f"{text_hash}.wav")
            if cache_path.is_file():
                return cache_path

        # Not in cache, need to synthesize
        LOG.debug("Synthesizing: %s", text)
        self.tts.get_tts(text, str(cache_path))
        return cache_path

    def _segment(self, utterance: str) -> list[str]:
        """Split an utterance into sentences"""
        if self._segmenter is not None:
            # Split into sentences intelligently
            segments = self._segmenter.segment(utterance)
            LOG.debug("Segments: %s", segments)
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
            LOG.debug("Loaded sentence segmenter for language %s", seg_lang)


def load_tts_module(config: dict[str, Any]) -> TTS:
    """Load text to speech module as a plugin"""
    module_name = config["tts"]["module"]
    if module_name == "dummy":
        LOG.debug("Using dummy TTS")
        return DummyTTS("", {})

    tts_config = config["tts"].get(module_name, {})
    lang = config.get("lang", "en-us")
    tts_lang = tts_config.get("lang", lang)

    LOG.debug("Loading text to speech module: %s", module_name)
    module = load_plugin("mycroft.plugin.tts", module_name)
    assert module, f"Failed to load {module_name}"
    tts = module(tts_lang, tts_config)
    LOG.info("Loaded text to speech module: %s", module_name)

    return tts


def hash_sentence(sentence: str):
    """Convert the sentence into a hash value used for the file name

    Args:
        sentence: The sentence to be cached
    """
    encoded_sentence = sentence.encode("utf-8", "ignore")
    sentence_hash = hashlib.md5(encoded_sentence).hexdigest()

    return sentence_hash
