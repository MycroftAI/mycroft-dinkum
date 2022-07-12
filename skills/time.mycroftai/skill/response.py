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
"""Determine the response to a time skill request."""
from datetime import datetime

import pytz

from mycroft.util.format import nice_time
from mycroft.util.log import LOG
from mycroft.util.format import nice_duration
from mycroft.util.parse import normalize
from mycroft.util.time import now_local
from .regex import find_in_utterance
from .util import (
    get_datetime_from_utterance,
    get_duration_from_utterance,
    get_geolocation,
)

ONE_HOUR = 3600


class Response:
    """Determine the response to a time skill request."""

    def __init__(self, core_config, location_regex_path):
        """Constructor.

        Args:
            core_config: Mycroft core configuration values.
            location_regex_path: Absolute path to the location regular expression file.
        """
        self.location_regex_path = location_regex_path
        self.time_format_24_hour = core_config.get("time_format") == "full"
        self.country_name_config = core_config["location"]["city"]["state"]["country"][
            "name"
        ]
        self.geolocation = None
        self.date_time = None
        self.dialog_name = None
        self.dialog_data = None
        self.speak_am_pm = False
        self.requested_location = None

    def build_current_time_response(self, utterance):
        """Build a response to a request for the current time.

        Time can be requested locally or in a specific city.

        Args:
            utterance: The words that comprise the user's request.
        """
        self.requested_location = find_in_utterance(utterance, self.location_regex_path)
        self._get_geolocation()
        self.date_time = self._get_current_datetime()
        self.speak_am_pm = not self.time_format_24_hour and self.geolocation is not None
        self.dialog_data = dict(time=self._get_speakable_time())
        if self.geolocation is None:
            self.dialog_name = "time-current-local"
        else:
            self.dialog_name = "time-current-location"
            self.dialog_data.update(location=self.get_display_location())

    def build_future_time_response(self, utterance):
        """Build a response to a request for a time in the future.

        Time can be requested locally or in a specific city.

        Args:
            utterance: The words that comprise the user's request.
        """
        utterance = normalize(utterance.lower())
        current_time_offset = get_duration_from_utterance(utterance)
        self.date_time, remaining_utterance = get_datetime_from_utterance(utterance)
        if self.date_time is not None:
            self.requested_location = find_in_utterance(
                remaining_utterance, self.location_regex_path
            )
            self._get_geolocation()
            if self.geolocation is not None:
                tz_info = pytz.timezone(self.geolocation["timezone"])
                self.date_time = self.date_time.astimezone(tz_info)
            self.speak_am_pm = True
            self.dialog_data = dict(
                time=self._get_speakable_time(),
                duration=nice_duration(current_time_offset),
            )
            if self.geolocation is None:
                self.dialog_name = "time-future-local"
            else:
                self.dialog_name = "time-future-location"
                self.dialog_data.update(location=self.get_display_location())

    # TODO: abstract out into a skill library
    def _get_geolocation(self):
        """Retrieve geographical data for a city from the Selene Geolocation API."""
        if self.requested_location is None:
            LOG.info("No location found in request")
        else:
            LOG.info("Location found in request: " + self.requested_location)
            self.geolocation = get_geolocation(self.requested_location)

    def _get_speakable_time(self) -> str:
        """Convert a datetime object into a string that can be passed to TTS.

        Returns:
            The words to be spoken in response to the time request.
        """
        speakable_time = nice_time(
            self.date_time,
            speech=True,
            use_24hour=self.time_format_24_hour,
            use_ampm=self.speak_am_pm,
        )
        # HACK: Mimic 2 has a bug with saying "AM".  Work around it for now.
        if self.speak_am_pm:
            speakable_time = speakable_time.replace("AM", "A.M.")

        return speakable_time

    def _get_current_datetime(self) -> datetime:
        """Determine the current datetime for the user's locale or a specified city.

        Returns:
            The current date and time to satisfy the request.
        """
        if self.geolocation is None:
            current_datetime = now_local()
        else:
            tz_info = pytz.timezone(self.geolocation["timezone"])
            current_datetime = now_local(tz=tz_info)

        return current_datetime

    # TODO: abstract out into a skill library
    def get_display_location(self) -> str:
        """Build a string representing the location of the weather for display on GUI

        If the geolocation is in the same country as that in the device configuration,
        the return value will be city and region.  A specified location in a different
        country will result in a return value of city and country.

        Returns:
            The weather location to be displayed on the GUI
        """
        display_location = self.geolocation["city"] + ", "
        if self.geolocation["country"] == self.country_name_config:
            display_location += self.geolocation["region"]
        else:
            display_location += self.geolocation["country"]

        return display_location
