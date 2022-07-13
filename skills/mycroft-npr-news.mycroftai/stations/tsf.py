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

from datetime import timedelta
from http import HTTPStatus

import requests
from mycroft.util.time import now_local
from pytz import timezone


def get_tsf_url():
    """Custom inews fetcher for TSF news.

    Constructs url using standard format with current date and time."""
    feed = (
        "https://www.tsf.pt/stream/audio/{year}/{month:02d}/"
        "noticias/{day:02d}/not{hour:02d}.mp3"
    )
    uri = None
    hours_offset = 0
    status = HTTPStatus.NOT_FOUND
    date = now_local(timezone("Portugal"))
    while status != HTTPStatus.OK and hours_offset < 5:
        date -= timedelta(hours=hours_offset)
        uri = feed.format(
            hour=date.hour, year=date.year, month=date.month, day=date.day
        )
        status = requests.get(uri).status_code
        hours_offset += 1
    if status != HTTPStatus.OK:
        return None
    return uri
