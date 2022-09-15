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
from typing import Optional

from adapt.intent import IntentBuilder
from mycroft.messagebus.message import Message
from mycroft.skills import GuiClear, MycroftSkill, intent_handler

STATUS_KEYS = ["track", "artist", "album", "image"]


class PlaybackControlSkill(MycroftSkill):
    def __init__(self, skill_id: str):
        super().__init__(skill_id=skill_id, name="Playback Control Skill")
        self.phrase: Optional[str] = None
        self.reply_message: Optional[Message] = None
        self._stream_session_id: Optional[str] = None

    def initialize(self):
        self.add_event("play:query.response", self.handle_play_query_response)
        self.add_event("mycroft.audio.service.playing", self.handle_stream_playing)

    def handle_stream_playing(self, message: Message):
        self._stream_session_id = message.data.get("mycroft_session_id")

    # Handle common audio intents.  'Audio' skills should listen for the
    # common messages:
    #   self.add_event('mycroft.audio.service.next', SKILL_HANDLER)
    #   self.add_event('mycroft.audio.service.prev', SKILL_HANDLER)
    #   self.add_event('mycroft.audio.service.pause', SKILL_HANDLER)
    #   self.add_event('mycroft.audio.service.resume', SKILL_HANDLER)

    # def clear_gui_info(self):
    #     """Clear the gui variable list."""
    #     # Initialize track info variables
    #     for k in STATUS_KEYS:
    #         self.gui[k] = ""

    # @intent_handler(IntentBuilder('').require('Next').require("Track"))
    # def handle_next(self, message):
    #     with self.activity():
    #         self.audio_service.next()

    # @intent_handler(IntentBuilder('').require('Prev').require("Track"))
    # def handle_prev(self, message):
    #     with self.activity():
    #         self.audio_service.prev()

    @intent_handler(IntentBuilder("").require("Pause").exactly())
    def handle_pause(self, message):
        self.bus.emit(
            Message(
                "play:pause",
                # data={"mycroft_session_id": self._stream_session_id},
            )
        )

    @intent_handler(IntentBuilder("").one_of("PlayResume", "Resume").exactly())
    def handle_play(self, message):
        """Resume playback if paused"""
        self.bus.emit(
            Message(
                "play:resume",
                # data={"mycroft_session_id": self._stream_session_id},
            )
        )

    # def stop(self, message=None):
    #     self.clear_gui_info()

    #     self.log.info(
    #         "Audio service status: " "{}".format(self.audio_service.track_info())
    #     )
    #     if self.audio_service.is_playing:
    #         self.audio_service.stop()
    #         self.has_played = False
    #         return True
    #     else:
    #         return False

    @intent_handler("play.rx")
    def play(self, message):
        # Playback flow
        # 1. We continue the current session, sending the 'play:query' message to Common Play skills
        # 2. Until the timeout is reached, we track the replies in handle_play_query_response
        # 3. When the timeout occurs, the skill with the highest confidence is sent a 'play:start' message
        self.reply_message = None
        self.phrase = message.data["Phrase"]
        self.schedule_event(
            self._play_query_timeout,
            5,
            data={
                "phrase": self.phrase,
                "mycroft_session_id": self._mycroft_session_id,
            },
            name="PlayQueryTimeout",
        )

        # Now we place a query on the messsagebus for anyone who wants to
        # attempt to service a 'play.request' message.  E.g.:
        #   {
        #      "type": "play.query",
        #      "phrase": "the news" / "tom waits" / "madonna on Pandora"
        #   }
        #
        # One or more skills can reply with a 'play.request.reply', e.g.:
        #   {
        #      "type": "play.request.response",
        #      "target": "the news",
        #      "skill_id": "<self.skill_id>",
        #      "conf": "0.7",
        #      "callback_data": "<optional data>"
        #   }
        # This means the skill has a 70% confidence they can handle that
        # request.  The "callback_data" is optional, but can provide data
        # that eliminates the need to re-parse if this reply is chosen.
        return self.continue_session(
            dialog="just.one.moment",
            speak_wait=False,
            message=Message("play:query", data={"phrase": self.phrase}),
            gui="SearchingForMusic.qml",
            gui_clear=GuiClear.NEVER,
        )

    def handle_play_query_response(self, message):
        if message.data.get("mycroft_session_id") != self._mycroft_session_id:
            # Different session now
            return

        searching = message.data.get("searching")
        if searching:
            # No answer yet
            return

        try:
            skill_id = message.data["skill_id"]
            conf = message.data.get("conf")
            if conf is None:
                self.log.debug("Skill couldn't handle request: %s", skill_id)
                return

            phrase = message.data["phrase"]

            if (not self.reply_message) or (conf > self.reply_message.data["conf"]):
                self.log.info(
                    "Reply from %s: %s (confidence=%s)", skill_id, phrase, conf
                )
                self.reply_message = message
        except Exception:
            self.log.exception("Error handling playback reply")

    def _play_query_timeout(self, message):
        if message.data.get("mycroft_session_id") != self._mycroft_session_id:
            # Different session now
            return

        try:
            if self.reply_message is not None:
                skill_id = self.reply_message.data["skill_id"]
                self.log.info("Playing with: %s", skill_id)

                start_data = {
                    "skill_id": skill_id,
                    "phrase": self.phrase,
                    "callback_data": self.reply_message.data.get("callback_data"),
                    "mycroft_session_id": self._mycroft_session_id,
                }
                self.bus.emit(self.reply_message.forward("play:start", start_data))
            else:
                self.log.info("No matches for %s", self.phrase)
                dialog = ("cant.play", {"phrase": self.phrase})
                result = self.end_session(dialog=dialog, gui_clear=GuiClear.AT_END)
                self.bus.emit(result)
        except Exception:
            self.log.exception("Error processing playback results")


def create_skill(skill_id: str):
    return PlaybackControlSkill(skill_id=skill_id)
