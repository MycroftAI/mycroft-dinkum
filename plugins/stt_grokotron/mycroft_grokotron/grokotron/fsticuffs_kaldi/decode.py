#!/usr/bin/env python3
import argparse
import base64
import sys
from typing import Iterable
from xml.etree import ElementTree as ET


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--flatten", action="store_true")
    args = parser.parse_args()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        words = line.split()
        for i, word in enumerate(words):
            if word.startswith("__"):
                words[i] = base64.b64decode(word[2:]).decode()

        if args.flatten:
            xml_str = '<?xml version="1.0"?>' + " ".join(words)
            print(flatten(xml_str))
        else:
            # Print as-is
            print(*words)


def flatten(xml_str: str) -> str:
    root = ET.fromstring(xml_str)
    return " ".join(word.strip() for word in _flatten_element(root) if word)


def _flatten_element(element: ET.Element) -> Iterable[str]:
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


if __name__ == "__main__":
    main()
