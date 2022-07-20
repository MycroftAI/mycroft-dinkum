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
from typing import Any, Dict

import sdnotify
from mycroft.configuration import Configuration
from mycroft.messagebus.client import create_client
from mycroft_bus_client import Message, MessageBusClient

from .namespace import NamespaceManager

SERVICE_ID = "gui"
LOG = logging.getLogger(SERVICE_ID)
NOTIFIER = sdnotify.SystemdNotifier()
WATCHDOG_DELAY = 0.5


def main():
    """Service entry point"""
    logging.basicConfig(level=logging.DEBUG)
    LOG.info("Starting service...")

    try:
        config = Configuration.get()
        bus = _connect_to_bus(config)
        namespace_manager = NamespaceManager(bus)

        # Start watchdog thread
        Thread(target=_watchdog, daemon=True).start()

        # Inform systemd that we successfully started
        NOTIFIER.notify("READY=1")
        bus.emit(Message(f"{SERVICE_ID}.initialize.ended"))

        try:
            # Wait for exit
            Event().wait()
        except KeyboardInterrupt:
            LOG.info("Service is shutting down...")
        finally:
            bus.close()
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
