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
# TODO
#   play <station name> should find if provided
#   add to favorites and play favorite
from typing import Optional, Tuple
import threading
import requests

from mycroft.skills import AdaptIntent, GuiClear, intent_handler
from mycroft.skills.common_play_skill import CommonPlaySkill, CPSMatchLevel
from mycroft_bus_client import Message

from .RadioStations import GenreTagNotFound, RadioStations

# Minimum confidence levels
CONF_EXACT_MATCH = 0.9
CONF_LIKELY_MATCH = 0.7
CONF_GENERIC_MATCH = 0.6

"""
Provides base functionality for Mycroft's radio skill.
"""


class RadioFreeMycroftSkill(CommonPlaySkill):
    """simple streaming radio skill"""

    def __init__(self, skill_id: str):
        super().__init__(skill_id=skill_id, name="Mycroft Radio Skill")
        self._rs: Optional[RadioStations] = None
        self.current_station = None
        self.station_name = "Mycroft Radio"
        self.img_pth = ""
        self.stream_uri = ""
        self.fg_color = "white"
        self.bg_color = "black"
        self.genre_images = {
            "alternative": "genre_alternative.svg",
            "classical": "genre_classical.svg",
            "country": "genre_country.svg",
            "generic": "genre_generic_radio.svg",
            "hip-hop": "genre_hip_hop.svg",
            "jazz": "genre_jazz.svg",
            "metal": "genre_metal.svg",
            "pop": "genre_pop.svg",
            "rnb": "genre_rnb.svg",
            "rock": "genre_rock.svg",
        }
        self._is_playing = False
        self._stream_session_id: Optional[str] = None
        self.settings_change_callback = None
        # The following is for tracking how long a station has been played.
        self.current_station_uuid: Optional[str] = None

    def initialize(self):
        """Wait for internet connection before accessing radio stations"""
        self.add_event("mycroft.ready", self.handle_ready)
        self.register_gui_handlers()

    def get_language_setting(self):
        language = self.settings.get("language", "not_set")
        if language == "not_set":
            language = "english"
        return language

    @property
    def rs(self) -> RadioStations:
        """Dynamically load radio stations"""
        self._load_radio_stations()
        assert self._rs is not None
        return self._rs

    def handle_ready(self, _):
        self._load_radio_stations()

    def _load_radio_stations(self):
        if self._rs is None:
            self._rs = RadioStations(self.get_language_setting())

    def register_gui_handlers(self):
        """Register handlers for events to or from the GUI."""
        self.log.debug("Registering gui handlers.")
        self.bus.on("mycroft.audio.service.playing", self.handle_media_playing)
        self.bus.on("mycroft.audio.service.stopped", self.handle_media_stopped)
        self.bus.on("play:pause", self.handle_pause)
        self.bus.on("play:resume", self.handle_resume)
        self.bus.on(
            "mycroft.audio.queue_end",
            self.handle_media_finished,
        )
        self.bus.on("register.station.click", self.handle_station_click)
        self.gui.register_handler(
            "cps.gui.pause", "RadioPlayer_mark_ii.qml", self.handle_gui_status_change
        )
        self.gui.register_handler(
            "cps.gui.play", "RadioPlayer_mark_ii.qml", self.handle_gui_status_change
        )
        self.gui.register_handler(
            "gui.next_station", "RadioPlayer_mark_ii.qml", self.handle_next_station
        )
        self.gui.register_handler(
            "gui.prev_station", "RadioPlayer_mark_ii.qml", self.handle_previous_station
        )
        self.gui.register_handler(
            "gui.next_genre", "RadioPlayer_mark_ii.qml", self.handle_next_channel
        )
        self.gui.register_handler(
            "gui.prev_genre", "RadioPlayer_mark_ii.qml", self.handle_previous_channel
        )
        self.gui.register_handler(
            "gui.stop_radio",
            "RadioPlayer_mark_ii.qml",
            self.handle_stop_radio,
        )
 
    def handle_station_click(self, message):
        """
        Radio Browser tracks 'clicks', meaning the number of times
        users play each station. To give this feedback we need to
        send a query to the server with the station uuid.

        For our purposes, since users don't currently have the option
        of easily playing specific stations, we will consider a station
        'click' to have occurred after the user has allowed a given
        station to play for one minute.
        """
        played_station_uuid = message.data.get("station_uuid", "")
        if played_station_uuid:
            threading.Timer(60.0, self._register_station_click, args=(played_station_uuid,)).start()
    
    def _register_station_click(self, played_station_uuid):
        if played_station_uuid == self.current_station_uuid:
            # Send 'click' feedback to Radio Browser.
            resp = self.rs.query_server(
                f"url/{played_station_uuid}"
            )
            station_name = resp.get("name", "")
            if station_name:
                self.log.info(f"Registered click for {resp}")
        
    def handle_pause(self, message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._stream_session_id:
            return
        self._audio_session_id = self._stream_session_id
        self.update_gui_values("RadioPlayer_mark_ii.qml", {"status": "Paused"})
        self._is_playing = False
        self.CPS_pause()

    def handle_resume(self, message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._stream_session_id:
            return
        self.update_gui_values("RadioPlayer_mark_ii.qml", {"status": "Playing"})
        self._is_playing = True
        self.handle_play_request()

    def handle_media_finished(self, message):
        """Handle media playback finishing."""
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id == self._stream_session_id:
            self.log.warning("RadioMediaFinished! should never get here!")

    def handle_media_playing(self, message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id == self._stream_session_id:
            self._is_playing = True
        else:
            self._is_playing = False

    def handle_media_stopped(self, message=None):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id == self._stream_session_id:
            self._is_playing = False

    def handle_gui_status_change(self, message):
        """Handle play and pause status changes from the GUI.
        This notifies the audioservice. The GUI state only changes once the
        audioservice emits the relevant messages to say the state has changed.
        """
        if not self._is_playing:
            return

        command = message.msg_type.split(".")[-1]
        if command == "play":
            self.log.info("Audio resumed by GUI.")
            self.CPS_resume()
        elif command == "pause":
            self.log.info("Audio paused by GUI.")
            self.CPS_pause()

    def update_radio_theme(self, status):
        self.img_pth = None
        if self.rs.genre_to_play and self.rs.genre_to_play in self.genre_images.keys():
            self.img_pth = self.find_resource(
                self.genre_images[self.rs.genre_to_play], "ui/images"
            )
        else:
            for genre_image_name, genre_image_path in self.genre_images.items():
                if genre_image_name in self.rs.genre_to_play:
                    self.img_pth = self.find_resource(genre_image_path, "ui/images")
        if not self.img_pth:
            self.img_pth = self.find_resource("genre_generic_radio.svg", "ui/images")

        channel_info = "%s/%s" % (self.rs.station_index + 1, len(self.rs.stations))
        station_name = self.current_station.get("name", "").replace("\n", "")
        gui_data = {
            "media_image": self.img_pth,
            "media_station": station_name,
            "media_genre": self.rs.genre_to_play,
            "media_skill": self.skill_id,
            "media_current_station_info": channel_info,
            "media_streaming": True,
            "media_status": status,
        }
        return ("RadioPlayer_mark_ii.qml", gui_data)

    def setup_for_play(self, utterance):
        try:
            self.rs.get_stations(utterance)
            self.current_station = self.rs.get_current_station()
        except GenreTagNotFound:
            self.log.debug("Genre not found exception in setup for play.")
            # Setting to None will cause it to do the right
            # thing down the line, i.e., tell the user
            # it doesn't know how to play x.
            self.current_station = None

    def handle_play_request(self):
        """play the current station if there is one"""
        if not self.current_station:
            # If there isn't a current station, that means we were unable to find
            # a genre that matches the search term.
            dialog = ("cant.find.stations", {"search": self.rs.last_search_terms})
            self._mycroft_session_id = self.emit_start_session(
                dialog=dialog, gui_clear=GuiClear.NEVER
            )
            return self.end_session(dialog=dialog)
        stream_uri = None
        station_name = None
        # station_uuid will be needed to increment clicks on the radio browser server.
        station_uuid = None

        # The first attempt to connect to the station server is to check mime type.
        # If we have connection problems, most of the time they will happen here.
        # In that case we will go to the next station and try again up to 10 times
        # before giving up.
        mime = None
        tries = 0
        while not mime and tries < 10:
            tries += 1
            try:
                stream_uri = self.current_station.get("url_resolved", "")
                if stream_uri:
                    self.log.debug(f"Getting mime type for {stream_uri}")
                else:
                    self.log.error("No stream uri found!")
                station_name = self.current_station.get("name", "").replace("\n", "")
                if station_name:
                    self.log.debug(f"Getting mime type for {station_name}")
                else:
                    self.log.error("No station name found!")
                station_uuid = self.current_station.get("stationuuid", "")
                self.log.debug(f"Attempting to check mime type: try {tries}")
                mime = self.rs.find_mime_type(stream_uri)
            except requests.exceptions.RequestException as e:
                self.log.debug(f"Mime type request failed: {e}")
                self.rs.get_next_station()
                self.current_station = self.rs.get_current_station()
        if not mime:
            self.log.error(
                "Unsuccessful mime type checks for 10 different stations, cannot connect."
            )

        self.CPS_play([stream_uri])

        # Send a message indicating a station has started playing.
        if station_uuid:
            self.current_station_uuid = station_uuid
            self.bus.emit(
                Message(
                    "register.station.click",
                    data={"station_uuid": station_uuid},
                )
            )
        else:
            self.log.debug("Station UUID not found, cannot register click with Radio Browser.")

        gui = self.update_radio_theme("Now Playing")
        self._stream_session_id = self._mycroft_session_id

        self._mycroft_session_id = self.emit_start_session(
            gui=gui, gui_clear=GuiClear.NEVER
        )

        self.CPS_send_status(image=self.img_pth, artist=station_name)

    # Intents
    @intent_handler("HelpRadio.intent")
    def handle_radio_help(self, _):
        return self.end_session(dialog="radio.help", gui_clear=GuiClear.NEVER)

    @intent_handler("ShowRadio.intent")
    def handle_show_radio(self, _):
        dialog = None
        gui = None

        if self._is_playing:
            gui = "RadioPlayer_mark_ii.qml"
        else:
            dialog = "no.radio.playing"

        return self.end_session(dialog=dialog, gui=gui, gui_clear=GuiClear.NEVER)

    @intent_handler("NextStation.intent")
    def handle_next_station(self, message=None):
        station_found = False
        ctr = 0
        while (not station_found) and (ctr < self.rs.get_station_count()):
            new_current_station = self.rs.get_next_station()
            self.current_station = new_current_station
            self.update_station_vars(new_current_station)

            try:
                self.handle_play_request()
                station_found = True
            except Exception:
                self.log.exception("Error in next station")

            ctr += 1

    @intent_handler("PreviousStation.intent")
    def handle_previous_station(self, message=None):
        station_found = False
        ctr = 0
        while (not station_found) and (ctr < self.rs.get_station_count()):
            new_current_station = self.rs.get_previous_station()
            self.update_station_vars(new_current_station)

            try:
                self.handle_play_request()
                station_found = True
            except Exception:
                self.log.exception("Error in previous station")

            ctr += 1

    @intent_handler("NextChannel.intent")
    def handle_next_channel(self, message):
        self.log.debug("Trying to get next channel.")
        self.rs.get_next_channel()
        self.handle_next_station(message)

    @intent_handler("PreviousChannel.intent")
    def handle_previous_channel(self, message):
        self.rs.get_previous_channel()
        self.handle_next_station(message)

    @intent_handler(AdaptIntent("").require("Play").require("Radio"))
    def handle_play_radio(self, message):
        return self.handle_listen_intent(message)

    @intent_handler("ListenToRadio.intent")
    def handle_listen_intent(self, message):
        self.setup_for_play(message.data.get("utterance", ""))
        self.handle_play_request()

    def play_current(self):
        station_found = False
        ctr = 0
        while not station_found and ctr < self.rs.get_station_count():
            new_current_station = self.rs.get_next_station()
            self.update_station_vars(new_current_station)
            try:
                self.handle_play_request()
                station_found = True
            except Exception:
                self.log.exception("Error while playing station")

            ctr += 1

        if not station_found:
            self.log.error(
                "of %s stations, none work!" % (self.rs.get_station_count(),)
            )

    def update_station_vars(self, new_current_station):
        self.current_station = new_current_station
        self.stream_uri = self.current_station.get("url_resolved", "")
        self.station_name = self.current_station.get("name", "")
        self.station_name = self.station_name.replace("\n", " ")
        self.station_name = " ".join(self.station_name.splitlines())
        self.current_station_uuid = self.current_station.get("stationuuid", "")

    @intent_handler("TurnOnRadio.intent")
    def handle_turnon_intent(self, _):
        if self.current_station is None:
            self.setup_for_play(self.rs.get_next_channel())
        self.play_current()

    @intent_handler("StopRadio.intent")
    def handle_stop_radio(self, _):
        return self.stop()

    # Common query stuff
    def CPS_match_query_phrase(self, phrase: str) -> Tuple[str, float, dict]:
        """Respond to Common Play Service query requests.
        Args:
            phrase: utterance request to parse
        Returns:
            Tuple(Name of station, confidence, Station information)
        """
        # Translate match confidence levels to CPSMatchLevels
        self.log.debug("CPS Match Request")
        self.setup_for_play(phrase)

        match_level = 0.0
        tags = []
        confidence = 0.0
        stream_uri = ""
        if self.current_station:
            match_level = CPSMatchLevel.EXACT
            tags = self.current_station.get("tags", [])
            confidence = self.current_station.get("confidence", 0.0)
            stream_uri = self.current_station.get("url_resolved", "")
        else:
            return None

        # skill specific alternations
        if len(phrase.split(" ")) < 4:
            # 3 words or less
            confidence += 0.1

        if "radio" in phrase:
            # the term radio found
            confidence += 0.1

        # if we have ' by ' in our original phrase
        # we can be pretty sure we have an artist
        # and title so this will save us a lot of
        # missed intents
        if " by " in phrase.lower():
            confidence = 0.01

        skill_data = {
            "name": self.station_name,
            "media_uri": stream_uri,
            "confidence": confidence,
            "tags": tags,
        }
        self.log.error(f"Confidence: {confidence}")
        return self.station_name, match_level, skill_data

    def CPS_start(self, _, data):
        """Handle request from Common Play System to start playback."""
        if self.current_station is not None:
            self.handle_play_request()
        else:
            self.log.error(
                "Can't find any matching stations for = %s", self.rs.last_search_terms
            )
            dialog = ("cant.find.stations", {"search": self.rs.last_search_terms})
            self.gui.release()
            return self.end_session(dialog=dialog)

    def stop(self) -> Optional[Message]:
        """Respond to system stop commands."""
        if self._is_playing:
            self.CPS_send_status()
            self.CPS_release_output_focus()
            self.gui.release()

    def handle_gui_idle(self):
        if self._is_playing:
            gui = "RadioPlayer_mark_ii.qml"
            self.emit_start_session(gui=gui, gui_clear=GuiClear.NEVER)
            return True

        return False


def create_skill(skill_id: str):
    return RadioFreeMycroftSkill(skill_id=skill_id)
