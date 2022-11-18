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
""""""
import socket
from threading import Thread
from typing import Optional

from mycroft.util.log import get_service_logger
from mycroft_bus_client import Message, MessageBusClient

EVENT_CREATE = "create-ap"
EVENT_CREATED = "ap-created"
EVENT_VISITED_PORTAL = "user-visited-portal"
EVENT_ENTERED_CREDS = "user-entered-credentials"
EVENT_DESTROYED = "ap-destroyed"

_log = get_service_logger("enclosure", __name__)


class AwconnectClient:
    """Communicates with awconnect server to manage Mycroft access point.

    Messages are sent and received as lines of text over the socket.
    """

    def __init__(self, bus: MessageBusClient, socket_path: str):
        self.bus = bus
        self.socket_path = socket_path
        self._socket: Optional[socket.socket] = None

    def start(self):
        """Connects to file-based socket and starts thread."""
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.connect(self.socket_path)

        Thread(target=self._run, daemon=True).start()

    def stop(self):
        """Closes socket."""
        if self._socket is not None:
            self._socket.close()

    def _run(self):
        """Loops through different states in the Wi-Fi connect process."""
        try:
            with self._socket.makefile(mode="rw") as conn_file:
                # Wait for hello
                _log.info("Waiting for hello message")
                conn_file.readline()
                _log.info("Connected to awconnect")

                # Request that access point is created
                print(EVENT_CREATE, file=conn_file, flush=True)

                for line in conn_file:
                    line = line.strip()

                    if line == EVENT_CREATED:
                        _log.info("Access point created")
                        self.bus.emit(Message("hardware.awconnect.ap-activated"))
                    elif line == EVENT_VISITED_PORTAL:
                        _log.info("User viewed captive portal page")
                        self.bus.emit(Message("hardware.awconnect.portal-viewed"))
                    elif line == EVENT_ENTERED_CREDS:
                        _log.info("User entered wifi credentials")
                        self.bus.emit(Message("hardware.awconnect.credentials-entered"))
                    elif line == EVENT_DESTROYED:
                        _log.info("Access point destroyed")
                        self.bus.emit(Message("hardware.awconnect.ap-deactivated"))
                        break
        except Exception:
            _log.exception("Error communicating with awconnect socket")
