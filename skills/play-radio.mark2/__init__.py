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

import requests
from mycroft.skills import GuiClear, intent_handler
from mycroft.skills.common_play_skill import CommonPlaySkill, CPSMatchLevel

from .RadioStations import RadioStations

# Minimum confidence levels
CONF_EXACT_MATCH = 0.9
CONF_LIKELY_MATCH = 0.7
CONF_GENERIC_MATCH = 0.6

"""
MIA - RestartRadio.intent
"""


class RadioFreeMycroftSkill(CommonPlaySkill):
    """simple streaming radio skill"""

    def __init__(self, skill_id: str):
        super().__init__(skill_id=skill_id, name="RfmSkill")
        self.rs = RadioStations()
        self.now_playing = None
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

    def initialize(self):
        self.register_gui_handlers()

    def register_gui_handlers(self):
        """Register handlers for events to or from the GUI."""
        self.bus.on("mycroft.audio.service.playing", self.handle_media_playing)
        self.bus.on("mycroft.audio.service.stopped", self.handle_media_stopped)
        self.bus.on(
            "mycroft.audio.service.pause", self.handle_audioservice_status_change
        )
        self.bus.on(
            "mycroft.audio.service.resume", self.handle_audioservice_status_change
        )
        self.bus.on(
            "mycroft.audio.queue_end",
            self.handle_media_finished,
        )
        self.gui.register_handler(
            "cps.gui.pause", "AudioPlayer_scalable.qml", self.handle_gui_status_change
        )
        self.gui.register_handler(
            "cps.gui.play", "AudioPlayer_scalable.qml", self.handle_gui_status_change
        )

    def handle_audioservice_status_change(self, message):
        """Handle changes in playback status from the Audioservice.
        Eg when someone verbally asks to pause.
        """
        if not self.now_playing:
            return

        command = message.msg_type.split(".")[-1]
        if command == "resume":
            new_status = "Playing"
        elif command == "pause":
            new_status = "Paused"

        # TODO
        # self.gui["status"] = new_status
        self.update_gui_values("AudioPlayer_scalable.qml", {"status": new_status})

    def handle_media_finished(self, _):
        """Handle media playback finishing."""
        self.log.warning("RadioMediaFinished! should never get here!")

    def handle_media_playing(self, message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id == self._stream_session_id:
            self._is_playing = True
        else:
            self._is_playing = False

    def handle_media_stopped(self, message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id == self._stream_session_id:
            self._is_playing = False

    def handle_gui_status_change(self, message):
        """Handle play and pause status changes from the GUI.
        This notifies the audioservice. The GUI state only changes once the
        audioservice emits the relevant messages to say the state has changed.
        """
        if not self.now_playing:
            return

        command = message.msg_type.split(".")[-1]
        if command == "play":
            self.log.info("Audio resumed by GUI.")
            self.CPS_resume()
        elif command == "pause":
            self.log.info("Audio paused by GUI.")
            self.CPS_pause()

    def update_radio_theme(self, status):
        if self.rs.genre_to_play and self.rs.genre_to_play in self.genre_images.keys():
            self.img_pth = self.find_resource(
                self.genre_images[self.rs.genre_to_play], "ui/images"
            )
        else:
            self.img_pth = self.find_resource("genre_generic_radio.svg", "ui/images")

        channel_info = "%s/%s" % (self.rs.index + 1, len(self.rs.stations))
        station_name = self.current_station.get("name", "").replace("\n", "")
        gui_data = {
            "theme_bg": self.bg_color,
            "theme_fg": self.fg_color,
            "media_image": self.img_pth,
            "media_artist": " NOW STREAMING: " + station_name,
            "media_track": "Track",
            "media_album": self.rs.genre_to_play,
            "media_skill": self.skill_id,
            "media_current_station_info": channel_info,
            "media_streaming": True,
            "media_status": status,
        }
        return ("AudioPlayer_scalable.qml", gui_data)

    def setup_for_play(self, utterance):
        self.rs.get_stations(utterance)
        self.current_station = self.rs.get_current_station()

    def handle_play_request(self):
        """play the current station if there is one"""
        speak = None
        gui = None

        if self.current_station is None:
            self.log.error(
                "Can't find any matching stations for = %s", self.rs.last_search_terms
            )
            speak = f"Can not find any {self.rs.last_search_terms} stations"
        else:
            stream_uri = self.current_station.get("url_resolved", "")
            station_name = self.current_station.get("name", "").replace("\n", "")

            mime = self.rs.find_mime_type(stream_uri)

            self.CPS_play((stream_uri, mime))

            self.now_playing = "Now Playing"
            gui = self.update_radio_theme(self.now_playing)
            self._stream_session_id = self._mycroft_session_id
            self._mycroft_session_id = self.emit_start_session(
                gui=gui,
                gui_clear=GuiClear.NEVER,
            )

            # cast to str for json serialization
            self.CPS_send_status(image=self.img_pth, artist=station_name)

        return speak, gui

    ## Intents
    @intent_handler("HelpRadio.intent")
    def handle_radio_help(self, _):
        speak = None
        gui = None

        speak = """Mycroft radio allows you to stream music and other content from a variety of free sources.
            If you ask me to play a specific type of music, like play Jazz, or play rock, I work very well.
            Play artist works Oh Kay for some artists but radio stations are not really artist specific.
            Next station and next channel or previous station and previous channel will select a different channel or station.
            You can also say change radio to change the radio Theme.
            For the graphical you eye."""

        return self.end_session(speak=speak, gui=gui, gui_clear=GuiClear.NEVER)

    @intent_handler("ChangeRadio.intent")
    def handle_change_radio(self, _):
        """change ui theme"""
        dialog = None
        gui = None

        if self.now_playing is not None:
            self.log.info(
                "change_radio request, now playing = %s" % (self.now_playing,)
            )
            if self.fg_color == "white":
                self.fg_color = "black"
                self.bg_color = "white"
            else:
                self.fg_color = "white"
                self.bg_color = "black"

            gui = self.update_radio_theme("Playing")
        else:
            dialog = "no.radio.playing"

        return self.end_session(dialog=dialog, gui=gui, gui_clear=GuiClear.NEVER)

    @intent_handler("ShowRadio.intent")
    def handle_show_radio(self, _):
        dialog = None
        gui = None

        if self.now_playing is not None:
            gui = "AudioPlayer_scalable.qml"
        else:
            dialog = "no.radio.playing"

        return self.end_session(dialog=dialog, gui=gui, gui_clear=GuiClear.NEVER)

    @intent_handler("NextStation.intent")
    def handle_next_station(self, message):
        exit_flag = False
        ctr = 0
        while not exit_flag and ctr < self.rs.get_station_count():
            new_current_station = self.rs.get_next_station()
            self.current_station = new_current_station
            self.stream_uri = self.current_station.get("url_resolved", "")
            self.station_name = self.current_station.get("name", "")
            self.station_name = self.station_name.replace("\n", " ")

            try:
                self.handle_play_request()
                exit_flag = True
            except:
                self.log.error("Caught Exception")

            ctr += 1

    @intent_handler("PreviousStation.intent")
    def handle_previous_station(self, message):
        exit_flag = False
        ctr = 0
        while not exit_flag and ctr < self.rs.get_station_count():
            new_current_station = self.rs.get_previous_station()
            self.current_station = new_current_station
            self.stream_uri = self.current_station.get("url_resolved", "")
            self.station_name = self.current_station.get("name", "")
            self.station_name = self.station_name.replace("\n", " ")

            try:
                self.handle_play_request()
                exit_flag = True
            except:
                self.log.error("Caught Exception")

            ctr += 1

    @intent_handler("NextChannel.intent")
    def handle_next_channel(self, message):
        self.rs.get_next_channel()
        self.handle_next_station(message)

    @intent_handler("PreviousChannel.intent")
    def handle_previous_channel(self, message):
        self.rs.get_previous_channel()
        self.handle_previous_station(message)

    @intent_handler("ListenToRadio.intent")
    def handle_listen_intent(self, message):
        if message.data:
            self.setup_for_play(message.data.get("utterance", ""))
            speak, gui = self.handle_play_request()
            return self.end_session(speak=speak, gui=gui, gui_clear=GuiClear.NEVER)

        return self.end_session()

    def play_current(self):
        exit_flag = False
        ctr = 0
        while not exit_flag and ctr < self.rs.get_station_count():
            new_current_station = self.rs.get_next_station()
            self.current_station = new_current_station
            self.stream_uri = self.current_station.get("url_resolved", "")
            self.station_name = self.current_station.get("name", "")
            self.station_name = self.station_name.replace("\n", " ")

            try:
                self.handle_play_request()
                exit_flag = True
            except:
                self.log.error("Caught Exception")

            ctr += 1

        if not exit_flag:
            self.log.error(
                "of %s stations, none work!" % (self.rs.get_station_count(),)
            )

    @intent_handler("TurnOnRadio.intent")
    def handle_turnon_intent(self, _):
        if self.current_station is None:
            self.setup_for_play(self.rs.get_next_channel())
        self.play_current()

    @intent_handler("StopRadio.intent")
    def handle_stop_radio(self, _):
        self.stop()

    ## Common query stuff
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

        return self.station_name, match_level, skill_data

    def CPS_start(self, _, data):
        """Handle request from Common Play System to start playback."""
        self.handle_play_request()

    def stop(self) -> None:
        """Respond to system stop commands."""
        self.now_playing = None
        self.CPS_send_status()
        self.CPS_release_output_focus()
        gui_clear = GuiClear.AT_END

        return self.end_session(dialog=None, gui_clear=gui_clear)

    def handle_gui_idle(self):
        if self._is_playing:
            gui = "AudioPlayer_scalable.qml"
            self.emit_start_session(gui=gui, gui_clear=GuiClear.NEVER)
            return True

        return False


def create_skill(skill_id: str):
    return RadioFreeMycroftSkill(skill_id=skill_id)
