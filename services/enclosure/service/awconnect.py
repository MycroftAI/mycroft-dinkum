import socket
from threading import Thread
from typing import Optional

from mycroft.util.log import LOG
from mycroft_bus_client import Message, MessageBusClient

SOCKET_PATH = "/awconnect/tmp/mycroft_socket"

EVENT_CREATE = "create-ap"
EVENT_CREATED = "ap-created"
EVENT_VISITED_PORTAL = "user-visited-portal"
EVENT_ENTERED_CREDS = "user-entered-credentials"
EVENT_DESTROYED = "ap-destroyed"


class AwconnectClient:
    """Communicates with awconnect server to manage Mycroft access point.

    Messages are sent and received as lines of text over the socket.
    """

    def __init__(self, bus: MessageBusClient):
        self.bus = bus
        self._socket: Optional[socket.socket] = None

    def start(self):
        # Connect to file-based socket
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.connect(SOCKET_PATH)

        Thread(target=self._run, daemon=True).start()

    def stop(self):
        if self._socket is not None:
            self._socket.close()

    def _run(self):
        try:
            with self._socket.makefile(mode="rw") as conn_file:
                # Wait for hello
                LOG.debug("Waiting for hello message")
                conn_file.readline()
                LOG.info("Connected to awconnect")

                # Request that access point is created
                print(EVENT_CREATE, file=conn_file, flush=True)

                for line in conn_file:
                    line = line.strip()

                    if line == EVENT_CREATED:
                        LOG.info("Access point created")
                        self.bus.emit(Message("hardware.awconnect.ap-activated"))
                    elif line == EVENT_VISITED_PORTAL:
                        LOG.info("User viewed captive portal page")
                        self.bus.emit(Message("hardware.awconnect.portal-viewed"))
                    elif line == EVENT_ENTERED_CREDS:
                        LOG.info("User entered wifi credentials")
                        self.bus.emit(Message("hardware.awconnect.credentials-entered"))
                    elif line == EVENT_DESTROYED:
                        LOG.info("Access point destroyed")
                        self.bus.emit(Message("hardware.awconnect.ap-deactivated"))
                        break
        except Exception:
            LOG.exception("Error communicating with awconnect socket")
