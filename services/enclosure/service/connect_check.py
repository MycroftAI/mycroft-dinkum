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
import time
from enum import Enum, auto
from http import HTTPStatus
from pathlib import Path
from typing import Optional
from uuid import uuid4

import requests
import xdg.BaseDirectory
from mycroft.api import DeviceApi, get_pantacor_device_id
from mycroft.configuration.remote import (
    download_remote_settings,
    get_remote_settings_path,
)
from mycroft.identity import IdentityManager
from mycroft.skills import GuiClear, MessageSend, MycroftSkill
from mycroft.skills.settings import SkillSettingsDownloader
from mycroft.util.network_utils import check_system_clock_sync_status
from mycroft_bus_client import Message, MessageBusClient
from requests import HTTPError

from .awconnect import AwconnectClient
from .skills_manifest import get_skills_manifest

INTERNET_RETRIES = 5
INTERNET_WAIT_SEC = 10

SERVER_AUTH_RETRIES = 3
SERVER_AUTH_WAIT_SEC = 10

MAX_PAIRING_CODE_RETRIES = 30
PAIRING_WAIT_SEC = 10

FAILURE_RESTART_SEC = 10

PAIRING_SHOW_URL_WAIT_SEC = 15
PAIRING_SPEAK_CODE_WAIT_SEC = 25

CLOCK_SYNC_RETIRES = 10
CLOCK_SYNC_WAIT_SEC = 1

PANTACOR_RETRIES = 10
PANTACOR_WAIT_SEC = 5


class Authentication(str, Enum):
    """Result of pairing check with mycroft.ai"""

    AUTHENTICATED = "authenticated"
    NOT_AUTHENTICATED = "not_authenticated"
    SERVER_UNAVAILABLE = "server_unavailable"


class State(Enum):
    """State of this skill"""

    CHECK_INTERNET = auto()
    #
    WIFI_SETUP_START = auto()
    WIFI_SETUP_AP_ACTIVATED = auto()
    WIFI_SETUP_PORTAL_VIEWED = auto()
    WIFI_SETUP_CREDS_ENTERED = auto()
    WIFI_SETUP_AP_DEACTIVATED = auto()
    #
    SYNC_CLOCK = auto()
    #
    CHECK_PAIRING = auto()
    PAIRING_START = auto()
    PAIRING_SHOW_CODE = auto()
    PAIRING_CHECK_ACTIVATION = auto()
    PAIRING_ACTIVATING = auto()
    #
    SYNC_PANTACOR = auto()
    #
    TUTORIAL_START = auto()
    #
    DOWNLOAD_SETTINGS = auto()
    #
    DONE = auto()


class ConnectCheck(MycroftSkill):
    """
    Skill for doing:

    1. Internet detection
    2. Wi-Fi setup
    3. NTP clock sync
    4. Pairing with mycroft.ai
    5. Remote config download
    6. Short tutorial (if paired for the first time)

    """

    def __init__(
        self, bus: MessageBusClient, skill_settings_downloader: SkillSettingsDownloader
    ):
        super().__init__(skill_id="connect-check.mark2", name="ConnectCheck", bus=bus)
        self.skill_id = "connect-check.mark2"
        self.api = DeviceApi()
        self._skill_settings_downloader = skill_settings_downloader

        self.pairing_token = None
        self.pairing_code = None
        self.pairing_code_expiration = None
        self.pairing_state = str(uuid4())
        self.nato_alphabet = None

        self._was_greeting_spoken = False
        self._show_tutorial = False
        self._state: State = State.CHECK_INTERNET
        self._awconnect_client: Optional[AwconnectClient] = None

    def initialize(self):
        self.nato_alphabet = self.translate_namedvalues("codes")

        # Internet detection
        self.add_event("internet-connect.detect.start", self._check_internet)
        self.add_event("internet-connect.detected", self._sync_clock)

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
        self.add_event("server-connect.pairing.check", self._check_pairing)
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

        # Pantacor sync
        self.add_event("server-connect.join-fleet.start", self._sync_with_pantacor)
        self.add_event("server-connect.authenticated", self._sync_with_pantacor)

        self.add_event(
            "server-connect.join-fleet.ended", self._download_remote_settings
        )

    def start(self):
        self._state = State.CHECK_INTERNET
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
        self._state = State.CHECK_INTERNET
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
    # 1. Internet Detection
    # -------------------------------------------------------------------------

    def _check_internet(self, _message: Message):
        if self._state != State.CHECK_INTERNET:
            return

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
            # Connected to the internet, sync clock next
            self._state = State.SYNC_CLOCK
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
                self._state = State.WIFI_SETUP_START
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
    # 1a. Wi-Fi Setup
    # -------------------------------------------------------------------------

    def _wifi_setup_start(self, _message: Message):
        if self._state != State.WIFI_SETUP_START:
            return

        self.log.debug("Starting wi-fi setup")
        self.bus.emit(
            Message(
                "internet-connect.setup.started",
                data={"mycroft_session_id": self._mycroft_session_id},
            )
        )

        self._state = State.WIFI_SETUP_AP_ACTIVATED

        dialog = ["network-connection-needed"]
        if not self._was_greeting_spoken:
            # Hi, I'm Mycroft...
            dialog.insert(0, "greeting")
            self._was_greeting_spoken = True

        self.bus.emit(
            self.continue_session(
                dialog=dialog,
                gui="ap_starting_mark_ii.qml",
                message=Message("hardware.awconnect.create-ap"),
                gui_clear=GuiClear.NEVER,
            )
        )

    def _wifi_setup_ap_activated(self, _message: Message):
        if self._state != State.WIFI_SETUP_AP_ACTIVATED:
            return

        # Access point has been activated over in awconnect.
        # Setup will continue when the user views the portal page.
        self._state = State.WIFI_SETUP_PORTAL_VIEWED
        self.bus.emit(
            self.continue_session(
                dialog="access-point-created",
                gui="access_point_select_mark_ii.qml",
                gui_clear=GuiClear.NEVER,
                mycroft_session_id=self._mycroft_session_id,
            )
        )

    def _wifi_setup_portal_viewed(self, _message: Message):
        if self._state != State.WIFI_SETUP_PORTAL_VIEWED:
            return

        # User has viewed the portal page.
        # Setup will continue when the user has entered their wi-fi credentials.
        self._state = State.WIFI_SETUP_CREDS_ENTERED
        self.bus.emit(
            self.continue_session(
                dialog="choose-wifi-network",
                gui="network_select_mark_ii.qml",
                gui_clear=GuiClear.NEVER,
                mycroft_session_id=self._mycroft_session_id,
            )
        )

    def _wifi_setup_credentials_entered(self, _message: Message):
        if self._state != State.WIFI_SETUP_CREDS_ENTERED:
            return

        # User has entered their wi-fi credentials.
        # Setup will continue when the access point is deactivated.
        #
        # If the access point is reactivated, it indicates that wi-fi setup has
        # failed.
        self._state = State.WIFI_SETUP_AP_DEACTIVATED
        self.bus.emit(
            self.continue_session(
                gui="connecting_mark_ii.qml",
                gui_clear=GuiClear.NEVER,
                mycroft_session_id=self._mycroft_session_id,
            )
        )

    def _wifi_setup_ap_deactivated(self, _message: Message):
        if self._state != State.WIFI_SETUP_AP_DEACTIVATED:
            return

        # End wi-fi setup
        self.bus.emit(
            Message(
                "internet-connect.setup.ended",
                data={"mycroft_session_id": self._mycroft_session_id},
            )
        )

        self._state = State.CHECK_INTERNET
        self.bus.emit(
            Message(
                "internet-connect.detect.start",
                data={"mycroft_session_id": self._mycroft_session_id},
            )
        )

    # -------------------------------------------------------------------------
    # 2. NTP clock sync
    # -------------------------------------------------------------------------

    def _sync_clock(self, _message: Message):
        """Block until system clock is synced with NTP"""
        if self._state != State.SYNC_CLOCK:
            return

        response = self.continue_session(
            gui=("startup_sequence_mark_ii.qml", {"step": 2}),
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

        self._state = State.CHECK_PAIRING
        self.bus.emit(Message("server-connect.pairing.check"))

    # -------------------------------------------------------------------------
    # 3. Pairing
    # -------------------------------------------------------------------------

    def _check_pairing(self, _message: Message):
        if self._state != State.CHECK_PAIRING:
            return

        self.log.debug("Started server authentication")

        # Start authentication
        self.bus.emit(
            self.continue_session(
                gui=("startup_sequence_mark_ii.qml", {"step": 3}),
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
            except Exception as error:
                if isinstance(error, HTTPError):
                    if error.response.status_code == HTTPStatus.UNAUTHORIZED:
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
            self._state = State.PAIRING_START
            self._show_tutorial = True
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
            # Paired already, continue with pantacor sync
            self._state = State.SYNC_PANTACOR
            self.bus.emit(
                Message(
                    "server-connect.authenticated",
                )
            )

    def _pairing_start(self, _message: Message):
        """Get pairing code and guide user through the process"""
        if self._state != State.PAIRING_START:
            return

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
        if self.pairing_code is None:
            # Too many errors while obtaining pairing code
            self._fail_and_restart()

        self._state = State.PAIRING_SHOW_CODE

        dialog = ["pairing.intro"]
        if not self._was_greeting_spoken:
            # Hi, I'm Mycroft...
            dialog.insert(0, "greeting")
            self._was_greeting_spoken = True

        self._mycroft_session_id = self.emit_start_session(
            dialog=dialog,
            gui="pairing_start_mark_ii.qml",
            gui_clear=GuiClear.NEVER,
        )

    def _pairing_show_code(self, _message: Message):
        """Speak pairing code to user"""
        if self._state != State.PAIRING_SHOW_CODE:
            return

        dialog = self._speak_pairing_code()
        gui = self._display_pairing_code()

        self._state = State.PAIRING_CHECK_ACTIVATION
        self._mycroft_session_id = self.emit_start_session(
            gui=gui,
            dialog=dialog,
            gui_clear=GuiClear.NEVER,
        )

    def _pairing_check_activation(self, message: Message):
        """Check if activation with mycroft.ai was successful"""
        if self._state != State.PAIRING_CHECK_ACTIVATION:
            return

        self._state = State.PAIRING_ACTIVATING
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

            # Stop speaking pairing code
            self.bus.emit(Message("mycroft.tts.stop"))

            # Pairing complete, sync pantacor config
            self._state = State.SYNC_PANTACOR
            self._mycroft_session_id = self.emit_start_session(
                gui=("startup_sequence_mark_ii.qml", {"step": 3}),
                gui_clear=GuiClear.NEVER,
                message=Message("server-connect.join-fleet.start"),
            )
        except Exception:
            self.log.exception("Error while activating")
            self._state = State.PAIRING_SHOW_CODE
            self._pairing_show_code(message)

    def _get_pairing_data(self):
        """Obtain a pairing code and access token from the Selene API

        A pairing code is good for 24 hours so set an expiration time in case
        pairing does not complete.  If the call to the API fails, retry for
        five minutes.  If the API call does not succeed after five minutes
        abort the pairing process.
        """
        self.pairing_code = None
        for i in range(MAX_PAIRING_CODE_RETRIES):
            self.log.info(
                "Retrieving pairing code from device API (%s/%s)",
                i + 1,
                MAX_PAIRING_CODE_RETRIES,
            )
            try:
                pairing_data = self.api.get_code(self.pairing_state)
                self.pairing_code = pairing_data["code"]
                self.pairing_token = pairing_data["token"]
                self.pairing_code_expiration = (
                    time.monotonic() + pairing_data["expiration"]
                )
                break
            except Exception:
                self.log.exception("API call to retrieve pairing data failed")
                time.sleep(PAIRING_WAIT_SEC)
            else:
                self.log.info("Pairing code obtained: %s")

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
            else:
                self.log.info("Identity file saved.")
                break

    def _sync_with_pantacor(self, _message=None):
        """Calls the Selene endpoint to sync the device with Pantacor.

        Selene interacts with the Pantacor Fleet API to determine if the
        device registration process is complete.  Upon registration success,
        Selene stores Pantacor data regarding the device in its database.

        There is no guarantee of when the device's registration with Pantacor will
        be complete, so we will wait here.
        """
        if self._state != State.SYNC_PANTACOR:
            return

        self.bus.emit(
            Message(
                "server-connect.join-fleet.started",
                data={"mycroft_session_id": self._mycroft_session_id},
            )
        )
        self.log.info(
            "Device uses Pantacor for continuous deployment - syncing Pantacor config"
        )

        sync_path = (
            Path(xdg.BaseDirectory.xdg_config_home) / "mycroft" / ".pantacor.synced"
        )
        if not sync_path.exists():
            for i in range(PANTACOR_RETRIES):
                try:
                    self.log.debug(
                        "Attempting to sync Pantacor config (%s/%s)",
                        i + 1,
                        PANTACOR_RETRIES,
                    )
                    pantacor_device_id = get_pantacor_device_id()
                    if pantacor_device_id:
                        try:
                            self.log.debug(
                                "Syncing with Pantacor id %s", pantacor_device_id
                            )
                            self.api.sync_pantacor_config(pantacor_device_id)
                        except HTTPError as http_error:
                            http_status = http_error.response.status_code
                            if http_status == HTTPStatus.NOT_FOUND:
                                self.log.warning(
                                    "Device not found on Pantacor - retrying shortly"
                                )
                            elif http_status == HTTPStatus.PRECONDITION_REQUIRED:
                                self.log.warning(
                                    "Device exists on Pantacor servers but Pantacor setup is not"
                                    "complete - retrying shortly"
                                )
                        else:
                            self.log.info("sync of pantacor config succeeded")
                            sync_path.write_text(pantacor_device_id)
                            break
                    else:
                        self.log.warning(
                            "Attempt to obtain Pantacor Device ID from file system failed - "
                            "retrying shortly"
                        )
                except Exception:
                    self.log.exception(
                        "Failed to sync Pantacor config. Will retry shortly."
                    )
                finally:
                    time.sleep(PANTACOR_WAIT_SEC)

        # Fleet joined, proceed with rest of setup
        self._state = State.DOWNLOAD_SETTINGS
        self.bus.emit(Message("server-connect.join-fleet.ended"))

    # -------------------------------------------------------------------------
    # 4. Remote settings from mycroft.ai
    # -------------------------------------------------------------------------

    def _download_remote_settings(self, _message: Message):
        """Download user config from mycroft.ai"""
        if self._state != State.DOWNLOAD_SETTINGS:
            return

        response = self.end_session(
            gui=("startup_sequence_mark_ii.qml", {"step": 4}),
            gui_clear=GuiClear.NEVER,
        )
        self.bus.emit(response)

        self.log.debug("Downloading remote settings")
        try:
            api = DeviceApi()

            # Remote mycroft.conf settings
            remote_config = download_remote_settings(api)
            settings_path = get_remote_settings_path()

            # Save to ~/.config/mycroft/mycroft.remote.conf
            with open(settings_path, "w", encoding="utf-8") as settings_file:
                json.dump(remote_config, settings_file)
            self.log.debug("Wrote remote config: %s", settings_path)

            # skills.json with installed skills
            self.log.debug("Uploading skills manifest")
            skills_manifest = get_skills_manifest()
            api.upload_skills_data(skills_manifest)

            # Individual skill settings
            self.log.debug("Downloading remote skill settings")
            self._skill_settings_downloader.download()
        except Exception:
            self.log.exception("Error downloading remote settings")

        if self._show_tutorial:
            # Show brief tutorial
            self._state = State.TUTORIAL_START
            self._mycroft_session_id = self.emit_start_session(
                dialog="pairing.paired",
                gui="pairing_done_mark_ii.qml",
                gui_clear=GuiClear.NEVER,
                message=Message("server-connect.startup-finished"),
                message_send=MessageSend.AT_END,
                message_delay=3,
            )
        else:
            # Done
            self._state = State.DONE
            self.bus.emit(Message("server-connect.startup-finished"))
            self.bus.emit(self.end_session(gui_clear=GuiClear.NEVER))
