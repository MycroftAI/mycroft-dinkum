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

from lingua_franca import load_languages
from mycroft.service import DinkumService

from .load import create_skill_instance, load_skill_source


class SkillsService(DinkumService):
    """
    Service for loading and managing the lifecycle of a single skill.
    """

    def __init__(self, args: argparse.Namespace):
        super().__init__(service_id="intent")
        self.args = args

    def start(self):
        self._load_language()

        # We can't register intents until the intent service is up
        self._wait_for_service("intent")

        # Load the skill
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

    def run(self):
        # Block skill from loading until ready
        self._wait_for_ready()

        super().run()

    def stop(self):
        self._skill_instance.default_shutdown()

    def _load_language(self):
        lang_code = self.config.get("lang", "en-us")
        load_languages([lang_code, "en-us"])


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
