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
import asyncio
import functools
import logging
import subprocess
import sys
from threading import Thread
from typing import Optional

from dbus_next import BusType
from dbus_next import Message as DBusMessage
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, dbus_property
from mycroft_bus_client import Message, MessageBusClient

MARK2_BUTTON = """
<!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
<node name="/ai/mycroft/mark2/button">
  <interface name="ai.mycroft.Mark2ButtonInterface">
    <signal name="volume_up">
      <arg name="new_value" type="b"/>
    </signal>
    <signal name="volume_down">
      <arg name="new_value" type="b"/>
    </signal>
    <signal name="action">
      <arg name="new_value" type="b"/>
    </signal>
    <signal name="mute">
      <arg name="new_value" type="b"/>
    </signal>
    <method name="report">
    </method>
  </interface>
</node>
"""


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
        """Runs asyncio loop for dbus-next"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._run_proc_async())
        loop.close()

    async def _run_proc_async(self):
        """Reads button state changes from Mark II DBus HAL service"""
        try:
            # Connect to DBus HAL service
            mark2_name = "ai.mycroft.mark2"
            button_namespace = "ai.mycroft.Mark2ButtonInterface"
            button_path = "/ai/mycroft/mark2/button"

            dbus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            introspection = await dbus.introspect(mark2_name, button_path)
            button_object = dbus.get_proxy_object(
                mark2_name, button_path, introspection
            )
            button_interface = button_object.get_interface(button_namespace)

            async def button_changed(name: str, is_active: bool):
                self._active[name] = is_active
                self._report_state(name, is_active)

            button_interface.on_volume_up(
                functools.partial(button_changed, "volume_up")
            )
            button_interface.on_volume_down(
                functools.partial(button_changed, "volume_down")
            )
            button_interface.on_action(functools.partial(button_changed, "action"))
            button_interface.on_mute(functools.partial(button_changed, "mute"))

            # Request current button states
            await button_interface.call_report()

            await dbus.wait_for_disconnect()
            self.log.debug("Disconnected from DBus")
        except Exception:
            self.log.exception("Error reading button state")

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
