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

import random
import requests

from mycroft.util.log import LOG

from pyradios.base_url import fetch_hosts


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

        self.base_urls = ["https://" + host + "/json/" for host in fetch_hosts()]
        self.base_url = random.choice(self.base_urls)
        LOG.debug(f"BASE URL CHOSEN: {self.base_url}")
        LOG.debug(f"NUMBER OF BASE URLS FOUND: {len(self.base_urls)}")
        self.genre_tags_response = self.query_server("tags?order=stationcount&reverse=true&hidebroken=true&limit=10000")
        if not self.genre_tags_response:
            # TODO: Figure out what to do if we can't get a server at all.
            pass

        # There are many "genre" tags which are actually specific to one station.
        # Since these aren't genres and they clutter things up, we'll
        # only take tags that have 2 or more.
        # First make a list of lists to simplify.
        self.genre_tags = [
            [genre.get("name", ""), genre.get("stationcount", "")] for genre in self.genre_tags_response
            if genre["stationcount"] and genre["stationcount"] > 2
        ]
        LOG.debug(f"{len(self.genre_tags_response)} genre tags returned.")
        LOG.debug(f"{len(self.genre_tags)} genre tags after filtering.")
        # Then split the lists. This will make things easier downstream
        # when we use station count to weight a random choice operation.
        self.genre_tags, self.genre_weights = map(list, zip(*self.genre_tags))
        LOG.debug(f"FIRST GENRE TAG IS {self.genre_tags[0]}")
        LOG.debug(f"FIRST GENRE WEIGHT IS {self.genre_weights[0]}")

        self.channel_index = 0
        # Default to using the genre tag with the most radio stations.
        # As of this comment it is "pop".
        self.last_search_terms = self.genre_tags[self.channel_index]
        LOG.debug(f"DEFAULT LAST SEARCH TERM: {self.last_search_terms}")
        self.genre_to_play = ""
        self.stations = self.get_stations(self.last_search_terms)
        # LOG.debug(f"SEARCH TERM RETURNS {len(self.stations)} stations")
        LOG.debug(f"FIRST STATION RETURNED IS {self.stations[0]}")
        self.original_utterance = ""

    def query_server(self, endpoint):
        """
        Since we have a list of possible servers to hit,
        and since servers can be unresponsive sometimes, if we
        don't get a success code we will retry with 10 different
        servers before giving up.

        Returns: a decoded response object.
        """
        uri = self.base_url + endpoint
        response = requests.get(uri)
        retries = 0
        while retries < 10:
            if 200 <= response.status_code < 300:
                return response.json()
            else:
                self.base_url = random.choice(self.base_urls)
                retries += 1

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
        LOG.debug(f"_SEARCH got {srch_term}, {limit}")
        endpoint = f"stations/search?limit={limit}&hidebroken=true&order=clickcount&reverse=true&tagList="
        query = srch_term.replace(" ", "+")
        endpoint += query
        LOG.debug(f"ENDPOINT: {endpoint}")
        # print("\n\n%s\n\n" % (uri,)) -- Where are print statements going?
        stations = self.query_server(endpoint)
        LOG.debug(f"RETURNED: {stations}")
        if stations:
            return stations
        else:
            # TODO: What if it fails?
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
        LOG.debug(f"SEARCH METHOD GOT: {sentence}, {limit}")
        unique_stations = {}
        self.original_utterance = sentence
        search_term_candidate = self.clean_sentence(sentence)
        LOG.debug(f"SEARCH TERM AFTER CLEANING: {search_term_candidate}")
        if search_term_candidate in self.genre_tags:
            self.last_search_terms = search_term_candidate
            self.genre_to_play = self.last_search_terms
        else:
            self.last_search_terms = ""
        if self.last_search_terms == "":
            # if search terms after clean are null it was most
            # probably something like 'play music' or 'play
            # radio' so we will just select a random genre
            # weighted by the number of stations in each
            self.last_search_terms = random.choices(self.genre_tags, weights=self.genre_weights, k=1)[0]
            self.genre_to_play = self.last_search_terms

        stations = self._search(self.last_search_terms, limit)
        LOG.debug("RETURNED FROM _SEARCH: {len(stations}")
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
        LOG.debug(f"RETURNED FROM SEARCH: {len(res)}")
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
            if self.index > (len(self.stations) - 1):
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
        if self.channel_index == len(self.genre_tags) - 1:
            self.channel_index = 0
        else:
            self.channel_index += 1
        self.index = 0
        self.get_stations(self.genre_tags[self.channel_index])
        return self.genre_tags[self.channel_index]

    def get_previous_channel(self):
        if self.channel_index == 0:
            self.channel_index = len(self.genre_tags) - 1
        else:
            self.channel_index -= 1
        self.index = 0
        self.get_stations(self.genre_tags[self.channel_index])
        return self.genre_tags[self.channel_index]
