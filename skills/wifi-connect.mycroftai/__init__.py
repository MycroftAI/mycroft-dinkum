# Copyright 2020 Mycroft AI Inc.
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
"""Mycroft skill for joining a device to a WiFi network."""
from enum import Enum
from time import sleep

from mycroft.audio import stop_speaking
from mycroft.identity import IdentityManager
from mycroft.messagebus import Message
from mycroft.skills import MycroftSkill, intent_handler
from mycroft.util.network_utils import check_captive_portal


MARK_II = "mycroft_mark_2"


class WifiConnect(MycroftSkill):
    """Skill that joins a device to a WiFi network."""

    def __init__(self):
        super().__init__()
        self._is_attempting_wifi_connection = False
        self._wifi_setup_started = False
        self.first_ever_run = None

    @property
    def platform(self):
        return self.config_core["enclosure"].get("platform", "unknown")

    def initialize(self):
        """Create event handlers"""
        # This setting will be set to True after first init.
        # We need to retain its state for the first boot greeting.
        self.first_ever_run = self.settings.get("__mycroft_skill_firstrun", True)

        self.add_event("mycroft.started", self._handle_mycroft_started)

        # Captive portal
        self.add_event("hardware.portal-detected", self._handle_portal_detected)

        # 1. Network detection fails
        self.add_event(
            "hardware.network-not-detected", self._handle_network_not_detected
        )

        # 2. Mycroft access point is ready
        self.add_event(
            "hardware.awconnect.ap-activated", self._handle_ap_activated,
        )

        # 3. User has connected to captive portal page
        self.add_event(
            "hardware.awconnect.portal-viewed", self._handle_portal_viewed,
        )

        # 4. User has entered wifi credentials
        self.add_event(
            "hardware.awconnect.credentials-entered", self._handle_credentials_entered,
        )

        # 5. Access point is deactivated, network detection is attempted again
        self.add_event(
            "hardware.awconnect.ap-deactivated", self._handle_ap_deactivated,
        )

        # 6. Network detection succeeds
        self.add_event("hardware.network-detected", self._handle_network_detected)

    def _handle_mycroft_started(self):
        self._show_page("connecting_to_internet")

    def _handle_network_not_detected(self, _message=None):
        """Triggers skill to start"""
        if self.first_ever_run:
            # This is the first time the Skill has ever run
            self.first_ever_run = False
            self.speak_dialog("greeting")
        self._start_wifi_setup()

    def _handle_ap_activated(self, _message=None):
        """Mycroft access point is ready in awconnect"""
        if self._is_attempting_wifi_connection:
            self._wifi_setup_failed()

            # Setup will automatically start again
            self.log.info("Restarting Wi-Fi setup")
            self._is_attempting_wifi_connection = False

        self._access_point_ready()

    def _handle_portal_viewed(self, _message=None):
        """User has connected to access point and visited captive portal page"""
        self._portal_page_viewed()

    def _handle_credentials_entered(self, _message=None):
        """User has selected their wifi network and entered a password"""
        self._wifi_credentials_entered()

    def _handle_ap_deactivated(self, _message=None):
        """Access point has deactivated (wifi success)"""
        # Request another network detection from enclosure
        self.bus.emit(Message("hardware.detect-network"))

    def _handle_network_detected(self, _message=None):
        """Network detection succeeded after setup"""
        if self.first_ever_run:
            # This is the first time the Skill has ever run
            self.first_ever_run = False
            self.speak_dialog("greeting")
        if self._wifi_setup_started:
            self._wifi_setup_started = False
            self._wifi_setup_succeeded()
            self._wifi_setup_ended()

    def _start_wifi_setup(self):
        self._wifi_setup_started = True
        self._is_attempting_wifi_connection = False
        self.bus.emit(Message("system.wifi.setup.started"))
        self.speak_dialog("network-connection-needed")

        # Request to enclosure to start activity
        self.bus.emit(Message("hardware.awconnect.create-ap"))

    def _access_point_ready(self):
        self._prompt_to_select_access_point()

    def _portal_page_viewed(self):
        self._prompt_to_select_wifi_network()

    def _wifi_credentials_entered(self):
        self._is_attempting_wifi_connection = True
        self._show_connecting_page()

    def _wifi_setup_succeeded(self):
        self.log.info("Wi-Fi setup succeeded")
        self._report_setup_complete()
        self.bus.emit(Message("system.wifi.setup.connected"))

    def _wifi_setup_failed(self):
        self.log.info("Wi-Fi setup failed")
        self._show_failure_page()
        self.bus.emit(Message("system.wifi.setup.failed"))

    def _wifi_setup_ended(self):
        self.bus.emit(Message("system.wifi.setup.ended"))

    def _prompt_to_select_access_point(self):
        """Prompt user to join temporary access point."""
        self._show_page("access_point_select")
        self.speak_dialog("access-point-created", wait=True)

    def _prompt_to_select_wifi_network(self):
        """Prompt user to sign into access point."""
        self._show_page("network_select")
        self.speak_dialog("choose-wifi-network", wait=True)
        self.speak_dialog("no-prompt", wait=True)

    def _show_connecting_page(self, _message=None):
        """Inform user that wifi connection is being attempted"""
        self._show_page("connecting")

    def _show_failure_page(self, _message=None):
        """Inform user that wifi connection failed"""
        self._show_page("wifi_failure")
        self.speak_dialog("wifi-failure", wait=True)

    def _report_setup_complete(self):
        """Report when wifi setup is complete, network is connected."""
        self.gui["label"] = self.translate("connected")
        self._show_page("wifi_success")
        sleep(5)
        self.gui.release()

    def _show_page(self, page_name_prefix: str):
        """Shows the appropriate screen for the device's platform.

        Args:
            page_name_prefix: part of the page name not platform-specific
        """
        if self.gui.connected:
            if self.platform == MARK_II:
                page_name = page_name_prefix + "_mark_ii.qml"
                self.gui.replace_page(page_name, override_idle=True)
            else:
                page_name = page_name_prefix + "_scalable.qml"
                self.gui.show_page(page_name, override_idle=True)

    def _handle_portal_detected(self, _message):
        """Called when a captive portal is detected.

        We show a known (non-HTTPS) URL in a web browser so the user can see the
        page and login.

        We periodically check to see if the captive portal is still present, and
        if not, clear the GUI and continue the wifi setup process.
        """
        self.log.info("Showing browser for captive portal login")
        self.cancel_scheduled_event("CheckPortal")
        self.gui.show_url("http://start.mycroft.ai/portal-check.html", override_idle=True)
        self.schedule_repeating_event(
            self._check_portal, when=3, frequency=2, name="CheckPortal"
        )
        self.speak_dialog("login")

    def _check_portal(self):
        self.log.info("Checking if captive portal is still active")

        if not check_captive_portal():
            self.log.info("Captive portal is no longer active")
            self.cancel_scheduled_event("CheckPortal")
            self.bus.emit(Message("hardware.detect-network"))
            self.gui.release()


def create_skill():
    return WifiConnect()
