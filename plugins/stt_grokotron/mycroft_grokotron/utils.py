import base64
import struct
from typing import Any, Dict, Optional, Iterable, IO
from xml.etree import ElementTree as ET


def decode_output(output_text: str):
    words = output_text.split()
    for i, word in enumerate(words):
        if word.startswith("__"):
            # Some "words" are base64-encoded XML tags
            words[i] = base64.b64decode(word[2:]).decode()

    decoded_text = " ".join(words)
    xml_text = f'<?xml version="1.0" ?>{decoded_text}'

    return flatten(xml_text)


def flatten(xml_str: str) -> str:
    """Flatten XML output from Grokotron into a string"""
    root = ET.fromstring(xml_str)
    return " ".join(word.strip() for word in _flatten_element(root) if word)


def _flatten_element(element: ET.Element) -> Iterable[str]:
    """Apply all substitutions (<sub>) and return a flat string"""
    if element.tag == "sub":
        yield element.attrib.get("value", "")
    else:
        # Text before any tags (or end tag)
        text = element.text if element.text is not None else ""
        if text.strip():
            yield text

        for child in element:
            # Sub-elements
            yield from _flatten_element(child)

        # Text after the current tag
        tail = element.tail if element.tail is not None else ""
        if tail.strip():
            yield tail


def make_wav_header():
    """Create a fake WAV header with the maximum data size"""
    header_data = b""
    header_data += b"RIFF"

    # Max data size, since we're streaming and can't know how big it will be.
    # Kaldi will issue a warning about this, but ultimately doesn't care.
    header_data += b"\xFF\xFF\xFF\xFF"

    header_data += b"WAVE"

    # fmt chunk
    header_data += b"fmt "
    fs = 16000  # sample rate
    format_tag = 0x0001  # PCM
    channels = 1  # mono
    bit_depth = 2 * 8  # 16-bit
    bytes_per_second = fs * (bit_depth // 8) * channels
    block_align = channels * (bit_depth // 8)

    fmt_chunk_data = struct.pack(
        "<HHIIHH",
        format_tag,
        channels,
        fs,
        bytes_per_second,
        block_align,
        bit_depth,
    )

    header_data += struct.pack("<I", len(fmt_chunk_data))
    header_data += fmt_chunk_data
    header_data += b"data"

    return header_data
