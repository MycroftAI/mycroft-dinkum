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
import itertools
import time
from threading import Thread
from typing import List, Tuple

from mycroft_bus_client import Message, MessageBusClient
from smbus2 import SMBus

from .led_animation.animation.solid import Solid
from .led_animation.animation.blink import Blink
from .led_animation.animation.pulse import Pulse
from .led_animation.animation.rainbowcomet import RainbowComet
from .led_animation import color

BUS_ID = 1
DEVICE_ADDRESS = 0x04

MAX_COLOR = 255
MIN_COLOR = 0
NUM_COLORS = 3

NUM_LEDS = 12
FIRST_LED = 0
MAX_LEDS_PER_WRITE = 10
COLORS_PER_WRITE = MAX_LEDS_PER_WRITE * NUM_COLORS


class MycroftColor:
    RED = (216, 17, 89)
    GREEN = (64, 219, 176)
    BLUE = (34, 167, 240)


class Mark2LedClient:
    """Updates the LED ring in response to messagebus events"""

    def __init__(self, bus: MessageBusClient):
        self.bus = bus
        self.log = logging.getLogger("hal.leds")
        self.i2c_bus = SMBus(BUS_ID)

        # pixel_object
        self.auto_write = False
        self._pixels = [color.BLACK] * NUM_LEDS

        self._is_running = True
        self._animation = Solid(self, color.BLACK)
        self._brightness = 1.0

        self._state: str = ""

    def start(self):
        self._state: str = "asleep"
        self.asleep()
        self._is_running = True
        Thread(target=self._animate, daemon=True).start()

        self.bus.on("mycroft.feedback.set-state", self._handle_set_state)

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

    def stop(self):
        self._state = ""
        self._animation = None
        self.fill(color.BLACK)
        self.show()

    def asleep(self, _message=None):
        self._animation = Solid(self, color=color.BLACK)

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
        # Write colors in blocks since i2c data length cannot exceed 32 bytes
        flat_rgb = list(
            max(MIN_COLOR, min(MAX_COLOR, int(c * self._brightness)))
            for c in itertools.chain.from_iterable(self._pixels)
        )

        last_value = COLORS_PER_WRITE
        write_offset = 0
        while flat_rgb:
            self.i2c_bus.write_i2c_block_data(
                DEVICE_ADDRESS,
                FIRST_LED + write_offset,
                flat_rgb[:last_value],
            )

            # Next block
            flat_rgb = flat_rgb[last_value:]
            write_offset += MAX_LEDS_PER_WRITE

    def fill(self, color):
        """Fill all leds with the same color"""
        self._pixels = [color] * NUM_LEDS

    def _animate(self):
        """Run animation in separate thread"""
        try:
            while self._is_running:
                if self._animation is not None:
                    if self._animation.animate():
                        self.show()

                time.sleep(0.001)
        except Exception:
            self.log.exception("Error in LED animation thread")
