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
"""Defines a News Station object"""

from abc import ABC, abstractproperty
from builtins import property
from collections.abc import Callable
from pathlib import Path

import feedparser
from mycroft.util.log import LOG

from .abc import get_abc_url
from .ft import get_ft_url
from .gpb import get_gpb_url
from .tsf import get_tsf_url


class BaseStation(ABC):
    """Abstract Base Class for all News Stations."""

    def __init__(
        self, acronym: str, full_name: str, image_file: str = None, color: str = None
    ):
        self.acronym = acronym
        self.full_name = full_name
        self.image_file = image_file
        self.color = color or "#198AFF"

    def as_dict(self):
        return {
            "acronym": self.acronym,
            "full_name": self.full_name,
            "image_path": str(self.image_path),
        }

    @property
    def image_path(self) -> Path:
        """The absolute path to the stations logo.

        Note that this currently traverses the path from this file and may
        break if this is moved in the file hierarchy.
        """
        if self.image_file is None:
            return None
        skill_path = Path(__file__).parent.parent.absolute()
        file_path = Path(skill_path, "images", self.image_file)
        if not file_path.exists():
            LOG.warning(f"{self.image_file} could not be found, using default image")
            file_path = Path(skill_path, "images", "generic.png")
        return file_path

    @abstractproperty
    def media_uri(self) -> str:
        """Get the uri for the media file to be played."""
        pass


class FileStation(BaseStation):
    """News Station that provides a static url for their latest briefing."""

    def __init__(
        self,
        acronym: str,
        full_name: str,
        media_url: str,
        image_file: str = None,
        color: str = None,
    ):
        super().__init__(acronym, full_name, image_file, color)
        self._media_url = media_url

    @property
    def media_uri(self) -> str:
        """The static media url for the station."""
        return self._media_url


class FetcherStation(BaseStation):
    """News Station that requires a custom url getter function."""

    def __init__(
        self,
        acronym: str,
        full_name: str,
        url_getter: Callable,
        image_file: str = None,
        color: str = None,
    ):
        super().__init__(acronym, full_name, image_file, color)
        self._get_media_url = url_getter

    @property
    def media_uri(self) -> str:
        """Get the uri for the media file to be played.

        Uses the stations custom getter function."""
        return self._get_media_url()


class RSSStation(BaseStation):
    """News Station based on an RSS feed."""

    def __init__(
        self,
        acronym: str,
        full_name: str,
        rss_url: str,
        image_file: str = None,
        color: str = None,
    ):
        super().__init__(acronym, full_name, image_file, color)
        self._rss_url = rss_url

    @property
    def media_uri(self) -> str:
        """Get the uri for the media file to be played."""
        media_url = self._get_audio_from_rss()
        # TODO - check on temporary workaround and remove - see issue #87
        if self._rss_url.startswith("https://www.npr.org/"):
            media_url = media_url.split("?")[0]
        return media_url

    def _get_audio_from_rss(self) -> str:
        """Get the first audio url from the Station RSS feed.

        Selects the first link to an audio file, or falls back to the
        first href link in the entry if no explicit audio can be found.

        Args:
            rss_url: RSS feed to parse

        Returns:
            Url to a media file or None if no link can be found.
        """
        audio_url = None
        data = feedparser.parse(self._rss_url)
        if data.entries:
            # select the first link to an audio file
            for link in data["entries"][0]["links"]:
                if "audio" in link["type"]:
                    audio_url = link["href"]
                    break
                else:
                    # fall back to using the first link in the entry
                    audio_url = data["entries"][0]["links"][0]["href"]
        return audio_url


def create_custom_station(station_url):
    """Create a new station from a custom url.

    First tests to see if the url can be read as an RSS feed, if not assumes it is a
    direct link.

    NOTE: it cannot be a FetcherStation because you can't define the fetching function.
    """
    is_rss_feed = len(feedparser.parse(station_url).entries) > 0
    if is_rss_feed:
        clazz = RSSStation
    else:
        clazz = FileStation
    stations["custom"] = clazz("custom", "Your custom station", station_url)


# NOTE: This list should be kept in sync with the settingsmeta select options,
# however modifying that file will cause the backend to consider it as a new
# group of settings. Until there is a better mechanism for handling updated
# settingsmeta files, we will not be adding new stations to the settings.
# They can be added to the list of country defaults below.

stations = dict(
    ABC=FetcherStation("ABC", "ABC News Australia", get_abc_url, "ABC.png", "#4B555C"),
    AP=RSSStation(
        "AP",
        "AP Hourly Radio News",
        "https://www.spreaker.com/show/1401466/episodes/feed",
        "AP.png",
        "#BE1617",
    ),
    BBC=RSSStation(
        "BBC",
        "BBC News",
        "https://podcasts.files.bbci.co.uk/p02nq0gn.rss",
        "BBC.png",
        "#C0311A",
    ),
    CBC=RSSStation(
        "CBC",
        "CBC News",
        "https://www.cbc.ca/podcasting/includes/hourlynews.xml",
        "CBC.png",
        "#EE1B2E",
    ),
    DLF=RSSStation(
        "DLF",
        "DLF",
        "https://www.deutschlandfunk.de/podcast-nachrichten.1257.de.podcast.xml",
        "DLF.png",
    ),
    Ekot=RSSStation(
        "Ekot", "Ekot", "https://api.sr.se/api/rss/pod/3795", "Ekot.png", "#0065BD"
    ),
    FOX=RSSStation(
        "FOX",
        "Fox News",
        "http://feeds.foxnewsradio.com/FoxNewsRadio",
        "FOX.png",
        "#22438D",
    ),
    FT=FetcherStation("FT", "Financial Times", get_ft_url, "FT.png", "#ffcc99"),
    GPB=FetcherStation("GPB", "Georgia Public Radio", get_gpb_url, None),
    NPR=RSSStation(
        "NPR",
        "NPR News Now",
        "https://www.npr.org/rss/podcast.php?id=500005",
        "NPR.png",
        "#BE1617",
    ),
    OE3=FileStation(
        "OE3",
        "Ö3 Nachrichten",
        "https://oe3meta.orf.at/oe3mdata/StaticAudio/Nachrichten.mp3",
        None,
    ),
    PBS=RSSStation(
        "PBS",
        "PBS NewsHour",
        "https://www.pbs.org/newshour/feeds/rss/podcasts/show",
        "PBS.png",
        "#B01F25",
    ),
    RDP=RSSStation("RDP", "RDP Africa", "http://www.rtp.pt//play/itunes/5442", None),
    RNE=RSSStation(
        "RNE",
        "National Spanish Radio",
        "http://api.rtve.es/api/programas/36019/audios.rs",
        None,
    ),
    TSF=FetcherStation("TSF", "TSF Radio", get_tsf_url, None),
    VRT=FileStation(
        "VRT",
        "VRT Nieuws",
        "https://progressive-audio.lwc.vrtcdn.be/content/fixed/11_11niws-snip_hi.mp3",
        None,
    ),
    WDR=RSSStation(
        "WDR",
        "WDR",
        "https://www1.wdr.de/mediathek/audio/wdr-aktuell-news/wdr-aktuell-152.podcast",
        "WDR.png",
        "#00375A",
    ),
    YLE=RSSStation(
        "YLE",
        "YLE",
        "https://feeds.yle.fi/areena/v1/series/1-1440981.rss",
        "Yle.png",
        "#00B8CD",
    ),
)

country_defaults = dict(
    AT="OE3",
    AU="ABC",
    BE="VRT",
    CA="CBC",
    DE="DLF",
    ES="RNE",
    FI="YLE",
    PT="TSF",
    SE="Ekot",
    UK="BBC",
    US="NPR",
)
