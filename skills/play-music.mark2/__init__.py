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
import random
import shutil
import subprocess
import tempfile
import threading
import typing
from enum import Enum
from pathlib import Path

from mycroft import AdaptIntent, intent_handler
from mycroft.messagebus import Message
from mycroft.skills.common_play_skill import CommonPlaySkill, CPSMatchLevel
from mycroft.util.log import LOG
from pytube import Search

from .skill import MpdClient, Song


class State(str, Enum):
    INACTIVE = "inactive"
    SEARCHING = "searching"
    PLAYING = "playing"
    PAUSED = "paused"


class DemoMusicSkill(CommonPlaySkill):
    """Music skill that uses MPD and YouTube.

    For MPD functionality, you need to:
    sudo apt-get install mpd mpc eyed3

    By default, MPD music is looked for in ~/Music
    """

    def __init__(self, skill_id: str):
        super().__init__(skill_id=skill_id, name="DemoMusicSkill")

    def initialize(self):
        self._temp_dir = tempfile.TemporaryDirectory(prefix="mycroft-music-demo")

        self.state: State = State.INACTIVE

        # get from config
        self.platform = "mycroft_mark_2"
        self.register_gui_handlers()

        # Used for local music
        self.mpd_client = MpdClient()
        self._mpd_playlist: typing.List[Song] = []

        # Temporary directory to hold album art
        self._temp_dir = tempfile.TemporaryDirectory(prefix="mycroft-music-demo")

        # Thread used to search YouTube
        self.search_thread: typing.Optional[threading.Thread] = None

        # Event to signal main thread when search is complete
        self.search_ready = threading.Event()

        # Selected search result from YouTube
        self.result = None

        # Selected audio stream to play from search result
        self.stream = None

        self._player_position_ms: int = 0

    def register_gui_handlers(self):
        """Register handlers for events to or from the GUI."""
        self.bus.on("mycroft.audio.service.pause", self.handle_media_pause)
        self.bus.on("mycroft.audio.service.resume", self.handle_media_resume)
        self.bus.on("mycroft.audio.service.position", self.handle_media_position)
        self.bus.on("mycroft.audio.queue_end", self.handle_media_finished)
        self.gui.register_handler("cps.gui.restart", self.handle_gui_restart)
        self.gui.register_handler("cps.gui.pause", self.handle_gui_pause)
        self.gui.register_handler("cps.gui.play", self.handle_gui_play)

    @intent_handler(AdaptIntent("").require("StopMusic"))
    def handle_stop_music(self, message):
        # for now just handles one phrase 'stop music'
        with self.activity():
            self.stop()

    @intent_handler(AdaptIntent("").require("Show").require("Music"))
    def handle_show_music(self, message):
        with self.activity():
            self._setup_gui()
            self._show_gui_page("audio_player")

    def handle_gui_restart(self, msg):
        pass

    def handle_gui_pause(self, msg):
        if self.state == State.INACTIVE:
            LOG.warning("Cannot pause (inactive)")
            return

        if self.state == State.PLAYING:
            self.state = State.PAUSED

        self.gui["status"] = "Paused"
        self.bus.emit(Message("mycroft.audio.service.pause"))

    def handle_gui_play(self, msg):
        if self.state == State.INACTIVE:
            return

        if self.state == State.PAUSED:
            self.state = State.PLAYING

        self.gui["status"] = "Playing"
        self.bus.emit(Message("mycroft.audio.service.resume"))
        self.gui["position"] = self._player_position_ms

    def handle_media_pause(self, msg):
        if self.state == State.INACTIVE:
            LOG.warning("Cannot pause (inactive)")
            return

        if self.state == State.PLAYING:
            self.state = State.PAUSED

        self.gui["status"] = "Paused"

    def handle_media_resume(self, msg):
        if self.state == State.INACTIVE:
            return

        if self.state == State.PAUSED:
            self.state = State.PLAYING

        self.gui["status"] = "Playing"

    def handle_media_position(self, msg):
        position_ms = msg.data.get("position_ms")
        if (position_ms is not None) and (position_ms >= 0):
            self._player_position_ms = position_ms

    def handle_media_finished(self, message):
        """Handle media playback finishing."""
        self.state = State.INACTIVE
        self._go_inactive()

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

        # Run search in separate thread
        self._search_for_music(phrase)

        # Assume we'll get something
        return (phrase, CPSMatchLevel.EXACT, {})

    def _search_for_music(self, phrase: str):
        """Run search in separate thread to avoid CPS timeouts"""
        self.search_ready.clear()
        self.state = State.SEARCHING

        self._mpd_playlist = []
        self.result = None
        self.stream = None
        self.search_thread = threading.Thread(
            target=self._run_search, daemon=True, args=(phrase,)
        )
        self.search_thread.start()

    def _run_search(self, phrase: str):
        """Search YouTube and grab first audio stream"""
        try:
            LOG.info("Searching local music for %s", phrase)
            try:
                self.mpd_client.update()
                self._mpd_playlist = list(self.mpd_client.search(phrase))
            except Exception:
                LOG.exception("Error searching local music with MPD")
                pass

            if not self._mpd_playlist:
                LOG.info("Searching YouTube for %s", phrase)
                yt_results = Search(phrase).results

                for result in yt_results:
                    try:
                        # From the docs:
                        #
                        # Raises different exceptions based on why the video
                        # is unavailable, otherwise does nothing.
                        result.check_availability()
                    except Exception:
                        # Skip result
                        continue

                    for stream in result.streams:
                        if stream.includes_audio_track:
                            # Take the first available stream with audio
                            self.result = result
                            self.stream = stream
                            break

                    if self.stream is not None:
                        break

                if (self.stream is None) or (self.result is None):
                    LOG.error("No stream found")
                else:
                    LOG.info("Stream found")
        except Exception:
            LOG.exception("error searching YouTube")
        finally:
            self.search_ready.set()

    def _show_gui_page(self, page):
        """Show a page variation depending on platform."""
        if self.gui.connected:
            if self.platform == "mycroft_mark_2":
                qml_page = f"{page}_mark_ii.qml"
            else:
                qml_page = f"{page}_scalable.qml"
            self.gui.show_page(qml_page, override_idle=True)

    def CPS_start(self, _, data):
        """Handle request from Common Play System to start playback."""
        self.search_ready.wait(timeout=20)
        mpd_successful = len(self._mpd_playlist) > 0
        youtube_successful = (self.stream is not None) and (self.result is not None)

        if (not mpd_successful) and (not youtube_successful):
            self.speak("No search results were found.")

            # We've already been stopped by CPS, so not much else to do
            self._go_inactive()
            return

        # Reset existing media
        self.gui["status"] = "Stopped"

        self._player_position_ms = 0
        self._setup_gui()
        self.gui["status"] = "Playing"

        if mpd_successful:
            # tracks = [f"file://{song.file_path}" for song in self._mpd_playlist]
            # HACK: Choosing a random track until skill has playlist functionality
            random_track = random.choice(self._mpd_playlist)
            tracks = [f"file://{song.file_path}" for song in [random_track]]
            self.CPS_play(tracks)
        else:
            mime = "audio/mpeg"
            self.CPS_play((self.stream.url, mime))

        self._show_gui_page("audio_player")

        self.state = State.PLAYING

    def _setup_gui(self):
        self.gui["theme"] = dict(fgColor="white", bgColor="black")
        media_settings = {
            "skill": self.skill_id,
            "streaming": "true",
            "position": self._player_position_ms,
        }

        artist: str = "No artist"
        title: str = "No song"

        if self._mpd_playlist:
            song = self._mpd_playlist[0]
            artist = song.artist
            title = f"{song.title} - {song.album}"
            media_settings["length"] = song.duration_sec * 1000

            thumbnail_path = self._get_album_art(song.file_path)
            if thumbnail_path:
                media_settings["image"] = f"file://{thumbnail_path}"
        elif (self.result is not None) and (self.stream is not None):
            metadata, artist, title = None, None, None
            if len(self.result.metadata.metadata) > 0:
                metadata = self.result.metadata.metadata[0]
                artist = metadata.get("Artist")
                title = metadata.get("Song")
            # If information is missing use video author and title
            artist = artist or self.result.author
            title = title or self.result.title
            if title.startswith(artist + " - "):
                title = title.replace(artist + " - ", "")

            media_settings["image"] = self.result.thumbnail_url
            media_settings["length"] = self.result.length * 1000

        media_settings["artist"] = artist
        media_settings["song"] = title

        self.gui["media"] = media_settings
        self.gui["position"] = self._player_position_ms

    def stop(self) -> bool:
        LOG.debug("Music Skill Stopping")
        self.CPS_release_output_focus()
        return self._go_inactive()

    def _go_inactive(self):
        if self.state == State.PLAYING:
            self.state = State.PAUSED
        else:
            self.state = State.INACTIVE

        self.gui["status"] = "Paused"
        if self.gui.connected:
            self.gui.release()

        LOG.info("Music is now inactive")
        return True

    def shutdown(self):
        self._temp_dir.cleanup()

    def _get_album_art(
        self, file_path: typing.Union[str, Path]
    ) -> typing.Optional[typing.Union[str, Path]]:
        """Use eyeD3 to get the album art from a music file"""
        try:

            encoded_path = str(file_path).encode("utf-8", "ignore")
            path_hash = hashlib.md5(encoded_path).hexdigest()

            art_path = Path(self._temp_dir.name) / f"{path_hash}.jpg"

            if not art_path.is_file():
                # Write out all images from the music file, grab the first one
                with tempfile.TemporaryDirectory(dir=self._temp_dir.name) as art_dir:
                    cmd = ["eyeD3", "--write-images", str(art_dir), str(file_path)]
                    subprocess.check_call(cmd)

                    art_dir = Path(art_dir)
                    for image_file in art_dir.iterdir():
                        if image_file.is_file():
                            shutil.copy(image_file, art_path)
                            break

            return art_path
        except Exception:
            LOG.exception("Failed to get album art")


def create_skill(skill_id: str):
    return DemoMusicSkill(skill_id=skill_id)
