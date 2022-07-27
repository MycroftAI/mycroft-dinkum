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
"""Defines a timer object."""
from datetime import timedelta
from typing import Optional

from mycroft.util.format import nice_duration
from mycroft.util.time import now_utc

from .util import format_timedelta

BACKGROUND_COLORS = ("#22A7F0", "#40DBB0", "#BDC3C7", "#4DE0FF")


class CountdownTimer:
    """Data attributes that define a timer."""

    _speakable_duration = None

    def __init__(self, duration: timedelta, name: str, index=None):
        self.duration = duration
        self.name = name
        self.index = index
        self.expiration = now_utc() + duration
        self.expiration_announced = False
        self.ordinal = 0

    @property
    def expired(self) -> bool:
        """Boolean value representing whether or not the timer has expired."""
        return self.expiration < now_utc()

    @property
    def speakable_duration(self) -> str:
        """Generate a string that can be used to speak the timer's initial duration."""
        if self._speakable_duration is None:
            self._speakable_duration = nice_duration(self.duration)

        return self._speakable_duration

    @property
    def time_remaining(self) -> Optional[timedelta]:
        """The amount of time remaining until the timer expires."""
        if self.expired:
            time_remaining = None
        else:
            time_remaining = self.expiration - now_utc()

        return time_remaining

    @property
    def percent_remaining(self) -> float:
        """The percentage of the timer duration that remains until expiration."""
        if self.expired:
            percent_remaining = None
        else:
            percent_remaining = (
                self.time_remaining.total_seconds() / self.duration.total_seconds()
            )

        return percent_remaining

    @property
    def time_since_expiration(self) -> Optional[timedelta]:
        """The amount of time elapsed since the timer expired."""
        if self.expired:
            time_since_expiration = now_utc() - self.expiration
        else:
            time_since_expiration = None

        return time_since_expiration

    @property
    def display_data(self) -> dict:
        """Build the name/value pairs to be passed to the GUI."""
        color_index = (self.index % 4) - 1
        if self.expired:
            expiration_delta = "-" + format_timedelta(self.time_since_expiration)
        else:
            expiration_delta = format_timedelta(self.time_remaining)

        return dict(
            backgroundColor=BACKGROUND_COLORS[color_index],
            expired=self.expired,
            percentRemaining=self.percent_remaining,
            timerName=self.name.title(),
            timeDelta=expiration_delta,
        )

    @property
    def spoken_name(self) -> str:
        """Name of timer with 'timer' appended if not already part of the name.

        Examples:
            * chicken -> chicken timer
            * timer 2 -> timer 2
        """
        spoken_name = self.name
        if "timer" not in spoken_name.lower().split():
            spoken_name = f"{spoken_name} timer"

        return spoken_name
