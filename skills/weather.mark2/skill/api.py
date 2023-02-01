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
"""Call the Open Weather Map One Call API through Selene.

The One Call API provides current weather, 48 hourly forecasts, 7 daily forecasts
and weather alert data all in a single API call.  The endpoint is passed a
latitude and longitude from either the user's configuration or a requested
location.

It also supports returning values in the measurement system (Metric/Imperial)
provided, precluding us from having to do the conversions.

"""
import base64
import json
import requests

from mycroft.api import Api
from mycroft.util.log import LOG
from mycroft.configuration import Configuration

from .weather import WeatherReport

OPEN_WEATHER_MAP_LANGUAGES = (
    "af",
    "al",
    "ar",
    "bg",
    "ca",
    "cz",
    "da",
    "de",
    "el",
    "en",
    "es",
    "eu",
    "fa",
    "fi",
    "fr",
    "gl",
    "he",
    "hi",
    "hr",
    "hu",
    "id",
    "it",
    "ja",
    "kr",
    "la",
    "lt",
    "mk",
    "nl",
    "no",
    "pl",
    "pt",
    "pt_br",
    "ro",
    "ru",
    "se",
    "sk",
    "sl",
    "sp",
    "sr",
    "sv",
    "th",
    "tr",
    "ua",
    "uk",
    "vi",
    "zh_cn",
    "zh_tw",
    "zu",
)


def owm_language(lang: str):
    """
    OWM supports 31 languages, see https://openweathermap.org/current#multi

    Convert Mycroft's language code to OpenWeatherMap's, if missing use english.

    Args:
        language_config: The Mycroft language code.
    """
    special_cases = {"cs": "cz", "ko": "kr", "lv": "la"}
    lang_primary, lang_subtag = lang.split("-")
    if lang.replace("-", "_") in OPEN_WEATHER_MAP_LANGUAGES:
        return lang.replace("-", "_")
    if lang_primary in OPEN_WEATHER_MAP_LANGUAGES:
        return lang_primary
    if lang_subtag in OPEN_WEATHER_MAP_LANGUAGES:
        return lang_subtag
    if lang_primary in special_cases:
        return special_cases[lang_primary]
    return "en"


class OpenWeatherMapApi(Api):
    """Use Open Weather Map's One Call API to retrieve weather information"""

    def __init__(self):
        super().__init__(path="owm")

    def get_weather_for_coordinates(
        self, temperature_units: str, latitude: float, longitude: float, lang: str
    ) -> WeatherReport:
        """Issue an API call and map the return value into a weather report

        Args:
            measurement_system: Metric or Imperial measurement units
            latitude: the geologic latitude of the weather location
            longitude: the geologic longitude of the weather location
        """
        # The api uses 'imperial' and 'metric' for units, but we want
        # to use 'fahrenheit' and 'celsius' when the unit names are spoken.
        # To avoid confusion with two attributes having two different
        # semantically identical (for our purposes) values, the attr
        # we use outside of this method is 'fahrenheit'/'celsius'. Here
        # we will translate that to conform with the api.
        if temperature_units == "fahrenheit":
            measurement_system = "imperial"
        else:
            measurement_system = "metric"
        query_parameters = dict(
            exclude="minutely",
            lang=owm_language(lang),
            lat=latitude,
            lon=longitude,
            units=measurement_system,
        )
        path = "/onecall"
        api_request = dict(path="/onecall", query=query_parameters)
        try:
            response = self.request(api_request)
            local_weather = WeatherReport(response)
        except Exception:
            # For whatever reason, we didn't get back a usable response.
            # This is a direct attempt to hit the api as fallback.
            weather_config = Configuration.get().get("openweathermap")
            # Yeah we know...
            default_yek = base64.b64decode(b'OWU0NzdkMDk0YmYxOWFiMDE4NzFjOTIwZDI3ZGJiODg=')
            owm_key = weather_config.get("key", default_yek.decode("utf-8"))
            owm_url = weather_config["url"]

            query_parameters["APPID"] = owm_key
            # Call will look like this: "https://api.openweathermap.org/data/2.5/onecall?exclude=minutely&lang=en&lat=37.9577&lon=-121.29078&units=imperial&APPID={query_parameters['APPID']}"
            response = requests.get(owm_url + "/" + path, params=query_parameters)
            decoded = json.loads(response.content.decode("utf-8"))
            local_weather = WeatherReport(decoded)

        return local_weather
