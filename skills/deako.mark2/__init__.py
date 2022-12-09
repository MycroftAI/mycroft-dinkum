# Copyright 2022, Mycroft AI Inc.
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

"""
Mycroft skill designed to interact with Deako smart switches.

Deako switches can communicate via bluetooth or (in some models)
over the local network with a telnet server. In multiple switch
setups with at least one wifi-capable switch, one switch will
act as the hub for all the others and will broadcast via
zero-configuration networking (Bonjour, etc.). The rest of
the switches will connect to this hub switch via bluetooth.

This skill first scans the local network for any switches acting
as the hub. If it finds one, it connects as a telnet client and
waits for commands to send using Deako's API (see
https://github.com/DeakoLights/local-integrations/blob/master/API.md).

Currently this supports turning lights on and off and setting dimming
levels. The API only exposes switch names, not zones or scenes, so
any zones or scenes would have to be configured on the backend, or,
ideally, imported from the Deako app where they are defined.

Note that this can also control the smart plug in the same way as
other switches.
"""

import json
from typing import Dict, List, Union, Optional

import zeroconf
import telnetlib
from telnetlib import Telnet

from mycroft.messagebus.message import Message
from mycroft.skills import MycroftSkill, intent_handler
from mycroft.skills.intent_service import AdaptIntent


# This is hardcoded here just for testing.
HOST = "10.0.0.252"

# Deako Command Templates Dicts
# These are the dicts for various command types. Some have default
# values.
DEVICE_PING = {
    "transactionId": "015c44d3-abec-4be0-bb0d-34adb4b81559",
    "type": "PING",
    "dst": "deako",
    "src": "ACME Corp"
}

DEVICE_LIST = {
    "transactionId": "015c44d3-abec-4be0-bb0d-34adb4b81559",
    "type": "DEVICE_LIST",
    "dst": "deako",
    "src": "ACME Corp"
}

CHANGE_DEVICE_STATE = {
    "transactionId": "015c44d3-abec-4be0-bb0d-34adb4b81559",
    "type": "CONTROL",
    "dst": "deako",
    "src": "ACME Corp",
    "data": {
        "target": "824e7745-eba0-4e24-aa9c-fec1e0703eb4",
        "state": {
            "power": True
        }
    }
}

# Type alias for the command / response dicts.
Device_message = Dict[str, Union[str, Dict[str, Union[str, bool, int]]]]


class DeakoSkill(MycroftSkill):
    """

    """

    def __init__(self, skill_id: str) -> None:
        super().__init__(skill_id=skill_id, name="DeakoSkill")
        self.host = None
        self.conn = None
        self.devices = None
        self.rooms = None
        self.appliances = None
        self.furniture = None

    def initialize(self):
        """Do these things after the skill is loaded."""
        self.host = self.discover_host()
        self.conn = self.connect_to_host()
        self.devices = self.get_device_list()
        self.rooms = self.load_names("./locale/en-us/vocabulary/rooms.voc")
        self.furniture = self.load_names("./locale/en-us/vocabulary/furniture.voc")
        self.appliances = self.load_names("./locale/en-us/vocabulary/appliances.voc")

    @staticmethod
    def load_names(file_path):
        with open(file_path, "r") as f:
            return [
                room.lower().strip() for room in f.readlines()
            ]

    def discover_host(self):
        # For now just return the test IP.
        return HOST

    def connect_to_host(self) -> Optional[Telnet]:
        try:
            return telnetlib.Telnet(self.host)
        except:
            # TODO: Fill in and specify.
            pass

    def get_device_list(self) -> List[Device_message]:
        result = None
        self._execute_command(DEVICE_LIST)
        results = self._read_result()
        if not results or len(results) < 2:
            # TODO: Something here.
            # Things didn't work.
            pass
        result_dicts = [
            json.loads(result) for result in results.strip().split("\n")
        ]
        confirm_message = result_dicts.pop(0)
        self.log.info(f'{confirm_message["data"]["number_of_devices"]} devices found.')
        return result_dicts

    def change_device_state(self, target: str, power: bool, dim: Optional[int] = None):
        CHANGE_DEVICE_STATE["data"]["target"] = target
        CHANGE_DEVICE_STATE["data"]["state"]["power"] = power
        if dim:
            CHANGE_DEVICE_STATE["data"]["state"]["dim"] = dim
        self._execute_command(CHANGE_DEVICE_STATE)

    def _execute_command(self, command: Device_message) -> bool:
        try:
            self.connection.write(json.dumps(command).encode() + b"x\r")
        except:
            # TODO: Fill this in and narrow exception type.
            return False
        return True

    def _read_result(self) -> str:
        output = None
        i = 300000
        while not output and i > 0:
            try:
                output = self.connection.read_very_eager().decode("utf-8")
            except:
                # TODO: Fill in and specify.
                pass
            i -= 1
        return output

    # Intent handlers.

    @intent_handler(
        AdaptIntent()
        .optionally("turn")
        .one_of("light", "lights")
        .one_of("on", "off")
    )
    def handle_toggle_lights(self, message):
        utterance = message.data.get("utterance", "").lower().strip()
        power = None
        light_name = None
        target = None
        known_devices = {
            device["data"]["name"]: device for device in self.devices
        }
        this_device = known_devices.get("light_name", "")
        if not this_device:
            # TODO: Something.
            pass
        # noinspection PyTypeChecker
        target = this_device["data"]["uuid"]
        if 'on' in utterance:
            power = True
        else:
            power = False
        self.change_device_state(target, power)
        acknowledgement = self._read_result()
        event = self._read_result()


def create_skill(skill_id: str):
    """Boilerplate to invoke the weather skill."""
    return DeakoSkill(skill_id=skill_id)






























