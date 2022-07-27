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
"""Definition of an alarm."""
from dataclasses import dataclass
from datetime import datetime, time
from typing import ClassVar, Optional, Tuple

from mycroft.skills.skill_data import RegexExtractor
from mycroft.util.format import nice_date_time, nice_time
from mycroft.util.parse import extract_datetime
from mycroft.util.time import now_local

from .repeat import (
    build_day_of_week_repeat_rule,
    build_repeat_rule_description,
    determine_next_occurrence,
)
from .resources import StaticResources

BACKGROUND_COLORS = ("#22A7F0", "#40DBB0", "#BDC3C7", "#4DE0FF")


@dataclass
class Alarm:
    """Defines the attributes of an alarm.

    Attributes:
        date_time: the date and time the alarm should sound
        description: speakable description of alarm for TTS purposes
        name: name of the alarm, either user-defined or defaulted to "alarm #"
        repeat_rule: defines the repeating behavior of the alarm.  Valid
            repeat_rules include None for a one-shot alarm or any other
            iCalendar rule from RFC <https://tools.ietf.org/html/rfc5545>.
        snooze: the date and time the alarm should sound after the snooze expires
    """

    MISSING_REPEAT_RULE: ClassVar[str] = "<MISSING>"

    name: Optional[str] = None
    date_time: Optional[datetime] = None
    repeat_rule: Optional[str] = None
    snooze: Optional[datetime] = None
    description: Optional[str] = None

    def __post_init__(self):
        if self.has_repeat_rule:
            self.date_time = determine_next_occurrence(self.repeat_rule, self.date_time)

    @property
    def expired(self) -> bool:
        """Indicates whether or not the alarm has expired."""
        if self.date_time is None:
            return False

        return self.date_time < now_local()

    @property
    def has_name(self) -> bool:
        return bool(self.name)

    @property
    def has_datetime(self) -> bool:
        return self.date_time is not None

    @property
    def has_repeat_rule(self) -> bool:
        return (not self.is_missing_repeat_rule) and bool(self.repeat_rule)

    @property
    def is_missing_repeat_rule(self) -> bool:
        return self.repeat_rule == Alarm.MISSING_REPEAT_RULE

    @staticmethod
    def datetime_from_utterance(
        utterance: str, resources: StaticResources
    ) -> Tuple[Optional[datetime], str]:
        # Extract date/time
        alarm_datetime: Optional[datetime] = None
        datetime_result = extract_datetime(utterance)
        remaining_utterance = utterance
        if datetime_result is not None:
            alarm_datetime, remaining_utterance = datetime_result
            if alarm_datetime.time() == time(0):
                # Check for midnight
                midnight_requested = any(
                    [word in utterance for word in resources.midnight_words]
                )
                if not midnight_requested:
                    alarm_datetime = None
                    remaining_utterance = utterance

        return alarm_datetime, remaining_utterance

    @staticmethod
    def repeat_rule_from_utterance(
        utterance: str, resources: StaticResources
    ) -> Tuple[bool, Optional[str]]:
        repeat_rule: Optional[str] = None
        repeat_in_utterance = any(
            [repeat[0] in utterance for repeat in resources.repeat_phrases]
        )
        if repeat_in_utterance:
            repeat_rule = build_day_of_week_repeat_rule(
                utterance, resources.repeat_rules
            )

        return repeat_in_utterance, repeat_rule

    @staticmethod
    def from_utterance(utterance: str, resources: StaticResources) -> "Alarm":
        # Extract date/time
        alarm_datetime, remaining_utterance = Alarm.datetime_from_utterance(
            utterance, resources
        )

        # Extract name
        name_extractor = RegexExtractor("name", resources.name_regex)
        alarm_name = name_extractor.extract(remaining_utterance)

        # Extract repeat rule
        repeat_in_utterance, repeat_rule = Alarm.repeat_rule_from_utterance(
            utterance, resources
        )
        if repeat_in_utterance and (repeat_rule is None):
            repeat_rule = Alarm.MISSING_REPEAT_RULE

        return Alarm(name=alarm_name, date_time=alarm_datetime, repeat_rule=repeat_rule)

    def format_for_display(
        self, index, translations: StaticResources, use_24_hour: bool
    ) -> dict:
        """Build the name/value pairs to be passed to the GUI.

        Args:
            index: the position of the alarm in the skill's alarm list
            translations: static translations of words into user's selected language.
            use_24_hour: boolean indicating if the time should use the 24 hour format.

        Returns:
            the data used to populate the GUI display.
        """
        color_index = index % 4
        if use_24_hour:
            display_time = nice_time(self.date_time, speech=False, use_24hour=True)
        else:
            display_time = nice_time(self.date_time, speech=False, use_ampm=True)
        if self.repeat_rule:
            display_days = build_repeat_rule_description(self.repeat_rule, translations)
        else:
            weekday = translations.weekdays[self.date_time.weekday()]
            month = translations.months[self.date_time.month - 1]
            display_days = f"{weekday}, {month} {self.date_time.day}"

        return dict(
            backgroundColor=BACKGROUND_COLORS[color_index],
            expired=self.expired,
            alarmName="" if self.name is None else self.name.title(),
            alarmTime=display_time,
            alarmDays=display_days.title(),
        )

    def build_description_dialog(self, resources: StaticResources, use_24_hour: bool):
        """Builds a speakable description of the alarm using its attributes.

        Args:
            resources: static translations of words into user's selected language.
            use_24_hour: boolean indicating if the time should use the 24 hour format.
        """
        if self.repeat_rule:
            dialog_name = "alarm-description-recurring"
            rule_description = build_repeat_rule_description(
                self.repeat_rule, resources
            )
            speakable_time = self._get_speakable_time(use_24_hour)
            dialog_data = dict(time=speakable_time, recurrence=rule_description)
        else:
            dialog_name = "alarm-description"
            if self.name and (self.name != "alarm"):
                dialog_name = "alarm-description-named"

            speakable_datetime = self._get_speakable_date_time(use_24_hour)
            dialog_data = dict(datetime=speakable_datetime)
        dialog_data.update(name=self.name)

        return dialog_name, dialog_data

    def _get_speakable_time(self, use_24_hour: bool) -> str:
        """Formats the alarm time into a speakable string.

        Args:
            use_24_hour: boolean indicating if the time should use the 24 hour format.

        Returns:
            speakable text representing the alarm's time of day.
        """
        assert self.date_time is not None
        if use_24_hour:
            speakable_time = nice_time(self.date_time, use_24hour=True)
        else:
            speakable_time = nice_time(self.date_time, use_ampm=True)

        return speakable_time

    def _get_speakable_date_time(self, use_24_hour: bool) -> str:
        """Formats the date and time into a speakable string.

        Args:
            use_24_hour: boolean indicating if the time should use the 24 hour format.

        Returns:
            speakable text representing the alarm's date and time.
        """
        assert self.date_time is not None
        if use_24_hour:
            speakable_datetime = nice_date_time(
                self.date_time, now=now_local(), use_24hour=True
            )
        else:
            speakable_datetime = nice_date_time(
                self.date_time, now=now_local(), use_ampm=True
            )

        return speakable_datetime
