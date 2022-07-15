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
"""Mycroft skill to respond to user requests for dates."""
import typing
from datetime import date, datetime, timedelta
from urllib import request

from mycroft.messagebus.message import Message
from mycroft.skills import MycroftSkill, intent_handler
from mycroft.skills.intent_service import AdaptIntent
from mycroft.util.format import date_time_format
from mycroft.util.time import now_local

from .skill import Response, get_speakable_weekend_date, is_leap_year
from .skill.util import extract_datetime_from_utterance

MARK_I = "mycroft_mark_1"
MARK_II = "mycroft_mark_2"


class DateSkill(MycroftSkill):
    """Mycroft skill to respond to user requests for dates."""

    def __init__(self):
        super().__init__("DateSkill")
        self.displayed_time = None

    # TODO: Move to reusable location
    @property
    def platform(self):
        """Get the platform identifier string

        Returns:
            str: Platform identifier, such as "mycroft_mark_1",
                 "mycroft_picroft", "mycroft_mark_2".  None for non-standard.
        """
        if self.config_core and self.config_core.get("enclosure"):
            return self.config_core["enclosure"].get("platform")
        else:
            return None

    def initialize(self):
        """Tasks to perform after constructor but before skill is ready for use."""
        date_time_format.cache(self.lang)

    @intent_handler(AdaptIntent().require("query").require("date").optionally("today"))
    def handle_current_date_request(self, message):
        """Respond to a request from the user for the current date.

        Example: "What is the date today?"
        """
        # First ensure that no other date has been requested
        # eg "What is the date tomorrow"
        # In the perfect world this would never happen...
        # However the keywords for this intent are very broad.
        utterance = message.data["utterance"]
        requested_date = extract_datetime_from_utterance(utterance)
        today_vocab = self.resources.load_vocabulary_file("today")[0][0]
        today_date = extract_datetime_from_utterance(today_vocab)
        if requested_date is None or requested_date == today_date:
            result = self._handle_current_date()
        else:
            result = self._handle_relative_date(message)

        return result

    @intent_handler(
        AdaptIntent().require("query").require("relative-day").require("date")
    )
    def handle_relative_date_request(self, message: Message):
        """Respond to a request from the user for a date in the past or future.

        Example: "What is the date in five days?"

        Args:
            request: The request from the user that triggered this intent.
        """
        return self._handle_relative_date(message)

    @intent_handler(AdaptIntent().require("query").require("month"))
    def handle_day_for_date(self, message: Message):
        """Respond to a request from the user for a specific past or future date.

        Example: "When is July 10th?"

        Args:
            request: The request from the user that triggered this intent.
        """
        return self._handle_relative_date(message)

    @intent_handler(AdaptIntent().require("query").require("leap-year"))
    def handle_next_leap_year_request(self, _message):
        """Respond to a request from the user for the next leap year.

        Example: "When is the next leap year?"
        """
        today = now_local().date()
        leap_date = date(today.year, 2, 28)
        year = today.year if today <= leap_date else today.year + 1
        while not is_leap_year(year):
            year += 1

        return self.end_session(dialog=("next-leap-year", dict(year=year)))

    @intent_handler("date-future-weekend.intent")
    def handle_future_weekend_request(self, _message):
        saturday_date = get_speakable_weekend_date("this saturday")
        sunday_date = get_speakable_weekend_date("this sunday")
        dialog_data = dict(saturday_date=saturday_date, sunday_date=sunday_date)

        return self.end_session(dialog=("date-future-weekend", dialog_data))

    @intent_handler("date-last-weekend.intent")
    def handle_last_weekend_request(self, _):
        """Respond to a request from the user for dates for the upcoming weekend.

        Example: "What were the dates last weekend?"
        """
        saturday_date = get_speakable_weekend_date("last saturday")
        sunday_date = get_speakable_weekend_date("last sunday")
        dialog_data = dict(saturday_date=saturday_date, sunday_date=sunday_date)

        return self.end_session(dialog=("date-last-weekend", dialog_data))

    def _handle_current_date(self):
        """Build, speak and display the response to a current date request."""
        response = Response()
        response.build_current_date_response()
        return self._respond(response)

    def _handle_relative_date(self, message: Message):
        """Build, speak and display the response to a current date request.

        Args:
            message: The request from the user that triggered this intent.
        """
        utterance = message.data["utterance"].lower()
        response = Response()
        response.build_relative_date_response(utterance)
        if response.date_time is not None:
            return self._respond(response)

        return None

    def _respond(self, response: Response):
        """Speak and display the response to a date request.

        Args:
            response: Data used by the speak/display logic to communicate the Response
        """
        return self.end_session(
            dialog=(
                response.dialog_name,
                response.dialog_data,
            ),
            gui_page="date-mark-ii.qml",
            gui_data={
                "weekdayString": response.date_time.strftime("%A").upper(),
                "monthString": response.date_time.strftime("%B"),
                "dayString": response.date_time.strftime("%-d"),
            },
            gui_clear_after_speak=True,
        )


def create_skill():
    """Boilerplate code used to load this skill into core."""
    return DateSkill()
