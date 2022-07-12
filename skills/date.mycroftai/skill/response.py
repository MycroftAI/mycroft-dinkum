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
"""Logic to generate response data for a date request."""
from datetime import timedelta

from mycroft.util.format import nice_date, nice_duration
from mycroft.util.time import now_local
from .util import extract_datetime_from_utterance


class Response:
    """Logic to generate response data for a date request."""
    def __init__(self):
        self.date_time = None
        self.dialog_name = None
        self.dialog_data = None

    @property
    def speakable_date(self) -> str:
        """Syntactic sugar to give context to why we are calling nice_date

        Returns:
            The date formatted in a string that can be spoken by a TTS engine.
        """
        return nice_date(self.date_time)

    def build_current_date_response(self):
        """Generate the data needed to respond to a current date request."""
        self.date_time = now_local()
        self.dialog_name = "date"
        self.dialog_data = dict(date=self.speakable_date)

    def build_relative_date_response(self, utterance: str):
        """Generate the data needed to respond to a relative date request.

        Args:
            utterance: The words spoken by the user to initiate the request.
        """
        self.date_time = extract_datetime_from_utterance(utterance)
        if self.date_time is not None:
            duration = self._determine_relative_duration()
            if duration.days >= 0:
                speakable_duration = nice_duration(duration)
                self.dialog_name = "date-relative-future"
            else:
                speakable_duration = nice_duration(abs(duration))
                self.dialog_name = "date-relative-past"
            self.dialog_data = dict(
                date=self.speakable_date, num_days=speakable_duration
            )

    def _determine_relative_duration(self) -> timedelta:
        """Determine the number of days from the current date requested by the user.

        Returns:
            The amount of time away from the current date requested by the user
        """
        relative_date = self.date_time.date()
        today = now_local().date()
        duration = relative_date - today

        return duration
