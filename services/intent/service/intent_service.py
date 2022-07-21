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
from dataclasses import dataclass, field
from threading import RLock, Thread
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

# Seconds before home screen is shown again (mycroft.gui.idle event)
IDLE_TIMEOUT = 15

# Seconds after speaking before going idle
IDLE_QUICK_TIMEOUT = 5


@dataclass
class Session:
    id: str
    skill_id: Optional[str] = None
    will_continue: bool = False
    expect_response: bool = False
    actions: List[Dict[str, Any]] = field(default_factory=dict)
    tick: int = field(default_factory=time.monotonic_ns)
    aborted: bool = False


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
        self._sessions: Dict[str, Session] = {}
        self._session_lock = RLock()

        self._last_gui_session: Optional[Session] = None

        self._idle_seconds_left: Optional[int] = None
        Thread(target=self._check_idle_timeout, daemon=True).start()

        self.bus.on("register_vocab", self.handle_register_vocab)
        self.bus.on("register_intent", self.handle_register_intent)

        self.bus.on("recognizer_loop:utterance", self.handle_utterance)
        self.bus.on("mycroft.session.start", self.handle_session_start)
        self.bus.on("mycroft.session.continue", self.handle_session_continue)
        self.bus.on("mycroft.session.end", self.handle_session_end)
        self.bus.on("mycroft.tts.session.ended", self.handle_tts_finished)
        self.bus.on("mycroft.audio.hal.media.ended", self.handle_media_finished)
        self.bus.on("mycroft.stop", self.handle_stop)

        self.bus.on("detach_intent", self.handle_detach_intent)
        self.bus.on("detach_skill", self.handle_detach_skill)

        # Intents API
        self.registered_vocab = []
        self.bus.on("intent.service.intent.get", self.handle_get_intent)
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

    def handle_stop(self, _message: Message):
        # Always stop TTS
        self.bus.emit(Message("mycroft.tts.stop"))

        # Determine target skill
        skill_id: Optional[str] = None
        with self._session_lock:
            if self._last_gui_session is not None:
                skill_id = self._last_gui_session.skill_id

        if skill_id:
            # TODO: Call skill handler
            LOG.debug("Stopping skill: %s", skill_id)

        # Return GUI to idle
        self._disable_idle_timeout()
        self.bus.emit(Message("mycroft.gui.idle"))

    def start_session(self, mycroft_session_id: str, skill_id: Optional[str] = None):
        LOG.debug("Starting session: %s", mycroft_session_id)
        self._sessions[mycroft_session_id] = Session(
            id=mycroft_session_id,
            skill_id=skill_id,
            will_continue=False,
            expect_response=False,
        )

        self.bus.emit(
            Message(
                "mycroft.session.started",
                data={"mycroft_session_id": mycroft_session_id, "skill_id": skill_id},
            )
        )

    def abort_session(self, mycroft_session_id: str):
        LOG.warning("Aborted session: %s", mycroft_session_id)
        self.end_session(mycroft_session_id, aborted=True)

    def end_session(self, mycroft_session_id: str, aborted: bool = False):
        LOG.debug("Ending session: %s", mycroft_session_id)
        session = self._sessions.pop(mycroft_session_id, None)
        if session is not None:
            self.bus.emit(
                Message(
                    "mycroft.session.ended",
                    data={"mycroft_session_id": session.id, "aborted": aborted},
                )
            )

    def _trigger_listen(self, mycroft_session_id: str):
        LOG.debug("Triggering listen for session %s", mycroft_session_id)
        self.bus.emit(
            Message(
                "mycroft.mic.listen",
                {
                    "mycroft_session_id": mycroft_session_id,
                },
            )
        )

    def handle_session_start(self, message: Message):
        mycroft_session_id = message.data["mycroft_session_id"]
        LOG.debug("Starting session: %s", mycroft_session_id)
        session = Session(
            id=mycroft_session_id,
            skill_id=message.data.get("skill_id"),
            will_continue=message.data.get("continue_session", False),
            expect_response=message.data.get("expect_response", False),
        )

        session.actions = message.data.get("actions", [])

        with self._session_lock:
            self._sessions[mycroft_session_id] = session
            self.bus.emit(
                Message(
                    "mycroft.session.started",
                    data={
                        "mycroft_session_id": mycroft_session_id,
                        "skill_id": session.skill_id,
                    },
                )
            )

            if not session.aborted:
                waiting_for_action = self.next_session_action(session)

                if not waiting_for_action:
                    if session.expect_response:
                        self._trigger_listen(session.id)
                    elif not session.will_continue:
                        # Session is over
                        self.end_session(session.id)
            else:
                self.abort_session(session.id)

    def handle_session_continue(self, message: Message):
        mycroft_session_id = message.data["mycroft_session_id"]
        LOG.debug("Continuing session: %s", mycroft_session_id)

        with self._session_lock:
            session = self._sessions.get(mycroft_session_id)
            if session is not None:
                session.skill_id = message.data.get("skill_id", session.skill_id)
                session.will_continue = True
                session.expect_response = message.data.get("expect_response", False)
                session.actions = message.data.get("actions", [])

                if not session.aborted:
                    waiting_for_action = self.next_session_action(session)
                    self.bus.emit(
                        Message(
                            "mycroft.session.continued",
                            data={"mycroft_session_id": session.id},
                        )
                    )

                    if (not waiting_for_action) and session.expect_response:
                        self._trigger_listen(session.id)
                else:
                    self.abort_session(session.id)

    def handle_session_end(self, message: Message):
        mycroft_session_id = message.data["mycroft_session_id"]
        LOG.debug("Requested session end: %s", mycroft_session_id)

        with self._session_lock:
            session = self._sessions.get(mycroft_session_id)
            if session is not None:
                session.will_continue = False
                session.expect_response = False
                session.skill_id = message.data.get("skill_id", session.skill_id)
                session.actions = message.data.get("actions", [])

                if not session.aborted:
                    waiting_for_action = self.next_session_action(session)
                    if not waiting_for_action:
                        self.end_session(session.id)
                else:
                    self.abort_session(session.id)

    def handle_tts_finished(self, message: Message):
        mycroft_session_id = message.data["mycroft_session_id"]
        LOG.debug("TTS finished: %s", mycroft_session_id)

        with self._session_lock:
            session = self._sessions.get(mycroft_session_id)
            if session is not None:
                if not session.aborted:
                    waiting_for_action = self.next_session_action(session)
                    if not waiting_for_action:
                        if session.expect_response:
                            self._trigger_listen(session.id)
                        elif not session.will_continue:
                            # Session will not continue
                            self.end_session(session.id)
                else:
                    self.end_session(session.id)

    def handle_media_finished(self, message: Message):
        channel = message.data.get("channel")
        if channel != 0:
            # Only handle sound effects here (channel 0)
            return

        mycroft_session_id = message.data["mycroft_session_id"]
        LOG.debug("Audio finished: %s", mycroft_session_id)

        with self._session_lock:
            session = self._sessions.get(mycroft_session_id)
            if session is not None:
                if not session.aborted:
                    waiting_for_action = self.next_session_action(session)
                    if not waiting_for_action:
                        if session.expect_response:
                            self._trigger_listen(session.id)
                        elif not session.will_continue:
                            # Session will not continue
                            self.end_session(session.id)
                else:
                    self.end_session(session.id)

    def next_session_action(self, session: Session) -> bool:
        self._disable_idle_timeout()

        while session.actions:
            action = session.actions[0] or {}
            session.actions = session.actions[1:]

            action_type = action.get("type")
            if action_type == "speak":
                utterance = action.get("utterance", "")
                if utterance:
                    self.bus.emit(
                        Message(
                            "speak",
                            data={
                                "mycroft_session_id": session.id,
                                "utterance": utterance,
                                "meta": {
                                    "dialog": action.get("dialog"),
                                    "skill_id": session.skill_id,
                                },
                            },
                        )
                    )

                    if action.get("wait", True):
                        # Will be called back when TTS is finished
                        return True
            elif action_type == "message":
                msg_type = action["message_type"]
                msg_data = action.get("data", {})
                self.bus.emit(Message(msg_type, data=msg_data))
            elif action_type == "show_page":
                gui_page = action.get("page")
                gui_data = action.get("data", {})
                if gui_page:
                    self._last_gui_session = session
                    self.bus.emit(
                        Message(
                            "gui.page.show",
                            {
                                "namespace": action["namespace"],
                                "page": gui_page,
                                "data": gui_data,
                                "skill_id": session.skill_id,
                            },
                        )
                    )
            elif action_type == "clear_display":
                # Go idle after a brief pause
                self._set_idle_timeout(IDLE_QUICK_TIMEOUT)
                self.bus.emit(Message("mycroft.gui.idle"))
            elif action_type == "wait_for_idle":
                # Go idle after default timeout
                self._set_idle_timeout()
            elif action_type == "audio_alert":
                alert_uri = action.get("uri")
                if alert_uri:
                    self.bus.emit(
                        Message(
                            "mycroft.audio.play-sound",
                            data={"uri": alert_uri, "mycroft_session_id": session.id},
                        )
                    )
                    if action.get("wait", True):
                        # Will be called back when audio is finished
                        return True

            elif action_type == "stream_music":
                alert_uri = action.get("uri")
                if alert_uri:
                    self.bus.emit(
                        Message(
                            "mycroft.audio.service.play",
                            data={
                                "tracks": [alert_uri],
                                "mycroft_session_id": session.id,
                            },
                        )
                    )

            self.bus.emit(
                Message(
                    "mycroft.session.action",
                    data={"mycroft_session_id": session.id, "action": action},
                )
            )

        return False

    def _set_idle_timeout(self, idle_seconds: Optional[int] = None):
        if idle_seconds is None:
            idle_seconds = IDLE_TIMEOUT

        self._idle_seconds_left = idle_seconds
        LOG.debug("Idle timeout set for %s second(s)", self._idle_seconds_left)

    def handle_utterance(self, message: Message):
        """Main entrypoint for handling user utterances with Mycroft skills

        Monitor the messagebus for 'recognizer_loop:utterance', typically
        generated by a spoken interaction but potentially also from a CLI
        or other method of injecting a 'user utterance' into the system.

        Utterances then work through this sequence to be handled:
        1) A skill expecting a response from continue_session is given priority
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
        mycroft_session_id = message.data.get("mycroft_session_id") or str(uuid4())
        self.fallback.session_id = mycroft_session_id

        with self._session_lock:
            LOG.debug("Current sessions: %s", self._sessions)
            if mycroft_session_id not in self._sessions:
                self.start_session(mycroft_session_id)

        LOG.debug(
            "Enter handle utterance: message.data:%s, session_id:%s",
            message.data,
            mycroft_session_id,
        )
        try:

            if self._handle_get_response(message):
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
                        "mycroft_session_id": mycroft_session_id,
                        **match.intent_data,
                    }
                    reply = message.reply(match.intent_type, match_data)
                    # Add back original list of utterances for intent handlers
                    # match.intent_data only includes the utterance with the
                    # highest confidence.
                    reply.data["utterances"] = utterances

                    self.bus.emit(reply)
            else:
                # Nothing was able to handle the intent
                # Ask politely for forgiveness for failing in this vital task
                self.send_complete_intent_failure(mycroft_session_id, message)
                self.end_session(mycroft_session_id)
        except Exception as err:
            LOG.exception(err)

        LOG.debug("Exit handle utterance")

    def _handle_get_response(self, message: Message) -> bool:
        """
        Check if this utterance was intended for a specific skill.
        This method avoids the race condition present in the previous "converse" implementation.
        """
        handled = False
        mycroft_session_id = message.data.get("mycroft_session_id")

        if mycroft_session_id is not None:
            with self._session_lock:
                LOG.debug(self._sessions)
                for session in self._sessions.values():
                    if session.expect_response and session.id == mycroft_session_id:
                        session.expect_response = False
                        mycroft_session_id = session.id
                        self.bus.emit(
                            Message(
                                "mycroft.skill-response",
                                data={
                                    "mycroft_session_id": mycroft_session_id,
                                    "skill_id": session.skill_id,
                                    "utterances": message.data.get("utterances"),
                                },
                            )
                        )
                        handled = True
                        LOG.debug(
                            "Raw utterance handled by skill %s, session=%s",
                            session.skill_id,
                            mycroft_session_id,
                        )
                        break

        return handled

    def _disable_idle_timeout(self):
        self._idle_seconds_left = None

    def _check_idle_timeout(self):
        """Runs in a daemon thread, checking if the idle timeout has been reached"""
        try:
            while True:
                if self._idle_seconds_left is not None:
                    self._idle_seconds_left -= 1
                    if self._idle_seconds_left <= 0:
                        self._idle_seconds_left = None
                        self._last_gui_session = None
                        self.bus.emit(Message("mycroft.gui.idle"))

                time.sleep(1)
        except Exception:
            LOG.exception("Error while checking idle timeout")

    # -------------------------------------------------------------------------

    def send_complete_intent_failure(self, mycroft_session_id: str, message):
        """Send a message that no skill could handle the utterance.

        Args:
            message (Message): original message to forward from
        """
        self.bus.emit(
            message.forward(
                "complete_intent_failure",
                data={"mycroft_session_id": mycroft_session_id},
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
