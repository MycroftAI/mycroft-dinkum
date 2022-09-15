# Copyright 2018 Mycroft AI Inc.
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
from mycroft.messagebus.message import Message
from mycroft.skills import intent_handler, MycroftSkill


class Privacy(MycroftSkill):
    def __init__(self, skill_id: str):
        super().__init__(skill_id=skill_id, name="Privacy Skill")

    @intent_handler("Privacy.intent")
    def handle_privacy_question(self, _message):
        return self.end_session(dialog="privacy", gui="main.qml")


def create_skill(skill_id: str):
    return Privacy(skill_id=skill_id)
