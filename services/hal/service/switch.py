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
import subprocess
import sys
from threading import Thread
from typing import Optional

from mycroft_bus_client import Message, MessageBusClient


class Mark2SwitchClient:
    """Reads the state of Mark II buttons/switches and reports changes on the messagebus"""

    def __init__(self, bus: MessageBusClient):
        self.bus = bus
        self.log = logging.getLogger("hal.leds")
        self._active = {
            "volume_up": False,
            "volume_down": False,
            "action": False,
            "mute": True,
        }
        self._proc_thread: Optional[Thread] = None

    def start(self):
        self._proc_thread = Thread(target=self._run_proc, daemon=True)
        self._proc_thread.start()
        self.bus.on("mycroft.switch.report-states", self._handle_get_state)

    def _run_proc(self):
        """Reads button state changes from the mark2-buttons command"""
        try:
            button_cmd = ["mark2-buttons"]
            self.log.debug(button_cmd)
            proc = subprocess.Popen(
                button_cmd, stdout=subprocess.PIPE, universal_newlines=True
            )
            with proc:
                for line in proc.stdout:
                    line = line.strip()
                    if not line:
                        continue

                    name, is_active_str = line.split(maxsplit=1)
                    is_active = is_active_str.strip().lower() == "true"
                    self._active[name] = is_active
                    self._report_state(name, is_active)
        except Exception:
            self.log.exception("Error reading button state")

            # Just exit the service. systemd will restart it.
            sys.exit(1)

    def _handle_get_state(self, _message: Message):
        """Report the state of all switches"""
        for name, is_active in self._active.items():
            self._report_state(name, is_active)

    def stop(self):
        pass

    def _report_state(self, name: str, is_active: bool):
        state = "on" if is_active else "off"
        self.bus.emit(
            Message("mycroft.switch.state", data={"name": name, "state": state})
        )
