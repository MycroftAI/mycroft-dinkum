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
import argparse
from pathlib import Path
from typing import Dict, List

from lingua_franca import load_languages
from mycroft.service import DinkumService
from mycroft.skills import MycroftSkill
from mycroft.skills.settings import SettingsMetaUploader
from mycroft.util.log import configure_loggers, get_service_logger

configure_loggers("skills")
_log = get_service_logger("skills", __name__)

from .load import create_skill_instance, load_skill_source


class SkillsService(DinkumService):
    """
    Service for loading and managing the lifecycle of a single skill.
    """

    def __init__(self, args: argparse.Namespace):
        super().__init__(service_id="skills")
        self.args = args
        self._skill_instances: Dict[str, MycroftSkill] = {}
        self._meta_uploaders: List[SettingsMetaUploader] = []

    def start(self):
        self._load_language()

        # We can't register intents until the intent service is up
        self._wait_for_service("intent")
        self._load_skills()

    def after_start(self):
        super().after_start()

        # Block skill from running state until ready.
        self._wait_for_ready()

        # Upload skill metadata
        self._upload_settings_meta()

    def stop(self):
        self._unload_skills()

    def _load_language(self):
        """Load language for Lingua Franca"""
        lang_code = self.config.get("lang", "en-us")
        load_languages([lang_code, "en-us"])

    def _load_skills(self):
        """Load/create skill instances and initialize"""
        for skill_directory in self.args.skill:
            skill_id = Path(skill_directory).name
            _log.info("Loading skill %s", skill_id)
            skill_module = load_skill_source(skill_directory, skill_id)
            assert (
                skill_module is not None
            ), f"Failed to load skill module from {skill_directory}"

            skill_instance = create_skill_instance(skill_module, skill_id, self.bus)
            assert skill_instance is not None, f"Failed to create skill {skill_id}"

            self._skill_instances[skill_id] = skill_instance

    def _unload_skills(self):
        try:
            for skill_instance in self._skill_instances.values():
                _log.info("Unloading skill %s", skill_instance.skill_id)
                skill_instance.default_shutdown()

            self._skill_instances.clear()
        finally:
            _log.info("Stopping meta uploaders")
            for meta_uploader in self._meta_uploaders:
                meta_uploader.stop()

            self._meta_uploaders.clear()

    def _upload_settings_meta(self):
        try:
            for skill_directory in self.args.skill:
                skill_id = Path(skill_directory).name
                skill_instance = self._skill_instances[skill_id]
                meta_uploader = SettingsMetaUploader(
                    skill_directory,
                    skill_id,
                    skill_instance.name,
                )
                meta_uploader.upload()
                self._meta_uploaders.append(meta_uploader)
        except Exception:
            _log.exception("Error while uploading settings meta")


def main():
    """Service entry point"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skill",
        required=True,
        action="append",
        help="Path to skill directory",
    )
    args, rest = parser.parse_known_args()

    SkillsService(args).main(rest)


if __name__ == "__main__":
    main()
