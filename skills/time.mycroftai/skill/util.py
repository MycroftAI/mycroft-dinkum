# Copyright 2021, Mycroft AI Inc.
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
"""Utility functions for the time skill."""
from datetime import datetime, timedelta
from typing import Optional, Tuple

from mycroft.api import GeolocationApi
from mycroft.util.format import nice_time
from mycroft.util.parse import extract_duration, extract_datetime


class LocationNotFoundError(Exception):
    """Raise this exception when the geolocation API returns no information."""

    pass


def get_geolocation(location: str) -> dict:
    """Retrieve the geolocation information about the requested location.

    Args:
        location: a location specified in the utterance

    Returns:
        A deserialized JSON object containing geolocation information for the
        specified city.

    Raises:
        LocationNotFound error if the API returns no results.
    """
    geolocation_api = GeolocationApi()
    geolocation = geolocation_api.get_geolocation(location)

    if geolocation is None:
        raise LocationNotFoundError("Location {} is unknown".format(location))

    return geolocation


def get_duration_from_utterance(utterance: str) -> Optional[timedelta]:
    """Find words in utterance that represent a duration and convert to a timedelta.

    Args:
        utterance: Words spoken by the user

    Returns:
        Amount of time represented in utterance or None if no duration is found.
    """
    extract = extract_duration(utterance)
    if extract is None:
        duration = None
    else:
        duration, _ = extract

    return duration


def get_datetime_from_utterance(utterance: str) -> Optional[Tuple[str, str]]:
    """Convert words in an utterance representing a date & time to a datetime.

    Args:
        utterance: Words spoken by the user

    Returns:
        The datetime found in the utterance and the remainder of the utterance after
        extracting the datetime.  None and None if no datetime is extracted.
    """
    extract = extract_datetime(utterance)
    if extract is None:
        date_time = None
        remaining_utterance = None
    else:
        date_time, remaining_utterance = extract

    return date_time, remaining_utterance


def get_display_time(date_time: datetime, config: dict) -> str:
    """Convert a datetime object to speakable words.

    Args:
        date_time: the datetime object to convert
        config: core config for indicating the time format.

    Returns:
        A speakable version of the date and time.
    """
    format_time_24_hour = config.get("time_format") == "full"
    return nice_time(date_time, speech=False, use_24hour=format_time_24_hour)
