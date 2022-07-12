# Copyright 2017 Mycroft AI Inc.
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
from alsaaudio import Mixer, mixers as alsa_mixers
from os.path import dirname, join

from adapt.intent import IntentBuilder
from mycroft.messagebus.message import Message
from mycroft.skills import MycroftSkill, intent_handler, skill_api_method
from mycroft.util.parse import extract_number


ALSA_PLATFORMS = ["mycroft_mark_1", "picroft", "unknown"]
ALSA_MIXER_NAMES = ["Master", "PCM", "Digital", "Playback"]


class VolumeSkill(MycroftSkill):
    """
    Control the audio volume for the Mycroft system

    Terminology:
       "Level" =  Mycroft volume levels, from 0 to 10
       "Volume" = ALSA mixer setting, from 0 to 100
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
        self.settings["default_level"] = 6  # can be 0 (off) to 10 (max)
        self.settings["min_volume"] = 0  # can be 0 to 100
        if self.config_core["enclosure"].get("platform") == "mycroft_mark_1":
            self.settings["max_volume"] = 83  # can be 0 to 83
        else:
            self.settings["max_volume"] = 100  # can be 0 to 100
        self.volume_sound = join(dirname(__file__), "blop-mark-diangelo.wav")
        self.vol_before_mute = None
        self._mixer = None
        self._translate_volume_words()

    def _clear_mixer(self):
        """For Unknown platforms reinstantiate the mixer.

        For mycroft_mark_1 do not reinstantiate the mixer.
        """
        platform = self.config_core["enclosure"].get("platform", "unknown")
        if platform != "mycroft_mark_1":
            self._mixer = None

    def _get_mixer(self):
        self.log.debug("Finding Alsa Mixer for control...")
        mixer = None
        try:
            mixers = alsa_mixers()
            if len(mixers) == 1:
                # If there are only 1 mixer use that one
                mixer = Mixer(mixers[0])
            else:
                # Look for known mixer names
                for mixer_name in mixers:
                    if mixer_name in ALSA_MIXER_NAMES:
                        mixer = Mixer(mixer_name)
                        break

                if mixer is None:
                    # should be equivalent to 'Master'
                    mixer = Mixer()
        except Exception:
            # Retry instanciating the mixer with the built-in default
            try:
                mixer = Mixer()
            except Exception as e:
                self.log.error("Couldn't allocate mixer, {}".format(repr(e)))
        self._mixer = mixer
        return mixer

    def initialize(self):
        # Register handlers to detect percentages as reported by STT
        for i in range(101):  # numbers 0 to 100
            self.register_vocabulary(str(i) + "%", "Percent")

        # Register handlers for messagebus events
        self.add_event("mycroft.volume.increase", self.handle_increase_volume)
        self.add_event("mycroft.volume.decrease", self.handle_decrease_volume)
        self.add_event("mycroft.volume.mute", self.handle_mute_volume)
        self.add_event("mycroft.volume.unmute", self.handle_unmute_volume)
        self.add_event("recognizer_loop:record_begin", self.duck)
        self.add_event("recognizer_loop:record_end", self.unduck)

        self.vol_before_mute = self.__get_system_volume()

    @property
    def mixer(self):
        platform = self.config_core["enclosure"].get("platform", "unknown")
        if platform in ALSA_PLATFORMS:
            return self._mixer or self._get_mixer()
        else:
            return None

    @skill_api_method
    def _set_volume(self, vol: int, emit: bool = True):
        """Set the system volume.

        First tries to set volume in ALSA if available.
        TODO: Remove this and control volume at the Enclosure level

        Args:
            vol: volume in range 0-100
            emit: whether to emit a 'mycroft.volume.set' msg
        """
        # Update ALSA
        if self.mixer:
            self.log.debug(f"Setting volume to {vol}")
            self.mixer.setvolume(vol)

        if emit:
            volume_percentage = vol / 100.0
            # Notify non-ALSA systems of volume change
            self.bus.emit(Message("mycroft.volume.set", data={"percent": volume_percentage}))

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
        with self.activity():
            self._clear_mixer()
            default_vol = self.__get_system_volume(50)

            level = self.__get_volume_level(message, default_vol)
            self._set_volume(self.__level_to_volume(level))
            if level == self.MAX_LEVEL:
                self.speak_dialog("max.volume", wait=True)
            else:
                self.speak_dialog("set.volume", data={"volume": level}, wait=True)

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
        with self.activity():
            self._clear_mixer()
            percent = extract_number(message.data["utterance"].replace("%", ""))
            percent = int(percent)
            self._set_volume(percent)
            self.speak_dialog("set.volume.percent", data={"level": percent}, wait=True)

    # Volume Status Intent Handlers
    @intent_handler(IntentBuilder("QueryVolume").optionally("Query").require("Volume"))
    def handle_query_volume(self, message):
        with self.activity():
            self._clear_mixer()
            level = self.__volume_to_level(self.__get_system_volume(0, show=True))
            self.speak_dialog("volume.is", data={"volume": round(level)}, wait=True)

    @intent_handler("Query.intent")
    def handle_query_volume_phrase(self, message):
        # will be in activity
        self.handle_query_volume(message)

    def __communicate_volume_change(self, message, dialog, code, changed):
        play_sound = message.data.get("play_sound", False)
        if play_sound:
            if changed:
                sound_uri = f"file://{self.volume_sound}"
                self.play_sound_uri(sound_uri)
        else:
            if (not changed) and (code != 0):
                self.speak_dialog(
                    "already.max.volume", data={"volume": code}, wait=True
                )

    # Increase Volume Intent Handlers
    @intent_handler(
        IntentBuilder("IncreaseVolume").require("Volume").require("Increase")
    )
    def handle_increase_volume(self, message):
        with self.activity():
            self.__communicate_volume_change(
                message, "increase.volume", *self.__update_volume(+1)
            )

    @intent_handler(
        IntentBuilder("IncreaseVolumeSet")
        .require("Set")
        .optionally("Volume")
        .require("Increase")
    )
    def handle_increase_volume_set(self, message):
        self._clear_mixer()

        # will be in activity
        self.handle_increase_volume(message)

    @intent_handler("Increase.intent")
    def handle_increase_volume_phrase(self, message):
        self._clear_mixer()

        # will be in activity
        self.handle_increase_volume(message)

    # Decrease Volume Intent Handlers
    @intent_handler(
        IntentBuilder("DecreaseVolume").require("Volume").require("Decrease")
    )
    def handle_decrease_volume(self, message):
        with self.activity():
            self.__communicate_volume_change(
                message, "decrease.volume", *self.__update_volume(-1)
            )

    @intent_handler(
        IntentBuilder("DecreaseVolumeSet")
        .require("Set")
        .optionally("Volume")
        .require("Decrease")
    )
    def handle_decrease_volume_set(self, message):
        # will be in activity
        self.handle_decrease_volume(message)

    @intent_handler("Decrease.intent")
    def handle_decrease_volume_phrase(self, message):
        # will be in activity
        self.handle_decrease_volume(message)

    # Maximum Volume Intent Handlers
    @intent_handler(
        IntentBuilder("MaxVolume")
        .optionally("Set")
        .require("Volume")
        .optionally("Increase")
        .require("MaxVolume")
    )
    def handle_max_volume(self, message):
        # will be in activity
        self._clear_mixer()
        self._set_volume(self.settings["max_volume"])
        speak_message = message.data.get("speak_message", True)
        if speak_message:
            self.speak_dialog("max.volume", wait=True)

    @intent_handler(
        IntentBuilder("MaxVolumeIncreaseMax")
        .require("Increase")
        .optionally("Volume")
        .require("MaxVolume")
    )
    def handle_max_volume_increase_to_max(self, message):
        # will be in activity
        self.handle_max_volume(message)

    @intent_handler("MaxVolume.intent")
    def handle_max_volume_increase(self, message):
        # will be in activity
        self.handle_max_volume(message)

    def duck(self, message):
        self._clear_mixer()
        if self.settings.get("ducking", True):
            self._mute_volume()

    def unduck(self, message):
        self._clear_mixer()
        if self.settings.get("ducking", True):
            self._unmute_volume()

    @skill_api_method
    def _mute_volume(self, message=None, speak=False):
        self.log.info("Muting audio output.")
        self.vol_before_mute = self.__get_system_volume()
        self.log.debug(self.vol_before_mute)
        if speak:
            self.speak_dialog("mute.volume", wait=True)
        self._set_volume(0)

    # Mute Volume Intent Handlers
    @intent_handler(IntentBuilder("MuteVolume").require("Volume").require("Mute"))
    def handle_mute_volume(self, message):
        with self.activity():
            self._clear_mixer()
            self._mute_volume(speak=message.data.get("speak_message", True))

    @intent_handler("Mute.intent")
    def handle_mute_short_phrases(self, message):
        """Handle short but explicit mute phrases

        Examples:
        - Mute
        - shut up
        - be quiet
        """
        self.handle_mute_volume(message)

    def _unmute_volume(self, message=None, speak=False):
        if self.vol_before_mute is None:
            vol = self.__level_to_volume(self.settings["default_level"])
        else:
            vol = self.vol_before_mute
        self.vol_before_mute = None

        self._set_volume(vol)

        if speak:
            self.speak_dialog(
                "reset.volume",
                data={"volume": self.settings["default_level"]},
                wait=True,
            )

    # Unmute/Reset Volume Intent Handlers
    @intent_handler(IntentBuilder("UnmuteVolume").require("Volume").require("Unmute"))
    def handle_unmute_volume(self, message):
        with self.activity():
            self._clear_mixer()
            self._unmute_volume(speak=message.data.get("speak_message", True))

    @intent_handler("Unmute.intent")
    def handle_unmute_short_phrases(self, message):
        """Handle short but explicit unmute phrases

        Examples:
        - Unmute
        - Turn mute off
        - Turn sound back on
        """
        self.handle_unmute_volume(message)

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
        """Get volume, either from mixer or ask on messagebus.

        The show parameter should only be True when a user is requesting
        the volume and not the system.
        TODO: Remove usage of Mixer and move that stuff to enclosure.
        TODO: What to report if no response received from mycroft.volume.get?
              Returning a default value seems inadequate. We should raise an error
              and do something about it.
        """
        vol = default
        if self.mixer:
            vol = min(self.mixer.getvolume()[0], 100)
            self.log.debug("Volume before mute: {}".format(vol))
        else:
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

    def shutdown(self):
        if self.vol_before_mute is not None:
            self._unmute_volume()


def create_skill():
    return VolumeSkill()
