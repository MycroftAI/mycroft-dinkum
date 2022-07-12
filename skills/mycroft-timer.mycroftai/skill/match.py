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
"""Logic to match one or more timers to a user's request."""
from copy import copy
from typing import List

from mycroft.util.log import LOG
from .timer import CountdownTimer
from .util import extract_ordinal, extract_timer_duration, extract_timer_name


class TimerMatcher:
    """Matches timers to a request made by the user."""

    def __init__(self, utterance: str, timers: List[CountdownTimer], static_resources):
        self.utterance = utterance
        self.timers = timers
        self.static_resources = static_resources
        self.matches = []
        self.requested_duration, remaining_utterance = extract_timer_duration(
            self.utterance
        )
        self.requested_name = extract_timer_name(
            remaining_utterance, static_resources, timer_names=[t.name for t in timers]
        )
        self.requested_ordinal = extract_ordinal(self.utterance)
        utterance_words = self.utterance.split()
        self.requested_all = any(
            word in utterance_words for word in static_resources.all_words
        )

    @property
    def no_match_criteria(self) -> bool:
        """Returns a boolean indicating if any criteria was found in the utterance."""
        return (
            self.requested_name is None
            and self.requested_duration is None
            and not self.requested_all
        )

    def match(self):
        """Main method to perform the matching."""
        if self.requested_all:
            # uses a copy of the passed alarms to avoid issues in the skill with
            # timers iterating over themselves
            self.matches = copy(self.timers)
        if self.requested_name is not None:
            self._match_timer_to_name()
        elif self.requested_duration is not None:
            self._match_timers_to_duration()
        elif self.requested_ordinal:
            self._match_ordinal()

    def _match_timers_to_duration(self):
        """If the utterance includes a duration, find timers that match it."""
        if self.requested_duration is not None:
            for timer in self.timers:
                if self.requested_duration == timer.duration:
                    self.matches.append(timer)
            LOG.info("Found {} duration matches".format(len(self.matches)))

    def _match_timer_to_name(self):
        """Finds a timer that matches the name requested by the user.

        In a conversation mode, when the user is asked "which timer?" the answer
        can be the name of the timer.  Timers that are not given specific names are
        named "timer x" but the name extractor will only extract "x".  So try to
        prepend the word "timer" to get a match if other matches fail.

        Returns:
            Timer matching the name requested by the user.
        """
        for timer in self.timers:
            match = timer.name == self.requested_name or timer.name == "timer " + str(
                self.requested_name
            )
            if match:
                self.matches.append(timer)
                LOG.info(f"Match found for timer name '{timer.name}'")
                break

    def _match_ordinal(self):
        """If the utterance includes a ordinal, find timers that match it."""
        if self.matches is not None:
            self._filter_matches_by_ordinal()
        else:
            self._match_timers_to_ordinal()

    def _filter_matches_by_ordinal(self):
        """Examine the timers already filtered by name and/or duration for ordinal."""
        for timer in self.matches:
            if self.requested_ordinal == timer.ordinal:
                self.matches = [timer]
                break

    def _match_timers_to_ordinal(self):
        """No timers have matched to name and/or duration so search all for ordinal."""
        for index, timer in enumerate(self.timers):
            ordinal_match_value = index + 1
            if self.requested_ordinal == ordinal_match_value:
                self.matches = [timer]
