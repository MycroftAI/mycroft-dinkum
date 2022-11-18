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
"""Defines the base class for all Dinkum services."""
import argparse
import signal
import time
from abc import ABC, abstractmethod
from enum import Enum
from threading import Event, Thread
from typing import Collection, List, Optional

import sdnotify
from mycroft_bus_client import Message

from mycroft.configuration import Configuration
from mycroft.messagebus.client import create_client
from mycroft.util.log import get_mycroft_logger

# Seconds between systemd watchdog updates
WATCHDOG_DELAY = 0.5

_log = get_mycroft_logger(__name__)


class ServiceState(str, Enum):
    """Enumerates the states (i.e. status) services can have."""
    NOT_STARTED = "not_started"
    STARTED = "started"
    RUNNING = "running"
    STOPPING = "stopping"


# TODO: Add logging of configuration values used by service at time of load and reload.
class DinkumService(ABC):
    """Shared base class for dinkum services.

    Attributes
        service_id: short textual description of the service
    """

    def __init__(self, service_id: str):
        self.service_id = service_id
        self.config = Configuration.get()
        self._notifier = sdnotify.SystemdNotifier()
        self._state: ServiceState = ServiceState.NOT_STARTED

    @property
    def state(self):
        """Exposes a read-only public property representing the service state.

        Only the service itself should be able to change its state.
        """
        return self._state

    def main(self, argv: Optional[List[str]] = None):
        """Service entry point.

        Args:
            argv: arguments passed to the service from the command line
        """
        parser = argparse.ArgumentParser()
        parser.add_argument("--service-id", help="Override service id")
        args = parser.parse_args(argv)

        if args.service_id is not None:
            self.service_id = args.service_id

        try:
            self._state = ServiceState.NOT_STARTED
            self.before_start()
            self.start()
            self._state = ServiceState.STARTED
            self.after_start()

            try:
                self._state = ServiceState.RUNNING
                self.run()
            except KeyboardInterrupt:
                pass
            finally:
                self._state = ServiceState.STOPPING
                self.stop()
                self.after_stop()
                self._state = ServiceState.NOT_STARTED
        except Exception:
            _log.exception("Service failed to start")

    def before_start(self):
        """Executes logic that needs to occur after constructor but prior to start."""
        _log.info("%s service starting...", self.service_id)
        self._connect_to_bus()

    @abstractmethod
    def start(self):
        """Executes service-specific startup logic.

        Any exception here will cause systemd to restart the service.
        """
        pass

    def after_start(self):
        """Executes logic that needs to occur after start but before run."""
        self._start_watchdog()

        # Inform systemd that we successfully started
        self._notifier.notify("READY=1")
        self.bus.emit(Message(f"{self.service_id}.initialize.ended"))

    def run(self):
        """Runs the service until it is stopped.

        Defaults to blocking until the service is terminated externally.
        """
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
        """Executes service-specific shutdown logic.

        Called even if there is an exception in run()
        """
        pass

    def after_stop(self):
        """Executes logic that needs to occur after stop but before exiting."""
        self.bus.close()

    def _connect_to_bus(self):
        """Connects to the websocket message bus"""
        self.bus = create_client(self.config)
        self.bus.run_in_thread()
        self.bus.connected_event.wait()
        _log.info("Connected to Mycroft Core message bus")

        # Add event handlers
        self.bus.on(f"{self.service_id}.service.state", self._report_service_state)
        self.bus.on("configuration.updated", self._reload_config)

        self.bus.emit(Message(f"{self.service_id}.initialize.started"))

    def _report_service_state(self, message):
        """Communicates service state changes."""
        self.bus.emit(message.response(data={"state": self.state.value}))
        _log.info("Service %s %s", self.service_id, self.state.value)

    def _reload_config(self, _message):
        """Forces reloading of config"""
        Configuration.reload()
        _log.info("Reloaded configuration")

    def _start_watchdog(self):
        """Runs systemd watchdog in separate thread."""
        Thread(target=self._watchdog, daemon=True).start()

    def _watchdog(self):
        """Notifies systemd that the service is still running."""
        try:
            while True:
                # Prevent systemd from restarting service
                self._notifier.notify("WATCHDOG=1")
                time.sleep(WATCHDOG_DELAY)
        except Exception:
            _log.exception("Unexpected error in watchdog thread")

    def _wait_for_service(
        self,
        service_id: str,
        states: Optional[Collection[ServiceState]] = None,
        wait_sec: float = 1.0,
    ):
        """Pauses this service while waiting for another service to report a state.

        Args:
            service_id: ID of the service being waited on
            states: States to wait for
            wait_sec: number of seconds to wait between checking for state
        """
        if states is None:
            states = {ServiceState.RUNNING}

        _log.info("Waiting for %s service to report %s state(s)", service_id, states)
        while True:
            response = self.bus.wait_for_response(
                Message(f"{service_id}.service.state")
            )
            if response and (response.data.get("state") in states):
                break

            time.sleep(wait_sec)

        _log.info(
            "Received %s state from %s service - ending wait",
            service_id,
            response.data.get("state")
        )

    def _wait_for_gui(self, wait_sec: float = 1.0):
        """Pauses this service while it waits for GUI to report ready.

        Args:
            wait_sec: number of seconds to wait between GUI status checks
        """
        _log.info("Connecting to GUI...")
        while True:
            response = self.bus.wait_for_response(Message("gui.status.request"))
            if response and response.data.get("connected", False):
                break

            time.sleep(wait_sec)

        _log.info("GUI connected")

    def _wait_for_ready(self, wait_sec: float = 1.0):
        """Pauses this service until all services report ready.

        Args:
            wait_sec: number of seconds to wait between system ready checks
        """
        _log.debug("Waiting for all services to report ready...")
        while True:
            response = self.bus.wait_for_response(Message("mycroft.ready.get"))
            if response and response.data.get("ready", False):
                break

            time.sleep(wait_sec)

        _log.debug("All services reported ready - ending wait")
