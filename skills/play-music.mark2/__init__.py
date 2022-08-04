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
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from mycroft.messagebus import Message
from mycroft.skills import AdaptIntent, GuiClear, intent_handler
from mycroft.skills.common_play_skill import CommonPlaySkill, CPSMatchLevel
from mycroft.util.file_utils import get_cache_directory

from .skill import MpdClient, Song


class LocalMusicSkill(CommonPlaySkill):
    """Music skill that uses MPD .

    For MPD functionality, you need to:
    sudo apt-get install mpd mpc eyed3

    By default, MPD music is looked for in /media
    """

    def __init__(self, skill_id: str):
        super().__init__(skill_id=skill_id, name="LocalMusicSkill")

    def initialize(self):
        self._stream_session_id: Optional[str] = None

        # Used for local music
        self.mpd_client = MpdClient()
        self._mpd_playlist: List[Song] = []

        # Temporary directory to hold album art
        self._album_art_dir = Path(get_cache_directory(), "music", "albumart")
        self._album_art_dir.mkdir(parents=True, exist_ok=True)

        # Selected search result from YouTube
        self._player_position_ms: int = 0

        self.register_handlers()

    def register_handlers(self):
        """Register handlers for events to or from the GUI."""
        # self.bus.on("mycroft.audio.service.pause", self.handle_media_pause)
        # self.bus.on("mycroft.audio.service.resume", self.handle_media_resume)
        self.add_event("gui.namespace.displayed", self.handle_gui_namespace_displayed)
        self.bus.on("mycroft.audio.service.position", self.handle_media_position)
        self.bus.on("mycroft.audio.queue_end", self.handle_media_finished)
        # self.gui.register_handler("cps.gui.restart", self.handle_gui_restart)
        # self.gui.register_handler("cps.gui.pause", self.handle_gui_pause)
        # self.gui.register_handler("cps.gui.play", self.handle_gui_play)

    @intent_handler(AdaptIntent("").require("StopMusic"))
    def handle_stop_music(self, message):
        # for now just handles one phrase 'stop music'
        return self.stop()

    @intent_handler(AdaptIntent("").require("Show").require("Music"))
    def handle_show_music(self, message):
        dialog = None
        gui = None
        if self._mpd_playlist:
            gui = "audio_player_mark_ii.qml"
        else:
            dialog = "no-music"

        return self.end_session(dialog=dialog, gui=gui, gui_clear=GuiClear.NEVER)

    def handle_media_position(self, message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._stream_session_id:
            return

        position_ms = message.data["position_ms"]
        self.update_gui_values(
            page="audio_player_mark_ii.qml",
            data={"playerPosition": position_ms},
            overwrite=False,
        )

    def handle_media_finished(self, message):
        """Handle media playback finishing."""
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._stream_session_id:
            return

        if self._mpd_playlist:
            self._mpd_playlist = self._mpd_playlist[1:]

        if self._mpd_playlist:
            self._play_next_song()
        elif self._gui_skill_id == self.skill_id:
            # Return to idle
            self.bus.emit(Message("mycroft.gui.idle"))

    def handle_gui_namespace_displayed(self, message: Message):
        self._gui_skill_id = message.data.get("skill_id")

    def CPS_match_query_phrase(self, phrase: str) -> tuple((str, float, dict)):
        """Respond to Common Play Service query requests."""
        phrase = phrase.strip()

        if not phrase:
            return None

        phrase = phrase.replace(" by ", " ")

        for word in ["play", "listen"]:
            if phrase.startswith(word):
                phrase = phrase[len(word) :]
                break

        phrase = phrase.strip()
        phrase = phrase.replace("&", " and ")
        phrase = phrase.replace("  ", " ")
        phrase = phrase.strip()

        result = None
        try:
            self._mpd_playlist = []
            self.mpd_client.update()

            self._mpd_playlist = list(self.mpd_client.search(phrase))
            self.log.debug("Result: %s", self._mpd_playlist)
            if self._mpd_playlist:
                result = (phrase, CPSMatchLevel.EXACT, {})
        except Exception:
            self.log.exception("Error searching local music with MPD")

        return result

    def CPS_start(self, _, data):
        """Handle request from Common Play System to start playback."""
        return self._play_next_song()

    def _play_next_song(self):
        """Handle request from Common Play System to start playback."""
        if self._mpd_playlist:
            song = self._mpd_playlist[0]
            self.CPS_play(tracks=[song.uri])

            self._stream_session_id = self._mycroft_session_id
            gui_page = "audio_player_mark_ii.qml"
            gui_data = self._setup_gui(song)

            self._mycroft_session_id = self.emit_start_session(
                gui=(gui_page, gui_data),
                gui_clear=GuiClear.NEVER,
            )

        return None

    def _setup_gui(self, song: Song) -> Dict[str, Any]:
        thumbnail_path = self._get_album_art(song.file_path)
        return {
            "theme": dict(fgColor="white", bgColor="black"),
            "artist": song.artist,
            "title": f"{song.title} - {song.album}",
            "length_ms": int(song.duration_sec * 1000),
            "image": f"file://{thumbnail_path}" if thumbnail_path else None,
            "playerPosition": 0,
        }

    def stop(self) -> bool:
        dialog = None
        self.log.debug("Music Skill Stopping")
        if self._mpd_playlist:
            # self._mpd_playlist = []
            # self._stream_session_id = None
            self.CPS_release_output_focus()
            gui_clear = GuiClear.AT_END
        else:
            dialog = "no-music"
            gui_clear = GuiClear.NEVER

        return self.end_session(dialog=dialog, gui_clear=gui_clear)

    def _get_album_art(self, file_path: Union[str, Path]) -> Optional[Union[str, Path]]:
        """Use eyeD3 to get the album art from a music file"""
        try:

            encoded_path = str(file_path).encode("utf-8", "ignore")
            path_hash = hashlib.md5(encoded_path).hexdigest()

            art_path = self._album_art_dir / f"{path_hash}.jpg"

            if not art_path.is_file():
                # Write out all images from the music file, grab the first one
                with tempfile.TemporaryDirectory() as art_dir:
                    cmd = ["eyeD3", "--write-images", str(art_dir), str(file_path)]
                    subprocess.check_call(cmd)

                    art_dir = Path(art_dir)
                    for image_file in art_dir.iterdir():
                        if image_file.is_file():
                            shutil.copy(image_file, art_path)
                            break

            return art_path
        except Exception:
            self.log.exception("Failed to get album art")


def create_skill(skill_id: str):
    return LocalMusicSkill(skill_id=skill_id)
