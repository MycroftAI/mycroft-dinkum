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
"""Executable for running the enclosure service."""
from pathlib import Path
from typing import Optional

import xdg.BaseDirectory
from mycroft_bus_client import Message

from mycroft.configuration.remote import RemoteSettingsDownloader
from mycroft.service import DinkumService
from mycroft.skills.settings import SkillSettingsDownloader
from mycroft.util.log import configure_mycroft_logger, get_mycroft_logger
from .connect_check import ConnectCheck

configure_mycroft_logger("enclosure")
_log = get_mycroft_logger(__name__)


class EnclosureService(DinkumService):
    """Defines the enclosure service."""

    def __init__(self):
        super().__init__(service_id="enclosure")
        self.led_session_id: Optional[str] = None
        self.mycroft_ready = False
        self._settings_downloader = RemoteSettingsDownloader()

    def start(self):
        """Performs service initialization logic."""
        enclosure = self.config["enclosure"]
        self._idle_display_skill = enclosure["idle_display_skill"]
        self._idle_skill_overrides = enclosure["idle_skill_overrides"]
        self._idle_skill_overrides.append(self._idle_display_skill)

        self._settings_downloader.initialize(self.bus)

        self.bus.on("mycroft.ready.get", self.handle_ready_get)
        self._wait_for_gui()

        self.bus.on("recognizer_loop:awoken", self.handle_wake)
        self.bus.on("mycroft.skill-response", self.handle_skill_response)
        self.bus.on("mycroft.session.started", self.handle_session_started)
        self.bus.on("mycroft.session.ended", self.handle_session_ended)
        self.bus.on("mycroft.gui.idle", self.handle_gui_idle)
        self.bus.on("mycroft.switch.state", self.handle_switch_state)
        self.bus.on(
            "recognizer_loop:speech.recognition.unknown",
            self.handle_unknown_recognition,
        )

        # Return to idle screen if GUI reconnects
        self.bus.on("gui.initialize.ended", self.handle_gui_reconnect)

        # Connected to internet + paired
        self.bus.on("server-connect.startup-finished", self.handle_startup_finished)

        remote_settings_path = (
            Path(xdg.BaseDirectory.xdg_config_home)
            / "mycroft"
            / "mycroft.remote.skill_settings.json"
        )
        self._skill_settings_downloader = SkillSettingsDownloader(
            self.bus, remote_settings_path
        )
        self._connect_check = ConnectCheck(
            self.bus, self.config, self._skill_settings_downloader
        )
        self._connect_check.load_data_files()
        self._connect_check.initialize()
        self._connect_check.start()

    def stop(self):
        """Performs service shutdown logic."""
        pass

    def handle_startup_finished(self, _: Message):
        """Performs tasks required system services are initialized."""
        # Skills should have been loaded by now
        self.bus.emit(Message("mycroft.skills.initialized"))

        # Request switch states so mute is correctly shown
        self.bus.emit(Message("mycroft.switch.report-states"))

        # Inform services that config may have changed
        self.bus.emit(Message("configuration.updated"))

        # Inform skills that we're ready
        self.mycroft_ready = True
        self.bus.emit(Message("mycroft.ready"))
        _log.info("Enclosure service ready")

        # Set default volume
        self.bus.emit(
            Message("mycroft.volume.set", data={"percent": 0.6, "no_osd": True})
        )

        # Show idle screen
        self.bus.emit(Message("mycroft.gui.idle"))

        # Stop connect check activity
        self._connect_check.default_shutdown()
        self._connect_check = None

        _log.info("All services ready for use")
        self._settings_downloader.schedule()

    def handle_ready_get(self, message: Message):
        """Responds to request for "ready" status.

        Args:
            message: event message for mycroft.ready.get
        """
        self.bus.emit(message.response(data={"ready": self.mycroft_ready}))

    def handle_wake(self, message: Message):
        """Prepare device to receive a request after the wake word is recognized.

        Args:
            message: event message for recognizer_loop:awoken
        """
        self.led_session_id = message.data.get("mycroft_session_id")

        # Stop speaking
        self.bus.emit(Message("mycroft.tts.stop"))
        self.bus.emit(Message("mycroft.feedback.set-state", data={"state": "awake"}))

    def handle_skill_response(self, message: Message):
        """Puts the device in a thinking state after a user response is received.

        Args:
            message: event message for mycroft.skill-response
        """
        self.led_session_id = message.data.get("mycroft_session_id")
        self.bus.emit(Message("mycroft.feedback.set-state", data={"state": "thinking"}))

    def handle_session_started(self, message: Message):
        """Puts the device in a thinking state after a user request is received.

        Args:
            message: event message for mycroft.session.started
        """
        if message.data.get("skill_id") != self._idle_display_skill:
            self.led_session_id = message.data.get("mycroft_session_id")
            self.bus.emit(
                Message("mycroft.feedback.set-state", data={"state": "thinking"})
            )

    def handle_session_ended(self, message: Message):
        """Puts the device in a sleeping state after a session ends.

        Args:
            message: event message for mycroft.session.ended
        """
        if message.data.get("mycroft_session_id") == self.led_session_id:
            self.led_session_id = None
            self.bus.emit(
                Message("mycroft.feedback.set-state", data={"state": "asleep"})
            )

    def handle_gui_idle(self, _: Message):
        """Displays idle screen if there are no idle overrides."""
        self.led_session_id = None
        self.bus.emit(Message("mycroft.feedback.set-state", data={"state": "asleep"}))

        for skill_id in self._idle_skill_overrides:
            response = self.bus.wait_for_response(
                Message("mycroft.gui.handle-idle", data={"skill_id": skill_id})
            )
            if response and response.data.get("handled", False):
                _log.info("Idle was handled by %s", skill_id)
                break

    def handle_switch_state(self, message: Message):
        """Toggles microphone mute status when the hardware switch changes position.

        Args:
           message: event message for mycroft.switch.state
        """
        name = message.data.get("name")
        state = message.data.get("state")
        if name == "mute":
            # This looks wrong, but the off/inactive state of the switch
            # means muted.
            if state == "off":
                self.bus.emit(Message("mycroft.mic.mute"))
            else:
                self.bus.emit(Message("mycroft.mic.unmute"))
        elif (name == "action") and (state == "on"):
            # Action button wakes up device
            self.bus.emit(Message("mycroft.mic.listen"))

    def handle_gui_reconnect(self, _: Message):
        """Shows idle skill GUI when the GUI connects."""
        self.bus.emit(Message("mycroft.gui.idle"))

    def handle_unknown_recognition(self, _: Message):
        """Shows idle skill GUI when speech recognition fails."""
        self.bus.emit(Message("mycroft.gui.idle"))


def main():
    """Service entry point"""
    EnclosureService().main()


if __name__ == "__main__":
    main()
