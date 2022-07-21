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
    def __init__(self):
        super().__init__(service_id="hal")

    def start(self):
        self._led_client = Mark2LedClient(self.bus)
        self._led_client.start()

        self._switch_client = Mark2SwitchClient(self.bus)
        self._switch_client.start()

        self._volume_client = Mark2VolumeClient(self.bus)
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
