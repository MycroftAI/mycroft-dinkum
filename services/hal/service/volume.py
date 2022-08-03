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
import logging
import subprocess
from math import exp, log
from typing import Optional

from mycroft.util.file_utils import resolve_resource_file
from mycroft_bus_client import Message, MessageBusClient
from smbus2 import SMBus

BUS_ID = 1
DEVICE_ADDRESS = 0x2F
VOLUME_ADDRESS = 0x4C

MAX_VOL = 84


class Mark2VolumeClient:
    """Sets/gets the volume"""

    def __init__(self, bus: MessageBusClient):
        self.bus = bus
        self.i2c_bus = SMBus(BUS_ID)
        self.log = logging.getLogger("hal.volume")

        self._beep_uri: Optional[str] = None
        beep = resolve_resource_file("snd/beep.wav")
        if beep:
            self._beep_uri = f"file://{beep}"

        self._volume_min: int = 0
        self._volume_max: int = 100
        self._volume_step: int = 10
        self._current_volume: int = 60
        self._volume_before_mute: int = self._current_volume

    @property
    def is_muted(self) -> bool:
        return self._current_volume == self._volume_min

    def start(self):
        self.bus.on("mycroft.switch.state", self._handle_switch_state)
        self.bus.on("mycroft.volume.set", self._handle_volume_set)
        self.bus.on("mycroft.volume.get", self._handle_volume_get)
        self.bus.on("mycroft.volume.mute", self._handle_volume_mute)
        self.bus.on("mycroft.volume.unmute", self._handle_volume_unmute)
        self.set_volume(self._current_volume, no_osd=True)

    def _handle_switch_state(self, message: Message):
        try:
            name = message.data.get("name")
            state = message.data.get("state")

            if (name in {"volume_down", "volume_up"}) and (state == "on"):
                if name == "volume_up":
                    self.set_volume(self._current_volume + self._volume_step)
                else:
                    self.set_volume(self._current_volume - self._volume_step)

                if self._beep_uri:
                    # Play short beep
                    self.bus.emit(
                        Message(
                            "mycroft.audio.play-sound", data={"uri": self._beep_uri}
                        )
                    )

        except Exception:
            self.log.exception("Error while setting volume")

    def _handle_volume_set(self, message: Message):
        try:
            # Not really a percent: actually in [0,1]
            percent = float(message.data["percent"])
            volume = self._volume_min + (
                percent * (self._volume_max - self._volume_min)
            )
            # True if volume OSD should not be displayed
            no_osd = message.data.get("no_osd", False)

            self.set_volume(volume, no_osd=no_osd)
        except Exception:
            self.log.exception("Error while setting volume")

    def _handle_volume_get(self, message: Message):
        # Not really a percent: actually in [0,1]
        percent = self._current_volume / (self._volume_max - self._volume_min)
        self.bus.emit(
            message.response(data={"percent": percent, "muted": self.is_muted})
        )

    def _handle_volume_mute(self, _message: Message):
        if not self.is_muted:
            self.log.debug("Muting volume")
            self._volume_before_mute = self._current_volume
            self.set_volume(self._volume_min)

    def _handle_volume_unmute(self, _message: Message):
        if self.is_muted:
            self.log.debug("Unmuting volume")
            self.set_volume(self._volume_before_mute)

    def stop(self):
        pass

    def set_volume(self, volume: int, no_osd: bool = False):
        """Sets the hardware volume using the I2C bus"""
        volume = min(self._volume_max, max(self._volume_min, volume))
        tas_volume = self._calc_log_y(volume)
        self.i2c_bus.write_byte_data(DEVICE_ADDRESS, VOLUME_ADDRESS, tas_volume)
        self._current_volume = volume
        self.log.debug("Volume set to %s (hw=%s)", volume, tas_volume)

        # Normalize to [0, 1]
        norm_volume = volume / (self._volume_max - self._volume_min)
        self.bus.emit(
            Message("hardware.volume", data={"volume": norm_volume, "no_osd": no_osd})
        )

    def _calc_log_y(self, x):
        """given x produce y. takes in an int
        0-100 returns a log oriented hardware
        value with larger steps for low volumes
        and smaller steps for loud volumes"""
        if x < 0:
            x = 0

        if x > 100:
            x = 100

        x0 = 0  # input range low
        x1 = 100  # input range hi

        y0 = MAX_VOL  # max hw vol
        y1 = 210  # min hw val

        p1 = (x - x0) / (x1 - x0)
        p2 = log(y0) - log(y1)
        pval = p1 * p2 + log(y1)

        return round(exp(pval))
