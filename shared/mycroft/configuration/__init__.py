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
import io
import json
import logging
import os
from pathlib import Path
from typing import Any, ClassVar, Dict, Iterable, Optional, Union, cast

import xdg.BaseDirectory

from .remote import get_remote_settings_path
from .util import load_commented_json, merge_dict

LOG = logging.getLogger(__package__)

_DIR = Path(__file__).parent
ConfigType = Dict[str, Any]


class Configuration:
    __config: ClassVar[ConfigType] = dict()
    __is_loaded: ClassVar[bool] = False

    @staticmethod
    def get(*args, cache: bool = True, **kwargs) -> ConfigType:
        """Get singleton configuration (load if necessary)"""
        if (not cache) or (not Configuration.__is_loaded):
            for config_path in Configuration.get_paths():
                LOG.debug("Loading config file: %s", config_path)
                try:
                    delta_config = Configuration.load(config_path)
                    merge_dict(Configuration.__config, delta_config)
                except Exception:
                    LOG.exception("Error loading config file: %s", config_path)

            Configuration.__is_loaded = True

        return Configuration.__config

    @staticmethod
    def load(config_path: Union[str, Path]) -> ConfigType:
        config = load_commented_json(config_path)
        return cast(ConfigType, config)

    @staticmethod
    def reload():
        LOG.debug("Reloading configuration")
        Configuration.get(cache=False)

    @staticmethod
    def get_paths() -> Iterable[Path]:
        system_config = os.environ.get(
            "MYCROFT_SYSTEM_CONFIG", "/etc/mycroft/mycroft.conf"
        )

        maybe_paths = [
            _DIR / "mycroft.conf",  # default
            Path(system_config),  # system
            Path("~").expanduser() / ".mycroft" / "mycroft",  # old user
            get_remote_settings_path(),  # selene
            Path(xdg.BaseDirectory.xdg_config_home)
            / "mycroft"
            / "mycroft.conf",  # new user
        ]

        for path in maybe_paths:
            if path.is_file():
                yield path
