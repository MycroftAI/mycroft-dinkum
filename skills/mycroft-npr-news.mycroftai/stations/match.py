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

from collections import namedtuple

from mycroft.util.log import LOG
from mycroft.util.parse import fuzzy_match

from .station import stations


# Minimum confidence levels
CONF_EXACT_MATCH = 0.9
CONF_HIGH_MATCH = 0.8
CONF_LIKELY_MATCH = 0.7
CONF_GENERIC_MATCH = 0.6

Match = namedtuple('Match', 'station confidence')


def match_station_name(phrase, station, aliases, news_keyword):
    """Determine confidence that a phrase requested a given station.

    Args:
        phrase (str): utterance from the user
        station (str): the station feed to match against
        aliases (list[str]): alternative names for the station
        news_keyword (str): localized keyword for "news"

    Returns:
        tuple: feed being matched, highest confidence level found
    """
    phrase = phrase.lower().replace("play", "").strip()

    match_confidences = [
        # fuzzy_match(phrase, station.acronym.lower()),
        fuzzy_match(phrase, station.full_name.lower()),
    ]

    # Check aliases defined in alt.feed.name.value
    if aliases:
        match_confidences.extend([fuzzy_match(phrase, alias) for alias in aliases])

    # If phrase contains both a station acronym and the news keyword
    # ensure minimum confidences.
    if f"{station.acronym.lower()} {news_keyword}" in phrase:
        # Eg "play DLF News"
        match_confidences.append(CONF_HIGH_MATCH)
    elif station.acronym.lower() in phrase:
        if news_keyword in phrase:
            # Eg "what's the news on DLF"
            match_confidences.append(CONF_LIKELY_MATCH)
        else:
            # Eg "what's on DLF"
            match_confidences.append(CONF_GENERIC_MATCH)

    highest_confidence = max(match_confidences)
    return Match(station, highest_confidence)


def match_station_from_utterance(skill, utterance):
    """Get the expected station from a user utterance.
    
    Returns:
        Station or None if news not requested.
    """
    match = Match(None, 0.0)

    utterance = utterance.lower().strip()
    # Remove articles like "the" as it matches too well with "other"
    word_list = utterance.split(' ')
    if 'the' in word_list:
        word_list.remove('the')
    utterance = ' '.join(word_list)

    # If news vocab does exist, provide a minimum default confidence
    default_station = skill.get_default_station()
    match = Match(default_station, CONF_GENERIC_MATCH)

    # Catch any short explicit phrases eg 'play the news'
    news_phrases = skill.translate_list("PlayTheNews") or []
    if utterance in news_phrases:
        LOG.debug("Explicit phrase without specific station detected.")
        return Match(default_station, 1.0)

    # Test against each station to find the best match.
    news_keyword = skill.translate('OnlyNews').lower()
    LOG.debug("Matching against specific stations")
    for station in stations.values():
        aliases = skill.alternate_station_names.get(station.acronym)
        station_match = match_station_name(utterance, station, aliases, news_keyword)
        LOG.debug(f"{station.acronym}: {match.confidence}")
        if station_match.confidence > match.confidence:
            match = station_match

    return match
