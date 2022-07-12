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
"""Common functions for loading plugins."""
import logging
import typing
from importlib.metadata import entry_points

LOG = logging.getLogger(__package__)


def find_plugins(plug_type: str) -> typing.Dict[str, typing.Any]:
    """Finds all plugins matching specific entrypoint type.

    Args:
        plug_type (str): plugin entrypoint string to retrieve

    Returns:
        dict mapping plugin names to plugin entrypoints
    """
    return {
        entry_point.name: entry_point.load()
        for entry_point in entry_points().get(plug_type, [])
    }


def load_plugin(plug_type: str, plug_name: str) -> typing.Any:
    """Load a specific plugin from a specific plugin type.

    Args:
        plug_type: (str) plugin type name. Ex. "mycroft.plugin.tts".
        plug_name: (str) specific plugin name

    Returns:
        Loaded plugin Object or None if no matching object was found.
    """
    plugins = find_plugins(plug_type)
    if plug_name in plugins:
        ret = plugins[plug_name]
    else:
        LOG.warning("Could not find the plugin %s.%s", plug_type, plug_name)
        ret = None

    return ret
