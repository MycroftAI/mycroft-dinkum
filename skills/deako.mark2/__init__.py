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
import time
from pathlib import Path
from typing import Dict, List, Union, Optional, Tuple

# import zeroconf
import telnetlib
from telnetlib import Telnet

from mycroft.messagebus.message import Message
from mycroft.skills import MycroftSkill, intent_handler
from mycroft.skills.intent_service import AdaptIntent
from mycroft.util.file_utils import resolve_resource_file

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

        # Telnet
        self.host = None
        self.connection = None

        # Devices
        self.devices = None

        # Names.
        self.rooms = None
        self.appliances = None
        self.furniture = None
        self.lights = None
        self.names = None

        # States
        self.percents = None
        self.powers = None
        self.states = None

        # Sound
        self.success_sound = None

    def initialize(self):
        """Do these things after the skill is loaded."""

        self.success_sound = resolve_resource_file("snd/blop-mark-diangelo.wav")

        # Get names.
        self.rooms = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Rooms.voc"))
        self.furniture = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Furniture.voc"))
        self.appliances = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Appliances.voc"))
        self.lights = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Lights.voc"))
        self.names = self.rooms + self.furniture + self.appliances + self.lights
        # Names can potentially be more than one word and can overlap. We want to get
        # the longest matching name so that we dont erroneously have a partial match.
        self.names.sort(key=len, reverse=True)

        # Get states.
        self.percents = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Percent.voc"))
        self.percents = [
            int(percent) for percent in self.percents
            if percent.isnumeric()
        ]
        self.percents.sort(reverse=True)
        # self.fractions = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Fraction.voc"))
        self.powers = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Power.voc"))

        # Connect and get device info.
        self.host = self.discover_host()
        self.log.info(f"Host discovered: {self.host}")
        self.connection = self.connect_to_host()
        self.devices = self.get_device_list()
        self.log.info(f"self.devices: {self.devices}")

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
            return telnetlib.Telnet(self.host, timeout=10)
        except:
            # TODO: Fill in and specify.
            self.log.error(f"Couldn't connect to {self.host}")

    def send_ping(self) -> str:
        """
        Pinging seems the best way to make sure a connection is
        still active before sending a new command.
        """
        self._execute_command(DEVICE_PING)
        return self.read_result()

    def get_device_list(self) -> List[Device_message]:
        result_dicts = None
        self._execute_command(DEVICE_LIST)
        time.sleep(.5)
        results = self.read_result()
        self.log.info(f"Device list results: {results}")
        if not results or len(results) < 2:
            # TODO: Something here.
            # Things didn't work.
            pass
        result_dicts = [
            json.loads(result) for result in results.strip().split("\n")
        ]
        self.log.info(f"result_dicts: {result_dicts}")
        confirm_message = result_dicts.pop(0)
        self.log.info(f'{confirm_message["data"]["number_of_devices"]} devices found.')
        return result_dicts

    def change_device_state(self, target: str, power: Optional[bool] = None, dim: Optional[int] = None) -> None:
        """
        All commands that result in a change of device state go through here.

        Although we connect when the skill is initialized, the connection
        may have been lost so we will ping the hub device first.
        """
        if not self.send_ping():
            # We aren't connected anymore. Re-initialize to make sure
            # everything is up to date.
            self.initialize()

        CHANGE_DEVICE_STATE["data"]["target"] = target
        CHANGE_DEVICE_STATE["data"]["state"]["power"] = power
        if dim:
            CHANGE_DEVICE_STATE["data"]["state"]["dim"] = dim
        self._execute_command(CHANGE_DEVICE_STATE)
        sound_uri = f"file://{self.success_sound}"
        self.play_sound_uri(sound_uri)

    def _execute_command(self, command: Device_message) -> bool:
        # Irrelevant messages can appear in the buffer when, for instance,
        # someone manually turns a light on or off, which sends an event 
        # message out. In order to make sure we are later reading the
        # message that is actually responding to the last command, we
        # need to flush the buffer by reading anything already sitting
        # in it.
        self.read_result(flush=True)
        try:
            self.connection.write(json.dumps(command).encode() + b"x\r")
            self.log.debug(f"Sent: {json.dumps(command)}")
        except:
            # TODO: Fill this in and narrow exception type.
            return False
        return True

    def read_result(self, flush=False) -> str:
        output = None
        i = 1
        if not flush:
            time.sleep(.25)
            i = 300000
        while not output and i > 0:
            try:
                output = self.connection.read_very_eager().decode("utf-8")
            except:
                # TODO: Fill in and specify.
                pass
            i -= 1
        tries = 300000 - i
        self.log.info(f"Tried read {tries}")
        return output

    # Intent handlers. ~~~~~~~~~~~~~~~~

    @intent_handler(
        AdaptIntent("SwitchStateChange")
        .one_of("Turn", "Dim")
        .one_of("Power", "Percent", "Fraction")
        .one_of("Lights", "Furniture", "Rooms", "Appliances")
    )
    def handle_change_device_state(self, message):
        """
        E.g.:
            "Turn on desk light."
        """
        dialog = None

        self.log.info("Deako skill handler triggered.")

        utterance = message.data.get("utterance", "").lower().strip()
        self.log.debug(f"Utterance: {utterance}")
        target_id, power, dim_value = self._parse_utterance(utterance)
        
        if not target_id:
            dialog = "cant.find.device"
            return self.end_session(dialog=dialog)

        self.change_device_state(target_id, power, dim_value)
        # We expect two messages from the api. First a confirmation,
        # then a message indicating that the event has taken place.
        conf_msg = self.read_result()
        event_msg = self.read_result()

        self.log.debug(f"Confirmation: {conf_msg}")
        self.log.debug(f"Event: {event_msg}")

        return self.end_session(
        #     audio_alert=audio_alert, 
            dialog=dialog
        )

    @intent_handler(
        AdaptIntent("GetDeviceList")
        .require("Scan")
        .require("Device")
    )
    def handle_scan_devices(self, message): 
        dialog = None
        self.emit_start_session(dialog) 
        new_device_list = self.get_device_list()
        self.log.debug(f"New device list: {new_device_list}")
        self.log.debug(f"Old devices: {self.devices}")
       
        old_ids, old_names = self._get_ids_names(self.devices)
        new_ids, new_names = self._get_ids_names(new_device_list)
        added_or_changed_ids = new_ids.difference(old_ids)
        added_or_changed_names = new_names.difference(old_names)
    
        if old_ids == new_ids and old_names = new_names:
            # Same set.
            dialog = "no.new.devices"
            return self.end_session(dialog=dialog)
        elif added_or_changed_names:
            # New name(s).
            # Are they new devices or just a new name?
            self

        elif new_ids.difference(old_ids):
            # New id.
            pass
        

        for new_id_name in new_ids_names:
            # Renamed device
            if new_id_name[0] :
                dialog = (
                    "renamed.device",
                    {
                        "old_name": known_ids_names[new_device["data"]["uuid"]],
                        "new_name": new_device["data"]["name"]
                    }
                )
                self.continue_session(dialog)
                # This is to keep subsequent dialog from coming too fast or overlapping.
                time.sleep(1)
            # New device
            elif new_device["data"]["uuid"] not in known_ids_names.keys():
                dialog = ("new.device", {"new_name": new_device["data"]["name"]})
                self.continue_session(dialog)
                # This is to keep subsequent dialog from coming too fast or overlapping.
                time.sleep(1)

        # Removed devices
        for known_id, known_name in known_ids_names.items():
            if known_id not in new_device_ids:
                dialog = ("removed.device", {"old_name": known_name})
                self.continue_session(dialog)
                # This is to keep subsequent dialog from coming too fast or overlapping.
                time.sleep(1)

        dialog = "scan.complete"
        return self.end_session(dialog=dialog)

    def _get_ids_names(device_list):
        ids = {device["data"]["uuid"] for device in device_list}
        names = {device["data"]["name"] for device in device_list}
        return ids, names

    def _find_device(devices, name=None, id=None):
        for device in devices:
            if name and device["data"]["name"] == name:
                return device
            elif device["data"]["uuid"] == id:
                return device
        return None

    def _parse_utterance(self, utterance: str) -> Tuple[str, bool, int]:
        target_id = None
        power = None
        dim_value = None
        dialog = None

        candidate_devices = [
            device for device in self.devices
            if device["data"]["name"] in utterance
        ]
        self.log.debug(f"Candidates: {candidate_devices}")
        if not candidate_devices:
            dialog = "cant.find.device"
            return "", "", ""

        # Names can be more than one word and can have overlapping words. Just in
        # case this is true, we take the longest matching name.
        named_device = sorted(candidate_devices, key=lambda d: d["data"]["name"]).pop()

        # If the utterance only mentions a dim value, we want to
        # keep power True.
        power = False if "off" in utterance else True

        for percent in self.percents:
            if str(percent) in utterance:
                dim_value = percent
                break

        if not dim_value:
            dim_value = self._convert_to_int(utterance)

        target_id = named_device["data"]["uuid"]
        return target_id, power, dim_value

    def _find_target_id(self, device_name):
        known_devices = {
            device["data"]["name"]: device for device in self.devices
        }
        self.log.info(f"Known devices: {known_devices}")
        self.log.info(f"Looking for name: {device_name}")
        for device in self.devices:
            if device["data"]["name"].lower().strip() == device_name:
                return device["data"]["uuid"]
        return None

    def _convert_to_int(self, utterance: str) -> Union[int, None]:
        """
        Devices use ints from 1-100 for dim/brightness values.
        This finds factions and converts them.
        Some of them are rounded to multiples of 5 because
        further precision isn't necessary.
        """
        fractions = [ 
            {"string": "three quarters", "int": 75}, 
            {"string": "two thirds", "int": 65},
            {"string": "quarter", "int": 25},
            {"string": "third", "int": 35},
            {"string": "half", "int": 50},
        ]
        for fraction in fractions:
            if fraction["string"] in utterance:
                return fraction["int"]
        return None




def create_skill(skill_id: str):
    """Boilerplate to invoke the weather skill."""
    return DeakoSkill(skill_id=skill_id)





#     device_name = None
    #     power = None
    #     dim_value = None
    #     target_id = None
    #     dialog = None
    #     self.log.info("Deako skill handler triggered.")
    #     utterance = message.data.get("utterance", "").lower().strip()
    #     self.log.debug(f"Utterance: {utterance}")
    #     device_name = message.data.get("name", "").lower().strip()
    #     self.log.debug(f"Device name: {device_name}")
    #     self.log.debug(f"Power: {message.data.get('power', '')}")
    #     power = True if message.data.get("power", "") in ["on", ""] else False
    #     self.log.debug(f"Power: {power}")
    #     dim_value = message.data.get("percent", "")
    #     self.log.debug(f"Dim value is {dim_value}")
    #     target_id = self._find_target_id(device_name)
    #     if not target_id:
    #         # Device not found.
    #         dialog = ("cant.find.device.name", {"name": device_name})
    #         return self.end_session(dialog=dialog)
    #     if dim_value.isnumeric():
    #         dim_value = int(dim_value)
    #     elif dim_value:
    #         dialog = "dim.integer"
    #         return self.end_session(dialog=dialog)
    #     if dim_value:
    #         self.change_device_state(target_id, power, dim_value)
    #     elif power:
    #         self.change_device_state(target_id, power)
    #     else:
    #         dialog = "power.or.dim"
    #         return self.end_session(dialog=dialog)
    #     acknowledgement = self._read_result()
    #     event = self._read_result()
    #     dialog = ""
    #     return self.end_session(dialog=dialog)
























