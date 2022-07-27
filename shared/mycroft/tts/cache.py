#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def hash_sentence(sentence: str):
    """Convert the sentence into a hash value used for the file name

    Args:
        sentence: The sentence to be cached
    """
    encoded_sentence = sentence.encode("utf-8", "ignore")
    sentence_hash = hashlib.md5(encoded_sentence).hexdigest()

    return sentence_hash


class AudioFile:
    def __init__(self, cache_dir: Path, sentence_hash: str, file_type: str):
        self.name = f"{sentence_hash}.{file_type}"
        self.path = cache_dir.joinpath(self.name)

    def save(self, audio: bytes):
        """Write a TTS cache file containing the audio to be spoken.

        Args:
            audio: TTS inference of a sentence
        """
        try:
            with open(self.path, "wb") as audio_file:
                audio_file.write(audio)
        except Exception:
            LOG.exception("Failed to write {} to cache".format(self.name))

    def exists(self):
        return self.path.exists()


class PhonemeFile:
    def __init__(self, cache_dir: Path, sentence_hash: str):
        self.name = f"{sentence_hash}.pho"
        self.path = cache_dir.joinpath(self.name)

    def load(self) -> List:
        """Load phonemes from cache file."""
        phonemes = None
        if self.path.exists():
            try:
                with open(self.path) as phoneme_file:
                    phonemes = phoneme_file.read().strip()
            except Exception:
                LOG.exception("Failed to read phoneme from cache")

        return json.loads(phonemes)

    def save(self, phonemes):
        """Write a TTS cache file containing the phoneme to be displayed.

        Args:
            phonemes: instructions for how to make the mouth on a device move
        """
        try:
            rec = json.dumps(phonemes)
            with open(self.path, "w") as phoneme_file:
                phoneme_file.write(rec)
        except Exception:
            LOG.exception("Failed to write {} to cache".format(self.name))

    def exists(self):
        return self.path.exists()


class TextToSpeechCache:
    def __init__(self):
        self.cached_sentences: Dict[str, Tuple[AudioFile, Optional[PhonemeFile]]] = {}

    def __contains__(self, sentence_key: str) -> bool:
        exists = False
        sentence_info = self.cached_sentences.get(sentence_key)
        if sentence_info is not None:
            # Audio file must exist, phonemes are optional.
            audio, phonemes = self.cached_sentences[sentence_key]
            exists = audio.exists() and ((phonemes is None) or phonemes.exists())

        return exists

    def clear(self):
        self.cached_sentences.clear()

    def curate(self):
        pass
