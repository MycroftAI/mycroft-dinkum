# Copyright 2018 Mycroft AI Inc.
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
from mycroft.messagebus.message import Message
from mycroft.skills import GuiClear, MycroftSkill


class Microphone(MycroftSkill):
    def __init__(self, skill_id: str):
        super().__init__(skill_id=skill_id, name="Microphone Skill")
        self._running = False
        self._max_energy = 1.0
        self._gui_data = {
            "vad_probability": 0.0,
            "hotword_probability": 0.0,
            "is_speech": False,
            "energy_norm": 0.0,
        }

    def initialize(self):
        self.add_event("mycroft.microphone.settings", self.handle_open)
        self.gui.register_handler(
            "mycroft.microphone.settings.close",
            "main.qml",
            self.handle_close,
        )

        self.add_event("mycroft.mic.diagnostics", self._mic_diagnostics)

    def handle_open(self, _message):
        self._set_diagnostics(True)
        self._running = True
        self.show_gui()

    def show_gui(self):
        self.emit_start_session(
            gui=(
                "main.qml",
                self._gui_data,
            ),
            gui_clear=GuiClear.NEVER,
        )

    def handle_close(self, _message):
        self._running = False
        self._set_diagnostics(False)
        self.bus.emit(Message("mycroft.gui.idle"))

    def _mic_diagnostics(self, message):
        data = message.data
        self._gui_data["vad_probability"] = data.get("vad_probability", 0.0)
        self._gui_data["hotword_probability"] = data.get("hotword_probability", 0.0)
        self._gui_data["is_speech"] = data.get("is_speech", False)

        energy = data.get("energy", 0.0)
        self._max_energy = max(1.0, max(energy, self._max_energy))
        self._gui_data["energy_norm"] = energy / self._max_energy

        self.update_gui_values("main.qml", self._gui_data)

    def _set_diagnostics(self, enabled: bool):
        self.bus.emit(Message("mycroft.mic.set-diagnostics", data={"enabled": enabled}))

    def handle_gui_idle(self):
        if self._running:
            self.show_gui()
            return True

        return False


def create_skill(skill_id: str):
    return Microphone(skill_id=skill_id)
