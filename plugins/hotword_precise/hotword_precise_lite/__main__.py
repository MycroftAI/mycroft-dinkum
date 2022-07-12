#!/usr/bin/env python3
# Copyright 2021 Mycroft AI Inc.
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
import argparse
import os
import sys
from pathlib import Path

from .mycroft_hotword import TFLiteHotWordEngine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Path to TFLite model")
    parser.add_argument(
        "--sensitivity",
        type=float,
        default=0.8,
        help="Model sensitivity (0-1, default: 0.8)",
    )
    parser.add_argument(
        "--trigger-level",
        type=int,
        default=4,
        help="Number of activations before detection occurs (default: 4)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=2048,
        help="Number of bytes to read at a time from stdin",
    )
    args = parser.parse_args()
    args.model = Path(args.model).absolute()

    engine = TFLiteHotWordEngine(
        local_model_file=args.model,
        sensitivity=args.sensitivity,
        trigger_level=args.trigger_level,
        chunk_size=args.chunk_size,
    )

    if os.isatty(sys.stdin.fileno()):
        print("Reading raw 16-bit 16khz mono audio from stdin", file=sys.stderr)

    try:
        while True:
            chunk = sys.stdin.buffer.read(args.chunk_size)
            if not chunk:
                break

            engine.update(chunk)

            if engine.found_wake_word(None):
                print("!", end="", flush=True)
            else:
                print(".", end="", flush=True)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
