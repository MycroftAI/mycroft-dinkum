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
"""Logic to match one or more alarms to a user's request."""
from copy import copy
from typing import List, Optional

from mycroft.skills.skill_data import RegexExtractor
from mycroft.util.log import LOG
from .alarm import Alarm
from .parse import extract_alarm_datetime
from .repeat import build_day_of_week_repeat_rule


class AlarmMatcher:
    """Matches alarms to a request made by the user."""

    def __init__(self, utterance: str, alarms: List[Alarm], static_resources):
        self.utterance = utterance
        self.alarms = alarms
        self.matches = []
        self._help_lingua_franca(static_resources)
        self.requested_repeat_rule = build_day_of_week_repeat_rule(
            utterance, static_resources.repeat_rules
        )
        self.requested_datetime, _ = extract_alarm_datetime(utterance)
        self.requested_name = self._extract_alarm_name(static_resources)
        utterance_words = self.utterance.split()
        self.requested_all = any(
            word in utterance_words for word in static_resources.all_words
        )
        self.requested_next = any(
            word in utterance_words for word in static_resources.next_words
        )

    def _help_lingua_franca(self, translations):
        """Works around a bug when day of week and month are both in the utterance.

        If both a day of week and a date are included in an utterance (e.g. "Monday
        April 5th"), Lingua Franca will return bad data. When this scenario is
        encountered, remove the day of week from the utterance as a work around
        until Lingua Franca is changed to support it.  For example, "Monday
        April 5th" becomes "April 5th".

        Args:
            translations: list of words translated into the user's language
        """
        for month in translations.months:
            if month in self.utterance:
                for day in translations.weekdays:
                    if day in self.utterance:
                        self.utterance = self.utterance.replace(day, "")
                        break
                break

    def _extract_alarm_name(self, static_resources) -> Optional[str]:
        """Attempts to extract a alarm name from an utterance.

        If the regex name matching logic returns no matches, it might be
        a cancel alarm request.  In this case, make another attempt to find the
        alarm name in the utterance by removing the first word ("cancel" or some
        variation) then the second word ("alarm").

        Returns:
            a matched alarm name or None if no match found
        """
        name_extractor = RegexExtractor("name", static_resources.name_regex)
        alarm_name = name_extractor.extract(self.utterance)
        if alarm_name is None:
            # Attempt to extract a name from a "cancel alarm" utterance
            words = self.utterance.split()
            possible_name = " ".join(words[1:])
            if possible_name in [alarm.name for alarm in self.alarms]:
                alarm_name = possible_name
            else:
                possible_name = " ".join(words[2:])
                if possible_name in [alarm.name for alarm in self.alarms]:
                    alarm_name = possible_name
            if alarm_name is not None:
                LOG.info(f'Extracted alarm name "{alarm_name}" from utterance')

        return alarm_name

    @property
    def no_match_criteria(self) -> bool:
        """Returns a boolean indicating if any criteria was found in the utterance."""
        return (
            self.requested_name is None
            and self.requested_datetime is None
            and self.requested_repeat_rule is None
            and not self.requested_next
            and not self.requested_all
        )

    def match(self):
        """Main method to perform the matching."""
        if self.requested_all:
            # uses a copy of the passed alarms to avoid issues in the skill with
            # alarms iterating over themselves
            self.matches = copy(self.alarms)
        elif self.requested_next:
            self.matches = [self.alarms[0]]
        if self.requested_name is not None:
            self._match_alarm_to_name()
        elif self.requested_repeat_rule is not None:
            self._match_alarm_to_repeat()
        elif self.requested_datetime is not None:
            self._match_alarm_to_datetime()

    def _match_alarm_to_name(self):
        """Finds a alarm that matches the name requested by the user.

        In a conversation mode, when the user is asked "which alarm?" the answer
        can be the name of the alarm.  Timers that are not given specific names are
        named "alarm x" but the name extractor will only extract "x".  So try to
        prepend the word "alarm" to get a match if other matches fail.

        Returns:
            Alarm matching the name requested by the user.
        """
        for alarm in self.alarms:
            match = alarm.name == self.requested_name or alarm.name == "alarm " + str(
                self.requested_name
            )
            if match:
                self.matches.append(alarm)
                LOG.info(f"Match found for alarm name '{self.requested_name}'")
                break

    def _match_alarm_to_datetime(self):
        """If the utterance includes a duration, find alarms that match it."""
        if self.requested_datetime is not None:
            for alarm in self.alarms:
                if self.requested_datetime == alarm.date_time:
                    self.matches.append(alarm)
                    LOG.info("Found datetime match")

    def _match_alarm_to_repeat(self):
        if self.requested_repeat_rule is not None:
            for alarm in self.alarms:
                if alarm.repeat_rule == self.requested_repeat_rule:
                    self.matches.append(alarm)
                    LOG.info(
                        f"Match found for repeat rule '{self.requested_repeat_rule}'"
                    )
                    break
