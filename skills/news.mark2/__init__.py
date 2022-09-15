# Copyright 2018 Mycroft AI Inc.
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
from typing import Optional, Tuple

from mycroft.messagebus import Message
from mycroft.skills import AdaptIntent, GuiClear, intent_handler
from mycroft.skills.common_play_skill import CommonPlaySkill, CPSMatchLevel

from .stations.match import Match, match_station_from_utterance
from .stations.station import (
    BaseStation,
    country_defaults,
    create_custom_station,
    stations,
)

# Minimum confidence levels
CONF_EXACT_MATCH = 0.9
CONF_LIKELY_MATCH = 0.7
CONF_GENERIC_MATCH = 0.6


class NewsSkill(CommonPlaySkill):
    def __init__(self, skill_id: str):
        super().__init__(skill_id=skill_id, name="NewsSkill")
        self.now_playing: Optional[BaseStation] = None
        self._stream_session_id: Optional[str] = None

    def initialize(self):
        # Longer titles or alternative common names of feeds for searching
        self.alternate_station_names = self.load_alternate_station_names()
        self.settings_change_callback = self.on_websettings_changed
        self.on_websettings_changed()
        self.add_event(
            "mycroft.audio.service.position", self.handle_audioservice_position
        )
        self.add_event("mycroft.audio.service.playing", self.handle_media_playing)
        self.add_event("mycroft.audio.service.stopped", self.handle_media_stopped)
        self.bus.on("mycroft.audio.queue_end", self.handle_media_finished)
        self.bus.on(
            "play:pause", self.handle_pause
        )
        self.bus.on(
            "play:resume", self.handle_resume
        )

    def load_alternate_station_names(self) -> dict:
        """Load the list of alternate station names from alt.feed.name.value

        These are provided as name, acronym pairs. They are reordered into a
        dict keyed by acronym for ease of use in station matching.

        Returns:
            Dict of alternative names for stations
                Keys: station acronym
                Values: list of alternative names
        """
        loaded_list = self.translate_namedvalues("alt.feed.name")
        alternate_station_names = {}
        for name in loaded_list:
            acronym = loaded_list[name]
            if alternate_station_names.get(acronym) is None:
                alternate_station_names[acronym] = []
            alternate_station_names[acronym].append(name)
        return alternate_station_names

    def handle_audioservice_position(self, message):
        if not self.now_playing:
            return

        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._stream_session_id:
            return

        position_ms = message.data["position_ms"]
        self.update_gui_values(
            page="AudioPlayer_mark_ii.qml",
            data={"playerPosition": position_ms},
            overwrite=False,
        )

    def handle_media_playing(self, message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._stream_session_id:
            self.now_playing = None

    def handle_media_stopped(self, message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id == self._stream_session_id:
            self.now_playing = None

    def handle_media_finished(self, message):
        """Handle media playback finishing."""
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id == self._stream_session_id:
            self.bus.emit(
                Message(
                    "mycroft.audio.service.stop",
                    data={"mycroft_session_id": self._stream_session_id},
                )
            )
            self._stream_session_id = None
            self.now_playing = None
            self.bus.emit(Message("mycroft.gui.idle"))

    def handle_audioservice_status_change(self, message):
        """Handle changes in playback status from the Audioservice.

        Eg when someone verbally asks to pause.
        """
        if not self.now_playing:
            return

        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._stream_session_id:
            return

        command = message.msg_type.split(".")[-1]
        if command in {"playing", "resumed"}:
            new_status = "Playing"
        elif command in {"paused", "stopped"}:
            new_status = "Paused"

        self.update_gui_values(
            page="AudioPlayer_mark_ii.qml", data={"status": new_status}, overwrite=False
        )

    def handle_pause(self, _):
        self._audio_session_id = self._stream_session_id
        self.log.debug("News pause triggered.")
        self.update_gui_values(
            page="AudioPlayer_mark_ii.qml", data={"status": "Paused"} #, overwrite=False
        )
        self.CPS_pause()

    def handle_resume(self, message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._stream_session_id:
            return
        self._audio_session_id = self._stream_session_id
        self.update_gui_values(
            page="AudioPlayer_mark_ii.qml", data={"status": "Playing"}, overwrite=False
        )
        self.bus.emit(
            Message(
                "mycroft.audio.service.resume",
                data={"mycroft_session_id": self._audio_session_id},
            )
        )

    def on_websettings_changed(self):
        """Callback triggered anytime Skill settings are modified on backend."""
        station_code = self.settings.get("station", "not_set")
        custom_url = self.settings.get("custom_url", "")
        if station_code == "not_set" and len(custom_url) > 0:
            self.log.info("Creating custom News Station from Skill settings.")
            create_custom_station(custom_url)

    @intent_handler(AdaptIntent("").one_of("Give", "Latest").require("News"))
    def handle_latest_news(self, message):
        """Adapt intent handler to capture general queries for the latest news."""
        match = match_station_from_utterance(self, message.data["utterance"])
        if match and match.station:
            station = match.station
        else:
            station = self.get_default_station()

        return self.handle_play_request(station)

    @intent_handler("PlayTheNews.intent")
    def handle_latest_news_alt(self, message):
        """Padatious intent handler to capture short distinct utterances."""
        return self.handle_latest_news(message)

    @intent_handler(AdaptIntent("").require("Play").require("News"))
    def handle_play_news(self, message):
        return self.handle_latest_news(message)

    @intent_handler(AdaptIntent("").require("Stop").require("News"))
    def handle_stop_news(self, message):
        dialog = None

        if self.now_playing is not None:
            self.bus.emit(
                Message(
                    "mycroft.audio.service.stop",
                    data={"mycroft_session_id": self._stream_session_id},
                )
            )
            self._stream_session_id = None
            self.now_playing = None
            gui_clear = GuiClear.AT_END
        else:
            dialog = "no.news.playing"
            gui_clear = GuiClear.NEVER

        return self.end_session(dialog=dialog, gui_clear=gui_clear)

    @intent_handler(AdaptIntent("").require("Show").require("News"))
    def handle_show_news(self, _):
        gui = None
        dialog = None

        if self.now_playing is not None:
            gui = "AudioPlayer_mark_ii.qml"
        else:
            dialog = "no.news.playing"

        return self.end_session(dialog=dialog, gui=gui, gui_clear=GuiClear.NEVER)

    def handle_play_request(self, station: BaseStation):
        dialog = ("news", {"from": station.full_name})
        media_uri = station.media_uri
        gui_page = "AudioPlayer_mark_ii.qml"
        gui_data = {
            "media": {
                "image": str(station.image_path),
                "artist": station.acronym,
                "track": station.full_name,
                "album": "",
                "skill": self.skill_id,
                "streaming": True,
            },
            "status": "Starting",
            "theme": dict(fgColor="white", bgColor=station.color),
            "playerPosition": 0.0,
        }

        # The session id of our stream in the audio UI will be this sesson's id
        self._stream_session_id = self._mycroft_session_id
        self.now_playing = station

        return self.end_session(
            dialog=dialog,
            gui=(gui_page, gui_data),
            music_uri=media_uri,
            gui_clear=GuiClear.NEVER,
        )

    def CPS_start(self, _, data):
        """Handle request from Common Play System to start playback."""
        if data and data.get("acronym"):
            # Play the requested news service
            selected_station = stations[data["acronym"]]
        else:
            # Just use the default news feed
            selected_station = self.get_default_station()

        return self.handle_play_request(selected_station)

    def CPS_match_query_phrase(self, phrase: str) -> Tuple[str, float, dict]:
        """Respond to Common Play Service query requests.

        Args:
            phrase: utterance request to parse

        Returns:
            Tuple(Name of station, confidence, Station information)
        """
        if not self.voc_match(phrase.lower(), "News"):
            # The utterance does not contain news vocab. Do not match.
            return None

        match = match_station_from_utterance(self, phrase)

        # If no match but utterance contains news, return low confidence level
        if match.confidence < CONF_GENERIC_MATCH:
            match = Match(self.get_default_station(), CONF_GENERIC_MATCH)

        # Translate match confidence levels to CPSMatchLevels
        if match.confidence >= CONF_EXACT_MATCH:
            match_level = CPSMatchLevel.EXACT
        elif match.confidence >= CONF_LIKELY_MATCH:
            match_level = CPSMatchLevel.ARTIST
        elif match.confidence >= CONF_GENERIC_MATCH:
            match_level = CPSMatchLevel.CATEGORY
        else:
            return None

        return match.station.full_name, match_level, match.station.as_dict()

    def get_default_station(self) -> BaseStation:
        """Get default station for user.

        Fallback order:
        1. Station defined in Skill Settings
        2. Default station for country
        3. NPR News as global default
        """
        station = None
        station_code = self.settings.get("station", "not_set")
        custom_url = self.settings.get("custom_url", "")
        if station_code != "not_set":
            station = stations[station_code]
        elif len(custom_url) > 0:
            station = stations.get("custom")
        if station is None:
            station = self.get_default_station_by_country()
        if station is None:
            station = stations["NPR"]
        return station

    def get_default_station_by_country(self) -> BaseStation:
        """Get the default station based on the devices location."""
        country_code = self.location["city"]["state"]["country"]["code"]
        station_code = country_defaults.get(country_code)
        return stations.get(station_code)

    @property
    def is_https_supported(self) -> bool:
        """Check if any available audioservice backend supports https."""
        for service in self.audioservice.available_backends().values():
            if "https" in service["supported_uris"]:
                return True
        return False

    def stop(self) -> Optional[Message]:
        if self.now_playing is not None:
            self.bus.emit(
                Message(
                    "mycroft.audio.service.stop",
                    data={"mycroft_session_id": self._stream_session_id},
                )
            )
            self._stream_session_id = None
            self.now_playing = None

            return self.end_session(gui_clear=GuiClear.AT_END)

    def handle_gui_idle(self):
        if self.now_playing is not None:
            gui = "AudioPlayer_mark_ii.qml"
            self.emit_start_session(gui=gui, gui_clear=GuiClear.NEVER)
            return True

        return False


def create_skill(skill_id: str):
    return NewsSkill(skill_id=skill_id)
