# Copyright 2017 Mycroft AI Inc.
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
"""Mycroft skill to pair a device to the Selene backend."""
import time
from datetime import datetime
from enum import Enum
from http import HTTPStatus
from threading import Lock, Timer
from uuid import uuid4
from typing import Optional

from mycroft.api import DeviceApi, get_pantacor_device_id
from mycroft.identity import IdentityManager
from mycroft.messagebus.message import Message
from mycroft.skills import MycroftSkill, intent_handler, GuiClear, MessageSend
from mycroft.skills.intent_service import AdaptIntent
from requests import HTTPError

MAX_PAIRING_CODE_RETRIES = 30
ACTIVATION_POLL_FREQUENCY = 10  # secs between checking server for activation
ONE_MINUTE = 60


class AuthenticationState(str, Enum):
    AUTHENTICATED = "authenticated"
    NOT_AUTHENTICATED = "not_authenticated"
    SERVER_UNAVAILABLE = "server_unavailable"


class PairingSkill(MycroftSkill):
    """Device pairing logic."""

    def __init__(self):
        super().__init__("PairingSkill")
        self.api = DeviceApi()

        self.pairing_token = None
        self.pairing_code = None
        self.pairing_code_expiration = None
        self.state = str(uuid4())
        # TODO replace self.platform logic with call to enclosure capabilities
        self.nato_alphabet = None
        self.mycroft_ready = False
        self.pairing_code_retry_cnt = 0

        # These attributes track the status of the device activation
        self.device_activation_lock = Lock()
        self.device_activation_checker = None
        self.device_activation_cancelled = False
        self.activation_attempt_count = 0

        # These attributes are used when tracking the ready state to control
        # when the paired dialog is spoken.
        self.pairing_performed = False

        # These attributes are used when determining if pairing has started.
        self.pairing_status_lock = Lock()
        self.pairing_in_progress = False

        self.pantacor_device_id = None

    def initialize(self):
        """Register event handlers, setup language and platform dependent info."""
        self.add_event(
            "server-connect.authentication.start", self.handle_authentication_start
        )
        self.add_event("server-connect.pairing.start", self.handle_pairing_start)
        self.add_event(
            "server-connect.pairing.url-communicated",
            self._show_pairing_code,
        )
        self.add_event(
            "server-connect.pairing.code-shown",
            self._check_for_activation,
        )
        self.add_event("mycroft.internet-ready", self.handle_internet_ready)
        self.add_event("server-connect.authenticated", self.handle_paired)
        self.nato_alphabet = self.translate_namedvalues("codes")

    @intent_handler(
        AdaptIntent("PairingIntent").require("PairingKeyword").require("DeviceKeyword")
    )
    def handle_pairing(self, _):
        """Handles request to connect to the server from the Adapt intent parser."""
        self.log.info("Attempting to pair device with server...")
        return self.continue_session(
            gui="server_connect_mark_ii.qml",
            message=Message("server-connect.authentication.start"),
            gui_clear=GuiClear.NEVER,
        )

    def handle_authentication_start(self, message: Message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._mycroft_session_id:
            # Different session now
            return

        self.bus.emit(
            Message(
                "server-connect.authentication.started",
                data={"mycroft_session_id": mycroft_session_id},
            )
        )

        server_state = AuthenticationState.SERVER_UNAVAILABLE
        retries = 3
        while retries > 0:
            try:
                self.api.get()
                server_state = AuthenticationState.AUTHENTICATED
                break
            except Exception as e:
                if isinstance(e, HTTPError) and (
                    e.response.status_code == HTTPStatus.UNAUTHORIZED
                ):
                    server_state = AuthenticationState.NOT_AUTHENTICATED
                    break

                self.log.exception("Error while connecting to Mycroft servers")
                server_state = AuthenticationState.SERVER_UNAVAILABLE
                retries -= 1
                self.log.debug("Retries left: %s", retries)
                time.sleep(10)

        self.bus.emit(
            Message(
                "server-connect.authentication.ended",
                data={
                    "state": str(server_state),
                    "mycroft_session_id": mycroft_session_id,
                },
            )
        )

        if server_state == AuthenticationState.NOT_AUTHENTICATED:
            self.log.debug("Device is not paired")
            response = self.continue_session(
                message=Message("server-connect.pairing.start"),
                mycroft_session_id=mycroft_session_id,
            )
        elif server_state == AuthenticationState.SERVER_UNAVAILABLE:
            # Show failure page and retry
            self.log.warning("Server was unavailable. Retrying...")
            response = self.continue_session(
                gui=["server_failure_mark_ii.qml", "server_connect_mark_ii.qml"],
                dialog="unexpected.error.restarting",
                message=Message("server-connect.authentication.start"),
                message_send=MessageSend.AT_END,
                gui_clear=GuiClear.NEVER,
                mycroft_session_id=mycroft_session_id,
            )
        else:
            self.log.debug("Device is already paired")
            self.bus.emit(Message("server-connect.authenticated"))
            response = self.end_session(
                mycroft_session_id=mycroft_session_id, gui_clear=GuiClear.AT_END
            )

        self.bus.emit(response)

    def handle_pairing_start(self, message: Message):
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
            message=Message("server-connect.pairing.url-communicated"),
            message_send=MessageSend.AT_END,
            message_delay=15,
        )
        self.bus.emit(response)

    def _show_pairing_code(self, message: Message):
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
            message=Message("server-connect.pairing.code-shown"),
            message_send=MessageSend.AT_END,
            message_delay=10,
        )
        self.bus.emit(response)

    def _check_for_activation(self, message: Message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id != self._mycroft_session_id:
            # Different session now
            return

        self.log.debug("Checking for device activation")
        try:
            self.log.info("Pairing successful")
            login = self.api.activate(self.state, self.pairing_token)
            self._save_identity(login)
            self.bus.emit(
                Message(
                    "server-connect.pairing.ended",
                    data={"mycroft_session_id": mycroft_session_id},
                )
            )
            self.bus.emit(Message("mycroft.paired", login))
            self.bus.emit(Message("server-connect.authenticated"))

            response = self.end_session(
                dialog="pairing.paired",
                gui="pairing_success_mark_ii.qml",
                gui_clear=GuiClear.AT_END,
            )
            self.bus.emit(response)
        except Exception:
            self._show_pairing_code(message)

    # def handle_authentication_ended(self, message: Message):
    #     mycroft_session_id = message.data.get("mycroft_session_id")
    #     if mycroft_session_id != self._mycroft_session_id:
    #         # Different session now
    #         return

    #     state = AuthenticationState(message.data["state"])
    #     if state == AuthenticationState.NOT_AUTHENTICATED:
    #         pass
    #     elif state == AuthenticationState.SERVER_UNAVAILABLE:
    #         pass

    def handle_internet_ready(self, _):
        """Handles connecting to server as part of the device boot sequence.

        Check pairing status after the system clock is synchronized to NTP.
        Attempting pairing before clock synchronization could result in SSL errors
        if the date is too far off.  This is especially common on first boot,
        when pairing usually takes place.
        """
        self.log.info("Attempting to pair device with server...")
        self.emit_start_session(
            gui="server_connect_mark_ii.qml",
            message=Message("server-connect.authentication.start"),
            gui_clear=GuiClear.NEVER,
        )

    # def _authenticate_with_server(self) -> AuthenticationState:
    #     """Attempts to connect to the configured server.

    #     The server endpoint being called requires authentication.  If the
    #     authentication attempt returns a HTTP 401 (unauthorized), the device is
    #     not paired with the server.  Any other HTTP error code is interpreted
    #     as the server being unavailable for pairing.
    #     """
    #     server_state = AuthenticationState.SERVER_UNAVAILABLE
    #     self.bus.emit(Message("server-connect.authentication.started"))
    #     retries = 3
    #     while retries > 0:
    #         try:
    #             self.api.get()
    #             server_state = AuthenticationState.AUTHENTICATED
    #             break
    #         except HTTPError as http_error:
    #             if http_error.response.status_code == HTTPStatus.UNAUTHORIZED:
    #                 server_state = AuthenticationState.NOT_AUTHENTICATED
    #                 break

    #             server_state = AuthenticationState.SERVER_UNAVAILABLE
    #             retries -= 1
    #             time.sleep(10)
    #     self.bus.emit(Message("server-connect.authentication.ended"))
    #     return server_state

    # def _call_device_endpoint(self) -> bool:
    #     """Attempts a simple API call to determine authentication status."""
    #     try:
    #         self.api.get()
    #     except HTTPError as http_error:
    #         if http_error.response.status_code == HTTPStatus.UNAUTHORIZED:
    #             return False
    #         else:
    #             raise

    #     return True

    # def _display_server_unavailable(self):
    #     self._show_page("server_failure")
    #     time.sleep(15)
    #     self._show_page("server_connect")

    # def _pair_with_server(self):
    #     start_pairing = self._check_pairing_in_progress()
    #     if start_pairing:
    #         self.reload_skill = False  # Prevent restart during pairing
    #         self._execute_pairing_sequence()

    # def _check_pairing_in_progress(self):
    #     """Determine if skill was invoked while pairing is in progress."""
    #     with self.pairing_status_lock:
    #         if self.pairing_in_progress:
    #             self.log.debug("Pairing in progress; ignoring call to handle_pairing")
    #             start_pairing = False
    #         else:
    #             self.pairing_in_progress = True
    #             start_pairing = True

    #     return start_pairing

    # def _execute_pairing_sequence(self):
    #     """Interact with the user to pair the device."""
    #     self.log.info("Initiating device pairing sequence...")
    #     self._get_pairing_data()
    #     if self.pairing_code is not None:
    #         self._communicate_pairing_url()
    #         self._display_pairing_code()
    #         self._speak_pairing_code()
    #         self._attempt_activation()

    def _get_pairing_data(self):
        """Obtain a pairing code and access token from the Selene API

        A pairing code is good for 24 hours so set an expiration time in case
        pairing does not complete.  If the call to the API fails, retry for
        five minutes.  If the API call does not succeed after five minutes
        abort the pairing process.
        """
        self.log.info("Retrieving pairing code from device API...")
        try:
            pairing_data = self.api.get_code(self.state)
            self.pairing_code = pairing_data["code"]
            self.pairing_token = pairing_data["token"]
            self.pairing_code_expiration = time.monotonic() + pairing_data["expiration"]
        except Exception:
            self.log.exception("API call to retrieve pairing data failed")
            self._handle_pairing_data_retrieval_error()
        else:
            self.log.info("Pairing code obtained: " + self.pairing_code)
            self.pairing_code_retry_cnt = 0  # Reset counter on success

    def _handle_pairing_data_retrieval_error(self):
        """Retry retrieving pairing code for five minutes, then abort."""
        if self.pairing_code_retry_cnt < MAX_PAIRING_CODE_RETRIES:
            time.sleep(10)
            self.pairing_code_retry_cnt += 1
            self._restart_pairing(quiet=True)
        else:
            self._end_pairing("connection.error")
            self.pairing_code_retry_cnt = 0

    # def _communicate_pairing_url(self):
    #     """Tell the user the URL for pairing and display it, if possible"""
    #     self.log.info("Communicating pairing URL to user")
    #     if self.gui.connected:
    #         self._show_page("pairing_start")
    #     else:
    #         self.enclosure.mouth_text("mycroft.ai/pair      ")
    #     self.speak_dialog("pairing.intro")
    #     time.sleep(30)

    def _display_pairing_code(self):
        """Show the pairing code on the display, if one is available"""
        return ("pairing_code_mark_ii.qml", {"pairingCode": self.pairing_code})

    # def _attempt_activation(self):
    #     """Speak the pairing code if two"""
    #     with self.device_activation_lock:
    #         if not self.device_activation_cancelled:
    #             self._check_speak_code_interval()
    #             self._start_device_activation_checker()

    # def _check_speak_code_interval(self):
    #     """Only speak pairing code every two minutes."""
    #     self.activation_attempt_count += 1
    #     if not self.activation_attempt_count % 12:
    #         self._speak_pairing_code()

    def _speak_pairing_code(self):
        """Speak pairing code."""
        self.log.debug("Speaking pairing code")
        pairing_code_utterance = map(self.nato_alphabet.get, self.pairing_code)
        speak_data = dict(code=". ".join(pairing_code_utterance) + ".")
        # TODO - There is a bug in the Mark 1 where the pairing code display is
        # immediately cleared if we do not wait for this dialog to be spoken.
        return "pairing.code", speak_data

    # def _start_device_activation_checker(self):
    #     """Set a timer to check the activation status in ten seconds."""
    #     self.device_activation_checker = Timer(
    #         ACTIVATION_POLL_FREQUENCY, self.check_for_device_activation
    #     )
    #     self.device_activation_checker.daemon = True
    #     self.device_activation_checker.start()

    # def check_for_device_activation(self):
    #     """Call the device API to determine if user completed activation.

    #     Called every 10 seconds by a Timer. Checks if user has activated the
    #     device on account.mycroft.ai.  Activation is considered successful when
    #     the API call returns without error. When the API call throws an
    #     HTTPError, the assumption is that the uer has not yet completed
    #     activation.
    #     """
    #     self.log.debug("Checking for device activation")
    #     try:
    #         login = self.api.activate(self.state, self.pairing_token)
    #     except HTTPError:
    #         self._handle_not_yet_activated()
    #     except Exception:
    #         self.log.exception("An unexpected error occurred.")
    #         self._restart_pairing()
    #     else:
    #         self._handle_activation(login)

    # def _handle_not_yet_activated(self):
    #     """Activation has not been completed, determine what to do next.

    #     The pairing code expires after 24 hours. Restart pairing if expired.
    #     If the pairing code is still valid, speak the pairing code if the
    #     appropriate amount of time has elapsed since last spoken and restart
    #     the device activation checking timer.
    #     """
    #     if time.monotonic() > self.pairing_code_expiration:
    #         self._reset_pairing_attributes()
    #         self.handle_pairing()
    #     else:
    #         self._attempt_activation()

    # def _handle_activation(self, login: dict):
    #     """Steps to take after successful device activation.

    #     Args:
    #         login: credentials for the device to log into the backend.
    #     """
    #     self._save_identity(login)
    #     self.stop_speaking()
    #     self._display_pairing_success()
    #     self.bus.emit(Message("mycroft.paired", login))
    #     self.pairing_performed = True
    #     self._speak_pairing_success()
    #     self.bus.emit(Message("server-connect.authenticated"))
    #     self.gui.release()
    #     self.bus.emit(Message("configuration.updated"))
    #     self.reload_skill = True

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

    # def _display_pairing_success(self):
    #     """Display a pairing complete screen on GUI or clear Arduino"""
    #     if self.gui.connected:
    #         self._show_page("pairing_success")
    #         time.sleep(5)
    #         self._show_page("pairing_done")
    #     else:
    #         self.enclosure.activate_mouth_events()  # clears the display

    def _speak_pairing_success(self):
        """Tell the user the device is paired."""
        if self.platform in ACTION_BUTTON_PLATFORMS:
            paired_dialog = "pairing.paired"
        else:
            paired_dialog = "pairing.paired.no.button"
        self.speak_dialog(paired_dialog, wait=True)

    def _end_pairing(self, error_dialog: str):
        """Resets the pairing and don't restart it.

        Arguments:
            error_dialog: Reason for the ending of the pairing process.
        """
        self.speak_dialog(error_dialog)
        self.bus.emit(Message("mycroft.mic.unmute", None))
        self._reset_pairing_attributes()

    def _restart_pairing(self, quiet: bool = False):
        """Resets the pairing and don't restart it.

        Arguments:
            quiet: indicates if an error message should be spoken to the user
        """
        self.log.info("Aborting pairing process and restarting...")
        if not quiet:
            self.speak_dialog("unexpected.error.restarting")
        self._reset_pairing_attributes()
        self.bus.emit(Message("mycroft.not.paired", data=dict(quiet=quiet)))

    def _reset_pairing_attributes(self):
        """Reset attributes that need to be in a certain state for pairing."""
        with self.pairing_status_lock:
            self.pairing_in_progress = False
        with self.device_activation_lock:
            self.activation_attempt_count = 0
        self.device_activation_checker = None
        self.pairing_code = None
        self.pairing_token = None

    def _show_page(self, page_name_prefix: str):
        """Display the correct pairing screen depending on the platform.

        Args:
            page_name_prefix: the first part of the QML file name is the same
                irregardless of platform.
        """
        return page_name_prefix + "_mark_ii.qml"

    def handle_paired(self, _):
        """Executes logic that is dependent on Selene pairing success."""
        if self.config_core["enclosure"].get("packaging_type") == "pantacor":
            self.log.info(
                "Device uses Pantacor for continuous deployment "
                "- syncing Pantacor config"
            )
            self.schedule_repeating_event(
                self.sync_with_pantacor,
                when=datetime.now(),
                frequency=60,
                name="PantacorSync",
            )
        else:
            self.log.info("Device does not uses Pantacor for continuous deployment.")

    def sync_with_pantacor(self):
        """Calls the Selene endpoint to sync the device with Pantacor.

        Selene interacts with the Pantacor Fleet API to determine if the
        device registration process is complete.  Upon registration success,
        Selene stores Pantacor data regarding the device in its database.

        There is no guarantee of when the device's registration with Pantacor will
        be complete, so call the endpoint once per minute until success.
        """
        self.log.info(
            "Device uses Pantacor for continuous deployment - syncing Pantacor config"
        )
        self.api = DeviceApi()
        self.pantacor_device_id = get_pantacor_device_id()
        if self.pantacor_device_id:
            try:
                self.api.sync_pantacor_config(self.pantacor_device_id)
            except HTTPError as http_error:
                http_status = http_error.response.status_code
                if http_status == HTTPStatus.NOT_FOUND:
                    self.log.warning(
                        "Device not found on Pantacor - retrying in one minute"
                    )
                elif http_status == HTTPStatus.PRECONDITION_REQUIRED:
                    self.log.warning(
                        "Device exists on Pantacor servers but Pantacor setup is not"
                        "complete - retrying in one minute"
                    )
            else:
                self.log.info("Sync of Pantacor config succeeded")
                self.cancel_scheduled_event("PantacorSync")
        else:
            self.log.warning(
                "Attempt to obtain Pantacor Device ID from file system failed - "
                "retrying in one minute"
            )

    # def shutdown(self):
    #     """Skill process termination steps."""
    #     with self.device_activation_lock:
    #         self.device_activation_cancelled = True
    #         if self.device_activation_checker:
    #             self.device_activation_checker.cancel()
    #     if self.device_activation_checker:
    #         self.device_activation_checker.join()


def create_skill():
    """Entrypoint for skill process to load the skill."""
    return PairingSkill()
