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

from mycroft.api import DeviceApi
from mycroft.identity import IdentityManager
from mycroft.util.log import LOG


def get_device_name():
    try:
        return DeviceApi().get()["name"]
    except Exception as err:
        LOG.exception("API Error", err)
        return ":error:"


def get_mycroft_uuid():
    """Get the UUID of a Mycroft device paired with the Mycroft backend."""
    identity = IdentityManager.get()
    return identity.uuid
