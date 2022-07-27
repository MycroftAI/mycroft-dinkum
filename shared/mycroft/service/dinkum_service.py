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
import signal
import sys
import time
from abc import ABC, abstractmethod
from threading import Event, Thread
from typing import Any, Dict

import sdnotify
from mycroft.configuration import Configuration
from mycroft.messagebus.client import create_client
from mycroft_bus_client import Message, MessageBusClient

# Seconds between systemd watchdog updates
WATCHDOG_DELAY = 0.5


class DinkumService(ABC):
    """Shared base class for dinkum services"""

    def __init__(self, service_id: str):
        self.service_id = service_id
        self.log = logging.getLogger(self.service_id)
        self._notifier = sdnotify.SystemdNotifier()

    def main(self):
        """Service entry point"""
        try:
            self.before_start()
            self.start()
            self.after_start()

            try:
                self.run()
            except KeyboardInterrupt:
                pass
            finally:
                self.stop()
                self.after_stop()
        except Exception:
            self.log.exception("Service failed to start")

    def before_start(self):
        """Initialization logic called before start()"""
        self.config = Configuration.get()

        level_str = self.config.get("log_level", "debug").upper()
        level = logging.getLevelName(level_str)
        logging.basicConfig(level=level)
        self.log.info("Starting service...")

        self._connect_to_bus()

    @abstractmethod
    def start(self):
        """
        User code for starting service.
        Any exception here will cause systemd to restart the service.
        """
        pass

    def after_start(self):
        """Initialization logic called after start()"""
        self._start_watchdog()

        # Inform systemd that we successfully started
        self._notifier.notify("READY=1")
        self.bus.emit(Message(f"{self.service_id}.initialize.ended"))

    def run(self):
        """
        User code for running the service.
        Defaults to blocking until the service is terminated externally.
        """
        # Wait for exit signal
        run_event = Event()

        def signal_handler(_sig, _frame):
            """Registers signal handlers to catch CTRL+C and TERM."""
            run_event.set()

        original_int_handler = signal.signal(signal.SIGINT, signal_handler)
        original_term_handler = signal.signal(signal.SIGTERM, signal_handler)

        try:
            run_event.wait()
        finally:
            # Restore original signal handlers
            signal.signal(signal.SIGINT, original_int_handler)
            signal.signal(signal.SIGTERM, original_term_handler)

    @abstractmethod
    def stop(self):
        """
        User code for stopping the service.
        Called even if there is an exception in run()
        """
        pass

    def after_stop(self):
        """Shut down code called after stop()"""
        self.bus.close()

    def _connect_to_bus(self):
        """Connects to the websocket message bus"""
        self.bus = create_client(self.config)
        self.bus.run_in_thread()
        self.bus.connected_event.wait()
        self.bus.on(
            f"{self.service_id}.service.connected",
            lambda m: self.bus.emit(m.response()),
        )
        self.bus.emit(Message(f"{self.service_id}.initialize.started"))
        self.log.info("Connected to Mycroft Core message bus")

    def _start_watchdog(self):
        """Run systemd watchdog in separate thread"""
        Thread(target=self._watchdog, daemon=True).start()

    def _watchdog(self):
        """Notify systemd that the service is still running"""
        try:
            while True:
                # Prevent systemd from restarting service
                self._notifier.notify("WATCHDOG=1")
                time.sleep(WATCHDOG_DELAY)
        except Exception:
            self.log.exception("Unexpected error in watchdog thread")

    def _wait_for_service(self, service_id: str, wait_sec: float = 0.5):
        # Wait for intent service
        self.log.debug("Waiting for %s service...", service_id)
        while True:
            response = self.bus.wait_for_response(
                Message(f"{service_id}.service.connected")
            )
            if response:
                break

            time.sleep(wait_sec)

        LOG.debug("%s service connected", service_id)
