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
#

import imghdr
import os
import re
import time
from typing import Any, Optional

import requests

from mycroft.util.log import LOG


def get_from_nested_dict(obj: dict, key: str) -> Optional[Any]:
    """Dig through a nested dict to find a key.

    Args:
        obj: Dict object to check
        key: key of interest
    """
    if key in obj:
        return obj[key]

    try:
        # there is no easy answer for whether an
        # item is truly iterable so we will take
        # the pythonic approach and catch the exception.
        for _, value in obj.items():
            if isinstance(value, dict):
                item = get_from_nested_dict(value, key)
                if item is not None:
                    return item
            elif isinstance(value, list):
                for list_item in value:
                    item = get_from_nested_dict(list_item, key)
                    if item is not None:
                        return item
    except:
        pass


def get_image_file_from_wikipedia_url(input_url):
    """Get actual image file from a Wikipedia File: url.

    Wolfram returns url to Wikipedia's file details page rather than the
    actual image file.
    """
    protocol, domain, wiki, *remaining = input_url.split("/")

    image_url = input_url.replace(
        "http://en.wikipedia.org/wiki/File:",
        "https://upload.wikimedia.org/wikipedia/commons/c/cc/",
    )
    return image_url


def process_wolfram_string(text: str, config: dict) -> str:
    """Clean and format an answer from Wolfram into a presentable format.

    Args:
        text: Original answer from Wolfram Alpha
        config: {
            lang: language of the answer
            root_dir: of the Skill to find a regex file
        }
    Returns:
        Cleaned version of the input string.
    """
    # Remove extra whitespace
    text = re.sub(r" \s+", r" ", text)

    # Convert | symbols to commas
    text = re.sub(r" \| ", r", ", text)

    # Convert newlines to commas
    text = re.sub(r"\n", r", ", text)

    # Convert !s to factorial
    text = re.sub(r"!", r",factorial", text)

    regex_file_path = os.path.join(
        config["root_dir"], "regex", config["lang"], "list.rx"
    )
    with open(regex_file_path, "r") as regex:
        list_regex = re.compile(regex.readline().strip("\n"))

    match = list_regex.match(text)
    if match:
        text = match.group("Definition")

    return text


def remove_nested_parentheses(input: str) -> str:
    """Remove content contained within parentheses from a string.

    This includes content that is nested within multiple sets, eg:
    Lemurs (/ˈliːmər/ (listen) LEE-mər)
    """
    ret = ""
    nest_depth = 0
    for char in input:
        if char == "(":
            nest_depth += 1
        elif (char == ")") and nest_depth:
            nest_depth -= 1
        elif not nest_depth:
            ret += char
    return ret


def save_image(img_url: str, file_dir: str) -> str:
    """Save the given image result to the provided directory.

    Currently saves file as timestamp and detected image type file extension.

    Args:
        img_url: Url to download image from.
        file_dir: Directory to save downloaded file to.
    Returns:
        Complete file path of saved image file or None.
    """
    if img_url is None:
        return None
    try:
        # Create unique filename for each request to avoid caching issues
        file_path = os.path.join(file_dir, str(time.time()))
        request_headers = {
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36",
            "referer": "https://mycroft.ai/",
        }
        img_data = requests.get(img_url, headers=request_headers).content
        with open(file_path, "wb+") as f:
            f.write(img_data)
        LOG.info(f"Image successfully downloaded: {file_path}")
        file_type = imghdr.what(file_path)
        if file_type is not None:
            saved_file_path = f"{file_path}.{file_type}"
            os.rename(file_path, saved_file_path)
            return saved_file_path
        else:
            os.remove(file_path)
            LOG.error("Downloaded file was not a valid image")
    except Exception as err:
        LOG.exception(err)


def clear_cache(cache_dir):
    """Delete all files from the given cache directory.

    Note there are no checks on what the directory is. Use with caution."""
    try:
        for file in os.listdir(cache_dir):
            os.remove(os.path.join(cache_dir, file))
        return True
    except:
        return False
