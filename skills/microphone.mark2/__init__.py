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
import subprocess
import time
from threading import Thread
from typing import Optional

from mycroft.messagebus.message import Message
from mycroft.skills import GuiClear, MycroftSkill


class Microphone(MycroftSkill):
    def __init__(self, skill_id: str):
        super().__init__(skill_id=skill_id, name="Microphone Skill")
        self._diagnostics_running = False
        self._max_energy = 1.0
        self._gui_data = {
            "vad_probability": 0.0,
            "hotword_probability": 0.0,
            "is_speech": False,
            "energy_norm": 0.0,
            "state": "idle",
            "utterance": "<none>",
            "gain": "<unknown>",
        }

        self._xmos_thread_running = True
        self._xmos_thread: Optional[Thread] = None

    def initialize(self):
        self.add_event("mycroft.microphone.settings", self.handle_open)
        self.gui.register_handler(
            "mycroft.microphone.settings.close",
            "main.qml",
            self.handle_close,
        )

        self.add_event("mycroft.mic.diagnostics", self._mic_diagnostics)
        self.add_event("mycroft.mic.diagnostics:utterance", self._handle_utterance)
        self.add_event("recognizer_loop:record_begin", self._handle_record_begin)
        self.add_event("recognizer_loop:record_end", self._handle_record_end)

        self._xmos_thread = Thread(target=self._update_xmos, daemon=True)
        self._xmos_thread.start()

    def shutdown(self):
        if self._xmos_thread is not None:
            self._xmos_thread_running = False
            self._xmos_thread.join()
            self._xmos_thread = None

    def handle_open(self, _message):
        self._set_diagnostics(True)
        self._diagnostics_running = True
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
        self._diagnostics_running = False
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

        self._update_gui()

    def _set_diagnostics(self, enabled: bool):
        self.bus.emit(Message("mycroft.mic.set-diagnostics", data={"enabled": enabled}))

    def _handle_record_begin(self, message):
        self._gui_data["state"] = "recording"
        self._gui_data["utterance"] = ""
        self._update_gui()

    def _handle_record_end(self, message):
        self._gui_data["state"] = "processing"
        self._gui_data["utterance"] = ""
        self._update_gui()

    def _handle_utterance(self, message):
        self._gui_data["utterance"] = message.data.get("utterance") or "<none>"
        self._update_gui()

    def _handle_utterance(self, message):
        self._gui_data["state"] = "idle"
        self._gui_data["utterance"] = message.data.get("utterance") or "<none>"
        self._update_gui()

        # Reset LED ring
        self.bus.emit(Message("mycroft.feedback.set-state", data={"state": "asleep"}))

    def _update_gui(self):
        self.update_gui_values("main.qml", self._gui_data)

    def _update_xmos(self):
        while self._xmos_thread_running:
            if self._diagnostics_running:
                try:
                    self._gui_data["gain"] = self._get_xmos_parameter("GAIN_CH0_AGC")
                except Exception:
                    self.log.exception("Error in XMOS thread")

            time.sleep(0.2)

    def _get_xmos_parameter(self, name: str) -> Optional[str]:
        try:
            xmos_name = f"GET_{name.upper()}"
            command = ["vfctrl_i2c", "--no-check-version", xmos_name]
            lines = subprocess.check_output(
                command, universal_newlines=True
            ).splitlines()
            for line in lines:
                line = line.strip()
                if line.startswith(f"{xmos_name}:"):
                    return line.split(":", maxsplit=1)[-1].strip()
        except Exception:
            self.log.exception("Error getting parameter: %s", name)

        return None

    def handle_gui_idle(self):
        if self._diagnostics_running:
            self.show_gui()
            return True

        return False


def create_skill(skill_id: str):
    return Microphone(skill_id=skill_id)
