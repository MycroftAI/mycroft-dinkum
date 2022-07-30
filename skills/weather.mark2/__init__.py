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
"""Mycroft skill for communicating weather information

This skill uses the Open Weather Map One Call API to retrieve weather data
from around the globe (https://openweathermap.org/api/one-call-api).  It
proxies its calls to the API through Mycroft's officially supported API,
Selene.  The Selene API is also used to get geographical information about the
city name provided in the request.
"""
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import List, Tuple

from mycroft.messagebus.message import Message
from mycroft.skills import MycroftSkill, intent_handler
from mycroft.skills.intent_service import AdaptIntent
from mycroft.util.parse import extract_number
from requests import HTTPError

from .skill import (
    DAILY,
    HOURLY,
    CurrentDialog,
    DailyDialog,
    DailyWeather,
    HourlyDialog,
    LocationNotFoundError,
    OpenWeatherMapApi,
    WeatherConfig,
    WeatherDialog,
    WeatherIntent,
    WeatherReport,
    WeeklyDialog,
    get_dialog_for_timeframe,
)

# TODO: VK Failures
#   Locations: Washington, D.C.
#
# TODO: Intent failures
#   Later weather: only the word "later" in the vocab file works all others
#       invoke datetime skill

TWELVE_HOUR = "half"


class WeatherSkill(MycroftSkill):
    """Main skill code for the weather skill."""

    def __init__(self):
        super().__init__("WeatherSkill")
        self.weather_api = OpenWeatherMapApi()
        self.gui_image_directory = Path(self.root_dir).joinpath("ui")
        self.weather_config = None

    def initialize(self):
        """Do these things after the skill is loaded."""
        self.weather_config = WeatherConfig(self.config_core, self.settings)
        self.add_event(
            "skill.weather.request-local-forecast", self.handle_get_local_forecast
        )

    def handle_get_local_forecast(self, _):
        """Handles a message bus command requesting current local weather information.

        Such a request will typically come from a domain external to this skill that
        requires weather information but should not go through the intent system
        to get it.
        """
        system_unit = self.config_core.get("system_unit")
        try:
            weather = self.weather_api.get_weather_for_coordinates(
                system_unit,
                self.weather_config.latitude,
                self.weather_config.longitude,
                self.lang,
            )
        except Exception:
            self.log.exception("Unexpected error getting weather.")
            self.bus.emit(Message("skill.weather.local-forecast-failure."))
        else:
            self._emit_local_weather_response(weather)

    def _emit_local_weather_response(self, weather):
        """Emits an event indicating that the request for local weather was satisfied.

        Responds to the command for local weather retrieval.
        """
        image_path = self.gui_image_directory.joinpath(weather.current.condition.image)
        weather_condition_url = "file://" + str(image_path)
        event_data = dict(
            temperature=weather.current.temperature,
            weather_condition=weather_condition_url,
        )
        event = Message("skill.weather.local-forecast-obtained", data=event_data)
        self.bus.emit(event)

    @intent_handler(
        AdaptIntent()
        .optionally("query")
        .one_of("weather", "forecast")
        .optionally("location")
        .optionally("today")
    )
    def handle_current_weather(self, message: Message):
        """Handle current weather requests such as: what is the weather like?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_current_weather(message)
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .require("query")
        .require("like")
        .require("outside")
        .optionally("location")
        .optionally("today")
    )
    def handle_like_outside(self, message: Message):
        """Handle current weather requests such as: what's it like outside?

        Args:
            message: Message Bus event information from the intent parser
        """
        return self.handle_current_weather(message)

    @intent_handler(
        AdaptIntent()
        .optionally("query")
        .one_of("weather", "forecast")
        .require("number-days")
        .optionally("location")
    )
    def handle_number_days_forecast(self, message: Message):
        """Handle multiple day forecast without specified location.

        Examples:
            "What is the 3 day forecast?"
            "What is the weather forecast?"

        Args:
            message: Message Bus event information from the intent parser
        """
        if self.voc_match(message.data["utterance"], "couple"):
            days = 2
        elif self.voc_match(message.data["utterance"], "few"):
            days = 3
        else:
            # Some STT engines hyphenate the day count (i.e. 3-day).  This is not
            # handled by extract_number() so remove the hyphen if it is there.
            utterance = message.data["utterance"].replace("-day", " day")
            days = int(extract_number(utterance))

        dialog, gui = self._report_multi_day_forecast(message, days)
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .optionally("query")
        .one_of("weather", "forecast")
        .require("relative-day")
        .optionally("location")
    )
    def handle_one_day_forecast(self, message):
        """Handle forecast for a single day.

        Examples:
            "What is the weather forecast tomorrow?"
            "What is the weather forecast on Tuesday in Baltimore?"

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_one_day_forecast(message)
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .require("query")
        .require("weather")
        .require("later")
        .optionally("location")
        .optionally("today")
    )
    def handle_weather_later(self, message: Message):
        """Handle future weather requests such as: what's the weather later?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_one_hour_weather(message)
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .optionally("query")
        .one_of("weather", "forecast")
        .require("relative-time")
        .optionally("relative-day")
        .optionally("location")
    )
    def handle_weather_at_time(self, message: Message):
        """Handle future weather requests such as: what's the weather tonight?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_one_hour_weather(message)
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .require("query")
        .one_of("weather", "forecast")
        .require("weekend")
        .optionally("location")
    )
    def handle_weekend_forecast(self, message: Message):
        """Handle requests for the weekend forecast.

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_weekend_forecast(message)
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .optionally("query")
        .one_of("weather", "forecast")
        .require("week")
        .optionally("location")
    )
    def handle_week_weather(self, message: Message):
        """Handle weather for week (i.e. seven days).

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_week_summary(message)
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .optionally("query")
        .require("temperature")
        .optionally("location")
        .optionally("unit")
        .optionally("today")
        .optionally("now")
    )
    def handle_current_temperature(self, message: Message):
        """Handle requests for current temperature.

        Examples:
            "What is the temperature in Celsius?"
            "What is the temperature in Baltimore now?"

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_temperature(message, temperature_type="current")
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .optionally("query")
        .require("temperature")
        .require("relative-day")
        .optionally("location")
        .optionally("unit")
    )
    def handle_daily_temperature(self, message: Message):
        """Handle simple requests for current temperature.

        Examples: "What is the temperature?"

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_temperature(message, temperature_type="current")
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .optionally("query")
        .require("temperature")
        .require("relative-time")
        .optionally("relative-day")
        .optionally("location")
    )
    def handle_hourly_temperature(self, message: Message):
        """Handle requests for current temperature at a relative time.

        Examples:
            "What is the temperature tonight?"
            "What is the temperature tomorrow morning?"

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_temperature(message)
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .optionally("query")
        .require("high")
        .optionally("temperature")
        .optionally("location")
        .optionally("unit")
        .optionally("relative-day")
        .optionally("now")
        .optionally("today")
    )
    def handle_high_temperature(self, message: Message):
        """Handle a request for the high temperature.

        Examples:
            "What is the high temperature tomorrow?"
            "What is the high temperature in London on Tuesday?"

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_temperature(message, temperature_type="high")
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .optionally("query")
        .require("low")
        .optionally("temperature")
        .optionally("location")
        .optionally("unit")
        .optionally("relative-day")
        .optionally("now")
        .optionally("today")
    )
    def handle_low_temperature(self, message: Message):
        """Handle a request for the high temperature.

        Examples:
            "What is the high temperature tomorrow?"
            "What is the high temperature in London on Tuesday?"

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_temperature(message, temperature_type="low")
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .require("confirm-query-current")
        .one_of("hot", "cold")
        .optionally("location")
        .optionally("today")
    )
    def handle_is_it_hot(self, message: Message):
        """Handler for temperature requests such as: is it going to be hot today?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_temperature(message, "current")
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .optionally("query")
        .one_of("hot", "cold")
        .require("confirm-query")
        .optionally("location")
        .optionally("relative-day")
        .optionally("today")
    )
    def handle_how_hot_or_cold(self, message):
        """Handler for temperature requests such as: how cold will it be today?

        Args:
            message: Message Bus event information from the intent parser
        """
        utterance = message.data["utterance"]
        temperature_type = "high" if self.voc_match(utterance, "hot") else "low"
        dialog, gui = self._report_temperature(message, temperature_type)
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .require("confirm-query")
        .require("windy")
        .optionally("location")
        .optionally("relative-day")
    )
    def handle_is_it_windy(self, message: Message):
        """Handler for weather requests such as: is it windy today?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_wind(message)
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .require("how")
        .require("windy")
        .optionally("confirm-query")
        .optionally("relative-day")
        .optionally("location")
    )
    def handle_windy(self, message):
        """Handler for weather requests such as: how windy is it?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_wind(message)
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent().require("confirm-query").require("snow").optionally("location")
    )
    def handle_is_it_snowing(self, message: Message):
        """Handler for weather requests such as: is it snowing today?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_weather_condition(message, "snow")
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent().require("confirm-query").require("clear").optionally("location")
    )
    def handle_is_it_clear(self, message: Message):
        """Handler for weather requests such as: is the sky clear today?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_weather_condition(message, "clear")
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .require("confirm-query")
        .require("clouds")
        .optionally("location")
        .optionally("relative-time")
    )
    def handle_is_it_cloudy(self, message: Message):
        """Handler for weather requests such as: is it cloudy today?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_weather_condition(message, "clouds")
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent().require("confirm-query").require("fog").optionally("location")
    )
    def handle_is_it_foggy(self, message: Message):
        """Handler for weather requests such as: is it foggy today?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_weather_condition(message, "fog")
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent().require("confirm-query").require("rain").optionally("location")
    )
    def handle_is_it_raining(self, message: Message):
        """Handler for weather requests such as: is it raining today?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_weather_condition(message, "rain")
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler("do-i-need-an-umbrella.intent")
    def handle_need_umbrella(self, message: Message):
        """Handler for weather requests such as: will I need an umbrella today?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_weather_condition(message, "rain")
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .require("confirm-query")
        .require("thunderstorm")
        .optionally("location")
    )
    def handle_is_it_storming(self, message: Message):
        """Handler for weather requests such as:  is it storming today?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog, gui = self._report_weather_condition(message, "thunderstorm")
        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .require("when")
        .optionally("next")
        .require("precipitation")
        .optionally("location")
    )
    def handle_next_precipitation(self, message: Message):
        """Handler for weather requests such as: when will it rain next?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog = None
        intent_data, dialog = self._get_intent_data(message)
        if intent_data is not None:
            weather, dialog = self._get_weather(intent_data)
            if weather is not None:
                forecast, timeframe = weather.get_next_precipitation(intent_data)
                intent_data.timeframe = timeframe
                dialog_args = intent_data, self.weather_config, forecast
                precipitation_dialog = get_dialog_for_timeframe(
                    intent_data.timeframe, dialog_args
                )
                precipitation_dialog.build_next_precipitation_dialog()
                spoken_percentage = self.translate(
                    "percentage-number",
                    data=dict(number=precipitation_dialog.data["percent"]),
                )
                precipitation_dialog.data.update(percent=spoken_percentage)
                dialog = (precipitation_dialog.name, precipitation_dialog.data)

        return self.end_session(dialog=dialog)

    @intent_handler(
        AdaptIntent()
        .require("query")
        .require("humidity")
        .optionally("relative-day")
        .optionally("location")
    )
    def handle_humidity(self, message: Message):
        """Handler for weather requests such as: how humid is it?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog = None
        intent_data, dialog = self._get_intent_data(message)
        if intent_data is not None:
            weather, dialog = self._get_weather(intent_data)
            if weather is not None:
                intent_weather = weather.get_weather_for_intent(intent_data)
                dialog_args = intent_data, self.weather_config, intent_weather
                humidity_dialog = get_dialog_for_timeframe(
                    intent_data.timeframe, dialog_args
                )
                humidity_dialog.build_humidity_dialog()
                humidity_dialog.data.update(
                    percent=self.translate(
                        "percentage-number",
                        data=dict(number=humidity_dialog.data["percent"]),
                    )
                )
                dialog = (humidity_dialog.name, humidity_dialog.data)

        return self.end_session(dialog=dialog)

    @intent_handler(
        AdaptIntent()
        .one_of("query", "when")
        .optionally("location")
        .require("sunrise")
        .optionally("today")
        .optionally("relative-day")
    )
    def handle_sunrise(self, message: Message):
        """Handler for weather requests such as: when is the sunrise?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog = None
        gui = None

        intent_data, dialog = self._get_intent_data(message)
        if intent_data is not None:
            weather, dialog = self._get_weather(intent_data)
            if weather is not None:
                intent_weather = weather.get_weather_for_intent(intent_data)
                dialog_args = intent_data, self.weather_config, intent_weather
                sunrise_dialog = get_dialog_for_timeframe(
                    intent_data.timeframe, dialog_args
                )
                sunrise_dialog.build_sunrise_dialog()
                dialog = (sunrise_dialog.name, sunrise_dialog.data)

                weather_location = self._build_display_location(intent_data)
                gui = self._display_sunrise_sunset(intent_weather, weather_location)

        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent()
        .one_of("query", "when")
        .require("sunset")
        .optionally("location")
        .optionally("today")
        .optionally("relative-day")
    )
    def handle_sunset(self, message: Message):
        """Handler for weather requests such as: when is the sunset?

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog = None
        gui = None

        intent_data, dialog = self._get_intent_data(message)
        if intent_data is not None:
            weather, dialog = self._get_weather(intent_data)
            if weather is not None:
                intent_weather = weather.get_weather_for_intent(intent_data)
                dialog_args = intent_data, self.weather_config, intent_weather
                sunset_dialog = get_dialog_for_timeframe(
                    intent_data.timeframe, dialog_args
                )
                sunset_dialog.build_sunset_dialog()
                dialog = (sunset_dialog.name, sunset_dialog.data)

                weather_location = self._build_display_location(intent_data)
                gui = self._display_sunrise_sunset(intent_weather, weather_location)

        return self.end_session(dialog=dialog, gui=gui)

    def _display_sunrise_sunset(self, forecast: DailyWeather, weather_location: str):
        """Display the sunrise and sunset on a Mark II device using a grid layout.

        Args:
            forecast: daily forecasts to display
            weather_location: the geographical location of the weather
        """
        gui_page = "sunrise_sunset_mark_ii.qml"
        gui_data = {
            "weatherDate": forecast.date_time.strftime("%A %b %d"),
            "weatherLocation": weather_location,
            "sunrise": self._format_sunrise_sunset_time(forecast.sunrise),
            "sunset": self._format_sunrise_sunset_time(forecast.sunset),
            "ampm": self.config_core["time_format"] == TWELVE_HOUR,
        }

        return gui_page, gui_data

    def _format_sunrise_sunset_time(self, date_time: datetime) -> str:
        """Format a the sunrise or sunset datetime into a string for GUI display.

        The datetime builtin returns hour in two character format.  Remove the
        leading zero when present.

        Args:
            date_time: the sunrise or sunset

        Returns:
            the value to display on the screen
        """
        if self.config_core["time_format"] == TWELVE_HOUR:
            display_time = date_time.strftime("%I:%M")
            if display_time.startswith("0"):
                display_time = display_time[1:]
        else:
            display_time = date_time.strftime("%H:%M")

        return display_time

    def _report_current_weather(self, message: Message):
        """Handles all requests for current weather conditions.

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog = None
        gui = None

        intent_data, dialog = self._get_intent_data(message)
        if intent_data is not None:
            weather, dialog = self._get_weather(intent_data)
            if weather is not None:
                weather_location = self._build_display_location(intent_data)
                gui = [
                    self._display_current_conditions(weather, weather_location),
                    self._display_more_current_conditions(weather, weather_location),
                ]

                weather_dialog = CurrentDialog(
                    intent_data, self.weather_config, weather.current
                )
                weather_dialog.build_weather_dialog()
                high_low_dialog = CurrentDialog(
                    intent_data, self.weather_config, weather.current
                )
                high_low_dialog.build_high_low_temperature_dialog()

                dialog = [
                    (weather_dialog.name, weather_dialog.data),
                    (high_low_dialog.name, high_low_dialog.data),
                ]

        return dialog, gui

    def _display_current_conditions(
        self, weather: WeatherReport, weather_location: str
    ):
        """Display current weather conditions on a screen.

        This is the first screen that shows.  Others will follow.

        Args:
            weather: current weather conditions from Open Weather Maps
            weather_location: the geographical location of the reported weather
        """
        gui_page = "current_1_mark_ii.qml"
        gui_data = {
            "currentTemperature": weather.current.temperature,
            "weatherCondition": weather.current.condition.image,
            "weatherLocation": weather_location,
            "highTemperature": weather.current.high_temperature,
            "lowTemperature": weather.current.low_temperature,
        }

        return gui_page, gui_data

    def _build_display_location(self, intent_data: WeatherIntent) -> str:
        """Build a string representing the location of the weather for display on GUI

        The return value will be the device's configured location if no location is
        specified in the intent.  If a location is specified, and it is in the same
        country as that in the device configuration, the return value will be city and
        region.  A specified location in a different country will result in a return
        value of city and country.

        Args:
            intent_data: information about the intent that was triggered

        Returns:
            The weather location to be displayed on the GUI
        """
        if intent_data.geolocation:
            location = [intent_data.geolocation["city"]]
            if intent_data.geolocation["country"] == self.weather_config.country:
                location.append(intent_data.geolocation["region"])
            else:
                location.append(intent_data.geolocation["country"])
        else:
            location = [self.weather_config.city, self.weather_config.state]

        return ", ".join(location)

    def _display_more_current_conditions(
        self, weather: WeatherReport, weather_location: str
    ):
        """Display current weather conditions on a device that supports a GUI.

        This is the second screen that shows for current weather.

        Args
            weather: current weather conditions from Open Weather Maps
            weather_location: geographical location of the reported weather
        """
        gui_page = "current_2_mark_ii.qml"
        gui_data = {
            "weatherLocation": weather_location,
            "windSpeed": weather.current.wind_speed,
            "humidity": weather.current.humidity,
        }

        return gui_page, gui_data

    def _report_one_hour_weather(self, message: Message):
        """Handles requests for a one hour forecast.

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog = None
        gui = None

        intent_data, dialog = self._get_intent_data(message)
        if intent_data is not None:
            weather, dialog = self._get_weather(intent_data)
            if weather is not None:
                try:
                    forecast = weather.get_forecast_for_hour(intent_data)
                except IndexError:
                    dialog = "forty-eight.hours.available"
                else:
                    hourly_dialog = HourlyDialog(
                        intent_data, self.weather_config, forecast
                    )
                    hourly_dialog.build_weather_dialog()
                    dialog = (hourly_dialog.name, hourly_dialog.data)

        return dialog, gui

    def _display_hourly_forecast(self, weather: WeatherReport, weather_location: str):
        """Display hourly forecast on a device that supports the GUI.

        On the Mark II this screen is the final for current weather.  It can
        also be shown when the hourly forecast is requested.

        :param weather: hourly weather conditions from Open Weather Maps
        """
        hourly_forecast = []
        for hour_count, hourly in enumerate(weather.hourly):
            if not hour_count:
                continue
            if hour_count > 4:
                break
            if self.config_core["time_format"] == TWELVE_HOUR:
                # The datetime builtin returns hour in two character format.  Convert
                # to a integer and back again to remove the leading zero when present.
                hour = int(hourly.date_time.strftime("%I"))
                am_pm = hourly.date_time.strftime(" %p")
                formatted_time = str(hour) + am_pm
            else:
                formatted_time = hourly.date_time.strftime("%H:00")
            hourly_forecast.append(
                dict(
                    time=hourly.date_time.strftime(formatted_time),
                    precipitation=hourly.chance_of_precipitation,
                    temperature=hourly.temperature,
                    weatherCondition=hourly.condition.image,
                )
            )
        self.gui["weatherLocation"] = weather_location
        self.gui["hourlyForecast"] = dict(hours=hourly_forecast)
        self.gui.replace_page("hourly_mark_ii.qml")

    def _report_one_day_forecast(self, message: Message):
        """Handles all requests for a single day forecast.

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog = None
        gui = None

        intent_data = WeatherIntent(message, self.lang)
        weather, dialog = self._get_weather(intent_data)
        if weather is not None:
            forecast = weather.get_forecast_for_date(intent_data)
            forecast_dialogs = self._build_forecast_dialogs([forecast], intent_data)
            dialog = [(d.name, d.data) for d in forecast_dialogs]
            gui = self._display_one_day_mark_ii(forecast, intent_data)

        return dialog, gui

    def _display_one_day_mark_ii(
        self, forecast: DailyWeather, intent_data: WeatherIntent
    ):
        """Display the forecast for a single day on a Mark II.

        :param forecast: daily forecasts to display
        """
        gui_page = "single_day_mark_ii.qml"
        gui_data = {
            "weatherLocation": self._build_display_location(intent_data),
            "weatherCondition": forecast.condition.image,
            "weatherDate": forecast.date_time.strftime("%A %b %d"),
            "highTemperature": forecast.temperature.high,
            "lowTemperature": forecast.temperature.low,
            "chanceOfPrecipitation": str(forecast.chance_of_precipitation),
        }

        return gui_page, gui_data

    def _report_multi_day_forecast(self, message: Message, days: int):
        """Handles all requests for multiple day forecasts.

        :param message: Message Bus event information from the intent parser
        """
        dialog = None
        gui = None

        intent_data = WeatherIntent(message, self.lang)
        weather, dialog = self._get_weather(intent_data)
        if weather is not None:
            try:
                forecast = weather.get_forecast_for_multiple_days(days)
            except IndexError:
                dialog = "seven.days.available"
                forecast = weather.get_forecast_for_multiple_days(7)

            forecast_dialogs = self._build_forecast_dialogs(forecast, intent_data)
            dialog = [(d.name, d.data) for d in forecast_dialogs]
            gui = self._display_multi_day_forecast(forecast, intent_data)

        return dialog, gui

    def _report_weekend_forecast(self, message: Message):
        """Handles requests for a weekend forecast.

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog = None
        gui = None

        intent_data, dialog = self._get_intent_data(message)
        if intent_data is not None:
            weather, dialog = self._get_weather(intent_data)
            if weather is not None:
                forecast = weather.get_weekend_forecast()
                forecast_dialogs = self._build_forecast_dialogs(forecast, intent_data)
                dialog = [(d.name, d.data) for d in forecast_dialogs]
                gui = self._display_multi_day_forecast(forecast, intent_data)

        return dialog, gui

    def _build_forecast_dialogs(
        self, forecast: List[DailyWeather], intent_data: WeatherIntent
    ) -> List[DailyDialog]:
        """
        Build the dialogs for each of the forecast days being reported to the user.

        :param forecast: daily forecasts to report
        :param intent_data: information about the intent that was triggered
        :return: one DailyDialog instance for each day being reported.
        """
        dialogs = list()
        for forecast_day in forecast:
            dialog = DailyDialog(intent_data, self.weather_config, forecast_day)
            dialog.build_weather_dialog()
            dialogs.append(dialog)

        return dialogs

    def _report_week_summary(self, message: Message):
        """Summarize the week's weather rather than giving daily details.

        When the user requests the weather for the week, rather than give a daily
        forecast for seven days, summarize the weather conditions for the week.

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog = None
        gui = None

        intent_data = WeatherIntent(message, self.lang)
        weather, dialog = self._get_weather(intent_data)
        if weather is not None:
            forecast = weather.get_forecast_for_multiple_days(7)
            forecast_dialogs = self._build_weekly_condition_dialogs(
                forecast, intent_data
            )
            forecast_dialogs.append(
                self._build_weekly_temperature_dialog(forecast, intent_data)
            )
            dialog = [(d.name, d.data) for d in forecast_dialogs]
            gui = self._display_multi_day_forecast(forecast, intent_data)

        return dialog, gui

    def _build_weekly_condition_dialogs(
        self, forecast: List[DailyWeather], intent_data: WeatherIntent
    ) -> List[WeeklyDialog]:
        """Build the dialog communicating a weather condition on days it is forecasted.

        Args:
            forecast: seven day daily forecast
            intent_data: Parsed intent data

        Returns:
            List of dialogs for each condition expected in the coming week.
        """
        dialogs = list()
        conditions = set([daily.condition.category for daily in forecast])
        for condition in conditions:
            dialog = WeeklyDialog(intent_data, self.weather_config, forecast)
            dialog.build_condition_dialog(condition=condition)
            dialogs.append(dialog)

        return dialogs

    def _build_weekly_temperature_dialog(
        self, forecast: List[DailyWeather], intent_data: WeatherIntent
    ) -> WeeklyDialog:
        """Build the dialog communicating the forecasted range of temperatures.

        Args:
            forecast: seven day daily forecast
            intent_data: Parsed intent data

        Returns:
            Dialog for the temperature ranges over the coming week.
        """
        dialog = WeeklyDialog(intent_data, self.weather_config, forecast)
        dialog.build_temperature_dialog()

        return dialog

    def _display_multi_day_forecast(
        self, forecast: List[DailyWeather], intent_data: WeatherIntent
    ):
        """Display daily forecast data on a Mark II.

        The Mark II supports displaying four days of a forecast at a time.

        Args:
            forecast: daily forecasts to display
            intent_data: Parsed intent data
        """
        gui_page = "daily_mark_ii.qml"
        daily_forecast = []
        for day in forecast:
            daily_forecast.append(
                dict(
                    weatherCondition=day.condition.image,
                    day=day.date_time.strftime("%a"),
                    highTemperature=day.temperature.high,
                    lowTemperature=day.temperature.low,
                )
            )

        gui_data = {
            "dailyForecast": dict(days=daily_forecast[:4]),
            "weatherLocation": self._build_display_location(intent_data),
        }

        return gui_page, gui_data

    def _report_temperature(self, message: Message, temperature_type: str = None):
        """Handles all requests for a temperature.

        Args:
            message: Message Bus event information from the intent parser
            temperature_type: current, high or low temperature
        """
        dialog = None
        gui = None

        intent_data, dialog = self._get_intent_data(message)
        if intent_data is not None:
            weather, dialog = self._get_weather(intent_data)
            if weather is not None:
                intent_weather = weather.get_weather_for_intent(intent_data)
                dialog_args = intent_data, self.weather_config, intent_weather
                temperature_dialog = get_dialog_for_timeframe(
                    intent_data.timeframe, dialog_args
                )
                temperature_dialog.build_temperature_dialog(temperature_type)
                dialog = (temperature_dialog.name, temperature_dialog.data)

        return dialog, gui

    def _report_weather_condition(self, message: Message, condition: str):
        """Handles all requests for a specific weather condition.

        Args:
            message: Message Bus event information from the intent parser
            condition: the weather condition specified by the user
        """
        dialog = None
        gui = None

        intent_data, dialog = self._get_intent_data(message)
        if intent_data is not None:
            weather, dialog = self._get_weather(intent_data)
            if weather is not None:
                intent_weather = weather.get_weather_for_intent(intent_data)
                condition_dialog = self._build_condition_dialog(
                    intent_weather, intent_data, condition
                )
                dialog = (condition_dialog.name, condition_dialog.data)
                self.log.debug(dialog)

        return dialog, gui

    def _build_condition_dialog(
        self, weather, intent_data: WeatherIntent, condition: str
    ):
        """Builds a dialog for the requested weather condition.

        Args:
            weather: Current, hourly or daily weather forecast
            intent_data: Parsed intent data
            condition: weather condition requested by the user
        """
        dialog_args = intent_data, self.weather_config, weather
        dialog = get_dialog_for_timeframe(intent_data.timeframe, dialog_args)
        intent_match = self.voc_match(weather.condition.category.lower(), condition)
        dialog.build_condition_dialog(intent_match)
        dialog.data.update(condition=self.translate(weather.condition.description))

        return dialog

    def _report_wind(self, message: Message):
        """Handles all requests for a wind conditions.

        Args:
            message: Message Bus event information from the intent parser
        """
        dialog = None
        gui = None

        intent_data, dialog = self._get_intent_data(message)
        if intent_data is not None:
            weather, dialog = self._get_weather(intent_data)
            if weather is not None:
                intent_weather = weather.get_weather_for_intent(intent_data)
                intent_weather.wind_direction = self.translate(
                    intent_weather.wind_direction
                )
                dialog_args = intent_data, self.weather_config, intent_weather
                wind_dialog = get_dialog_for_timeframe(
                    intent_data.timeframe, dialog_args
                )
                wind_dialog.build_wind_dialog()
                dialog = (wind_dialog.name, wind_dialog.data)

        return dialog, gui

    def _get_intent_data(self, message: Message) -> WeatherIntent:
        """Parse the intent data from the message into data used in the skill.

        Args:
            message: Message Bus event information from the intent parser

        Returns:
            parsed information about the intent
        """
        intent_data = None
        dialog = None
        try:
            intent_data = WeatherIntent(message, self.lang)
        except ValueError:
            dialog = "cant.get.forecast"
        else:
            if self.voc_match(intent_data.utterance, "relative-time"):
                intent_data.timeframe = HOURLY
            elif self.voc_match(intent_data.utterance, "later"):
                intent_data.timeframe = HOURLY
            elif self.voc_match(intent_data.utterance, "relative-day"):
                if not self.voc_match(intent_data.utterance, "today"):
                    intent_data.timeframe = DAILY

        return intent_data, dialog

    def _get_weather(self, intent_data: WeatherIntent) -> WeatherReport:
        """Call the Open Weather Map One Call API to get weather information

        Args:
            intent_data: Parsed intent data

        Returns:
            An object representing the data returned by the API
        """
        weather = None
        dialog = None
        if intent_data is not None:
            try:
                latitude, longitude = self._determine_weather_location(intent_data)
                weather = self.weather_api.get_weather_for_coordinates(
                    self.config_core.get("system_unit"), latitude, longitude, self.lang
                )
            except HTTPError as api_error:
                self.log.exception("Weather API failure")
                dialog = self._handle_api_error(api_error)
            except LocationNotFoundError:
                self.log.exception("City not found.")
                dialog = (
                    "location-not-found",
                    dict(location=intent_data.location),
                )
            except Exception:
                self.log.exception("Unexpected error retrieving weather")
                dialog = "cant-get-forecast"

        return weather, dialog

    def _handle_api_error(self, exception: HTTPError):
        """Communicate an error condition to the user.

        Args:
            exception: the HTTPError returned by the API call
        """
        dialog = None
        if exception.response.status_code == 401:
            self.bus.emit(Message("mycroft.not.paired"))
        else:
            dialog = "cant.get.forecast"

        return dialog

    def _determine_weather_location(
        self, intent_data: WeatherIntent
    ) -> Tuple[float, float]:
        """Determine latitude and longitude using the location data in the intent.

        Args:
            intent_data: Parsed intent data

        Returns
            latitude and longitude of the location
        """
        if intent_data.location is None:
            latitude = self.weather_config.latitude
            longitude = self.weather_config.longitude
        else:
            latitude = intent_data.geolocation["latitude"]
            longitude = intent_data.geolocation["longitude"]

        return latitude, longitude


def create_skill():
    """Boilerplate to invoke the weather skill."""
    return WeatherSkill()
