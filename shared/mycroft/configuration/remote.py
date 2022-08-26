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
import json
import re
from pathlib import Path
from threading import Timer
from typing import Any, Dict, Union

import xdg.BaseDirectory
from mycroft_bus_client import Message, MessageBusClient
from mycroft.util.log import LOG
from mycroft.util.string_utils import camel_case_split


ONE_MINUTE = 60


def get_remote_settings_path() -> Path:
    return Path(xdg.BaseDirectory.xdg_config_home) / "mycroft" / "mycroft.remote.conf"


def download_remote_settings(api) -> Dict[str, Any]:
    setting = api.get_settings()

    location = None
    try:
        location = api.get_location()
    except Exception:
        LOG.exception("RequestException fetching remote location")

    if location:
        setting["location"] = location

    # Remove server specific entries
    config = {}
    translate_remote(config, setting)
    return config


def is_remote_list(values):
    """Check if list corresponds to a backend formatted collection of dicts"""
    for v in values:
        if not isinstance(v, dict):
            return False
        if "@type" not in v.keys():
            return False
    return True


def translate_remote(config, setting):
    """Translate config names from server to equivalents for mycroft-core.

    Args:
        config:     base config to populate
        settings:   remote settings to be translated
    """
    IGNORED_SETTINGS = ["uuid", "@type", "active", "user", "device"]

    for k, v in setting.items():
        if k not in IGNORED_SETTINGS:
            # Translate the CamelCase values stored remotely into the
            # Python-style names used within mycroft-core.
            key = re.sub(r"Setting(s)?", "", k)
            key = camel_case_split(key).replace(" ", "_").lower()
            if isinstance(v, dict):
                config[key] = config.get(key, {})
                translate_remote(config[key], v)
            elif isinstance(v, list):
                if is_remote_list(v):
                    if key not in config:
                        config[key] = {}
                    translate_list(config[key], v)
                else:
                    config[key] = v
            else:
                config[key] = v


def translate_list(config, values):
    """Translate list formated by mycroft server.

    Args:
        config (dict): target config
        values (list): list from mycroft server config
    """
    for v in values:
        module = v["@type"]
        if v.get("active"):
            config["module"] = module
        config[module] = config.get(module, {})
        translate_remote(config[module], v)


class RemoteSettingsDownloader:
    def __init__(self):
        self._config_path = get_remote_settings_path()
        self._timer: Optional[Timer] = None
        self._last_settings: Dict[str, Any] = {}
        self.bus: Optional[MessageBusClient] = None

        from mycroft.api import DeviceApi
        self.api = DeviceApi()

    def initialize(self, bus: MessageBusClient):
        self.bus = bus

    def schedule(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

        self._timer = Timer(ONE_MINUTE, self._download)
        self._timer.daemon = True
        self._timer.start()
        LOG.debug("Scheduled download of remote config in %s second(s)", ONE_MINUTE)

    def _download(self):
        try:
            # Load remote config if it exists
            if (not self._last_settings) and (self._config_path.exists()):
                with open(self._config_path, "r") as config_file:
                    self._last_settings = json.load(config_file)

            LOG.debug("Downloading remote settings")
            current_settings = download_remote_settings(self.api)

            if current_settings != self._last_settings:
                # Save to ~/.config/mycroft/mycroft.remote.conf
                with open(self._config_path, "w", encoding="utf-8") as settings_file:
                    json.dump(current_settings, settings_file)

                self._last_settings = current_settings
                LOG.debug("Wrote remote config: %s", self._config_path)

                assert self.bus is not None

                # Inform services that config may have changed
                self.bus.emit(Message("configuration.updated"))
        except Exception:
            LOG.exception("Error downloading remote config")
        finally:
            self.schedule()
