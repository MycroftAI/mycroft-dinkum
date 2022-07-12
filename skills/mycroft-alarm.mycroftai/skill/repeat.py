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
"""Repeat functions for the Mycroft Alarm Skill."""
from datetime import datetime, timedelta
from dateutil.rrule import rrulestr

from mycroft.util.format import join_list
from mycroft.util.log import LOG
from mycroft.util.time import now_local

DAY_ABBREVIATIONS = ("SU", "MO", "TU", "WE", "TH", "FR", "SA")
DAY_OF_WEEK_RULE = "RRULE:FREQ=WEEKLY;INTERVAL=1;BYDAY="


# TODO: Support more complex alarms, e.g. first monday, monthly, etc
def build_day_of_week_repeat_rule(utterance: str, repeat_phrases: dict) -> str:
    """Create a repeat rule in iCal rrule format.

    Arguments:
        utterance: words uttered by the user
        repeat_phrases: map of phrases to repeat patterns

    Returns:
        next recurrence of alarm and an iCal repeat rule (rrule)
    """
    repeat_rule = None
    repeat_days = set()
    for repeat_phrase in repeat_phrases:
        if repeat_phrase in utterance:
            day_numbers = repeat_phrases[repeat_phrase].split()
            repeat_days = {int(day) for day in day_numbers}

    if repeat_days:
        days = [DAY_ABBREVIATIONS[day] for day in repeat_days]
        repeat_rule = DAY_OF_WEEK_RULE + ",".join(days)

    return repeat_rule


def determine_next_occurrence(repeat_rule: str, start_datetime: datetime):
    """Uses the repeat rule to determine the next occurrence of an alarm."""
    LOG.info(
        f"Determining next repeating alarm occurrence given rule '{repeat_rule}' and "
        f"start date/time '{start_datetime}'..."
    )
    if start_datetime > now_local():
        past = start_datetime - timedelta(days=45)
        repeat_scheduler = rrulestr(repeat_rule, dtstart=past)
    else:
        repeat_scheduler = rrulestr(repeat_rule, dtstart=start_datetime)
    next_occurrence = repeat_scheduler.after(now_local())
    LOG.info(f"Next occurrence is {next_occurrence}")

    return next_occurrence


def build_repeat_rule_description(repeat_rule: str, static_resources) -> str:
    """Create a textual description of the repeat rule.

    Arguments:
        repeat_rule: iCal encoded string representing the alarm repeating
        static_resources: words translated to the language in use

    Returns:
        Phrase representing the days the alarm repeats
    """
    repeat_description = None
    day_names = []
    days_of_week = convert_day_of_week(repeat_rule)
    day_numbers = days_of_week.split()
    for phrase, days in static_resources.repeat_rules.items():
        if days == days_of_week:
            repeat_description = phrase
            break  # accept the first perfect match
        elif days in day_numbers:
            day_names.append(phrase)

    if repeat_description is None:
        repeat_description = join_list(day_names, static_resources.and_word)

    return repeat_description


def convert_day_of_week(repeat_rule: str) -> str:
    """Convert the day of week argument in a repeat rule to numeric values."""
    repeat_days = set()
    conversion = dict(SU="0", MO="1", TU="2", WE="3", TH="4", FR="5", SA="6")
    rule_days = repeat_rule[len(DAY_OF_WEEK_RULE) :]  # e.g. "SU,WE"
    for day_abbreviation, day_number in conversion.items():
        if day_abbreviation in rule_days:
            repeat_days.add(day_number)
    repeat_days = list(repeat_days)
    repeat_days.sort()

    return " ".join(repeat_days)
