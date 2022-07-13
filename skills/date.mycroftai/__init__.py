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
        self._cached_tts_date: typing.Optional[datetime] = None

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

        self._current_date_cache_key = f"{self.skill_id}.current-date"

        self.add_event("mycroft.ready", self._cache_current_date_tts)

        # Check if date has changed once a minute
        self.schedule_repeating_event(
            handler=self._cache_current_date_tts,
            when=None,
            frequency=60,
            name="CacheTTS",
        )

    @intent_handler(AdaptIntent().require("query").require("date").optionally("today"))
    def handle_current_date_request(self, message):
        """Respond to a request from the user for the current date.

        Example: "What is the date today?"
        """
        with self.activity():
            # First ensure that no other date has been requested
            # eg "What is the date tomorrow"
            # In the perfect world this would never happen...
            # However the keywords for this intent are very broad.
            utterance = message.data["utterance"]
            requested_date = extract_datetime_from_utterance(utterance)
            today_vocab = self.resources.load_vocabulary_file("today")[0][0]
            today_date = extract_datetime_from_utterance(today_vocab)
            if requested_date is None or requested_date == today_date:
                self._handle_current_date()
            else:
                self._handle_relative_date(message)

    @intent_handler(
        AdaptIntent().require("query").require("relative-day").require("date")
    )
    def handle_relative_date_request(self, request: Message):
        """Respond to a request from the user for a date in the past or future.

        Example: "What is the date in five days?"

        Args:
            request: The request from the user that triggered this intent.
        """
        with self.activity():
            self._handle_relative_date(request)

    @intent_handler(AdaptIntent().require("query").require("month"))
    def handle_day_for_date(self, request):
        """Respond to a request from the user for a specific past or future date.

        Example: "When is July 10th?"

        Args:
            request: The request from the user that triggered this intent.
        """
        with self.activity():
            self._handle_relative_date(request)

    @intent_handler(AdaptIntent().require("query").require("leap-year"))
    def handle_next_leap_year_request(self, _):
        """Respond to a request from the user for the next leap year.

        Example: "When is the next leap year?"
        """
        with self.activity():
            today = now_local().date()
            leap_date = date(today.year, 2, 28)
            year = today.year if today <= leap_date else today.year + 1
            while not is_leap_year(year):
                year += 1
            self.speak_dialog("next-leap-year", data=dict(year=year), wait=True)

    @intent_handler("date-future-weekend.intent")
    def handle_future_weekend_request(self, _):
        with self.activity():
            saturday_date = get_speakable_weekend_date("this saturday")
            sunday_date = get_speakable_weekend_date("this sunday")
            dialog_data = dict(saturday_date=saturday_date, sunday_date=sunday_date)
            self.speak_dialog("date-future-weekend", data=dialog_data, wait=True)

    @intent_handler("date-last-weekend.intent")
    def handle_last_weekend_request(self, _):
        """Respond to a request from the user for dates for the upcoming weekend.

        Example: "What were the dates last weekend?"
        """
        with self.activity():
            saturday_date = get_speakable_weekend_date("last saturday")
            sunday_date = get_speakable_weekend_date("last sunday")
            dialog_data = dict(saturday_date=saturday_date, sunday_date=sunday_date)
            self.speak_dialog("date-last-weekend", data=dialog_data, wait=True)

    def _handle_current_date(self):
        """Build, speak and display the response to a current date request."""
        response = Response()
        response.build_current_date_response()
        self._respond(response, cache_key=self._current_date_cache_key)
        self._cache_current_date_tts()

    def _handle_relative_date(self, request: Message):
        """Build, speak and display the response to a current date request.

        Args:
            request: The request from the user that triggered this intent.
        """
        utterance = request.data["utterance"].lower()
        response = Response()
        response.build_relative_date_response(utterance)
        if response.date_time is not None:
            self._respond(response)

    def _respond(self, response: Response, cache_key=None):
        """Speak and display the response to a date request.

        Args:
            response: Data used by the speak/display logic to communicate the Response
        """
        self._display(response)
        self.speak_dialog(
            response.dialog_name, response.dialog_data, wait=True, cache_key=cache_key
        )
        self._clear_display()

    def _display(self, response: Response):
        """Display the response to a date request if the platform supports it.

        Args:
            response: Data used by the display logic to communicate the Response
        """
        if self.platform == MARK_I:
            self._display_mark_i(response)
        elif self.gui.connected:
            self._display_gui(response)

    def _display_mark_i(self, response: Response):
        """Display the response to a date request on the Mark I.

        This logic could be re-used for other platforms that have an Arduino faceplate
        with the same dimensions as the Mark I's.

        Args:
            response: Data used by the display logic to communicate the Response
        """
        display_date = self._get_display_date(response.date_time)
        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_text(display_date)

    def _get_display_date(self, date_time: datetime) -> str:
        """Format the datetime object returned from the parser for display purposes.

        Args:
            date_time: Contains the date that will be displayed.
        """
        if self.config_core.get("date_format") == "MDY":
            display_date = date_time.strftime("%-m/%-d/%Y")
        else:
            display_date = date_time.strftime("%Y/%-d/%-m")

        return display_date

    def _display_gui(self, response: Response):
        """Display the response to a date request on a device using the GUI Framework.

        Args:
            response: Data used by the display logic to communicate the Response
        """
        self.gui["weekdayString"] = response.date_time.strftime("%A").upper()
        self.gui["monthString"] = response.date_time.strftime("%B")
        self.gui["dayString"] = response.date_time.strftime("%-d")
        if self.platform == MARK_II:
            self.gui.show_page("date-mark-ii.qml", override_idle=True)
        else:
            self.gui.show_page("date-scalable.qml", override_idle=True)

    def _clear_display(self):
        """Clear the display medium of the date."""
        if self.platform == MARK_I:
            self.enclosure.mouth_reset()
            self.enclosure.activate_mouth_events()
            self.enclosure.display_manager.remove_active()
        elif self.gui.connected:
            self.gui.release()

    def _cache_current_date_tts(self, _message=None):
        try:
            now = datetime.now()
            if (self._cached_tts_date is None) or (
                self._cached_tts_date.date() != now.date()
            ):
                self._cached_tts_date = now

                response = Response()
                response.build_current_date_response()

                self.cache_dialog(
                    response.dialog_name,
                    response.dialog_data,
                    cache_key=self._current_date_cache_key,
                )
        except Exception:
            self.log.exception("Error while caching TTS")


def create_skill():
    """Boilerplate code used to load this skill into core."""
    return DateSkill()
