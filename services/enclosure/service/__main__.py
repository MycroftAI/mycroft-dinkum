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

            # Stop speaking
            bus.emit(Message("mycroft.tts.stop"))
            bus.emit(Message("mycroft.feedback.set-state", data={"state": "awake"}))

        def handle_session_started(message):
            nonlocal led_session_id
            if message.data.get("skill_id") != IDLE_SKILL_ID:
                led_session_id = message.data.get("mycroft_session_id")
                bus.emit(
                    Message("mycroft.feedback.set-state", data={"state": "thinking"})
                )

        # def handle_session_ended(message):
        #     nonlocal led_session_id
        #     if led_session_id == message.data.get("mycroft_session_id"):
        #         bus.emit(
        #             Message("mycroft.feedback.set-state", data={"state": "asleep"})
        #         )

        def handle_idle(message):
            nonlocal led_session_id
            led_session_id = None
            bus.emit(Message("mycroft.feedback.set-state", data={"state": "asleep"}))

        def handle_switch_state(message):
            name = message.data.get("name")
            state = message.data.get("state")
            if name == "mute":
                # This looks wrong, but the off/inactive state of the switch
                # means muted.
                if state == "off":
                    bus.emit(Message("mycroft.mic.mute"))
                else:
                    bus.emit(Message("mycroft.mic.unmute"))

        bus.on("recognizer_loop:awoken", handle_wake)
        bus.on("mycroft.session.started", handle_session_started)
        # bus.on("mycroft.session.ended", handle_session_ended)
        bus.on("mycroft.gui.idle", handle_idle)
        bus.on("mycroft.switch.state", handle_switch_state)

        # Return to idle screen if GUI reconnects
        bus.on("gui.initialize.ended", lambda m: bus.emit(Message("mycroft.gui.idle")))

        # Start watchdog thread
        Thread(target=_watchdog, daemon=True).start()

        # Inform systemd that we successfully started
        NOTIFIER.notify("READY=1")
        bus.emit(Message(f"{SERVICE_ID}.initialize.ended"))

        # HACK: Show home screen
        bus.emit(Message("mycroft.gui.idle"))

        # Request switch states so mute is correctly shown
        bus.emit(Message("mycroft.switch.report-states"))

        bus.emit(Message("mycroft.ready"))

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
