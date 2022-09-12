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
from mycroft.service import DinkumService

from .leds import Mark2LedClient
from .switch import Mark2SwitchClient
from .volume import Mark2VolumeClient


class HalService(DinkumService):
    """
    Service for controlling and getting input from Mark II specific hardware.

    Hardware includes:
    * LED ring
      * 12 RGB LEDs
      * On i2c bus 1 at 0x04
    * Switches and buttons
      * 3 buttons, 1 switch
      * action
        * Large button
        * GPIO pin 24 (BCM)
      * volume_up
        * Small button (center)
        * GPIO pin 22 (BCM)
      * volume_down
        * Small button (right)
        * GPIO pin 23 (BCM)
      * mute
        * Switch (left)
        * GPIO pin 25 (BCM)
    * Amplifier
      * On i2c bus 1 at 0x2F

    Input messages:
    * mycroft.volume.set
      * Set volume to "percent"
    * mycroft.volume.get
      * Request volume as "percent"
    * mycroft.switch.report-states
      * Request publication of mycroft.switch.state for each switch/button
    * mycroft.feedback.set-state
      * Set LED "state"
        * asleep
        * awake
        * thinking

    Output messages:
    * mycroft.switch.state
      * State of a switch/button
    * mycroft.volume.get.response
      * Response to mycroft.volume.get
    * mycroft.mic.mute
      * Mute microphone (mute switch)
    * mycroft.mic.unmute
      * Unmute microphone (mute switch)

    Service messages:
    * hal.service.connected
    * hal.service.connected.response
    * hal.initialize.started
    * hal.initialize.ended

    """

    def __init__(self):
        super().__init__(service_id="hal")

    def start(self):
        self._led_client = Mark2LedClient(self.bus)
        self._led_client.start()

        self._switch_client = Mark2SwitchClient(self.bus)
        self._switch_client.start()

        self._volume_client = Mark2VolumeClient(self.bus, self.config)
        self._volume_client.start()

    def stop(self):
        self._led_client.stop()
        self._switch_client.stop()
        self._volume_client.stop()


def main():
    """Service entry point"""
    HalService().main()


if __name__ == "__main__":
    main()
