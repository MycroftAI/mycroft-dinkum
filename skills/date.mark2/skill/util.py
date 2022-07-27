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
"""Utility functions for the date skill."""
from datetime import datetime

from mycroft.util.format import nice_date
from mycroft.util.log import LOG
from mycroft.util.parse import extract_datetime


def extract_datetime_from_utterance(utterance: str) -> datetime:
    """Extract the date and time requested by the user.

    Args:
        utterance: the words spoken by the user
    """
    extracted_datetime = None
    extract = extract_datetime(utterance)
    LOG.info("extracted datetime: {}".format(extract))
    if extract is not None:
        extracted_datetime, _ = extract

    return extracted_datetime


def get_speakable_weekend_date(day_of_week: str) -> str:
    """Convert the requested weekend day to words speakable by a TTS engine.

    Args:
        day_of_week: words to be converted to a speakable date (e.g. "last saturday")

    Returns:
        The requested date in words speakable by a TTS engine
    """
    date_time, _ = extract_datetime(day_of_week, lang="en-us")
    speakable_datetime = nice_date(date_time)
    speakable_day_of_week, speakable_date, __ = speakable_datetime.split(", ")

    return ", ".join([speakable_day_of_week, speakable_date])


def is_leap_year(year: int) -> bool:
    """Convenience function for determining if a year is a leap year.

    Args:
        year: The year to evaluate against leap year criteria

    Returns:
        whether or not the specified year is a leap year
    """
    return (year % 400 == 0) or ((year % 4 == 0) and (year % 100 != 0))
