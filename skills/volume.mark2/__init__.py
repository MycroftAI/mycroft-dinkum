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
#
from os.path import dirname, join

from adapt.intent import IntentBuilder
from mycroft.messagebus.message import Message
from mycroft.skills import (
    GuiClear,
    MessageSend,
    MycroftSkill,
    intent_handler,
    skill_api_method,
)
from mycroft.util.file_utils import resolve_resource_file
from mycroft.util.parse import extract_number


class VolumeSkill(MycroftSkill):
    """
    Control the audio volume for the Mycroft system

    Terminology:
       "Level" =  Mycroft volume levels, from 0 to 10
    """

    MIN_LEVEL = 0
    MAX_LEVEL = 10

    VOLUME_WORDS = {"loud": 9, "normal": 6, "quiet": 3}

    def _translate_volume_words(self):
        """Translate VOLUME_WORDS keys for non-english support.

        Any words in volume.words.value must also be contained in Level.voc
        """
        volume_words = self.translate_namedvalues("volume.words")
        if volume_words:
            new_volume_words = {}
            for volume_words_key in self.VOLUME_WORDS:
                if volume_words.get(volume_words_key):
                    new_volume_words[
                        volume_words.get(volume_words_key)
                    ] = self.VOLUME_WORDS[volume_words_key]
            self.VOLUME_WORDS = new_volume_words

    def __init__(self):
        super(VolumeSkill, self).__init__("VolumeSkill")
        self.settings["min_volume"] = self.settings.get("min_volume", 0)
        self.settings["max_volume"] = self.settings.get("max_volume", 100)
        self.settings["default_level"] = self.settings.get(
            "default_level", VolumeSkill.VOLUME_WORDS["normal"]
        )
        self.volume_sound = resolve_resource_file("snd/beep.wav")
        self._translate_volume_words()
        self.vol_before_mute = None

    def initialize(self):
        # Register handlers to detect percentages as reported by STT
        for i in range(101):  # numbers 0 to 100
            self.register_vocabulary(str(i) + "%", "Percent")

        # Register handlers for messagebus events
        # self.add_event("mycroft.volume.increase", self.handle_increase_volume)
        # self.add_event("mycroft.volume.decrease", self.handle_decrease_volume)
        # self.add_event("mycroft.volume.mute", self.handle_mute_volume)
        # self.add_event("mycroft.volume.unmute", self.handle_unmute_volume)

    @skill_api_method
    def _set_volume(self, vol: int, emit: bool = True):
        """Set the system volume.

        First tries to set volume in ALSA if available.
        TODO: Remove this and control volume at the Enclosure level

        Args:
            vol: volume in range 0-100
            emit: whether to emit a 'mycroft.volume.set' msg
        """
        if emit:
            volume_percentage = self._volume_to_percent(vol)
            self.bus.emit(
                Message("mycroft.volume.set", data={"percent": volume_percentage})
            )

    def _volume_to_percent(self, vol: int) -> float:
        vol = max(0, min(100, vol))
        return vol / 100.0

    # Change Volume to X (Number 0 to) Intent Handlers
    @intent_handler(
        IntentBuilder("SetVolume")
        .require("Volume")
        .optionally("Increase")
        .optionally("Decrease")
        .optionally("To")
        .require("Level")
    )
    def handle_set_volume(self, message):
        default_vol = self.__get_system_volume(50)

        level = self.__get_volume_level(message, default_vol)
        self._set_volume(self.__level_to_volume(level))
        if level >= self.MAX_LEVEL:
            dialog = "max.volume"
        else:
            dialog = ("set.volume", {"volume": level})

        return self.end_session(dialog=dialog)

    # Set Volume Percent Intent Handlers
    @intent_handler(
        IntentBuilder("SetVolumePercent")
        .require("Volume")
        .optionally("Increase")
        .optionally("Decrease")
        .optionally("To")
        .require("Percent")
    )
    def handle_set_volume_percent(self, message):
        percent = extract_number(message.data["utterance"].replace("%", ""))
        percent = int(percent)
        self._set_volume(percent)
        dialog = ("set.volume.percent", {"level": percent})

        return self.end_session(dialog=dialog)

    # Volume Status Intent Handlers
    @intent_handler(IntentBuilder("QueryVolume").optionally("Query").require("Volume"))
    def handle_query_volume(self, message):
        level = self.__volume_to_level(self.__get_system_volume(0, show=True))
        dialog = ("volume.is", {"volume": round(level)})

        return self.end_session(dialog=dialog)

    @intent_handler("Query.intent")
    def handle_query_volume_phrase(self, message):
        return self.handle_query_volume(message)

    def __communicate_volume_change(self, message, dialog, code, changed):
        audio_alert = None
        dialog = None

        play_sound = message.data.get("play_sound", False)
        if play_sound:
            if changed and self.volume_sound:
                sound_uri = f"file://{self.volume_sound}"
                audio_alert = sound_uri
        else:
            if (not changed) and (code != 0):
                dialog = ("already.max.volume", {"volume": code})

        return self.end_session(
            audio_alert=audio_alert, dialog=dialog, gui_clear=GuiClear.NEVER
        )

    # Increase Volume Intent Handlers
    @intent_handler(
        IntentBuilder("IncreaseVolume").require("Volume").require("Increase")
    )
    def handle_increase_volume(self, message):
        return self.__communicate_volume_change(
            message, "increase.volume", *self.__update_volume(+1)
        )

    @intent_handler(
        IntentBuilder("IncreaseVolumeSet")
        .require("Set")
        .optionally("Volume")
        .require("Increase")
    )
    def handle_increase_volume_set(self, message):
        return self.handle_increase_volume(message)

    @intent_handler("Increase.intent")
    def handle_increase_volume_phrase(self, message):
        return self.handle_increase_volume(message)

    # Decrease Volume Intent Handlers
    @intent_handler(
        IntentBuilder("DecreaseVolume").require("Volume").require("Decrease")
    )
    def handle_decrease_volume(self, message):
        return self.__communicate_volume_change(
            message, "decrease.volume", *self.__update_volume(-1)
        )

    @intent_handler(
        IntentBuilder("DecreaseVolumeSet")
        .require("Set")
        .optionally("Volume")
        .require("Decrease")
    )
    def handle_decrease_volume_set(self, message):
        return self.handle_decrease_volume(message)

    @intent_handler("Decrease.intent")
    def handle_decrease_volume_phrase(self, message):
        return self.handle_decrease_volume(message)

    # Maximum Volume Intent Handlers
    @intent_handler(
        IntentBuilder("MaxVolume")
        .optionally("Set")
        .require("Volume")
        .optionally("Increase")
        .require("MaxVolume")
    )
    def handle_max_volume(self, message):
        dialog = None

        self._set_volume(self.settings["max_volume"])
        speak_message = message.data.get("speak_message", True)
        if speak_message:
            dialog = "max.volume"

        return self.end_session(dialog=dialog)

    @intent_handler(
        IntentBuilder("MaxVolumeIncreaseMax")
        .require("Increase")
        .optionally("Volume")
        .require("MaxVolume")
    )
    def handle_max_volume_increase_to_max(self, message):
        return self.handle_max_volume(message)

    @intent_handler("MaxVolume.intent")
    def handle_max_volume_increase(self, message):
        return self.handle_max_volume(message)

    # Mute Volume Intent Handlers
    @intent_handler(IntentBuilder("MuteVolume").require("Volume").require("Mute"))
    def handle_mute_volume(self, message):
        dialog = None
        if message.data.get("speak_message", True):
            dialog = "mute.volume"

        self.vol_before_mute = self.__get_system_volume()
        message = Message("mycroft.volume.mute")
        return self.end_session(
            dialog=dialog, message=message, message_send=MessageSend.AT_END
        )

    @intent_handler("Mute.intent")
    def handle_mute_short_phrases(self, message):
        """Handle short but explicit mute phrases

        Examples:
        - Mute
        - shut up
        - be quiet
        """
        return self.handle_mute_volume(message)

    # Unmute/Reset Volume Intent Handlers
    @intent_handler(IntentBuilder("UnmuteVolume").require("Volume").require("Unmute"))
    def handle_unmute_volume(self, message):
        dialog = None
        if self.vol_before_mute is None:
            vol = self.__level_to_volume(self.settings["default_level"])
        else:
            vol = self.vol_before_mute

        level = self.__volume_to_level(vol)
        if message.data.get("speak_message", True):
            dialog = ("reset.volume", {"volume": level})

        message = Message("mycroft.volume.unmute")
        return self.end_session(
            dialog=dialog, message=message, message_send=MessageSend.AT_START
        )

    @intent_handler("Unmute.intent")
    def handle_unmute_short_phrases(self, message):
        """Handle short but explicit unmute phrases

        Examples:
        - Unmute
        - Turn mute off
        - Turn sound back on
        """
        return self.handle_unmute_volume(message)

    # -------------------------------------------------------------------------

    def __volume_to_level(self, volume):
        """
        Convert a 'volume' to a 'level'

        Args:
            volume (int): min_volume..max_volume
        Returns:
            int: the equivalent level
        """
        range = self.MAX_LEVEL - self.MIN_LEVEL
        min_vol = self.settings["min_volume"]
        max_vol = self.settings["max_volume"]
        prop = float(volume - min_vol) / max_vol
        level = int(round(self.MIN_LEVEL + range * prop))
        if level > self.MAX_LEVEL:
            level = self.MAX_LEVEL
        elif level < self.MIN_LEVEL:
            level = self.MIN_LEVEL
        return level

    def __level_to_volume(self, level):
        """
        Convert a 'level' to a 'volume'

        Args:
            level (int): 0..MAX_LEVEL
        Returns:
            int: the equivalent volume
        """
        range = self.settings["max_volume"] - self.settings["min_volume"]
        prop = float(level) / self.MAX_LEVEL
        volume = int(round(self.settings["min_volume"] + int(range) * prop))

        return volume

    @staticmethod
    def __bound_level(level):
        if level > VolumeSkill.MAX_LEVEL:
            level = VolumeSkill.MAX_LEVEL
        elif level < VolumeSkill.MIN_LEVEL:
            level = VolumeSkill.MIN_LEVEL
        return level

    def __update_volume(self, change=0):
        """
        Attempt to change audio level

        Args:
            change (int): +1 or -1; the step to change by

        Returns: tuple(new level code int(0..10),
                       whether level changed (bool))
        """
        old_level = self.__volume_to_level(self.__get_system_volume(0))
        new_level = self.__bound_level(old_level + change)
        self.enclosure.eyes_volume(new_level)
        self._set_volume(self.__level_to_volume(new_level))
        return new_level, new_level != old_level

    def __get_system_volume(self, default=50, show=False):
        """Get volume by asking on the messagebus.

        The show parameter should only be True when a user is requesting
        the volume and not the system.
        TODO: What to report if no response received from mycroft.volume.get?
              Returning a default value seems inadequate. We should raise an error
              and do something about it.
        """
        vol = default
        vol_msg = self.bus.wait_for_response(
            Message("mycroft.volume.get", {"show": show})
        )
        if vol_msg:
            vol = int(vol_msg.data["percent"] * 100)

        return vol

    def __get_volume_level(self, message, default=None):
        """Retrieves volume from message."""
        level_str = str(message.data.get("Level", default))
        level = self.settings["default_level"]

        try:
            level = self.VOLUME_WORDS[level_str]
        except KeyError:
            try:
                level = int(extract_number(level_str))
                if level == self.MAX_LEVEL + 1:
                    # Assume that user meant max volume
                    level = self.MAX_LEVEL
                elif level > self.MAX_LEVEL:
                    # Guess that the user said something like 100 percent
                    # so convert that into a level value
                    level = self.MAX_LEVEL * level / 100
            except ValueError:
                pass

        level = self.__bound_level(level)
        return level


def create_skill():
    return VolumeSkill()
