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
import json
import logging
import time
from enum import Enum, auto
from http import HTTPStatus
from typing import Optional
from uuid import uuid4

import requests
from mycroft.api import DeviceApi
from mycroft.configuration.remote import (
    download_remote_settings,
    get_remote_settings_path,
)
from mycroft.identity import IdentityManager
from mycroft.skills import GuiClear, MessageSend, MycroftSkill
from mycroft.util.network_utils import check_system_clock_sync_status
from mycroft_bus_client import Message, MessageBusClient
from requests import HTTPError

from .awconnect import AwconnectClient

INTERNET_RETRIES = 5
INTERNET_WAIT_SEC = 10

SERVER_AUTH_RETRIES = 3
SERVER_AUTH_WAIT_SEC = 10

MAX_PAIRING_CODE_RETRIES = 30

FAILURE_RESTART_SEC = 10

PAIRING_SHOW_URL_WAIT_SEC = 15
PAIRING_SPEAK_CODE_WAIT_SEC = 25

CLOCK_SYNC_RETIRES = 10
CLOCK_SYNC_WAIT_SEC = 1


class Authentication(str, Enum):
    AUTHENTICATED = "authenticated"
    NOT_AUTHENTICATED = "not_authenticated"
    SERVER_UNAVAILABLE = "server_unavailable"


class ConnectCheck(MycroftSkill):
    def __init__(self, bus: MessageBusClient):
        super().__init__(name="ConnectCheck", bus=bus)
        self.skill_id = "connect-check.mark2"
        self.api = DeviceApi()

        self.pairing_token = None
        self.pairing_code = None
        self.pairing_code_expiration = None
        self.pairing_state = str(uuid4())
        self.nato_alphabet = None

        self._awconnect_client: Optional[AwconnectClient] = None

    def initialize(self):
        self.nato_alphabet = self.translate_namedvalues("codes")

        # Internet detection
        self.add_event("internet-connect.detect.start", self._check_internet)
        self.add_event("internet-connect.detected", self._check_pairing)

        # WiFi setup step
        self.add_event("internet-connect.setup.start", self._wifi_setup_start)
        self.add_event(
            "hardware.awconnect.ap-activated",
            self._wifi_setup_ap_activated,
        )
        self.add_event(
            "hardware.awconnect.portal-viewed",
            self._wifi_setup_portal_viewed,
        )
        self.add_event(
            "hardware.awconnect.credentials-entered",
            self._wifi_setup_credentials_entered,
        )
        self.add_event(
            "hardware.awconnect.ap-deactivated",
            self._wifi_setup_ap_deactivated,
        )

        # Pairing steps
        self.add_event("server-connect.pairing.start", self._pairing_start)

        # Sent from GUI (button or timeout)
        self.gui.register_handler(
            "pairing.show-code", "pairing_start_mark_ii.qml", self._pairing_show_code
        )
        self.gui.register_handler(
            "pairing.check-activation",
            "pairing_code_mark_ii.qml",
            self._pairing_check_activation,
        )

        # Tutorial
        self.add_event("server-connect.tutorial.start", self._tutorial_start)

        # After pairing check or tutorial
        self.add_event("server-connect.authenticated", self._sync_clock)
        self.add_event(
            "server-connect.download-settings", self._download_remote_settings
        )

    def start(self):
        self._mycroft_session_id = self.emit_start_session(continue_session=True)
        self.bus.emit(
            Message(
                "internet-connect.detect.start",
                data={"mycroft_session_id": self._mycroft_session_id},
            )
        )

    def shutdown(self):
        self._disconnect_from_awconnect()

    def _connect_to_awconnect(self):
        """Connect to Pantacor awconnect container socket"""
        self._disconnect_from_awconnect()
        self._awconnect_client = AwconnectClient(self.bus)
        self._awconnect_client.start()

    def _disconnect_from_awconnect(self):
        """Disconnect from Pantacor awconnect container socket"""
        if self._awconnect_client is not None:
            self._awconnect_client.stop()
            self._awconnect_client = None

    def _fail_and_restart(self):
        self.bus.emit(
            self.continue_session(
                dialog="unexpected.error.restarting",
                gui="wifi_failure_mark_ii.qml",
                message=Message("internet-connect.detect.start"),
                message_send=MessageSend.AT_END,
                message_delay=FAILURE_RESTART_SEC,
                gui_clear=GuiClear.NEVER,
            )
        )

    # -------------------------------------------------------------------------

    def _check_internet(self, message: Message):
        self.log.debug("Starting internet detection")
        self.bus.emit(
            self.continue_session(
                gui=("startup_sequence_mark_ii.qml", {"step": 1}),
                gui_clear=GuiClear.NEVER,
                message=Message("internet-connect.detect.started"),
            )
        )

        # Start detection
        is_connected = False
        for i in range(INTERNET_RETRIES):
            self.log.debug(
                "Checking for internet connection (%s/%s)", i + 1, INTERNET_RETRIES
            )
            try:
                is_connected = requests.get(
                    "http://start.mycroft.ai/portal-check.html",
                ).ok
                if is_connected:
                    break
            except Exception:
                self.log.exception("Error checking internet connection")

            time.sleep(INTERNET_WAIT_SEC)

        # End detection
        self.log.debug("Ended internet detection: connected=%s", is_connected)
        self.bus.emit(
            Message(
                "internet-connect.detect.ended",
                data={
                    "connected": is_connected,
                },
            )
        )

        if is_connected:
            # Connected to the internet, check pairing next
            self.bus.emit(
                Message(
                    "internet-connect.detected",
                )
            )
        else:
            # Not connected to the internet, start wi-fi setup
            try:
                # Connect to awconnect container
                self._connect_to_awconnect()
                self.bus.emit(
                    Message(
                        "internet-connect.setup.start",
                    )
                )
            except Exception:
                self.log.exception("Failed to connect to awconnect socket")

                # Not sure what else to do besides show an error and restart
                self._fail_and_restart()

    # -------------------------------------------------------------------------
    # Wi-Fi Setup
    # -------------------------------------------------------------------------

    def _wifi_setup_start(self, message: Message):
        self.log.debug("Starting wi-fi setup")
        self.bus.emit(
            Message(
                "internet-connect.setup.started",
                data={"mycroft_session_id": self._mycroft_session_id},
            )
        )

        self.bus.emit(
            self.continue_session(
                dialog="network-connection-needed",
                gui="ap_starting_mark_ii.qml",
                message=Message("hardware.awconnect.create-ap"),
                gui_clear=GuiClear.NEVER,
            )
        )

    def _wifi_setup_ap_activated(self, message: Message):
        # Access point has been activated over in awconnect.
        # Setup will continue when the user views the portal page.
        self.bus.emit(
            self.continue_session(
                dialog="access-point-created",
                gui="access_point_select_mark_ii.qml",
                gui_clear=GuiClear.NEVER,
                mycroft_session_id=self._mycroft_session_id,
            )
        )

    def _wifi_setup_portal_viewed(self, message: Message):
        # User has viewed the portal page.
        # Setup will continue when the user has entered their wi-fi credentials.
        self.bus.emit(
            self.continue_session(
                dialog="choose-wifi-network",
                gui="network_select_mark_ii.qml",
                gui_clear=GuiClear.NEVER,
                mycroft_session_id=self._mycroft_session_id,
            )
        )

    def _wifi_setup_credentials_entered(self, message: Message):
        # User has entered their wi-fi credentials.
        # Setup will continue when the access point is deactivated.
        #
        # If the access point is reactivated, it indicates that wi-fi setup has
        # failed.
        self.bus.emit(
            self.continue_session(
                gui="connecting_mark_ii.qml",
                gui_clear=GuiClear.NEVER,
                mycroft_session_id=self._mycroft_session_id,
            )
        )

    def _wifi_setup_ap_deactivated(self, message: Message):
        # End wi-fi setup
        self.bus.emit(
            Message(
                "internet-connect.setup.ended",
                data={"mycroft_session_id": self._mycroft_session_id},
            )
        )

        self.bus.emit(
            self.continue_session(
                gui=(
                    "wifi_success_mark_ii.qml",
                    {"label": self.translate("connected")},
                ),
                gui_clear=GuiClear.NEVER,
                message=Message(
                    "internet-connect.detect.start",
                    data={"mycroft_session_id": self._mycroft_session_id},
                ),
                message_send=MessageSend.AT_END,
                message_delay=5.0,
                mycroft_session_id=self._mycroft_session_id,
            )
        )

    # -------------------------------------------------------------------------
    # Pairing
    # -------------------------------------------------------------------------

    def _check_pairing(self, message: Message):
        self.log.debug("Started server authentication")

        # Start authentication
        self.bus.emit(
            self.continue_session(
                gui=("startup_sequence_mark_ii.qml", {"step": 2}),
                gui_clear=GuiClear.NEVER,
                message=Message("server-connect.authentication.started"),
            )
        )

        server_state = Authentication.SERVER_UNAVAILABLE
        for i in range(SERVER_AUTH_RETRIES):
            self.log.debug("Checking if paired (%s/%s)", i + 1, SERVER_AUTH_RETRIES)
            try:
                self.api.get()
                server_state = Authentication.AUTHENTICATED
                break
            except Exception as e:
                if isinstance(e, HTTPError) and (
                    e.response.status_code == HTTPStatus.UNAUTHORIZED
                ):
                    server_state = Authentication.NOT_AUTHENTICATED
                    break

                self.log.exception("Error while connecting to Mycroft servers")
                server_state = Authentication.SERVER_UNAVAILABLE
                time.sleep(SERVER_AUTH_WAIT_SEC)

        # End authentication
        self.log.debug("Ended server authentication: state=%s", server_state.value)
        self.bus.emit(
            Message(
                "server-connect.authentication.ended",
                data={
                    "state": server_state.value,
                },
            )
        )

        if server_state == Authentication.NOT_AUTHENTICATED:
            # Not paired, start pairing process
            self.bus.emit(
                Message(
                    "server-connect.pairing.start",
                )
            )
        elif server_state == Authentication.SERVER_UNAVAILABLE:
            # Show failure page and retry
            self.log.warning("Server was unavailable. Retrying...")
            self._fail_and_restart()
        else:
            # Paired already, continue in enclosure
            self.bus.emit(
                Message(
                    "server-connect.authenticated",
                )
            )

    def _pairing_start(self, message: Message):
        """Get pairing code and guide user through the process"""
        self.log.debug("Started pairing")

        # Start pairing
        self.bus.emit(
            Message(
                "server-connect.pairing.started",
                data={"mycroft_session_id": self._mycroft_session_id},
            )
        )

        self.log.info("Initiating device pairing sequence...")
        self._get_pairing_data()
        response = self.continue_session(
            gui="pairing_start_mark_ii.qml",
            dialog="pairing.intro",
            gui_clear=GuiClear.NEVER,
        )
        self.bus.emit(response)

    def _pairing_show_code(self, message: Message):
        """Speak pairing code to user"""
        dialog = self._speak_pairing_code()
        gui = self._display_pairing_code()

        # Close previous session
        self.bus.emit(
            self.end_session(
                mycroft_session_id=self._mycroft_session_id,
                gui_clear=GuiClear.NEVER,
            )
        )

        self._mycroft_session_id = self.emit_start_session(
            gui=gui,
            dialog=dialog,
            mycroft_session_id=self._mycroft_session_id,
            gui_clear=GuiClear.NEVER,
            continue_session=True,
        )

    def _pairing_check_activation(self, message: Message):
        """Check if activation with mycroft.ai was successful"""
        self.log.debug("Checking for device activation")
        try:
            self.log.info("Pairing successful")
            login = self.api.activate(self.pairing_state, self.pairing_token)
            self._save_identity(login)
            self.bus.emit(
                Message(
                    "server-connect.pairing.ended",
                    data={"mycroft_session_id": self._mycroft_session_id},
                )
            )
            self.bus.emit(Message("mycroft.paired", login))

            # Pairing complete, begin tutorial
            response = self.continue_session(
                gui="pairing_success_mark_ii.qml",
                gui_clear=GuiClear.NEVER,
                mycroft_session_id=self._mycroft_session_id,
                message=Message("server-connect.tutorial.start"),
                message_send=MessageSend.AT_END,
                message_delay=3,
            )
            self.bus.emit(response)
        except Exception:
            self._pairing_show_code(message)

    def _get_pairing_data(self):
        """Obtain a pairing code and access token from the Selene API

        A pairing code is good for 24 hours so set an expiration time in case
        pairing does not complete.  If the call to the API fails, retry for
        five minutes.  If the API call does not succeed after five minutes
        abort the pairing process.
        """
        self.log.info("Retrieving pairing code from device API...")
        try:
            pairing_data = self.api.get_code(self.pairing_state)
            self.pairing_code = pairing_data["code"]
            self.pairing_token = pairing_data["token"]
            self.pairing_code_expiration = time.monotonic() + pairing_data["expiration"]
        except Exception:
            self.log.exception("API call to retrieve pairing data failed")

            # TODO
        else:
            self.log.info("Pairing code obtained: " + self.pairing_code)
            self.pairing_code_retry_cnt = 0  # Reset counter on success

    def _display_pairing_code(self):
        """Show the pairing code on the display, if one is available"""
        return ("pairing_code_mark_ii.qml", {"pairingCode": self.pairing_code})

    def _speak_pairing_code(self):
        """Speak pairing code."""
        self.log.debug("Speaking pairing code")
        pairing_code_utterance = map(self.nato_alphabet.get, self.pairing_code)
        speak_data = dict(code=". ".join(pairing_code_utterance) + ".")
        return "pairing.code", speak_data

    def _save_identity(self, login: dict):
        """Save this device's identifying information to disk.

        The user has successfully paired the device on account.mycroft.ai.
        The UUID and access token of the device can now be saved to the
        local identity file.  If saving the identity file fails twice,
        something went very wrong and the pairing process will restart.

        Args:
            login: credentials for the device to log into the backend.
        """
        save_attempts = 1
        while save_attempts < 2:
            try:
                IdentityManager.save(login)
            except Exception:
                if save_attempts == 1:
                    save_attempts += 1
                    log_msg = "First attempt to save identity file failed."
                    self.log.exception(log_msg)
                    time.sleep(2)
                else:
                    log_msg = (
                        "Second attempt to save identity file failed. "
                        "Restarting the pairing sequence..."
                    )
                    self.log.exception(log_msg)
                    self._restart_pairing()
            else:
                self.log.info("Identity file saved.")
                break

    # -------------------------------------------------------------------------
    # Tutorial
    # -------------------------------------------------------------------------

    def _tutorial_start(self, message: Message):
        """Give user a quick tutorial on how to get started"""
        self.bus.emit(
            Message(
                "server-connect.tutorial.started",
                data={"mycroft_session_id": self._mycroft_session_id},
            )
        )

        # Continue with clock sync, etc.
        response = self.end_session(
            dialog="pairing.paired",
            gui="pairing_done_mark_ii.qml",
            gui_clear=GuiClear.NEVER,
            message=Message("server-connect.authenticated"),
            message_send=MessageSend.AT_END,
        )
        self.bus.emit(response)
        self.bus.emit(
            Message(
                "server-connect.tutorial.ended",
            )
        )

    # -------------------------------------------------------------------------
    # NTP clock sync
    # -------------------------------------------------------------------------

    def _sync_clock(self):
        """Block until system clock is synced with NTP"""
        response = self.continue_session(
            gui=("startup_sequence_mark_ii.qml", {"step": 3}),
            gui_clear=GuiClear.NEVER,
        )
        self.bus.emit(response)

        try:
            for i in range(CLOCK_SYNC_RETIRES):
                self.log.debug(
                    "Checking for clock sync (%s/%s)", i + 1, CLOCK_SYNC_RETIRES
                )
                if check_system_clock_sync_status():
                    break

                time.sleep(CLOCK_SYNC_WAIT_SEC)
        except Exception:
            self.log.exception("Error while syncing clock")

        self.bus.emit(Message("server-connect.download-settings"))

    # -------------------------------------------------------------------------
    # Remote settings from mycroft.ai
    # -------------------------------------------------------------------------

    def _download_remote_settings(self):
        """Download user config from mycroft.ai"""
        response = self.continue_session(
            gui=("startup_sequence_mark_ii.qml", {"step": 4}),
            gui_clear=GuiClear.NEVER,
        )
        self.bus.emit(response)

        self.log.debug("Downloading remote settings")
        try:
            api = DeviceApi()
            remote_config = download_remote_settings(api)
            settings_path = get_remote_settings_path()

            # Save to ~/.config/mycroft/mycroft.remote.conf
            with open(settings_path, "w", encoding="utf-8") as settings_file:
                json.dump(remote_config, settings_file)
        except Exception:
            self.log.exception("Error downloading remote settings")

        self.bus.emit(Message("server-connect.startup-finished"))
        self.bus.emit(self.end_session(gui_clear=GuiClear.NEVER))
