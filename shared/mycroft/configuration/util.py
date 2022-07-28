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
import io
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, Union


def load_commented_json(config_path: Union[str, Path]) -> Dict[str, Any]:

    with open(config_path, "r", encoding="utf-8") as config_file:
        with io.StringIO() as uncommented_file:
            for line in strip_comments(config_file):
                uncommented_file.write(line)

            uncommented_file.seek(0)
            config = json.load(uncommented_file)

    return config


def strip_comments(source: Iterable[str], comment: str = "//") -> Iterable[str]:
    for line in source:
        if not line.strip().startswith(comment):
            yield line


def merge_dict(base: Dict[str, Any], delta: Dict[str, Any]):
    """
    Recursively merging configuration dictionaries.

    Args:
        base:  Target for merge
        delta: Dictionary to merge into base
    """

    for d_key, d_val in delta.items():
        b_val = base.get(d_key)
        if isinstance(d_val, dict) and isinstance(b_val, dict):
            merge_dict(b_val, d_val)
        else:
            base[d_key] = d_val
