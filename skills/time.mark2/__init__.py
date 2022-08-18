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
"""Mycroft skill for reporting the current and future time.

NOTE ON REGULAR EXPRESSION HANDLING:
    Most skills that have regular expression files (those with a ".rx" extension) can
    use the intent system to determine if words matching the regular expression(s) are
    present in the utterance.  This has the benefit of improving intent confidence
    calculations.  This skill, however, foregoes that mechanism.

    Consider the following request from the user:
        What time is it in London in 5 hours?

    A regular expression to find the location in this request is difficult to write.
    The location can be found looking of the word "in" followed by a city name.  But in
    this case, the future offset "in 5 hours" would also match this type of pattern.

    To get around this situation, this skill does not pass the regular expression on to
    Adapt.  Instead, it pulls the future offset out of the user's request first,
    leaving only the city to match the regular expression looking for a location.
"""
from pathlib import Path

from mycroft.messagebus.message import Message
from mycroft.skills import MycroftSkill, intent_handler
from mycroft.skills.intent_service import AdaptIntent
from mycroft.util.format import date_time_format

from .skill import LocationNotFoundError, Response, get_display_time

TEN_SECONDS = 10


class TimeSkill(MycroftSkill):
    """Mycroft skill for reporting the current and future time."""

    def __init__(self, skill_id: str):
        super().__init__(skill_id=skill_id, name="TimeSkill")
        self.displayed_time = None
        self.location_regex_path = Path(self.find_resource("location.rx"))

    def initialize(self):
        """Do the things after the constructor but before logic is executed."""
        date_time_format.cache(self.lang)

    @intent_handler(AdaptIntent().require("query").require("time"))
    def handle_current_time_adapt(self, message: Message):
        """Respond to a request for the current time (e.g. "what time is it?")

        Args:
            request: Data from the intent parser regarding the user's voice request.
        """
        dialog, gui = self._handle_current_time(message)
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler("what-time-is-it.intent")
    def handle_current_time_padatious(self, message: Message):
        """Respond to a less common request for the current time.

        Example: "do you have the time?"

        Args:
            request: Data from the intent parser regarding the user's voice request.
        """
        return self.handle_current_time_adapt(message)

    @intent_handler(
        AdaptIntent("")
        .optionally("query")
        .require("time")
        .require("future")
        .require("duration")
    )
    def handle_future_time_adapt(self, message: Message):
        """Respond to a request for the future time.

        Example: "What time will it be in 8 hours?"

        Args:
            request: Data from the intent parser regarding the user's voice request.
        """
        dialog, gui = self._handle_future_time(message)
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler("what-time-will-it-be.intent")
    def handle_future_time_padatious(self, message: Message):
        """Respond to a less common request for the future time.

        Example: "when is it 8 hours from now?"

        Args:
            request: Data from the intent parser regarding the user's voice request.
        """
        return self.handle_current_time_adapt(message)

    def _handle_future_time(self, request: Message):
        """Respond to a request for the future time.

        Determine the future time, then speak the result to the user and display
        it (if applicable).

        Args:
            request: Data from the intent parser regarding the user's voice request.
        """
        dialog = None
        gui = None

        response = Response(self.config_core, self.location_regex_path)
        try:
            response.build_future_time_response(request.data["utterance"])
        except LocationNotFoundError:
            dialog, gui = self._handle_location_not_found(response)
        else:
            if response.date_time is None:
                dialog, gui = self._handle_current_time(request)
            else:
                dialog, gui = self._respond(response)

        return dialog, gui

    def _handle_current_time(self, request: Message):
        """Respond to a request for the current time.

        Determine the current time, then speak the result to the user and display
        it (if applicable).

        Args:
            request: Data from the intent parser regarding the user's voice request.
        """
        dialog = None
        gui = None

        self.log.info("request data: %s", request.data.keys())
        response = Response(self.config_core, self.location_regex_path)
        try:
            response.build_current_time_response(request.data["utterance"])
        except LocationNotFoundError:
            dialog, gui = self._handle_location_not_found(response)
        else:
            dialog, gui = self._respond(response)

        return dialog, gui

    def _handle_location_not_found(self, response: Response):
        """User requested time in a city not recognized by a Geolocation API call.

        Args:
            response: object used to formulate the response
        """
        dialog_data = dict(location=response.requested_location)
        dialog = ("location-not-found", dialog_data)
        gui = None

        return dialog, gui

    def _respond(self, response: Response):
        """Speak and display the response to the user's request.

        Args:
            response: object used to formulate the response
        """
        dialog = (response.dialog_name, response.dialog_data)
        gui = (
            "time-scalable.qml",
            {"timeString": get_display_time(response.date_time, self.config_core)},
        )

        return dialog, gui

    def load_regex_files(self):
        """Skip this logic to handle the location regular expression in the skill.

        See note in module-level docstring.
        """
        pass


def create_skill(skill_id: str):
    """Boilerplate code used to load the skill."""
    return TimeSkill(skill_id=skill_id)
