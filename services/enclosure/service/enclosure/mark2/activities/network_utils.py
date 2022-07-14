# Copyright 2021 Mycroft AI Inc.
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
"""Utilities for network and internet detection."""
import typing

from dbus_next import BusType as DBusType
from dbus_next.aio import MessageBus as DBusMessageBus

NM_NAMESPACE = "org.freedesktop.NetworkManager"
NM_PATH = "/org/freedesktop/NetworkManager"


def get_dbus(bus_address: typing.Optional[str] = None) -> DBusMessageBus:
    """Get DBus message bus"""

    if bus_address:
        # Configured bus
        return DBusMessageBus(bus_address=bus_address)

    # System bus
    return DBusMessageBus(bus_type=DBusType.SYSTEM)


async def get_network_manager(dbus: DBusMessageBus):
    """Get DBus object, interface to NetworkManager"""
    introspection = await dbus.introspect(NM_NAMESPACE, NM_PATH)

    nm_object = dbus.get_proxy_object(NM_NAMESPACE, NM_PATH, introspection)

    return nm_object, nm_object.get_interface(NM_NAMESPACE)
