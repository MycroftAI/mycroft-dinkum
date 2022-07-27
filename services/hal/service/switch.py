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
import functools
import time

import RPi.GPIO as GPIO
from mycroft_bus_client import Message, MessageBusClient


# sj201Rev4+
PINS = {"volume_up": 22, "volume_down": 23, "action": 24, "mute": 25}

# Switch debounce time in milliseconds
DEBOUNCE = 100

# Delay after callback before reading switch state in seconds
WAIT_SEC = 0.05

# Pin value when switch is active
ACTIVE = 0

# State strings reported for active (on) and inactive (off)
SWITCH_ON = "on"
SWITCH_OFF = "off"


class Mark2SwitchClient:
    """Reads the state of Mark II buttons/switches and reports changes on the messagebus"""

    def __init__(self, bus: MessageBusClient):
        self.bus = bus

    def start(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        for name, pin in PINS.items():
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                pin,
                GPIO.BOTH,
                callback=functools.partial(self._handle_gpio_event, name, pin),
                bouncetime=DEBOUNCE,
            )

        self.bus.on("mycroft.switch.report-states", self._handle_get_state)

    def _handle_get_state(self, message: Message):
        """Report the state of all switches"""
        for name, pin in PINS.items():
            value = GPIO.input(pin)
            self._report_state(name, value)

    def stop(self):
        pass

    def _handle_gpio_event(self, name, pin, _channel):
        """Read and report the state of a switch that has changed state"""
        time.sleep(WAIT_SEC)
        value = GPIO.input(pin)
        self._report_state(name, value)

    def _report_state(self, name: str, value: int):
        state = SWITCH_ON if value == ACTIVE else SWITCH_OFF
        self.bus.emit(
            Message("mycroft.switch.state", data={"name": name, "state": state})
        )
