# Copyright 2016 Mycroft AI Inc.
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

from adapt.intent import IntentBuilder
from mycroft.messagebus.message import Message
from mycroft.skills import MycroftSkill, intent_handler

# If one of these is the current skill, all background skills are sent a stop
# message instead.
IGNORE_SKILLS = {"homescreen.mycroftai"}

# Skills that can be stopped by "stop", even if they are not in the foreground.
BACKGROUND_SKILLS = {"skill-music-demo.mycroftai", "mycroft-npr-news.mycroftai"}


class StopSkill(MycroftSkill):
    def __init__(self):
        super().__init__(name="StopSkill")

    def initialize(self):
        self.bus.on("gui.namespace.displayed", self.handle_namespace_displayed)
        self.currently_active_skill = None

    def handle_namespace_displayed(self, msg):
        self.currently_active_skill = msg.data["skill_id"]

    @intent_handler(IntentBuilder("").require("Stop"))
    def handle_stop(self, event):
        with self.activity():
            utt = event.data["utterance"]
            # Framework used to 'catches this, invokes stop() method on all skills'
            # but is now more discerning in its behavior
            # self.bus.emit(Message("mycroft.stop"))
            if "everything" in utt:
                self.log.debug(
                    "The word 'everything' was detected, sending broadcast stop"
                )
                self.bus.emit(Message("mycroft.stop", data={"skill": "*"}))
            elif self.currently_active_skill in IGNORE_SKILLS:
                # Send stop to all background skills
                self.log.debug("Stopping background skills")
                for bg_skill_id in BACKGROUND_SKILLS:
                    self.bus.emit(Message("mycroft.stop", data={"skill": bg_skill_id}))
            else:
                self.log.debug(
                    "Mycroft Stop Skill emitting stop msg for %s, event=%s"
                    % (self.currently_active_skill, event.data)
                )
                self.bus.emit(
                    Message("mycroft.stop", data={"skill": self.currently_active_skill})
                )

    @intent_handler(IntentBuilder("").require("Nevermind"))
    def handle_nevermind(self, event):
        with self.activity():
            # No feedback
            pass

    ######################################################################
    # Typically the enclosure will handle all of the following
    # NOTE: system.update is generated by skill-version-checker
    ######################################################################

    @intent_handler("reboot.intent")
    def handle_reboot(self, event):
        with self.activity():
            if self.ask_yesno("confirm.reboot") == "yes":
                self.bus.emit(Message("system.reboot"))

    @intent_handler("shutdown.intent")
    def handle_shutdown(self, event):
        with self.activity():
            if self.ask_yesno("confirm.shutdown") == "yes":
                self.bus.emit(Message("system.shutdown"))

    @intent_handler("wifi.setup.intent")
    def handle_wifi_setup(self, event):
        with self.activity():
            self.bus.emit(Message("system.wifi.setup"))

    @intent_handler("ssh.enable.intent")
    def handle_ssh_enable(self, event):
        with self.activity():
            self.bus.emit(Message("system.ssh.enable"))

    @intent_handler("ssh.disable.intent")
    def handle_ssh_disable(self, event):
        with self.activity():
            self.bus.emit(Message("system.ssh.disable"))


def create_skill():
    return StopSkill()
