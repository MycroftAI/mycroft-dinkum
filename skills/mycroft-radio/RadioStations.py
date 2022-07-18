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
from random import randrange

import requests


def sort_on_vpc(k):
    return k["votes_plus_clicks"]


def sort_on_confidence(k):
    return k["confidence"]


class RadioStations:
    def __init__(self):
        self.index = 0
        self.blacklist = [
            "icecast",
        ]
        self.media_verbs = ["play", "listen", "turn on", "start"]
        self.noise_words = ["on", "to", "the", "music", "station", "channel", "radio"]
        self.search_limit = 1000

        self.generic_search_terms = [
            "jazz",
            "rock",
            "classical",
            "easy listening",
            "ska",
            "fusion",
            "punk",
            "rockabily",
            "metal",
            "bluegrass",
            "country",
        ]
        self.channel_index = 0
        self.last_search_terms = self.generic_search_terms[self.channel_index]
        self.stations = self.get_stations(self.last_search_terms)
        self.original_utterance = ""

    def find_mime_type(self, url: str) -> str:
        """Determine the mime type of a file at the given url.
        Args:
            url: remote url to check
        Returns:
            Mime type - defaults to 'audio/mpeg'
        """
        mime = "audio/mpeg"
        response = requests.Session().head(url, allow_redirects=True)
        if 200 <= response.status_code < 300:
            mime = response.headers["content-type"]
        return mime

    def clean_sentence(self, sentence):
        sentence = sentence.lower()
        sa = sentence.split(" ")
        vrb = sa[0].lower()
        if vrb in self.media_verbs:
            sentence = sentence[len(vrb) :]

        sa = sentence.split(" ")
        final_sentence = ""
        for wrd in sa:
            if wrd not in self.noise_words:
                final_sentence += " " + wrd

        return final_sentence.strip()

    def domain_is_unique(self, stream_uri, stations):
        return True

    def blacklisted(self, stream_uri):
        for bl in self.blacklist:
            if bl in stream_uri:
                return True
        return False

    def _search(self, srch_term, limit):
        uri = (
            "https://de1.api.radio-browser.info/json/stations/search?limit=%s&hidebroken=true&order=clickcount&reverse=true&tagList="
            % (limit,)
        )
        query = srch_term.replace(" ", "+")
        uri += query
        print("\n\n%s\n\n" % (uri,))
        res = requests.get(uri)
        if res:
            return res.json()

        return []

    def confidence(self, phrase, station):
        # TODO this needs to be shared between radio
        # and music (probably all common plays) BUT I don't know if I want it
        # to be the one in common play. we will see.
        phrase = phrase.lower()
        name = station["name"]
        name = name.replace("\n", " ")
        name = name.lower()
        tags = station.get("tags", [])
        if type(tags) is not list:
            tags = tags.split(",")
        confidence = 0.0
        if phrase in name:
            confidence += 0.1
        for tag in tags:
            tag = tag.lower()
            if phrase in tag:
                confidence += 0.01
            if phrase == tag:
                confidence += 0.1

        confidence = min(confidence, 1.0)
        return confidence

    def search(self, sentence, limit):
        unique_stations = {}
        self.original_utterance = sentence
        self.last_search_terms = self.clean_sentence(sentence)
        if self.last_search_terms == "":
            # if search terms after clean are null it was most
            # probably something like 'play music' or 'play
            # radio' so we will just select a random genre
            self.channel_index = randrange(len(self.generic_search_terms) - 1)
            self.last_search_terms = self.generic_search_terms[self.channel_index]

        stations = self._search(self.last_search_terms, limit)

        # whack dupes, favor match confidence
        for station in stations:
            station_name = station.get("name", "")
            station_name = station_name.replace("\n", " ")
            stream_uri = station.get("url_resolved", "")
            if stream_uri != "" and not self.blacklisted(stream_uri):
                if station_name in unique_stations:
                    if (
                        self.confidence(self.original_utterance, station)
                        > unique_stations[station_name]["confidence"]
                    ):
                        station["confidence"] = self.confidence(
                            self.original_utterance, station
                        )
                        unique_stations[station_name] = station
                else:
                    if self.domain_is_unique(stream_uri, stations):
                        station["confidence"] = self.confidence(
                            self.original_utterance, station
                        )
                        unique_stations[station_name] = station

        res = []
        for station in unique_stations:
            votes_plus_clicks = 0
            votes_plus_clicks += int(unique_stations[station].get("votes", 0))
            votes_plus_clicks += int(unique_stations[station].get("clickcount", 0))
            unique_stations[station]["votes_plus_clicks"] = votes_plus_clicks

            res.append(unique_stations[station])

        # res.sort(key=sort_on_vpc, reverse=True)
        res.sort(key=sort_on_confidence, reverse=True)

        return res

    def convert_array_to_dict(self, stations):
        new_dict = {}
        for station in stations:
            uri = station.get("url_resolved", "")
            if uri != "":
                votes_plus_clicks = int(station.get("votes", 0)) + int(
                    station.get("clickcount", 0)
                )
                new_dict[uri] = {
                    "name": station.get("name", "").replace("\n", ""),
                    "url_resolved": uri,
                    "home": station.get("homepage", ""),
                    "tags": station.get("tags", ""),
                    "country": station.get("country", ""),
                    "countrycode": station.get("countrycode", ""),
                    "votes": station.get("votes", ""),
                    "clickcount": station.get("clickcount", ""),
                    "votes_plus_clicks": votes_plus_clicks,
                }
        return new_dict

    def get_stations(self, utterance):
        self.stations = self.search(utterance, self.search_limit)
        self.index = 0

    def get_station_count(self):
        return len(self.stations)

    def get_station_index(self):
        return self.index

    def get_current_station(self):
        if len(self.stations) > 0:
            if self.index > len(self.stations):
                # this covers up a bug
                self.index = 0
            return self.stations[self.index]
        return None

    def get_next_station(self):
        if self.index == len(self.stations):
            self.index = 0
        else:
            self.index += 1
        return self.get_current_station()

    def get_previous_station(self):
        if self.index == 0:
            self.index = len(self.stations) - 1
        else:
            self.index -= 1
        return self.get_current_station()

    def get_next_channel(self):
        if self.channel_index == len(self.generic_search_terms) - 1:
            self.channel_index = 0
        else:
            self.channel_index += 1
        self.index = 0
        self.get_stations(self.generic_search_terms[self.channel_index])
        return self.generic_search_terms[self.channel_index]

    def get_previous_channel(self):
        if self.channel_index == 0:
            self.channel_index = len(self.generic_search_terms) - 1
        else:
            self.channel_index -= 1
        self.index = 0
        self.get_stations(self.generic_search_terms[self.channel_index])
        return self.generic_search_terms[self.channel_index]
