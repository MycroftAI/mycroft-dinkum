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
from mycroft.service import DinkumService
from mycroft.skills.event_scheduler import EventScheduler
from mycroft.util.log import configure_loggers
from .intent_service import IntentService as InternalIntentService

configure_loggers("intent")


class IntentService(DinkumService):
    """
    Service for recognizing intents and managing sessions.
    """

    def __init__(self):
        super().__init__(service_id="intent")

    def start(self):
        self._intent_service = InternalIntentService(self.config, self.bus)
        self._event_scheduler = EventScheduler(self.bus)

        self._intent_service.start()

    def stop(self):
        self._intent_service.stop()
        self._event_scheduler.shutdown()


def main():
    """Service entry point"""
    IntentService().main()


if __name__ == "__main__":
    main()
