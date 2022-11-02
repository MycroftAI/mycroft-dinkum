# Copyright 2020 Mycroft AI Inc.
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
"""Intent service wrapping padatious."""
from functools import partial
from os.path import expanduser, isfile
from subprocess import call
from threading import Thread
from time import sleep

from mycroft.messagebus.message import Message
from mycroft.util.log import get_mycroft_logger

_log = get_mycroft_logger(__name__)

from .base import IntentMatch


class PadatiousMatcher:
    """Matcher class to avoid redundancy in padatious intent matching."""

    def __init__(self, service):
        self.service = service
        self.has_result = False
        self.ret = None
        self.conf = None

    def _match_level(self, utterances, limit):
        """Match intent and make sure a certain level of confidence is reached.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
            limit (float): required confidence level.
        """
        if not self.has_result:
            padatious_intent = None
            _log.info("Padatious Matching confidence > {}".format(limit))
            for utt in utterances:
                for variant in utt:
                    intent = self.service.calc_intent(variant)
                    if intent:
                        best = padatious_intent.conf if padatious_intent else 0.0
                        if best < intent.conf:
                            padatious_intent = intent
                            padatious_intent.matches["utterance"] = utt[0]

            if padatious_intent:
                _log.info("Padatious match: %s", padatious_intent)
                skill_id = padatious_intent.name.split(":")[0]
                self.ret = IntentMatch(
                    "Padatious",
                    padatious_intent.name,
                    padatious_intent.matches,
                    skill_id,
                )
                self.conf = padatious_intent.conf
            self.has_result = True

        if self.conf and self.conf > limit:
            return self.ret
        return None

    def match_high(self, utterances, _=None, __=None):
        """Intent matcher for high confidence.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
        """
        return self._match_level(utterances, 0.95)

    def match_medium(self, utterances, _=None, __=None):
        """Intent matcher for medium confidence.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
        """
        return self._match_level(utterances, 0.8)

    def match_low(self, utterances, _=None, __=None):
        """Intent matcher for low confidence.

        Args:
            utterances (list of tuples): Utterances to parse, originals paired
                                         with optional normalized version.
        """
        return self._match_level(utterances, 0.5)


class PadatiousService:
    """Service class for padatious intent matching."""

    def __init__(self, bus, config):
        self.padatious_config = config
        self.bus = bus
        intent_cache = expanduser(self.padatious_config["intent_cache"])

        try:
            from padatious import IntentContainer
        except ImportError:
            _log.error("Padatious not installed. Please re-run dev_setup.sh")
            try:
                call(
                    [
                        "notify-send",
                        "Padatious not installed",
                        "Please run build_host_setup and dev_setup again",
                    ]
                )
            except OSError:
                pass
            return

        self.container = IntentContainer(intent_cache)

        self._bus = bus

        self.train_delay = self.padatious_config["train_delay"]
        self.is_training_needed = True
        self.train_time_left = self.train_delay

        self.registered_intents = []
        self.registered_entities = []

        Thread(target=self.wait_and_train, daemon=True).start()

        self.bus.on("padatious:register_intent", self.register_intent)
        self.bus.on("padatious:register_entity", self.register_entity)
        self.bus.on("detach_intent", self.handle_detach_intent)
        self.bus.on("detach_skill", self.handle_detach_skill)
        # self.bus.on("mycroft.skills.initialized", self.train)

    def train(self):
        """Perform padatious training."""
        # padatious_single_thread = Configuration.get()["padatious"]["single_thread"]
        # if message is None:
        #     single_thread = padatious_single_thread
        # else:
        #     single_thread = message.data.get("single_thread", padatious_single_thread)
        single_thread = True

        _log.info("Training... (single_thread=%s)", single_thread)
        self.container.train(single_thread=single_thread)
        _log.info("Training complete.")

    def wait_and_train(self):
        """Wait for minimum time between training and start training."""
        interval = 0.1
        while True:
            try:
                sleep(interval)
                if not self.is_training_needed:
                    continue

                self.train_time_left -= interval
                if self.train_time_left <= 0:
                    self.train()
                    self.is_training_needed = False
            except Exception:
                _log.exception("Error while training")

    def __detach_intent(self, intent_name):
        """Remove an intent if it has been registered.

        Args:
            intent_name (str): intent identifier
        """
        if intent_name in self.registered_intents:
            self.registered_intents.remove(intent_name)
            self.container.remove_intent(intent_name)

    def handle_detach_intent(self, message: Message):
        """Messagebus handler for detaching padatious intent.

        Args:
            message (Message): message triggering action
        """
        self.__detach_intent(message.data.get("intent_name"))

    def handle_detach_skill(self, message: Message):
        """Messagebus handler for detaching all intents for skill.

        Args:
            message (Message): message triggering action
        """
        skill_id = message.data["skill_id"]
        remove_list = [i for i in self.registered_intents if skill_id in i]
        for i in remove_list:
            self.__detach_intent(i)

    def _register_object(self, message: Message, object_name: str, register_func):
        """Generic method for registering a padatious object.

        Args:
            message (Message): trigger for action
            object_name (str): type of entry to register
            register_func (callable): function to call for registration
        """
        file_name = message.data["file_name"]
        name = message.data["name"]

        _log.debug("Registering Padatious " + object_name + ": " + name)

        if not isfile(file_name):
            _log.warning("Could not find file " + file_name)
            return False

        register_func(name, file_name)
        self.train_time_left = self.train_delay
        self.is_training_needed = True

        return True

    def register_intent(self, message: Message):
        """Messagebus handler for registering intents.

        Args:
            message (Message): message triggering action
        """
        self.registered_intents.append(message.data["name"])
        is_registered = self._register_object(
            message,
            "intent",
            partial(self.container.load_intent),
        )
        if is_registered:
            _log.debug("Registered Padatious intent: %s", message.data["name"])
        else:
            _log.warning(
                "Failed to register Padatious intent: %s", message.data["name"]
            )

    def register_entity(self, message: Message):
        """Messagebus handler for registering entities.

        Args:
            message (Message): message triggering action
        """
        self.registered_entities.append(message.data)
        self._register_object(message, "entity", partial(self.container.load_entity))

    def calc_intent(self, utt):
        """Cached version of container calc_intent.

        This improves speed when called multiple times for different confidence
        levels.

        NOTE: This cache will keep a reference to this class
        (PadatiousService), but we can live with that since it is used as a
        singleton.

        Args:
            utt (str): utterance to calculate best intent for
        """
        return self.container.calc_intent(utt)
