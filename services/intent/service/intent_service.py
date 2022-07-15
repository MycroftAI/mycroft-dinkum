# Copyright 2017 Mycroft AI Inc.
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
"""Mycroft's intent service, providing intent parsing since forever!"""
import time
from copy import copy
from typing import Any, Dict, List, Optional
from uuid import uuid4

from mycroft.configuration import Configuration
from mycroft.configuration.locale import set_default_lf_lang
from mycroft.messagebus.message import Message
from mycroft.skills.intent_service_interface import open_intent_envelope
from mycroft.util.log import LOG
from mycroft.util.parse import normalize

from .intent_services import (
    AdaptIntent,
    AdaptService,
    FallbackService,
    IntentMatch,
    PadatiousMatcher,
    PadatiousService,
    RegexService,
)


def _get_message_lang(message):
    """Get the language from the message or the default language.

    Args:
        message: message to check for language code.

    Returns:
        The languge code from the message or the default language.
    """
    default_lang = Configuration.get().get("lang", "en-us")
    return message.data.get("lang", default_lang).lower()


def _normalize_all_utterances(utterances):
    """Create normalized versions and pair them with the original utterance.

    This will create a list of tuples with the original utterance as the
    first item and if normalizing changes the utterance the normalized version
    will be set as the second item in the tuple, if normalization doesn't
    change anything the tuple will only have the "raw" original utterance.

    Args:
        utterances (list): list of utterances to normalize

    Returns:
        list of tuples, [(original utterance, normalized) ... ]
    """
    # normalize() changes "it's a boy" to "it is a boy", etc.
    norm_utterances = [normalize(u.lower(), remove_articles=False) for u in utterances]

    # Create pairs of original and normalized counterparts for each entry
    # in the input list.
    combined = []
    for utt, norm in zip(utterances, norm_utterances):
        if utt == norm:
            combined.append((utt,))
        else:
            combined.append((utt, norm))

    LOG.debug("Utterances: {}".format(combined))
    return combined


class IntentService:
    """Mycroft intent service. parses utterances using a variety of systems.

    The intent service also provides the internal API for registering and
    querying the intent service.
    """

    def __init__(self, bus):
        # Dictionary for translating a skill id to a name
        self.bus = bus

        self.skill_names = {}
        self.skill_categories = {}
        config = Configuration.get()
        self.regex_service = RegexService(bus, config)
        self.adapt_service = AdaptService(config.get("context", {}))
        try:
            self.padatious_service = PadatiousService(bus, config["padatious"])
        except Exception as err:
            LOG.exception(
                "Failed to create padatious handlers " "({})".format(repr(err))
            )
        self.fallback = FallbackService(bus)

        self._response_skill_id: Optional[str] = None
        self._session_id: Optional[str] = None
        self._session_actions: List[Dict[str, Any]] = []

        self.bus.on("register_vocab", self.handle_register_vocab)
        self.bus.on("register_intent", self.handle_register_intent)

        self.bus.on("recognizer_loop:utterance", self.handle_utterance)
        self.bus.on("mycroft.mic.listen", self.handle_listen)
        self.bus.on("mycroft.session.end", self.handle_session_end)
        self.bus.on("mycroft.tts.speaking-finished", self.handle_tts_finished)

        self.bus.on("detach_intent", self.handle_detach_intent)
        self.bus.on("detach_skill", self.handle_detach_skill)
        # Context related handlers
        self.bus.on("add_context", self.handle_add_context)
        self.bus.on("remove_context", self.handle_remove_context)
        self.bus.on("clear_context", self.handle_clear_context)

        # Converse method
        self.bus.on("mycroft.speech.recognition.unknown", self.reset_converse)
        self.bus.on("mycroft.skills.loaded", self.update_skill_name_dict)
        self.bus.on("mycroft.skills.list", self.update_skill_list)

        def add_active_skill_handler(message):
            category = "undefined"
            if message.data.get("skill_cat") is not None:
                category = message.data["skill_cat"]

            self.add_active_skill(message.data["skill_id"], category)

        def remove_active_skill_handler(message):
            self.remove_active_skill(message.data["skill_id"])
            LOG.debug(
                "IntentSvc:After remove_skill %s, active_skills=%s"
                % (message.data["skill_id"], self.active_skills)
            )

        self.bus.on("active_skill_request", add_active_skill_handler)
        self.bus.on("deactivate_skill_request", remove_active_skill_handler)
        self.active_skills = []  # [skill_id , timestamp, category]

        self.converse_timeout = 5  # minutes to prune active_skills

        # Intents API
        self.registered_vocab = []
        self.bus.on("intent.service.intent.get", self.handle_get_intent)
        self.bus.on("intent.service.skills.get", self.handle_get_skills)
        self.bus.on("intent.service.active_skills.get", self.handle_get_active_skills)
        self.bus.on("intent.service.adapt.get", self.handle_get_adapt)
        self.bus.on("intent.service.adapt.manifest.get", self.handle_adapt_manifest)
        self.bus.on(
            "intent.service.adapt.vocab.manifest.get", self.handle_vocab_manifest
        )
        self.bus.on("intent.service.padatious.get", self.handle_get_padatious)
        self.bus.on(
            "intent.service.padatious.manifest.get", self.handle_padatious_manifest
        )
        self.bus.on(
            "intent.service.padatious.entities.manifest.get",
            self.handle_entity_manifest,
        )

    @property
    def registered_intents(self):
        return [parser.__dict__ for parser in self.adapt_service.engine.intent_parsers]

    def update_skill_name_dict(self, message):
        """Messagebus handler, updates dict of id to skill name conversions."""
        self.skill_names[message.data["id"]] = message.data["name"]
        self.bus.emit(Message("skillmanager.list"))

    def update_skill_list(self, message):
        for skill in message.data:
            self.skill_categories[message.data[skill]["id"]] = message.data[skill][
                "cat"
            ]

    def get_skill_name(self, skill_id):
        """Get skill name from skill ID.

        Args:
            skill_id: a skill id as encoded in Intent handlers.

        Returns:
            (str) Skill name or the skill id if the skill wasn't found
        """
        return self.skill_names.get(skill_id, skill_id)

    def reset_converse(self, message):
        """Let skills know there was a problem with speech recognition"""
        lang = _get_message_lang(message)
        set_default_lf_lang(lang)
        for skill in copy(self.active_skills):
            self.do_converse(None, skill[0], lang, message)

    def do_converse(self, utterances, skill_id, lang, message):
        """Call skill and ask if they want to process the utterance.

        Args:
            utterances (list of tuples): utterances paired with normalized
                                         versions.
            skill_id: skill to query.
            lang (str): current language
            message (Message): message containing interaction info.
        """
        LOG.debug(
            "do_converse()-utterances:%s, active_skills=%s"
            % (utterances, self.active_skills)
        )
        converse_msg = message.reply(
            "skill.converse.request",
            {"skill_id": skill_id, "utterances": utterances, "lang": lang},
        )
        result = self.bus.wait_for_response(converse_msg, "skill.converse.response")
        if result and "error" in result.data:
            self.handle_converse_error(result)
            ret = False
        elif result is not None:
            ret = result.data.get("result", False)
        else:
            ret = False
        return ret

    def handle_converse_error(self, message):
        """Handle error in converse system.

        Args:
            message (Message): info about the error.
        """
        skill_id = message.data["skill_id"]
        error_msg = message.data["error"]
        LOG.error("{}: {}".format(skill_id, error_msg))
        if message.data["error"] == "skill id does not exist":
            self.remove_active_skill(skill_id)

    def remove_active_skill(self, skill_id):
        """Remove a skill from being targetable by converse.

        Args:
            skill_id (str): skill to remove
        """
        for skill in copy(self.active_skills):
            if skill[0] == skill_id:
                self.active_skills.remove(skill)

    def add_active_skill(self, skill_id, category="undefined"):
        """Add a skill or update the position of an active skill.

        The skill is added to the front of the list, if it's already in the
        list it's removed so there is only a single entry of it.

        Args:
            skill_id (str): identifier of skill to be added.
        """
        # search the list for an existing entry that already contains it
        # and remove that reference
        if skill_id != "":
            self.remove_active_skill(skill_id)
            # add skill with timestamp to start of skill_list
            self.active_skills.insert(0, [skill_id, time.time(), category])
        else:
            LOG.warning("Skill ID was empty, won't add to list of " "active skills.")

        LOG.debug(
            "Exit add active skill_id:%s, active_skills=%s"
            % (skill_id, self.active_skills)
        )

    def start_session(self, mycroft_session_id: str):
        if self._session_id is not None:
            # Abort existing session
            self.abort_session(self._session_id)

        self._session_id = mycroft_session_id
        self._session_actions.clear()
        self.bus.emit(
            Message(
                "mycroft.session.started",
                data={"mycroft_session_id": mycroft_session_id},
            )
        )

        # TODO: Timeout session

    def abort_session(self, mycroft_session_id: str):
        LOG.warning("Aborted session: %s", mycroft_session_id)
        self.end_session(mycroft_session_id, aborted=True)

    def end_session(self, mycroft_session_id: str, aborted: bool = False):
        if self._session_id == mycroft_session_id:
            self._session_id = None
            self._session_actions.clear()

        self.bus.emit(
            Message(
                "mycroft.session.ended",
                data={"mycroft_session_id": mycroft_session_id, "aborted": aborted},
            )
        )

    def handle_session_continue(self, message: Message):
        mycroft_session_id = message.data["mycroft_session_id"]
        if mycroft_session_id == self._session_id:
            self._session_actions = message.data.get("actions", [])
            if self._session_actions:
                skill_id = message.data["skill_id"]
                self.next_session_action(skill_id)

            self.bus.emit(
                Message(
                    "mycroft.session.continued",
                    data={"mycroft_session_id": mycroft_session_id},
                )
            )
        else:
            # Newer session has taken over
            self.abort_session(mycroft_session_id)

    def handle_session_end(self, message: Message):
        mycroft_session_id = message.data["mycroft_session_id"]
        if mycroft_session_id == self._session_id:
            self._session_actions = message.data.get("actions", [])
            if self._session_actions:
                skill_id = message.data["skill_id"]
                self.next_session_action(skill_id)
            else:
                self.end_session(message.data["mycroft_session_id"])

    def handle_tts_finished(self, message: Message):
        mycroft_session_id = message.data["mycroft_session_id"]
        if mycroft_session_id == self._session_id:
            if self._session_actions:
                skill_id = message.data["skill_id"]
                self.next_session_action(skill_id)
            else:
                self.end_session(mycroft_session_id)

    def handle_listen(self, message: Message):
        """Prime the next utterance to possibly be intended for a specific skill"""
        mycroft_session_id = message.data.get("mycroft_session_id") or str(uuid4())
        if mycroft_session_id != self._session_id:
            self.start_session(mycroft_session_id)

        self._response_skill_id = message.data.get("response_skill_id")

    def next_session_action(self, skill_id: str):
        mycroft_session_id = self._session_id

        while self._session_actions:
            action = self._session_actions[0] or {}
            self._session_actions = self._session_actions[1:]

            action_type = action.get("type")
            if action_type == "speak":
                utterance = action.get("utterance", "")
                expect_response = action.get("expect_response", False)
                self.bus.emit(
                    Message(
                        "speak",
                        data={
                            "mycroft_session_id": mycroft_session_id,
                            "skill_id": skill_id,
                            "utterance": utterance,
                            "listen": expect_response,
                            "meta": {
                                "dialog": action.get("dialog"),
                                "skill_id": skill_id,
                            },
                        },
                    )
                )

                if action.get("wait", True):
                    # Will be called back when TTS is finished
                    return

            # TODO: get_response
            # TODO: show_page
            # TODO: clear_display

            self.bus.emit(
                Message(
                    "mycroft.session.action",
                    data={"mycroft_session_id": self._session_id, "action": action},
                )
            )

        self.end_session(mycroft_session_id)

    def handle_utterance(self, message: Message):
        """Main entrypoint for handling user utterances with Mycroft skills

        Monitor the messagebus for 'recognizer_loop:utterance', typically
        generated by a spoken interaction but potentially also from a CLI
        or other method of injecting a 'user utterance' into the system.

        Utterances then work through this sequence to be handled:
        1) Active skills attempt to handle using converse()
        2) Padatious high match intents (conf > 0.95)
        3) Adapt intent handlers
        5) High Priority Fallbacks
        6) Padatious near match intents (conf > 0.8)
        7) General Fallbacks
        8) Padatious loose match intents (conf > 0.5)
        9) Catch all fallbacks including Unknown intent handler

        If all these fail the complete_intent_failure message will be sent
        and a generic info of the failure will be spoken.

        Args:
            message (Message): The messagebus data
        """
        mycroft_session_id = message.data.get(
            "mycroft_session_id", self._session_id
        ) or str(uuid4())

        if mycroft_session_id != self._session_id:
            self.start_session(mycroft_session_id)

        self.fallback.session_id = self._session_id

        LOG.debug(
            "Enter handle utterance: message.data:%s, active_skills:%s, session_id:%s"
            % (message.data, self.active_skills, self._session_id)
        )
        try:

            if self._handle_get_response(message):
                # Handled by a specific skill
                return

            lang = _get_message_lang(message)
            set_default_lf_lang(lang)

            utterances = message.data.get("utterances", [])
            combined = _normalize_all_utterances(utterances)

            # Create matchers
            padatious_matcher = PadatiousMatcher(self.padatious_service)

            # List of functions to use to match the utterance with intent.
            # These are listed in priority order.
            match_funcs = [
                # self._converse,
                padatious_matcher.match_high,
                self.adapt_service.match_intent,
                self.regex_service.match_intent,
                self.fallback.high_prio,
                padatious_matcher.match_medium,
                self.fallback.medium_prio,
                padatious_matcher.match_low,
                self.fallback.low_prio,
            ]

            match = None
            # Loop through the matching functions until a match is found.
            for match_func in match_funcs:
                match = match_func(combined, lang, message)
                if match:
                    break

            if match:
                # Launch skill if not handled by the match function
                if match.intent_type:
                    match_data = {
                        "mycroft_session_id": self._session_id,
                        **match.intent_data,
                    }
                    reply = message.reply(match.intent_type, match_data)
                    # Add back original list of utterances for intent handlers
                    # match.intent_data only includes the utterance with the
                    # highest confidence.
                    reply.data["utterances"] = utterances

                    self.bus.emit(reply)

                    # if match.intent_service == "Fallback":
                    #     # Already received response
                    #     self.bus.emit(reply)
                    #     self._end_session()
                    # else:
                    #     # HACK: Wait for skill handler to finish
                    #     response = self.bus.wait_for_response(reply, timeout=600)
                    #     if response:
                    #         if (
                    #             response.data.get("mycroft_session_id")
                    #             == self._session_id
                    #         ):
                    #             self._end_session()

            else:
                # Nothing was able to handle the intent
                # Ask politely for forgiveness for failing in this vital task
                self.send_complete_intent_failure(message)
                self.end_session(self._session_id)
        except Exception as err:
            LOG.exception(err)

        LOG.debug("Exit handle utterance")

    def _handle_get_response(self, message: Message) -> bool:
        """
        Check if this utterance was intended for a specific skill.
        This method avoids the race condition present in the previous "converse" implementation.

        This works with MycroftSkill.get_response() by:
        1. "speak" contains a "response_skill_id" with the id of the skill that wants the response
        2. The "mycroft.mic.listen" message gets "response_skill_id"
        3. The intent service caches "response_skill_id"
        4. When the next utterance arrives, it will either use the cached id or override it
        5. If "response_skill_id" is set, a "mycroft.skill-response" message is sent
        6. A reply to "mycroft.skill-response" means the appropriate skill got the response
        """
        handled = False

        # Check if this is intended for a specific skill
        response_skill_id = message.data.get(
            "response_skill_id", self._response_skill_id
        )
        self._response_skill_id = None

        if response_skill_id:
            reply = self.bus.wait_for_response(
                Message(
                    "mycroft.skill-response",
                    data={
                        "skill_id": response_skill_id,
                        "utterances": message.data.get("utterances"),
                    },
                )
            )
            if reply:
                handled = True
                LOG.debug("Utterance handled by skill: %s", response_skill_id)

        return handled

    def _converse(self, utterances, lang, message):
        """Give active skills a chance at the utterance

        Args:
            utterances (list):  list of utterances
            lang (string):      4 letter ISO language code
            message (Message):  message to use to generate reply

        Returns:
            IntentMatch if handled otherwise None.
        """
        utterances = [item for tup in utterances for item in tup]
        # check for conversation time-out
        self.active_skills = [
            skill
            for skill in self.active_skills
            if time.time() - skill[1] <= self.converse_timeout * 60
        ]

        # first check for system levl skills
        tmp_active_skills = copy(self.active_skills)
        for skill in tmp_active_skills:
            if skill[2] == "system":
                if self.do_converse(utterances, skill[0], lang, message):
                    # update timestamp, or there will be a timeout where
                    # intent stops conversing whether its being used or not
                    return IntentMatch("Converse", None, None, skill[0])

        # check if any skill wants to handle utterance
        for skill in tmp_active_skills:
            if self.do_converse(utterances, skill[0], lang, message):
                # update timestamp, or there will be a timeout where
                # intent stops conversing whether its being used or not
                return IntentMatch("Converse", None, None, skill[0])

        return None

    def send_complete_intent_failure(self, message):
        """Send a message that no skill could handle the utterance.

        Args:
            message (Message): original message to forward from
        """
        self.bus.emit(
            message.forward(
                "complete_intent_failure", data={"mycroft_session_id": self._session_id}
            )
        )
        LOG.info("No intent recognized")

    def handle_register_vocab(self, message):
        """Register adapt vocabulary.

        Args:
            message (Message): message containing vocab info
        """
        # TODO: 22.02 Remove backwards compatibility
        if _is_old_style_keyword_message(message):
            LOG.warning(
                "Deprecated: Registering keywords with old message. "
                "This will be removed in v22.02."
            )
            _update_keyword_message(message)

        entity_value = message.data.get("entity_value")
        entity_type = message.data.get("entity_type")
        regex_str = message.data.get("regex")
        alias_of = message.data.get("alias_of")
        self.adapt_service.register_vocabulary(
            entity_value, entity_type, alias_of, regex_str
        )
        self.registered_vocab.append(message.data)

    def handle_register_intent(self, message):
        """Register adapt intent.

        Args:
            message (Message): message containing intent info
        """
        intent = open_intent_envelope(message)
        self.adapt_service.register_intent(intent)

    def handle_detach_intent(self, message):
        """Remover adapt intent.

        Args:
            message (Message): message containing intent info
        """
        intent_name = message.data.get("intent_name")
        self.adapt_service.detach_intent(intent_name)

    def handle_detach_skill(self, message):
        """Remove all intents registered for a specific skill.

        Args:
            message (Message): message containing intent info
        """
        skill_id = message.data.get("skill_id")
        self.adapt_service.detach_skill(skill_id)

    def handle_add_context(self, message):
        """Add context

        Args:
            message: data contains the 'context' item to add
                     optionally can include 'word' to be injected as
                     an alias for the context item.
        """
        entity = {"confidence": 1.0}
        context = message.data.get("context")
        word = message.data.get("word") or ""
        origin = message.data.get("origin") or ""
        # if not a string type try creating a string from it
        if not isinstance(word, str):
            word = str(word)
        entity["data"] = [(word, context)]
        entity["match"] = word
        entity["key"] = word
        entity["origin"] = origin
        self.adapt_service.context_manager.inject_context(entity)

    def handle_remove_context(self, message):
        """Remove specific context

        Args:
            message: data contains the 'context' item to remove
        """
        context = message.data.get("context")
        if context:
            self.adapt_service.context_manager.remove_context(context)

    def handle_clear_context(self, _):
        """Clears all keywords from context"""
        self.adapt_service.context_manager.clear_context()

    def handle_get_intent(self, message):
        """Get intent from either adapt or padatious.

        Args:
            message (Message): message containing utterance
        """
        utterance = message.data["utterance"]
        lang = message.data.get("lang", "en-us")
        combined = _normalize_all_utterances([utterance])

        # Create matchers
        padatious_matcher = PadatiousMatcher(self.padatious_service)

        # List of functions to use to match the utterance with intent.
        # These are listed in priority order.
        # TODO once we have a mechanism for checking if a fallback will
        #  trigger without actually triggering it, those should be added here
        match_funcs = [
            padatious_matcher.match_high,
            self.adapt_service.match_intent,
            # self.fallback.high_prio,
            padatious_matcher.match_medium,
            # self.fallback.medium_prio,
            padatious_matcher.match_low,
            # self.fallback.low_prio
        ]
        # Loop through the matching functions until a match is found.
        for match_func in match_funcs:
            match = match_func(combined, lang, message)
            if match:
                if match.intent_type:
                    intent_data = match.intent_data
                    intent_data["intent_name"] = match.intent_type
                    intent_data["intent_service"] = match.intent_service
                    intent_data["skill_id"] = match.skill_id
                    intent_data["handler"] = match_func.__name__
                    self.bus.emit(
                        message.reply(
                            "intent.service.intent.reply", {"intent": intent_data}
                        )
                    )
                return

        # signal intent failure
        self.bus.emit(message.reply("intent.service.intent.reply", {"intent": None}))

    def handle_get_skills(self, message):
        """Send registered skills to caller.

        Argument:
            message: query message to reply to.
        """
        self.bus.emit(
            message.reply("intent.service.skills.reply", {"skills": self.skill_names})
        )

    def handle_get_active_skills(self, message):
        """Send active skills to caller.

        Argument:
            message: query message to reply to.
        """
        self.bus.emit(
            message.reply(
                "intent.service.active_skills.reply", {"skills": self.active_skills}
            )
        )

    def handle_get_adapt(self, message):
        """handler getting the adapt response for an utterance.

        Args:
            message (Message): message containing utterance
        """
        utterance = message.data["utterance"]
        lang = message.data.get("lang", "en-us")
        combined = _normalize_all_utterances([utterance])
        intent = self.adapt_service.match_intent(combined, lang)
        intent_data = intent.intent_data if intent else None
        self.bus.emit(
            message.reply("intent.service.adapt.reply", {"intent": intent_data})
        )

    def handle_adapt_manifest(self, message):
        """Send adapt intent manifest to caller.

        Argument:
            message: query message to reply to.
        """
        self.bus.emit(
            message.reply(
                "intent.service.adapt.manifest", {"intents": self.registered_intents}
            )
        )

    def handle_vocab_manifest(self, message):
        """Send adapt vocabulary manifest to caller.

        Argument:
            message: query message to reply to.
        """
        self.bus.emit(
            message.reply(
                "intent.service.adapt.vocab.manifest", {"vocab": self.registered_vocab}
            )
        )

    def handle_get_padatious(self, message):
        """messagebus handler for perfoming padatious parsing.

        Args:
            message (Message): message triggering the method
        """
        utterance = message.data["utterance"]
        norm = message.data.get("norm_utt", utterance)
        intent = self.padatious_service.calc_intent(utterance)
        if not intent and norm != utterance:
            intent = self.padatious_service.calc_intent(norm)
        if intent:
            intent = intent.__dict__
        self.bus.emit(
            message.reply("intent.service.padatious.reply", {"intent": intent})
        )

    def handle_padatious_manifest(self, message):
        """Messagebus handler returning the registered padatious intents.

        Args:
            message (Message): message triggering the method
        """
        self.bus.emit(
            message.reply(
                "intent.service.padatious.manifest",
                {"intents": self.padatious_service.registered_intents},
            )
        )

    def handle_entity_manifest(self, message):
        """Messagebus handler returning the registered padatious entities.

        Args:
            message (Message): message triggering the method
        """
        self.bus.emit(
            message.reply(
                "intent.service.padatious.entities.manifest",
                {"entities": self.padatious_service.registered_entities},
            )
        )


def _is_old_style_keyword_message(message):
    """Simple check that the message is not using the updated format.

    TODO: Remove in v22.02

    Args:
        message (Message): Message object to check

    Returns:
        (bool) True if this is an old messagem, else False
    """
    return "entity_value" not in message.data and "start" in message.data


def _update_keyword_message(message):
    """Make old style keyword registration message compatible.

    Copies old keys in message data to new names.

    Args:
        message (Message): Message to update
    """
    message.data["entity_value"] = message.data["start"]
    message.data["entity_type"] = message.data["end"]
