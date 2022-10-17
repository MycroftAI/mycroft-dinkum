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

"""
Mycroft Radio Skill Module

This plays radio stations sourced from Radio Browser
(https://www.radio-browser.info/). It can take an utterance
and tries to find a genre tag from the Radio Browser
service. If it finds one, it chooses a station to play
and streams it.

If no type of radio station is specified, it returns
a station based on a random choice weighted by the
station count of the tags plus some other things.
"""
import random
import re
from collections import namedtuple
from typing import Optional, Tuple

import requests
from mycroft.skills.common_play_skill import CommonPlaySkill
from pyradios.base_url import fetch_hosts

EXACT_MATCH_CONFIDENCE = 0.5
PARTIAL_MATCH_CONFIDENCE = 0.1


class GetHostError(Exception):
    """Can't find any hosts from pyradio"""

    pass


class GetGenreTagsError(Exception):
    """Can't get genre tags from Radio Browser"""

    pass


class MycroftRadio(CommonPlaySkill):
    """
    Mycroft Radio Skill.
    """

    def __init__(self, skill_id: str, utterance: str):
        super().__init__(skill_id=skill_id, name="Mycroft Radio Skill")
        self.station_index = 0
        self.blacklist = [
            "icecast",
        ]
        self.media_verbs = ["play", "listen", "turn on", "start"]
        self.stop_words = ["on", "to", "the", "music", "station", "channel", "radio"]
        self.genre_stop_words = [
            "radio",
            "station",
            "música",
            "estación",
        ]
        self.search_limit = 1000
        self.exact_genre_match = {}
        self.partial_genre_matches = []
        self.stations = []
        self.most_recent_genre_match = {}
        self.genre_index = 0
        try:
            self.base_urls = ["https://" + host + "/json/" for host in fetch_hosts()]
        except GetHostError as e:
            # TODO: Figure this out.
            pass
        if not self.base_urls:
            raise GetHostError
        self.base_url = random.choice(self.base_urls)
        try:
            self.genre_tags_response = self.query_server(
                "tags?order=stationcount&reverse=true&hidebroken=true&limit=10000"
            )
        except GetGenreTagsError as e:
            # TODO: Figure this out.
            pass
        if not self.genre_tags_response:
            raise GetGenreTagsError
        # There are many "genre" tags which are actually specific to one station.
        # First make a list of lists to simplify.
        self.genre_tags = [
            {
                "name": genre["name"].lower,
                "stationcount": genre["stationcount"],
                genre["rank"]: rank,
            }
            for rank, genre in enumerate(self.genre_tags_response)
            if genre["name"]
            and genre["stationcount"]
            and genre["stationcount"] > 0
            and genre["name"] not in self.genre_stop_words
        ]
        if not self.genre_tags:
            raise GetGenreTagsError

        self.language_code = None
        self.settings_change_callback = None

    def initialize(self):
        self.settings_change_callback = self.on_websettings_changed
        self.on_websettings_changed()

    def on_websettings_changed(self):
        """Callback triggered anytime Skill settings are modified on backend."""
        self.language_code = self.settings.get("language", "not_set")
        if self.language_code == "not_set":
            self.language_code = "en"

    def get_confidence(self, utterance: str) -> float:
        utterance = utterance.lower()
        self.exact_genre_match, self.partial_genre_matches = self.get_genre_matches(
            utterance
        )
        return min(
            (self.exact_genre_match * EXACT_MATCH_CONFIDENCE)
            + (len(self.partial_genre_matches) * PARTIAL_MATCH_CONFIDENCE),
            1,
        )

    def get_genre_matches(self, utterance: str) -> Optional[Tuple[dict, list]]:
        genre_term = self.extract_genre_from_utterance(utterance)
        if not genre_term:
            return None
        exact_genre_match = {}
        partial_genre_matches = []
        for genre_tag in self.genre_tags:
            if genre_term == genre_tag["name"] and not self.exact_genre_match:
                self.exact_genre_match = genre_tag
            elif genre_term in genre_tag["name"]:
                self.partial_genre_matches.append(genre_tag)
        return exact_genre_match, partial_genre_matches

    def extract_genre_from_utterance(self, utterance: str) -> str:
        words = utterance.split(" ")
        genre_term = ""
        direct_object = []
        if words[0] in self.media_verbs:
            direct_object = words[1:]
        for word in direct_object:
            if word not in self.stop_words:
                genre_term += " " + word
        return genre_term

    def get_language(self) -> str:
        if self.language_code:
            return self.language_code
        else:
            self.language_code = self.settings.get("language", "not_set")
        if self.language_code == "not_set":
            self.language_code = 'en'
        return self.language_code

    def get_radio_stations(self):
        language = self.get_language()
        endpoint = f"stations/search?language={language}&limit={self.search_limit}&hidebroken=true&order=clickcount&reverse=true&tagList="
        query = ""
        if self.exact_genre_match:
            self.most_recent_genre_match = self.exact_genre_match
            query = self.exact_genre_match["name"].replace(" ", "+")
        elif self.partial_genre_matches:
            self.most_recent_genre_match = self.partial_genre_matches[0]
            query = self.partial_genre_matches[0]["name"].replace(" ", "+")
        endpoint += query
        self.log.debug(f"ENDPOINT: {endpoint}")
        self.stations = self.query_server(endpoint)
        self.station_index = 0
        return self.stations[0]

    def get_next_station(self):
        self.station_index = wrap_around(
            self.station_index, self.stations, ascending=True
        )
        return self.stations[self.station_index]

    def get_previous_station(self):
        self.station_index = wrap_around(
            self.station_index, self.stations, ascending=False
        )
        return self.stations[self.station_index]

    def get_next_genre(self):
        self.genre_index = wrap_around(
            self.most_recent_genre_match["rank"], self.genre_tags, ascending=True
        )
        return self.genre_tags[self.genre_index]

    def get_previous_genre(self):
        self.genre_index = wrap_around(
            self.most_recent_genre_match["rank"], self.genre_tags, ascending=False
        )
        return self.genre_tags[self.genre_index]

    def query_server(self, endpoint):
        """
        Since we have a list of possible servers to hit,
        and since servers can be unresponsive sometimes, if we
        don't get a success code we will retry with 10 different
        servers before giving up.

        Returns: a decoded response object.
        """
        retries = 0
        while retries < 10:
            response = self._get_response(endpoint)
            if 200 <= response.status_code < 300:
                self.log.debug(
                    f"Successful response from RadioBrowser server: {self.base_url}"
                )
                return response.json()
            else:
                self.log.debug(
                    f"Unsuccessful response from RadioBrowser server: {self.base_url}"
                )
                self.base_url = random.choice(self.base_urls)
                self.log.debug(
                    f"Retrying request from next RadioBrowser server: {self.base_url}"
                )
                retries += 1


# Helper functions.


def wrap_around(index: int, collection: list, ascending: bool):
    if ascending:
        if index >= len(collection):
            index = 0
        else:
            index -= 1
    else:
        if index == 0:
            index = len(collection) - 1
        else:
            index -= 1
    return index


class RadioGenre:
    """
    Retrieves and manipulates all radio stations
    (i.e., servers) with a given genre tag.
    """


RadioStation = namedtuple(
    "RadioStation",
    [
        "changeuuid",
        "stationuuid",
        "name",
        "url",
        "url_resolved",
        "homepage",
        "favicon",
        "tags",
        "country",
        "countrycode",
        "state",
        "language",
        "languagecodes",
        "votes",
        "lastchangetime",
        "lastchangetime_iso8601",
        "codec",
        "bitrate",
        "hls",
        "lastcheckok",
        "lastchecktime",
        "lastchecktime_iso8601",
        "lastcheckoktime",
        "lastcheckoktime_iso8601",
        "lastlocalchecktime",
        "lastlocalchecktime_iso8601",
        "clicktimestamp",
        "clicktimestamp_iso8601",
        "clickcount",
        "clicktrend",
        "ssl_error",
        "geo_lat",
        "geo_long",
        "has_extended_info",
    ],
)


class RadioStation:
    def __init__(self):
        changeuuid
        stationuuid
        name
        url
        url_resolved
        homepage
        favicon
        tags
        country
        countrycode
        state
        language
        languagecodes
        votes
        lastchangetime
        lastchangetime_iso8601
        codec
        bitrate
        hls
        lastcheckok
        lastchecktime
        lastchecktime_iso8601
        lastcheckoktime
        lastcheckoktime_iso8601
        lastlocalchecktime
        lastlocalchecktime_iso8601
        clicktimestamp
        clicktimestamp_iso8601
        clickcount
        clicktrend
        ssl_error
        geo_lat
        geo_long
        has_extended_info
