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
import sys
import time
from threading import Event, Thread
from typing import Any, Dict, Optional

import sdnotify
from mycroft.configuration import Configuration
from mycroft.messagebus.client import create_client
from mycroft_bus_client import Message, MessageBusClient

# from .enclosure.mark2 import EnclosureMark2

SERVICE_ID = "enclosure"
LOG = logging.getLogger(SERVICE_ID)
NOTIFIER = sdnotify.SystemdNotifier()
WATCHDOG_DELAY = 0.5

IDLE_SKILL_ID = "homescreen.mycroftai"


def main():
    """Service entry point"""
    logging.basicConfig(level=logging.DEBUG)
    LOG.info("Starting service...")

    try:
        config = Configuration.get()
        bus = _connect_to_bus(config)

        # Wait for GUI connected
        LOG.debug("Waiting for GUI...")
        while True:
            response = bus.wait_for_response(Message("gui.status.request"))
            if response.data.get("connected", False):
                break

            time.sleep(0.5)

        LOG.debug("GUI connected")

        # enclosure = EnclosureMark2(bus, config)
        # enclosure.run()
        led_session_id: Optional[str] = None

        def handle_wake(message):
            nonlocal led_session_id
            led_session_id = message.data.get("mycroft_session_id")

            # Stop speaking and clear LEDs
            bus.emit(Message("mycroft.tts.stop"))
            bus.emit(Message("mycroft.hal.set-leds", data={"pattern": "pulse"}))

        def handle_session_started(message):
            nonlocal led_session_id
            if message.data.get("skill_id") != IDLE_SKILL_ID:
                led_session_id = message.data.get("mycroft_session_id")
                bus.emit(Message("mycroft.hal.set-leds", data={"pattern": "chase"}))

        def handle_session_ended(message):
            nonlocal led_session_id
            if led_session_id == message.data.get("mycroft_session_id"):
                bus.emit(
                    Message(
                        "mycroft.hal.set-leds",
                        data={"pattern": "solid", "rgb": [0, 0, 0]},
                    )
                )

        def handle_idle(message):
            nonlocal led_session_id
            led_session_id = None
            bus.emit(
                Message(
                    "mycroft.hal.set-leds",
                    data={"pattern": "solid", "rgb": [0, 0, 0]},
                )
            )

        bus.on("recognizer_loop:awoken", handle_wake)
        bus.on("mycroft.session.started", handle_session_started)
        bus.on("mycroft.session.ended", handle_session_ended)
        bus.on("mycroft.gui.idle", handle_idle)

        # Start watchdog thread
        Thread(target=_watchdog, daemon=True).start()

        # Inform systemd that we successfully started
        NOTIFIER.notify("READY=1")
        bus.emit(Message(f"{SERVICE_ID}.initialize.ended"))

        # HACK: Show home screen
        bus.emit(Message("mycroft.gui.idle"))

        try:
            # Wait for exit signal
            Event().wait()
        except KeyboardInterrupt:
            pass
        finally:
            enclosure.stop()
            bus.close()

        LOG.info("Service is shutting down...")
    except Exception:
        LOG.exception("Service failed to start")


def _connect_to_bus(config: Dict[str, Any]) -> MessageBusClient:
    bus = create_client(config)
    bus.run_in_thread()
    bus.connected_event.wait()
    bus.on(f"{SERVICE_ID}.service.connected", lambda m: bus.emit(m.response()))
    bus.emit(Message(f"{SERVICE_ID}.initialize.started"))
    LOG.info("Connected to Mycroft Core message bus")

    return bus


def _watchdog():
    try:
        while True:
            # Prevent systemd from restarting service
            NOTIFIER.notify("WATCHDOG=1")
            time.sleep(WATCHDOG_DELAY)
    except Exception:
        LOG.exception("Unexpected error in watchdog thread")


if __name__ == "__main__":
    main()
