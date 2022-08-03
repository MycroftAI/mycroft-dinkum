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
from typing import Optional

from lingua_franca import load_languages
from mycroft.service import DinkumService
from mycroft.skills import MycroftSkill
from mycroft.skills.settings import SettingsMetaUploader
from mycroft_bus_client import Message

from .load import create_skill_instance, load_skill_source


class SkillsService(DinkumService):
    """
    Service for loading and managing the lifecycle of a single skill.
    """

    def __init__(self, args: argparse.Namespace):
        super().__init__(service_id=args.skill_id)
        self.args = args
        self._skill_instance: Optional[MycroftSkill] = None
        self._meta_uploader: Optional[SettingsMetaUploader] = None

    def start(self):
        self._load_language()

        # We can't register intents until the intent service is up
        self._wait_for_service("intent")
        self._load_skill()

    def after_start(self):
        super().after_start()

        # Block skill from running state until ready.
        self._wait_for_ready()

        # Upload skill metadata
        # self._upload_settings_meta()

    def stop(self):
        self._unload_skill()

    def _load_language(self):
        """Load language for Lingua Franca"""
        lang_code = self.config.get("lang", "en-us")
        load_languages([lang_code, "en-us"])

    def _load_skill(self):
        """Load/create skill instance and initialize"""
        self._skill_module = load_skill_source(
            self.args.skill_directory, self.args.skill_id
        )
        assert (
            self._skill_module is not None
        ), f"Failed to load skill module from {self.args.skill_directory}"

        self._skill_instance = create_skill_instance(
            self._skill_module, self.args.skill_id, self.bus
        )
        assert (
            self._skill_instance is not None
        ), f"Failed to create skill {self.args.skill_id}"

    def _unload_skill(self):
        try:
            if self._skill_instance is not None:
                self._skill_instance.default_shutdown()
                self._skill_instance = None
        finally:
            if self._meta_uploader is not None:
                self._meta_uploader.stop()
                self._meta_uploader = None

    def _upload_settings_meta(self):
        try:
            self._meta_uploader = SettingsMetaUploader(
                self.args.skill_directory, self._skill_instance.name
            )
            self._meta_uploader.upload()
        except Exception:
            self.log.exception("Error while uploading settings meta")


def main():
    """Service entry point"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skill-directory", required=True, help="Path to skill directory"
    )
    parser.add_argument("--skill-id", required=True, help="Mycroft skill id")
    args = parser.parse_args()

    SkillsService(args).main()


if __name__ == "__main__":
    main()
