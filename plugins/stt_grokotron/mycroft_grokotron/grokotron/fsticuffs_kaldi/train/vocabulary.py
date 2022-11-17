import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import IO, Callable, Dict, Iterable, List, Optional, Set

_LOGGER = logging.getLogger("vocabulary")


@dataclass
class Pronunciation:
    phonemes: List[str]
    role: Optional[str] = None


class SqliteDictionary:
    def __init__(self, database):
        self._db_conn = sqlite3.connect(database)

    def get_pronunciations(
        self, word: str, role: Optional[str] = None
    ) -> List[Pronunciation]:
        prons: List[Pronunciation] = []

        if role is not None:
            cursor = self._db_conn.execute(
                "SELECT role, phonemes FROM word_phonemes WHERE word = ? AND role = ? ORDER BY pron_order",
                (word, role),
            )
        else:
            cursor = self._db_conn.execute(
                "SELECT role, phonemes FROM word_phonemes WHERE word = ? ORDER BY pron_order",
                (word,),
            )

        for row in cursor:
            db_role, db_phonemes = row[0], row[1].split()
            prons.append(Pronunciation(phonemes=db_phonemes, role=db_role))

        return prons


def read_dictionary(
    dict_file: Iterable[str],
    word_dict: Optional[Dict[str, List[str]]] = None,
    transform: Optional[Callable[[str], str]] = None,
    silence_words: Optional[Set[str]] = None,
) -> Dict[str, List[str]]:
    """
    Loads a CMU/Julius word dictionary, optionally into an existing Python dictionary.
    """
    if word_dict is None:
        word_dict = {}

    for i, line in enumerate(dict_file):
        line = line.strip()
        if not line:
            continue

        try:
            # Use explicit whitespace (avoid 0xA0)
            word, *parts = re.split(r"[ \t]+", line)

            # Skip Julius extras
            pronounce = " ".join(p for p in parts if p[0] not in {"[", "@"})

            word = word.split("(")[0]
            # Julius format word1+word2
            words = word.split("+")

            for word in words:
                # Don't transform silence words
                if transform and (
                    (silence_words is None) or (word not in silence_words)
                ):
                    word = transform(word)

                if word in word_dict:
                    word_dict[word].append(pronounce)
                else:
                    word_dict[word] = [pronounce]
        except Exception as e:
            _LOGGER.warning("read_dict: %s (line %s)", e, i + 1)

    return word_dict


def write_dictionary(word_dict: Dict[str, List[str]], dict_file: IO[str]):
    """Write a CMU style dictionary/lexicon to a file"""
    for word in word_dict.keys():
        for word_pron in word_dict[word]:
            print(word, word_pron, file=dict_file)
