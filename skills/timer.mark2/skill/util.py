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
"""Utility functions for the timer skill."""
import re
from datetime import timedelta
from typing import Dict, Optional, Sequence, Tuple

from mycroft.skills.skill_data import RegexExtractor
from mycroft.util.format import pronounce_number
from mycroft.util.log import LOG
from mycroft.util.parse import extract_duration, extract_number

# Substitutions for timer names.
# A value of None means to not interpret the key as a timer name.
TIMER_NAME_REPLACEMENTS = {"to": "2", "for": "four", "an": None, "new": None}


def extract_timer_duration(utterance: str) -> Tuple[Optional[timedelta], Optional[str]]:
    """Extract duration in seconds.

    Args:
        utterance: Full request, e.g. "set a 30 second timer"

    Returns
        Number of seconds requested (or None if no duration was extracted) and remainder
        of utterance
    """
    normalized_utterance = _normalize_utterance(utterance)
    extract_result = extract_duration(normalized_utterance)
    if extract_result is None:
        duration = remaining_utterance = None
    else:
        duration, remaining_utterance = extract_result
    if duration is None:
        LOG.info("No duration found in request")
    else:
        LOG.info("Duration of {} found in request".format(duration))

    return duration, remaining_utterance


def _normalize_utterance(utterance: str) -> str:
    """Make the duration of the timer in the utterance consistent for parsing.

    Some STT engines return "30-second timer" not "30 second timer".

    Args:
        utterance: Full request, e.g. "set a 30 second timer"

    Returns:
        The same utterance with any dashes replaced by spaces.

    """
    # TODO: Fix inside parsers
    return utterance.replace("-", " ")


def remove_conjunction(conjunction: str, utterance: str) -> str:
    """Remove the specified conjunction from the utterance.

    For example, remove the " and" left behind from extracting "1 hour" and "30 minutes"
    from "for 1 hour and 30 minutes".  Leaving it behind can confuse other intent
    parsing logic.

    Args:
        conjunction: translated conjunction (like the word "and") to be
            removed from utterance
        utterance: Full request, e.g. "set a 30 second timer"

    Returns:
        The same utterance with any dashes replaced by spaces.

    """
    pattern = r"\s\s{}".format(conjunction)
    remaining_utterance = re.sub(pattern, "", utterance, flags=re.IGNORECASE)

    return remaining_utterance


def extract_ordinal(utterance: str) -> str:
    """Extract ordinal number from the utterance.

    Args:
        utterance: Full request, e.g. "set a 30 second timer"

    Returns:
        An integer representing the numeric value of the ordinal or None if no ordinal
        is found in the utterance.
    """
    ordinal = None
    extracted_number = extract_number(utterance, ordinals=True)
    if type(extracted_number) == int:
        ordinal = extracted_number

    return ordinal


def get_speakable_ordinal(ordinal) -> str:
    """Get speakable ordinal if other timers exist with same duration.

    Args:
        ordinal: if more than one timer exists for the same duration, this value will
            indicate if it is the first, second, etc. instance of the duration.

    Returns:
        The ordinal that can be passed to TTS (i.e. "first", "second")
    """
    return pronounce_number(ordinal, ordinals=True)


def format_timedelta(time_delta: timedelta) -> str:
    """Convert number of seconds into a displayable time string.

    Args:
        time_delta: an amount of time to convert to a displayable string.

    Returns:
        the value to display on a device's screen or faceplate.
    """
    hours = abs(time_delta // timedelta(hours=1))
    minutes = abs((time_delta - timedelta(hours=hours)) // timedelta(minutes=1))
    seconds = abs(
        (time_delta - timedelta(hours=hours) - timedelta(minutes=minutes))
        // timedelta(seconds=1)
    )
    if hours:
        time_elements = [str(hours), str(minutes).zfill(2), str(seconds).zfill(2)]
    else:
        time_elements = [str(minutes).zfill(2), str(seconds).zfill(2)]
    formatted_time_delta = ":".join(time_elements)

    return formatted_time_delta


def extract_timer_name(
    utterance: str,
    static_resources,
    timer_names: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """Attempts to extract a timer name from an utterance.

    If the regex name matching logic returns no matches, it might be
    a cancel alarm request.  In this case, make another attempt to find the
    alarm name in the utterance by removing the first word ("cancel" or some
    variation) then the second word ("alarm").

    Returns:
        a matched timer name or None if no match found
    """
    if timer_names and (utterance in timer_names):
        return utterance

    name_extractor = RegexExtractor("Name", static_resources.name_regex)
    timer_name = name_extractor.extract(utterance)
    timer_name = TIMER_NAME_REPLACEMENTS.get(timer_name, timer_name)
    if timer_name is not None:
        LOG.info(f'Extracted timer name "{timer_name}" from utterance')
    else:
        LOG.info("No timer name extracted from utterance")

    return timer_name


def encode_timedelta(duration: timedelta) -> Dict[str, int]:
    return {
        "days": duration.days,
        "seconds": duration.seconds,
        "microseconds": duration.microseconds,
    }


def decode_timedelta(value: Dict[str, int]) -> timedelta:
    return timedelta(
        days=value.get("days", 0),
        seconds=value.get("seconds", 0),
        microseconds=value.get("microseconds", 0),
    )
