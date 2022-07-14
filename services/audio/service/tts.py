import hashlib
import logging
import tempfile
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import pysbd
from mycroft.tts import TTS
from mycroft.tts.dummy_tts import DummyTTS
from mycroft.util.plugins import load_plugin
from mycroft_bus_client import Message, MessageBusClient

LOG = logging.getLogger("audio")


class SpeakHandler:
    def __init__(self, config: dict[str, Any], bus: MessageBusClient, tts: TTS):
        self.config = config
        self.bus = bus
        self.tts = tts

        self._temp_dir = tempfile.TemporaryDirectory()
        self._cache_dirs = [Path(self._temp_dir.name)]

        self._segmenter: Optional[pysbd.Segmenter] = None
        self._load_segmenter()

    def __call__(self, message: Message):
        try:
            utterance = message.data["utterance"]
            listen = message.data.get("expect_response", False)
            response_skill_id = message.data.get("response_skill_id")
            mycroft_session_id = message.data.get("mycroft_session_id")

            segments = self._segment(utterance)
            session_id = message.data.get("session_id") or str(uuid4())
            for i, sentence in enumerate(segments):
                is_last_chunk = i == (len(segments) - 1)
                cache_path = self._synthesize(sentence)
                audio_uri = "file://" + str(cache_path)
                self.bus.emit(
                    Message(
                        "mycroft.tts.speak-chunk",
                        data={
                            "uri": audio_uri,
                            "session_id": session_id,
                            "chunk_index": i,
                            "num_chunks": len(segments),
                            "listen": listen if is_last_chunk else False,
                            "response_skill_id": response_skill_id
                            if is_last_chunk
                            else None,
                            "mycroft_session_id": mycroft_session_id,
                        },
                    )
                )
        except Exception:
            LOG.exception("Unexpected error handling speak")

    def _synthesize(self, text: str) -> Path:
        text_hash = hash_sentence(text)
        for cache_dir in self._cache_dirs:
            cache_path = Path.joinpath(cache_dir, f"{text_hash}.wav")
            if cache_path.is_file():
                return cache_path

        LOG.debug("Synthesizing: %s", text)
        self.tts.get_tts(text, str(cache_path))
        return cache_path

    def _segment(self, utterance: str) -> list[str]:
        if self._segmenter is not None:
            # Split into sentences intelligently
            segments = self._segmenter.segment(utterance)
            LOG.debug("Segments: %s", segments)
        else:
            # No segmentation
            segments = [utterance]

        return segments

    def _load_segmenter(self):
        module_name = self.config["tts"]["module"]
        tts_config = self.config["tts"].get(module_name, {})
        lang = self.config.get("lang", "en-us")
        tts_lang = tts_config.get("lang", lang)

        # en-us -> en
        seg_lang = tts_lang[:2]
        if seg_lang in pysbd.languages.LANGUAGE_CODES:
            self._segmenter = pysbd.Segmenter(language=seg_lang, clean=False)
            LOG.debug("Loaded sentence segmenter for language %s", seg_lang)


def register_tts(config: dict[str, Any], bus: MessageBusClient, tts: TTS):
    bus.on("speak", SpeakHandler(config, bus, tts))


def load_tts_module(config: dict[str, Any]) -> TTS:
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
