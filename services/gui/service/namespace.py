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
"""Defines the API for the QT GUI.

Manages what is displayed on a device with a touch screen using a LIFO stack
of "active" namespaces (e.g. skills).  At the bottom of the stack is the
namespace for the idle screen skill (if one is specified in the device
configuration).  The namespace for the idle screen skill should never be
removed from the stack.

When a skill with a GUI is triggered by the user, the namespace for that skill
is placed at the top of the stack.  The namespace at the top of the stack
represents the namespace that is visible on the device.  When the skill is
finished displaying information on the screen, it is removed from the top of
the stack.  This will result in the previously active namespace being
displayed.

The persistence of a namespace indicates how long that namespace stays in the
active stack.  A persistence expressed using a number represents how many
seconds the namespace will be active.  A persistence expressed with a True
value will be active until the skill issues a command to remove the namespace.
If a skill with a numeric persistence replaces a namespace at the top of the
stack that also has a numeric persistence, the namespace being replaced will
be removed from the active namespace stack.

The state of the active namespace stack is maintained locally and in the GUI
code.  Changes to namespaces, and their contents, are communicated to the GUI
over the GUI message bus.
"""
from dataclasses import dataclass, field
from threading import Lock, Timer
from typing import Any, Dict, List, Union

from mycroft.configuration import Configuration
from mycroft.messagebus import Message, MessageBusClient
from mycroft.util.log import LOG

from .bus import (
    create_gui_service,
    determine_if_gui_connected,
    get_gui_websocket_config,
    send_message_to_gui,
)

# namespace_lock = Lock()

# RESERVED_KEYS = ["__from", "__idle"]


@dataclass
class Namespace:
    """A grouping mechanism for related GUI pages and data.

    In the majority of cases, a namespace represents a skill.  There is a
    SYSTEM namespace for GUI screens that exist outside of skills.  This class
    defines an API to manage a namespace, its pages and its data.  Actions
    are communicated to the GUI message bus.

    Attributes:
        name: the name of the Namespace, generally the skill ID
        pages: when the namespace is active, contains all the pages that are
            displayed at the same time
        data: a key/value pair representing the data used to populate the GUI
    """

    name: str
    pages: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)


class NamespaceManager:
    """Manages the active namespace stack and the content of namespaces.

    Attributes:
        core_bus: client for communicating with the core message bus
        gui_bus: client for communicating with the GUI message bus
        loaded_namespaces: cache of namespaces that have been introduced
        active_namespaces: LIFO stack of namespaces being displayed
    """

    def __init__(self, core_bus: MessageBusClient):
        self.core_bus = core_bus
        self.gui_bus = create_gui_service(self)
        self.loaded_namespaces: Dict[str, Namespace] = dict()
        self.active_namespaces: List[Namespace] = list()
        self._define_message_handlers()

    def _define_message_handlers(self):
        """Assigns methods as handlers for specified message types."""
        self.core_bus.on("gui.page.show", self.handle_show_page)
        self.core_bus.on("gui.status.request", self.handle_status_request)
        self.core_bus.on("gui.value.set", self.handle_set_value)
        self.core_bus.on("mycroft.gui.connected", self.handle_client_connected)

    def synchronize(self):
        """Synchronize active namespaces with GUI"""
        for namespace_pos, namespace in enumerate(self.active_namespaces):
            send_message_to_gui(
                {
                    "type": "mycroft.session.list.remove",
                    "namespace": "mycroft.system.active_skills",
                    "from": namespace_pos,
                    "to": namespace_pos,
                    "items_number": 1,
                }
            )
            send_message_to_gui(
                {
                    "type": "mycroft.session.list.insert",
                    "namespace": "mycroft.system.active_skills",
                    "position": namespace_pos,
                    "data": [{"skill_id": namespace.name}],
                }
            )
            self._update_namespace_data(namespace)
            send_message_to_gui(
                {
                    "type": "mycroft.gui.list.insert",
                    "namespace": namespace.name,
                    "data": [{"url": namespace.pages}],
                }
            )

    def handle_show_page(self, message: Message):
        """Replaces the current GUI page with a new one"""
        try:
            namespace = self._ensure_namespace_exists(message.data["namespace"])
            namespace.pages = message.data["page"]

            data = message.data.get("data")
            if data is None:
                data = namespace.data

            namespace.data = data

            # DEBUG
            self._activate_namespace(namespace)
            self.synchronize()
            # if namespace not in self.active_namespaces:
            #     self._activate_namespace(namespace)
            #     self.synchronize()
            # else:
            #     # Only send session data
            #     self._update_namespace_data(namespace)

            LOG.debug(
                "Showing page %s on namespace %s with data %s",
                namespace.pages,
                namespace.name,
                namespace.data,
            )
        except Exception:
            LOG.exception("Unexpected error showing GUI page")

    def handle_set_value(self, message: Message):
        """Sets session data values"""
        try:
            namespace = self._ensure_namespace_exists(message.data["namespace"])
            data = message.data.get("data", {})
            if message.data.get("overwrite", True):
                namespace.data = data
            else:
                namespace.data.update(data)

            send_message_to_gui(
                {
                    "type": "mycroft.session.set",
                    "namespace": namespace.name,
                    "data": message.data.get("data", {}),
                }
            )
            LOG.debug("Setting values for namespace %s to %s", namespace, data)
        except Exception:
            LOG.exception("Unexpected error showing GUI page")

    def _activate_namespace(self, namespace: Namespace):
        """Instructs the GUI to load a namespace and its associated data.

        Args:
            namespace: the namespace to activate
        """
        # Only one active namespace
        self.active_namespaces.clear()
        self.active_namespaces.append(namespace)

        # self._emit_namespace_displayed_event()

    def _ensure_namespace_exists(self, namespace_name: str) -> Namespace:
        """Retrieves the requested namespace, creating one if it doesn't exist.

        Args:
            namespace_name: the name of the namespace being retrieved

        Returns:
            the requested namespace
        """
        # TODO: - Update sync to match.
        namespace = self.loaded_namespaces.get(namespace_name)
        if namespace is None:
            namespace = Namespace(namespace_name)
            self.loaded_namespaces[namespace_name] = namespace

        return namespace

    def _update_namespace_data(self, namespace: Namespace):
        LOG.info(namespace)
        send_message_to_gui(
            {
                "type": "mycroft.session.set",
                "namespace": namespace.name,
                "data": namespace.data,
            }
        )

    def handle_status_request(self, message: Message):
        """Handles a GUI status request by replying with the connection status.

        Args:
            message: the request for status of the GUI
        """
        gui_connected = determine_if_gui_connected()
        reply = message.reply(
            "gui.status.request.response", dict(connected=gui_connected)
        )
        self.core_bus.emit(reply)

    def handle_client_connected(self, message: Message):
        """Handles an event from the GUI indicating it is connected to the bus.

        Args:
            message: the event sent by the GUI
        """
        # GUI has announced presence
        # Announce connection, the GUI should connect on it soon
        gui_id = message.data.get("gui_id")
        LOG.info(f"GUI with ID {gui_id} connected to core message bus")
        websocket_config = get_gui_websocket_config()
        port = websocket_config["base_port"]
        message = Message("mycroft.gui.port", dict(port=port, gui_id=gui_id))
        self.core_bus.emit(message)
