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
import logging
import importlib
import os
import sys

from mycroft_bus_client import MessageBusClient

LOG = logging.getLogger("skills")
SKILL_MAIN_MODULE = "__init__.py"


def create_skill_instance(skill_module, skill_id: str, bus: MessageBusClient):
    """Use v2 skills framework to create the skill."""
    try:
        instance = skill_module.create_skill()
    except Exception as e:
        log_msg = "Skill __init__ failed with {}"
        LOG.exception(log_msg.format(repr(e)))
        instance = None

    if instance:
        instance.skill_id = skill_id
        instance.bind(bus)
        try:
            instance.load_data_files()
            # Set up intent handlers
            # TODO: can this be a public method?
            instance._register_decorated()
            instance.initialize()
        except Exception as e:
            # If an exception occurs, make sure to clean up the skill
            instance.default_shutdown()
            instance = None
            log_msg = "Skill initialization failed with {}"
            LOG.exception(log_msg.format(repr(e)))

    return instance


def load_skill_source(skill_directory: str, skill_id: str):
    """Use Python's import library to load a skill's source code."""
    main_file_path = os.path.join(skill_directory, SKILL_MAIN_MODULE)
    if not os.path.exists(main_file_path):
        error_msg = "Failed to load {} due to a missing file."
        LOG.error(error_msg.format(skill_id))
    else:
        try:
            skill_module = _load_skill_module(main_file_path, skill_id)
        except Exception as e:
            LOG.exception("Failed to load skill: " "{} ({})".format(skill_id, repr(e)))
        else:
            module_is_skill = hasattr(skill_module, "create_skill") and callable(
                skill_module.create_skill
            )
            if module_is_skill:
                return skill_module
    return None  # Module wasn't loaded


def _load_skill_module(path: str, skill_id: str):
    """Load a skill module

    This function handles the differences between python 3.4 and 3.5+ as well
    as makes sure the module is inserted into the sys.modules dict.

    Args:
        path: Path to the skill main file (__init__.py)
        skill_id: skill_id used as skill identifier in the module list
    """
    module_name = skill_id.replace(".", "_")

    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod
