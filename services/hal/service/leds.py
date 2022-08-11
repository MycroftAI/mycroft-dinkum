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
import itertools
import logging
import subprocess
import time
from threading import Thread
from typing import List, Optional, Tuple

from mycroft_bus_client import Message, MessageBusClient

from .led_animation import color
from .led_animation.animation import Animation
from .led_animation.animation.pulse import Pulse
from .led_animation.animation.rainbowcomet import RainbowComet
from .led_animation.animation.solid import Solid

MAX_COLOR = 255
MIN_COLOR = 0
NUM_COLORS = 3

NUM_LEDS = 12


class MycroftColor:
    RED = (216, 17, 89)
    GREEN = (64, 219, 176)
    BLUE = (34, 167, 240)


class Mark2LedClient:
    """Updates the LED ring in response to messagebus events"""

    def __init__(self, bus: MessageBusClient):
        self.bus = bus
        self.log = logging.getLogger("hal.leds")

        # pixel_object
        self.auto_write = False
        self._last_pixels: Optional[List[Tuple[int, int, int]]] = None
        self._pixels: List[Tuple[int, int, int]] = [color.BLACK] * NUM_LEDS

        self._asleep_color = color.BLACK
        self._is_running = True
        self._animation: Optional[Animation] = None
        self._brightness: int = 50

        self._state: Optional[str] = None

    def start(self):
        self._state: str = "asleep"
        self.asleep()
        self._is_running = True
        Thread(target=self._animate, daemon=True).start()

        self.bus.on("mycroft.feedback.set-state", self._handle_set_state)
        self.bus.on("mycroft.mic.mute", self._handle_mute)
        self.bus.on("mycroft.mic.unmute", self._handle_unmute)

    def _handle_set_state(self, message: Message):
        state = message.data.get("state")
        if state != self._state:
            self._state = state

            if state == "asleep":
                self.asleep()
            elif state == "awake":
                self.awake()
            elif state == "thinking":
                self.thinking()

    def _handle_mute(self, _message: Message):
        self._asleep_color = MycroftColor.RED

        if self._state == "asleep":
            self.asleep()

    def _handle_unmute(self, _message: Message):
        self._asleep_color = color.BLACK

        if self._state == "asleep":
            self.asleep()

    def stop(self):
        self._state = None
        self._animation = None
        self.fill(color.BLACK)
        self.show()

    def asleep(self, _message=None):
        self._animation = Solid(self, color=self._asleep_color)

    def awake(self, _message=None):
        self._animation = Pulse(self, speed=0.05, color=MycroftColor.GREEN, period=2)

    def thinking(self, _message=None):
        self._animation = RainbowComet(self, speed=0.1, ring=True)

    # Pixel object
    def __len__(self):
        return NUM_LEDS

    def __setitem__(self, index, value):
        self._pixels[index] = value

    def __getitem__(self, index):
        return self._pixels[index]

    def __iter__(self):
        return iter(self._pixels)

    def show(self):
        """Sets the LED colors using the mark2-leds command"""
        try:
            if (self._last_pixels == self._pixels):
                return

            self._last_pixels = list(self._pixels)

            rgb_str = ",".join(
                str(max(MIN_COLOR, min(MAX_COLOR, c)))
                for c in itertools.chain.from_iterable(self._pixels)
            )
            led_cmd = ["mark2-leds", rgb_str, str(self._brightness)]
            self.log.debug(led_cmd)
            subprocess.check_call(led_cmd)
        except Exception:
            self.log.exception("Error setting LEDs")

    def fill(self, fill_color):
        """Fill all leds with the same color"""
        self._pixels = [fill_color] * NUM_LEDS

    def _animate(self):
        """Run animation in separate thread"""
        try:
            while self._is_running:
                if self._animation is not None:
                    self._animation.animate()

                time.sleep(0.001)
        except Exception:
            self.log.exception("Error in LED animation thread")
