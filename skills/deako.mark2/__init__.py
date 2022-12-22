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

import re
import json
import time
from pathlib import Path
from typing import Dict, List, Union, Optional, Tuple, Any

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
        self.name_map = dict()
        self.stt_vocab = None
        self.current_names = None
        self.last_used_device = None

        # Pronouns, determiners, etc.
        self.pronouns = None
        self.determiners = None
        self.quantifiers = None

        # States
        self.percents = None
        self.powers = None
        self.dim_terms = None

        # Sound
        self.success_sound = None

    def initialize(self):
        """Do these things after the skill is loaded."""

        self.success_sound = resolve_resource_file("snd/blop-mark-diangelo.wav")

        # Get names.
        # TODO: Currently these are reading from intent vocab files, which are assumed to
        # be identical to the corresponding STT slot files. We will need some mechanism to
        # ensure this. Or, if we decide to trim these down to only the names currently in
        # use, then we need a mechanism to do that as well.
        self.rooms = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Rooms.voc"))
        self.furniture = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Furniture.voc"))
        self.appliances = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Appliances.voc"))
        self.lights = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Lights.voc"))
        self.names = self.rooms + self.furniture + self.appliances + self.lights
        # Names can potentially be more than one word and can overlap. We want to get
        # the longest matching name so that we dont erroneously have a partial match.
        self.names.sort(key=len, reverse=True)

        # Get pronouns, determiners, etc.
        self.pronouns = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Pronouns.voc"))
        self.determiners = self.load_names(
            Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Determiners.voc")
        )
        self.quantifiers = self.load_names(
            Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Quantifiers.voc")
        )

        # Get possible names from STT slot files. The slot files define all possible names
        # that local STT (Grokotron) can recognize -- assuming that the most recent STT
        # training run used the up-to-date files.
        stt_vocab_path = Path("/opt/grokotron/slots")
        stt_vocab_files = list(stt_vocab_path.iterdir())
        self.stt_vocab = [
            self.load_names(stt_vocab_file) for stt_vocab_file in stt_vocab_files
        ]
        # Flattening vocab list.
        self.stt_vocab = [
            item for slotlist in self.stt_vocab for item in slotlist
        ]
        # Certain terms, like "light" can be redundant when we are searching for 
        # device names. For now, we'll remove them.
        # TODO: Instead when searching for names we should make it flexible enough
        # to deal with things like "desk light" instead of just "desk" as a name.
        stop_names = ["light", "lights"]
        self.stt_vocab = [
            term for term in self.stt_vocab
            if term not in stop_names
        ]

        # Get states.
        self.percents = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Percent.voc"))
        self.percents = [
            int(percent) for percent in self.percents
            if percent.isnumeric()
        ]
        self.percents.sort(reverse=True)
        self.powers = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Power.voc"))
        self.dim_terms = self.load_names(Path(self.root_dir).joinpath("locale", "en-us", "vocabulary", "Dim.voc"))

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
                name.lower().strip() for name in f.readlines()
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
        dialog = None
        result_dicts = None
        self._execute_command(DEVICE_LIST)
        time.sleep(.5)
        results = self.read_result()
        self.log.info(f"Device list results: {results}")
        if not results or len(results) < 2:
            # TODO: Something here.
            # Things didn't work.
            dialog = "cant.find.device"
            return self.end_session(dialog=dialog)
        result_dicts = [
            json.loads(result) for result in results.strip().split("\n")
        ]
        self.log.info(f"result_dicts: {result_dicts}")
        confirm_message = result_dicts.pop(0)
        self.log.info(f'{confirm_message["data"]["number_of_devices"]} devices found.')
        return self._update_names(result_dicts)

    def _update_names(self, new_result_dicts):
        # Since devices can be renamed, we need to keep them when
        # we get a new device list.
        # First, the api allows caps in names, which we never want.
        for i, new_result in enumerate(new_result_dicts):
            new_result_dicts[i]["data"]["name"] = new_result["data"]["name"].lower()
        if not self.devices:
            return new_result_dicts
        for i, new_result in enumerate(new_result_dicts):
            for old_device in self.devices:
                if new_result["data"]["uuid"] == old_device["data"]["uuid"]:
                    new_result_dicts[i]["data"]["name"] == old_device["data"]["name"]
        return new_result_dicts

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

    def handle_change_multi_device_state(self, utterance):
        """
        We should be able to handle multiple switches with one
        command. For now, since we have no access to "zones", i.e.,
        arbitrary collections of switches, all we can do is affect
        all switches.
        """
        dialog = None

        target_ids, power, dim_value, target_devices = self._parse_utterance_multiple(utterance)

        if not target_ids:
            dialog = "cant.find.device"
            return self.end_session(dialog=dialog)

        for target_id in target_ids:
            self.change_device_state(target_id, power, dim_value)
            # We expect two messages from the api. First a confirmation,
            # then a message indicating that the event has taken place.
            conf_msg = self.read_result()
            event_msg = self.read_result()
            self.log.debug(f"Confirmation: {conf_msg}")
            self.log.debug(f"Event: {event_msg}")

        return self.end_session(
            dialog=dialog
        )

    @intent_handler(
        AdaptIntent("SwitchStateChange")
        .one_of("Turn", "Dim")
        # .one_of("Power", "Percent", "Fraction", "Dim")
        .one_of("Lights", "Furniture", "Rooms", "Appliances", "Pronouns", "Determiners")
    )
    def handle_change_device_state(self, message):
        """
        E.g.:
            "Turn on desk light."
        """
        dialog = None
        self.current_names = list()

        self.log.info("Deako skill handler triggered.")

        utterance = message.data.get("utterance", "").lower().strip()
        self.log.debug(f"Utterance: {utterance}")
        for word in utterance.split(" "):
            if word in self.quantifiers:
                self.handle_change_multi_device_state(utterance)
                return None

        target_id, power, dim_value, target_device = self._parse_utterance(utterance)
        self.log.debug(f"target_id: {target_id}\npower: {power}\ndim_value: {dim_value}") 
        if not target_id:
            dialog = "cant.find.device"
            return self.end_session(dialog=dialog)

        self._register_last_used_device(target_device)
        self.change_device_state(target_id, power, dim_value)
        # We expect two messages from the api. First a confirmation,
        # then a message indicating that the event has taken place.
        conf_msg = self.read_result()
        event_msg = self.read_result()

        self.log.debug(f"Confirmation: {conf_msg}")
        self.log.debug(f"Event: {event_msg}")

        return self.end_session(
            dialog=dialog
        )


    def _parse_utterance_multiple(self, utterance):
        power, dim_value = self._extract_power_and_dim(utterance)
        target_ids = list()
        target_devices = list()
        for device in self.devices:
            target_ids.append(device["data"]["uuid"])
            target_devices.append(device)
        return target_ids, power, dim_value, target_devices

    @intent_handler(
        AdaptIntent("GetDeviceList")
        .require("Scan")
        .require("Device")
    )
    def handle_scan_devices(self, message): 
        dialog = None
        self.current_names = list()

        self.emit_start_session(dialog) 
        new_device_list = self.get_device_list()
        self.log.debug(f"New device list: {new_device_list}")
        self.log.debug(f"Old devices: {self.devices}")

        added_devices, removed_devices, renamed_devices = self._compare_devices(self.devices, new_device_list)

        self.log.debug(f"Added: {added_devices}")
        self.log.debug(f"Removed: {removed_devices}")
        self.log.debug(f"Renamed: {renamed_devices}")

        if added_devices:
            for added_device in added_devices:
                dialog = ("new.device", {"new_name": added_device["data"]["name"]})
                self.bus.emit(
                    self.continue_session(dialog)
                )
                # This is to keep subsequent dialog from coming too fast or overlapping.
                time.sleep(1)
        elif removed_devices:
            for removed_device in removed_devices:
                dialog = ("removed.device", {"old_name": removed_device["data"]["name"]})
                self.bus.emit(
                    self.continue_session(dialog)
                )
                # This is to keep subsequent dialog from coming too fast or overlapping.
                time.sleep(1)
        elif renamed_devices:
            self.log.debug("Going to speak.")
            for renamed_device in renamed_devices:
                
                dialog = (
                    "renamed.device",
                    {
                        "old_name": renamed_device["old_name"],
                        "new_name": renamed_device["new_name"]
                    }
                )
                self.bus.emit(self.continue_session(dialog))
                # This is to keep subsequent dialog from coming too fast or overlapping.
                time.sleep(1)
        else:
            dialog = "no.new.devices"
            return self.end_session(dialog=dialog)

        dialog = "scan.complete"
        return self.end_session(dialog=dialog)

    @intent_handler(
        AdaptIntent("ChangeDeviceName")
        .require("Change") 
        .require("Name")
    )
    def handle_change_device_name(self, message):
        dialog = None
        self.current_names = list()
        # self.emit_start_session(dialog=dialog)
        utterance = message.data.get("utterance", "").lower().strip()

        self.log.debug(f"Utterance: {utterance}")
        # Populates self.current_names
        # self.raw_utterance(
        #     utterance,
        #     state={
        #         "number_of_names": 2
        #     }
        # )

        self.ask_for_names(utterance)
        self.log.debug(f"Names found: {self.current_names}")

        # Now we should have everything needed.
        # Make the change.
        # self._change_device_name(self.current_names[0], self.current_names[1])
        for device in self.devices:
            if device["data"]["name"] == self.current_names[0]:
                # Plase this here first so that we remember the device
                # requested even if there should be an error.
                self._register_last_used_device(device)
                device["data"]["deako_name"] = device["data"]["name"]
                device["data"]["name"] = self.current_names[1]
                # Call this again to have the correctly updated version
                # if nothing goes wrong.
                self._register_last_used_device(device)
        
        dialog = (
            "renamed.device",
            {
                "old_name": self.current_names[0],
                "new_name": self.current_names[1]
            }
        )
        return self.end_session(dialog=dialog)

    def ask_for_names(self, utterance, name=None):
        self.log.debug(f"Didn't get two names, asking for more info: utterance {utterance}")
        return self.continue_session(
            dialog="what.old.new.name",
            expect_response=True,
            state={"number_of_names": 2},
        )

    def raw_utterance(
        self, utterance: Optional[str], state: Optional[Dict[str, Any]] = None
    ) -> Optional[Message]:
        """Callback when expect_response=True in continue_session

        Unlike _find_candidates, which looks only for the list
        of existing device names, this looks for any name that
        the local STT can currently recognize.
        """
        dialog = None
        self.log.debug(f"Processing follow up utterance: {utterance} with state {state}")
        found = list()
        for name in self.stt_vocab:
            found.extend([(m.group(), m.start(), m.end()) for m in re.finditer(name, utterance)])
        self.log.debug(f"Found namnes: {found}")
        # Sort these based on start index.
        # TODO: Use end value to find overlapping matches.
        self.current_names = [
            name[0] for name in sorted(found, key=lambda x: x[1])
        ]

        self.log.debug(f"Follow up utterance: {utterance}, state: {state}, current names found: {self.current_names}")
        self.log.debug(f'len(self.current_names): {len(self.current_names)} - state["number_of_names"]: {state["number_of_names"]} = {len(self.current_names) >= state["number_of_names"]}')
        if state["number_of_names"] >= len(self.current_names):
            dialog = "need.more.names"
            return self.end_session(dialog=dialog)
        return self.end_session()

    @intent_handler(
        AdaptIntent("SpeakDeviceNames")
        .require("List")
        .require("Device")
        .require("Name")
    )
    def handle_speak_device_names(self, message):
        dialog = None
        names = [
            device["data"]["name"] for device in self.devices
        ]
        if names:
            if len(names) > 1:
                last = names.pop()
                names = names + ["and"]
                names_string = ", ".join(names)
                names_string = names_string + " " + last
            else:
                names_string = names[0]
            dialog = ("list.devices", {"names": names_string})
            return self.end_session(dialog=dialog)

    # Helper functions/methods. ~~~~~~~~~~~~~~~~

    def _register_last_used_device(self, last_device):
        self.last_used_device = last_device



        


       # elif state["number_of_names"] - len(self.current_names) == 1:
       #     # Old name given, ask for new one.
       #     dialog = ("what.new.name", {"old_name": self.current_names[0]})
       #     self.log.debug(f"Dialog: {dialog}")
       #     return self.continue_session(
       #         dialog,
       #         # Want to get names in their response.
       #         # This tells mycroft to send their
       #         # next utterance to the "raw_utterance"
       #         # method.
       #         expect_response=True
       #     )
       # elif state["number_of_names"] - len(self.current_names) == 2:
       #     # No initial name given, ask for both.
       #     dialog = "what.old.new.name"
       #     self.log.debug(f"Dialog: {dialog}")
       #     return self.emit_start_session(
       #         dialog,
       #         # Want to get names in their response.
       #         # This tells mycroft to send their
       #         # next utterance to the "raw_utterance"
       #         # method.
       #         expect_response=True,
       #     )





    def _compare_devices(self, old_list, new_list):
        # Find changed devices.
        added_devices = list()
        removed_devices = list()
        renamed_devices = list()

        added_devices = self._find_mismatch(new_list, old_list)
        removed_devices = self._find_mismatch(old_list, new_list)
        old_list = {
            old_device["data"]["uuid"]: old_device["data"]["name"] for old_device in old_list
        }
        for new_device in new_list:
            if old_list[new_device["data"]["uuid"]]:
                if old_list[new_device["data"]["uuid"]] != new_device["data"]["name"]:
                    renamed_devices.append(
                        {
                            "new_name": new_device["data"]["name"],
                            "old_name": old_list[new_device["data"]["uuid"]]
                        }
                    )
        return added_devices, removed_devices, renamed_devices

    def _find_mismatch(self, list1, list2):
        mismatched = list()
        for item1 in list1:
            found = False
            for item2 in list2:
                if item1["data"]["uuid"] == item2["data"]["uuid"]:
                    found = True
            if not found:
                mismatched.append(item1)
        return mismatched

    def _get_ids_names(self, device_list):
        ids = {device["data"]["uuid"] for device in device_list}
        names = {device["data"]["name"] for device in device_list}
        return ids, names

    def _find_device(self, devices, name=None, id=None):
        for device in devices:
            if name and device["data"]["name"] == name:
                return device
            elif device["data"]["uuid"] == id:
                return device
        return None

    def _find_candidate_devices(self, utterance):
        return [
            device for device in self.devices
            if device["data"]["name"] in utterance
        ]

    def _parse_utterance(self, utterance: str) -> Tuple[str, bool, int, Device_message]:
        target_id = None
        power = None
        dim_value = None
        dialog = None

        candidate_devices = self._find_candidate_devices(utterance)
        self.log.debug(f"Candidates: {candidate_devices}")

        if not candidate_devices and self.last_used_device:
            # Found no name matches. Check for pronouns or determiners
            # which can refer back to the previously used device.
            for word in utterance.split(" "):
                if word in self.pronouns or word in self.determiners:
                    candidate_devices = [self.last_used_device]
                    break
        if not candidate_devices:
            # No names and no pronouns/determiners: maybe our device
            # list is out of date. Get it again and try again.
            self.devices = self.get_device_list()
            candidate_devices = self._find_candidate_devices(utterance)
            self.log.debug(f"Candidates: {candidate_devices}")
        if not candidate_devices:
            # Nothing worked, still no device matches.
            dialog = "cant.find.device"
            return "", "", "", ""

        # Names can be more than one word and can have overlapping words. Just in
        # case this is true, we take the longest matching name.
        target_device = sorted(
            [
                candidate_device for candidate_device in candidate_devices
            ],
            key=len
        ).pop()

        target_id = target_device["data"]["uuid"]

        power, dim_value = self._extract_power_and_dim(utterance)

        # target_id = named_device["data"]["uuid"]
        return target_id, power, dim_value, target_device

    def _extract_power_and_dim(self, utterance):
        power = None
        dim_value = None

        # If the utterance only mentions a dim value, we want to
        # keep power True.
        power = False if "off" in utterance else True

        for percent in self.percents:
            if str(percent) in utterance:
                dim_value = percent
                break
        if not dim_value:
            # Check for fractions or other representations.
            dim_value = self._convert_to_int(utterance)
        if not dim_value:
            for word in utterance.split(" "):
                if word in self.dim_terms:
                    # We presumably have an unspecified dim command,
                    # so use default.
                    dim_value = 50

        return power, dim_value

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


# if not self.current_names:
#     if state and state["number_of_names"] == 2:
#
#     else:
#         self.log.debug(f"Base")
#         self.current_names.extend([
#             name for name in self.stt_vocab
#             if name in utterance
#         ])
#         return None
# elif len(self.current_names) == 1:
#
# elif len(self.current_names) == 2:
#     # Old and new names given. Execute.
#     pass
# else:
#     # More than two, or something else went wrong.
#     # Try again.
#     dialog = "what.old.new.name"
#     self.log.debug(f"Dialog: {dialog}")
#     return self.emit_start_session(
#         dialog,
#         # Want to get names in their response.
#         # This tells mycroft to send their
#         # next utterance to the "raw_utterance"
#         # method.
#         expect_response=True,
#         state={
#             "number_of_names": 2
#         }
#     )




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
























