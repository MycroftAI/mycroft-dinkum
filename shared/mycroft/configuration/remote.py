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
import re
from pathlib import Path
from typing import Any, Dict

import xdg.BaseDirectory
from mycroft.util.log import LOG
from mycroft.util.string_utils import camel_case_split

from .util import load_commented_json


def get_remote_settings_path() -> Path:
    return Path(xdg.BaseDirectory.xdg_config_home) / "mycroft" / "mycroft.remote.conf"


def download_remote_settings(api) -> Dict[str, Any]:
    setting = api.get_settings()

    location = None
    try:
        location = api.get_location()
    except RequestException as e:
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
