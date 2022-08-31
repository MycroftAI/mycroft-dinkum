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
import re
from typing import Optional

from mycroft.util.log import LOG

from pyradios.base_url import fetch_hosts

# The maximum length for strings to be displayed in the UI.
# Strings that are too long will overlap and be unreadable
# in the marquee field. If strings are distorted, reduce
# this number.
CHARACTER_LIMIT = 35


def sort_on_vpc(k):
    return k["votes_plus_clicks"]


def sort_on_confidence(k):
    return k["confidence"]


# Helper functions.


def clean_string(string: str) -> str:
    """
    Cleans up input for display in the GUI.

    Some kind of full sanitization might be preferable,
    but for now we will just remove anything that is not
    a word, a space, or a few punctuation marks.

    The punctuation marks it leaves are mostly
    delimiters that can be used for truncation later.
    """
    string = (
        string.replace("'", "").replace('"', "").replace("\n", " ").replace("\t", " ")
    )
    string = re.sub(r"[^\w,/\-\. ]", " ", string)
    string = re.sub(r"\s\s+", " ", string)
    return string.strip()


def truncate_input_string(string: str) -> str:
    """
    Takes a string (expected to be from the Radio
    Browser service) and attempts to truncate it
    (if it is too long) in a smart way.
    """
    if len(string) <= CHARACTER_LIMIT:
        return string
    chunks = [chunk.strip() for chunk in re.split(r"[/\-]", string)]
    truncated_string = _construct_string(chunks)
    if not truncated_string:
        subchunks = chunks[0].split(" ")
        truncated_string = _construct_string(subchunks)
    if truncated_string:
        return truncated_string
    else:
        return chunks[0][:CHARACTER_LIMIT]


def _construct_string(chunks: list) -> Optional[str]:
    """
    Rebuilds a string that is too long, up to
    the value in CHARACTER_LIMIT.
    """
    truncated_string = ""
    for chunk in chunks:
        if len(truncated_string) + len(chunk) < CHARACTER_LIMIT:
            truncated_string += " " + chunk
        else:
            return truncated_string.strip()
    return None


class RadioStations:
    def __init__(self):
        self.station_index = 0
        self.blacklist = [
            "icecast",
        ]
        self.media_verbs = ["play", "listen", "turn on", "start"]
        self.noise_words = ["on", "to", "the", "music", "station", "channel", "radio"]
        self.search_limit = 1000

        self.base_urls = ["https://" + host + "/json/" for host in fetch_hosts()]
        self.base_url = random.choice(self.base_urls)
        self.genre_tags_response = self.query_server(
            "tags?order=stationcount&reverse=true&hidebroken=true&limit=10000"
        )
        self.stations = []

        if self.genre_tags_response:
            # TODO: Figure out what to do if we can't get a server at all.

            # The way this mess is currently written we can't end the session
            # with some dialog within this class, instead we must wait for
            # the RadioFreeMycroftSkill class to find these attributes empty
            # (since that class just accesses all of this
            # class's attributes without waiting for anything to be
            # returned).
            # Once it gets nothing back it will emit a fairly appropriate
            # bit of dialog and end the session. I can't think of a better
            # way to do this without a major refactoring.

            # There are many "genre" tags which are actually specific to one station.
            # First make a list of lists to simplify.
            self.genre_tags = [
                [genre.get("name", ""), genre.get("stationcount", "")]
                for genre in self.genre_tags_response
            ]
            # Then split the lists. This will make things easier downstream
            # when we use station count to weight a random choice operation.
            self.genre_tags, self.genre_weights = map(list, zip(*self.genre_tags))

            self.channel_index = 0
            # Default to using the genre tag with the most radio stations.
            # As of this comment it is "pop".
            self.last_search_terms = self.genre_tags[self.channel_index]
            self.genre_to_play = ""
            self.get_stations(self.last_search_terms)
            self.original_utterance = ""

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
                LOG.debug(
                    f"Successful response from RadioBrowser server: {self.base_url}"
                )
                return response.json()
            else:
                LOG.debug(
                    f"Unsuccessful response from RadioBrowser server: {self.base_url}"
                )
                self.base_url = random.choice(self.base_urls)
                LOG.debug(
                    f"Retrying request from next RadioBrowser server: {self.base_url}"
                )
                retries += 1

    def _get_response(self, endpoint):
        retries = 0
        response = None
        while retries < 10:
            uri = self.base_url + endpoint
            try:
                response = requests.get(uri, timeout=3)
                return response
            except requests.Timeout:
                LOG.debug(f"Timeout {self.base_url}")
                self.base_url = random.choice(self.base_urls)
                LOG.debug(f"Trying with {self.base_url}")
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
        endpoint = f"stations/search?limit={limit}&hidebroken=true&order=clickcount&reverse=true&tagList="
        query = srch_term.replace(" ", "+")
        endpoint += query
        LOG.debug(f"ENDPOINT: {endpoint}")
        # print("\n\n%s\n\n" % (uri,)) -- Where are print statements going?
        stations = self.query_server(endpoint)
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

    def weighted_random_genre(self) -> str:
        """
        Performs a weighted random search of genre tags
        using a special reweighting system founded on
        station count but that gives extra weight to
        more popular, etc., stations. Also excludes
        tags with only one station.
        """
        # First zip up the weights and genre tags.
        genre_weights = zip(self.genre_tags, self.genre_weights)
        filtered_tags = [
            genre_weight for genre_weight in genre_weights if genre_weight[1] > 1
        ]
        # TODO: Additional weighting fun to go here very soon.
        # Split the lists again.
        filtered_genre_tags, filtered_genre_weights = map(list, zip(*filtered_tags))
        return random.choices(filtered_genre_tags, weights=filtered_genre_weights, k=1)[
            0
        ]

    def search(self, sentence, limit):
        unique_stations = {}
        self.original_utterance = sentence
        search_term_candidate = self.clean_sentence(sentence)
        if search_term_candidate in self.genre_tags:
            self.last_search_terms = search_term_candidate
            self.genre_to_play = self.last_search_terms
        else:
            self.last_search_terms = ""
        if not self.last_search_terms:
            # if search terms after clean are null it was most
            # probably something like 'play music' or 'play
            # radio' so we will just select a random genre
            # weighted by the number of stations in each
            self.last_search_terms = self.weighted_random_genre()
            self.genre_to_play = self.last_search_terms

        stations = self._search(self.last_search_terms, limit)
        LOG.debug("RETURNED FROM _SEARCH: {len(stations})")
        # whack dupes, favor match confidence
        for station in stations:
            if station["name"]:
                station["name"] = truncate_input_string(clean_string(station["name"]))
            station_name = station.get("name", "")
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

    def get_stations(self, utterance):
        self.stations = self.search(utterance, self.search_limit)
        self.station_index = 0

    def get_station_count(self):
        return len(self.stations)

    def get_station_index(self):
        return self.station_index

    def get_current_station(self):
        if self.stations and len(self.stations) > 0:
            if self.station_index > (len(self.stations) - 1):
                # this covers up a bug
                self.station_index = 0
            return self.stations[self.station_index]
        return None

    def get_next_station(self):
        if self.station_index == len(self.stations):
            self.station_index = 0
        else:
            self.station_index += 1
        return self.get_current_station()

    def get_previous_station(self):
        if self.station_index == 0:
            self.station_index = len(self.stations) - 1
        else:
            self.station_index -= 1
        return self.get_current_station()

    def get_next_channel(self):
        LOG.debug(f"NEXT CHANNEL CALLED: CHANNEL INDEX IS {self.channel_index}")
        if self.channel_index == len(self.genre_tags) - 1:
            self.channel_index = 0
        else:
            self.channel_index += 1
        LOG.debug(f"CHANNEL INCREMENTED: {self.channel_index}")
        LOG.debug(f"CORESPONDING GENRE: {self.genre_tags[self.channel_index]}")
        self.station_index = 0
        self.get_stations(self.genre_tags[self.channel_index])
        # This appears to serve no purpose at all.
        # Only place it is called doesn't take any return.
        return self.genre_tags[self.channel_index]

    def get_previous_channel(self):
        if self.channel_index == 0:
            self.channel_index = len(self.genre_tags) - 1
        else:
            self.channel_index -= 1
        self.station_index = 0
        self.get_stations(self.genre_tags[self.channel_index])
        return self.genre_tags[self.channel_index]
