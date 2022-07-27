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
import time
from enum import Enum, auto
from http import HTTPStatus
from typing import Optional
from uuid import uuid4

from mycroft.api import DeviceApi
from mycroft.identity import IdentityManager
from mycroft.skills import GuiClear, MessageSend, MycroftSkill
from mycroft.util.network_utils import connected
from mycroft_bus_client import Message, MessageBusClient
from requests import HTTPError

from .awconnect import AwconnectClient

INTERNET_RETRIES = 2
INTERNET_WAIT_SEC = 10

SERVER_AUTH_RETRIES = 3
SERVER_AUTH_WAIT_SEC = 10

MAX_PAIRING_CODE_RETRIES = 30

FAILURE_RESTART_SEC = 10

PAIRING_SHOW_URL_WAIT_SEC = 15
PAIRING_SPEAK_CODE_WAIT_SEC = 25


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
        self.add_event("server-connect.pairing.show-code", self._pairing_show_code)
        self.add_event(
            "server-connect.pairing.check-activation", self._pairing_check_activation
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
        self._disconnect_from_awconnect()
        self._awconnect_client = AwconnectClient(self.bus)
        self._awconnect_client.start()

    def _disconnect_from_awconnect(self):
        if self._awconnect_client is not None:
            self._awconnect_client.stop()
            self._awconnect_client = None

    # -------------------------------------------------------------------------

    def _check_internet(self, message: Message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._mycroft_session_id:
            # Different session now
            return

        self.bus.emit(
            self.continue_session(
                gui="connecting_mark_ii.qml", gui_clear=GuiClear.NEVER
            )
        )

        # Start detection
        self.bus.emit(
            Message(
                "internet-connect.detect.started",
                data={"mycroft_session_id": self._mycroft_session_id},
            )
        )
        is_connected = False
        for i in range(INTERNET_RETRIES):
            self.log.debug(
                "Checking for internet connection (%s/%s)", i + 1, INTERNET_RETRIES
            )
            try:
                is_connected = connected()
                if is_connected:
                    break
            except Exception:
                self.log.exception("Error checking internet connection")

            time.sleep(INTERNET_WAIT_SEC)

        # End detection
        self.bus.emit(
            Message(
                "internet-connect.detect.ended",
                data={
                    "connected": is_connected,
                    "mycroft_session_id": mycroft_session_id,
                },
            )
        )

        if is_connected:
            # Connected to the internet
            self.log.debug("Internet connected")
            self.bus.emit(
                Message(
                    "internet-connect.detected",
                    data={"mycroft_session_id": mycroft_session_id},
                )
            )
        else:
            # Not connected to the internet, start wi-fi setup
            self.log.debug("Internet not connected")
            try:
                # Connect to awconnect container
                self._connect_to_awconnect()
                self.bus.emit(
                    Message(
                        "internet-connect.setup.start",
                        data={"mycroft_session_id": mycroft_session_id},
                    )
                )
            except Exception:
                self.log.exception("Failed to connect to awconnect socket")

                # Not sure what else to do besides show an error and restart
                self.bus.emit(
                    self.continue_session(
                        dialog="unexpected.error.restarting",
                        gui="wifi_failure_mark_ii.qml",
                        message=Message("internet-connect.detect.start"),
                        message_send=MessageSend.AT_END,
                        message_delay=FAILURE_RESTART_SEC,
                        gui_clear=GuiClear.NEVER,
                        mycroft_session_id=mycroft_session_id,
                    )
                )

    # -------------------------------------------------------------------------
    # Wi-Fi Setup
    # -------------------------------------------------------------------------

    def _wifi_setup_start(self, message: Message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._mycroft_session_id:
            # Different session now
            return

        # Start wi-fi setup
        self.bus.emit(
            Message(
                "internet-connect.setup.started",
                data={"mycroft_session_id": mycroft_session_id},
            )
        )

        self.bus.emit(
            self.continue_session(
                dialog="network-connection-needed",
                gui="ap_starting_mark_ii.qml",
                message=Message("hardware.awconnect.create-ap"),
                gui_clear=GuiClear.NEVER,
                mycroft_session_id=mycroft_session_id,
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
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._mycroft_session_id:
            # Different session now
            return

        self.bus.emit(
            self.continue_session(
                gui="server_connect_mark_ii.qml", gui_clear=GuiClear.NEVER
            )
        )

        # Start authentication
        self.bus.emit(
            Message(
                "server-connect.authentication.started",
                data={"mycroft_session_id": mycroft_session_id},
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
        self.bus.emit(
            Message(
                "server-connect.authentication.ended",
                data={
                    "state": server_state.value,
                    "mycroft_session_id": mycroft_session_id,
                },
            )
        )

        if server_state == Authentication.NOT_AUTHENTICATED:
            self.log.debug("Device is not paired")
            self.bus.emit(
                Message(
                    "server-connect.pairing.start",
                    data={"mycroft_session_id": mycroft_session_id},
                )
            )
        elif server_state == Authentication.SERVER_UNAVAILABLE:
            # Show failure page and retry
            self.log.warning("Server was unavailable. Retrying...")
        else:
            self.log.debug("Device is already paired")
            self.bus.emit(
                Message(
                    "server-connect.authenticated",
                    data={"mycroft_session_id": mycroft_session_id},
                )
            )

    def _pairing_start(self, message: Message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._mycroft_session_id:
            # Different session now
            return

        self.bus.emit(
            Message(
                "server-connect.pairing.started",
                data={"mycroft_session_id": mycroft_session_id},
            )
        )

        self.log.info("Initiating device pairing sequence...")
        self._get_pairing_data()
        response = self.continue_session(
            gui="pairing_start_mark_ii.qml",
            dialog="pairing.intro",
            mycroft_session_id=mycroft_session_id,
            gui_clear=GuiClear.NEVER,
            message=Message("server-connect.pairing.show-code"),
            message_send=MessageSend.AT_END,
            message_delay=PAIRING_SHOW_URL_WAIT_SEC,
        )
        self.bus.emit(response)

    def _pairing_show_code(self, message: Message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._mycroft_session_id:
            # Different session now
            return

        dialog = self._speak_pairing_code()
        gui = self._display_pairing_code()

        response = self.continue_session(
            gui=gui,
            dialog=dialog,
            mycroft_session_id=mycroft_session_id,
            gui_clear=GuiClear.NEVER,
            message=Message("server-connect.pairing.check-activation"),
            message_send=MessageSend.AT_END,
            message_delay=PAIRING_SPEAK_CODE_WAIT_SEC,
        )
        self.bus.emit(response)

    def _pairing_check_activation(self, message: Message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._mycroft_session_id:
            # Different session now
            return

        self.log.debug("Checking for device activation")
        try:
            self.log.info("Pairing successful")
            login = self.api.activate(self.pairing_state, self.pairing_token)
            self._save_identity(login)
            self.bus.emit(
                Message(
                    "server-connect.pairing.ended",
                    data={"mycroft_session_id": mycroft_session_id},
                )
            )
            self.bus.emit(Message("mycroft.paired", login))

            response = self.end_session(
                dialog="pairing.paired",
                gui="pairing_success_mark_ii.qml",
                gui_clear=GuiClear.NEVER,
                message=Message("server-connect.authenticated"),
                message_send=MessageSend.AT_END,
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
        # TODO - There is a bug in the Mark 1 where the pairing code display is
        # immediately cleared if we do not wait for this dialog to be spoken.
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
