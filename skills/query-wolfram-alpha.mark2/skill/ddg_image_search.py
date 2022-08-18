import json
import re
from typing import Optional

import requests
from mycroft.util.log import LOG

from .util import save_image


def search_ddg_images(query, file_path: str) -> Optional[str]:
    """Search Duck Duck Go and return the first image result.

    Args:
        query: search term
        file_path: path to save image file, excluding file ext

    Returns:
        Full path of saved image file or None
    """
    url = "https://duckduckgo.com/"
    params = {"q": query}

    #   First make a request to above URL, and parse out the 'vqd'
    #   This is a special token, which should be used in the subsequent request
    response = requests.post(url, data=params)
    search_object = re.search(r"vqd=([\d-]+)\&", response.text, re.M | re.I)

    if not search_object:
        LOG.error("DDG token parsing failed.")
        return

    headers = {
        "authority": "duckduckgo.com",
        "accept": "application/json, text/javascript, */*; q=0.01",
        "sec-fetch-dest": "empty",
        "x-requested-with": "XMLHttpRequest",
        "accept-language": "en-GB,en-US;q=0.8,en;q=0.6,ms;q=0.4",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36",
        "referer": "https://duckduckgo.com/",
        # "accept-language": "en-US,en;q=0.9",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
    }

    params = (
        ("l", "us-en"),
        ("o", "json"),
        ("q", query),
        ("vqd", search_object.group(1)),
        ("f", ",,,"),
        ("p", "1"),
        ("v7exp", "a"),
    )

    requestUrl = url + "i.js"

    try:
        response = requests.get(requestUrl, headers=headers, params=params)
        data = json.loads(response.text)
        if len(data["results"]) > 0:
            saved_file_path = save_image(data["results"][0]["image"], file_path)
        return saved_file_path
    except ValueError as err:
        LOG.exception(err)
