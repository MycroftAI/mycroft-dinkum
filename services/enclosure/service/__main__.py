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
from mycroft_bus_client import Message

IDLE_SKILL_ID = "homescreen.mycroftai"


class EnclosureService(DinkumService):
    def __init__(self):
        super().__init__(service_id="enclosure")

        self.led_session_id: Optional[str] = None

    def start(self):
        self._wait_for_gui()

        self.bus.on("recognizer_loop:awoken", self.handle_wake)
        self.bus.on("mycroft.skill-response", self.handle_skill_response)
        self.bus.on("mycroft.session.started", self.handle_session_started)
        self.bus.on("mycroft.session.ended", self.handle_session_ended)
        self.bus.on("mycroft.session.no-active-sessions", self.handle_idle)
        self.bus.on("mycroft.gui.idle", self.handle_idle)
        self.bus.on("mycroft.switch.state", self.handle_switch_state)

        # Return to idle screen if GUI reconnects
        self.bus.on(
            "gui.initialize.ended", lambda m: self.bus.emit(Message("mycroft.gui.idle"))
        )

        # HACK: Show home screen
        self.bus.emit(Message("mycroft.gui.idle"))

        # Request switch states so mute is correctly shown
        self.bus.emit(Message("mycroft.switch.report-states"))

        # TODO: Make this request/response
        self.bus.emit(Message("mycroft.ready"))

    def stop(self):
        pass

    def handle_wake(self, message):
        self.led_session_id = message.data.get("mycroft_session_id")

        # Stop speaking
        self.bus.emit(Message("mycroft.tts.stop"))
        self.bus.emit(Message("mycroft.feedback.set-state", data={"state": "awake"}))

    def handle_skill_response(self, message):
        self.led_session_id = message.data.get("mycroft_session_id")
        self.bus.emit(Message("mycroft.feedback.set-state", data={"state": "thinking"}))

    def handle_session_started(self, message):
        if message.data.get("skill_id") != IDLE_SKILL_ID:
            self.led_session_id = message.data.get("mycroft_session_id")
            self.bus.emit(
                Message("mycroft.feedback.set-state", data={"state": "thinking"})
            )

    def handle_session_ended(self, message):
        if message.data.get("mycroft_session_id") == self.led_session_id:
            self.led_session_id = None
            self.bus.emit(
                Message("mycroft.feedback.set-state", data={"state": "asleep"})
            )

    def handle_idle(self, message):
        self.led_session_id = None
        self.bus.emit(Message("mycroft.feedback.set-state", data={"state": "asleep"}))

    def handle_switch_state(self, message):
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


def main():
    """Service entry point"""
    EnclosureService().main()


if __name__ == "__main__":
    main()
