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
"""Mycroft's intent service, providing intent parsing since forever!"""
import time
from copy import copy
from threading import RLock, Thread
from typing import Any, ClassVar, Dict, List, Optional
from uuid import uuid4

from mycroft.configuration import Configuration
from mycroft.configuration.locale import set_default_lf_lang
from mycroft.skills.intent_service_interface import open_intent_envelope
from mycroft.util.log import LOG
from mycroft.util.parse import normalize
from mycroft_bus_client import Message, MessageBusClient

from .intent_services import (
    AdaptIntent,
    AdaptService,
    FallbackService,
    IntentMatch,
    PadatiousMatcher,
    PadatiousService,
    RegexService,
)
from .session import (
    ClearDisplayAction,
    GetResponseAction,
    MessageAction,
    Session,
    ShowPageAction,
    SpeakAction,
    WaitForIdleAction,
)

# Seconds before home screen is shown again (mycroft.gui.idle event)
IDLE_TIMEOUT = 15

# Seconds after speaking before going idle
IDLE_QUICK_TIMEOUT = 2


class IntentService:
    """Mycroft intent service. parses utterances using a variety of systems.

    The intent service also provides the internal API for registering and
    querying the intent service.
    """

    def __init__(self, config: Dict[str, Any], bus: MessageBusClient):
        self.config = config
        self.bus = bus

        self.skill_names = {}
        self.skill_categories = {}

        self._response_skill_id: Optional[str] = None
        self._sessions: Dict[str, Session] = {}
        self._session_lock = RLock()

        self._last_gui_session: Optional[Session] = None

        self._idle_seconds_left: Optional[int] = None
        self._delayed_messages_lock = RLock()
        self._delayed_messages: List[MessageAction] = []

        self.registered_vocab = []

        # Register services
        self.regex_service = RegexService(bus, config)
        self.adapt_service = AdaptService(config.get("context", {}))
        try:
            self.padatious_service = PadatiousService(bus, config["padatious"])
        except Exception as err:
            LOG.exception(
                "Failed to create padatious handlers " "({})".format(repr(err))
            )
        self.fallback = FallbackService(bus)

    def start(self):
        self._register_event_handlers()

        # Show idle GUI screen on timeout
        Thread(target=self._check_idle_timeout, daemon=True).start()

    def stop(self):
        pass

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

    def _register_event_handlers(self):
        self.bus.on("register_vocab", self.handle_register_vocab)
        self.bus.on("register_intent", self.handle_register_intent)

        self.bus.on("recognizer_loop:awoken", self.handle_wake)
        self.bus.on("recognizer_loop:utterance", self.handle_utterance)
        self.bus.on("mycroft.session.start", self.handle_session_start)
        self.bus.on("mycroft.session.continue", self.handle_session_continue)
        self.bus.on("mycroft.session.end", self.handle_session_end)
        self.bus.on("mycroft.session.ended", self.handle_session_ended)
        self.bus.on("mycroft.tts.session.ended", self.handle_tts_finished)
        self.bus.on("mycroft.audio.hal.media.ended", self.handle_media_finished)
        self.bus.on("mycroft.stop", self.handle_stop)

        self.bus.on("detach_intent", self.handle_detach_intent)
        self.bus.on("detach_skill", self.handle_detach_skill)

        # Intents API
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

    def handle_wake(self, message: Message):
        self._disable_idle_timeout()
        mycroft_session_id = message.data.get("mycroft_session_id")
        with self._session_lock:
            sessions_to_abort = []
            for session in self._sessions.values():
                if session.id != mycroft_session_id:
                    sessions_to_abort.append(session)

            for session in sessions_to_abort:
                self.abort_session(session.id)

    def handle_stop(self, message: Message):
        skill_id = message.data.get("skill_id")
        if skill_id is None:
            # Always stop TTS
            self.bus.emit(Message("mycroft.tts.stop"))

            # Determine target skill
            skill_id: Optional[str] = None
            with self._session_lock:
                if self._last_gui_session is not None:
                    skill_id = self._last_gui_session.skill_id

                # Abort all other sessions
                for session in self._sessions.values():
                    if session.skill_id != skill_id:
                        session.aborted = True

            if skill_id:
                # Target skill directly
                LOG.debug("Stopping skill: %s", skill_id)
                mycroft_session_id = str(uuid4())
                self.start_session(
                    mycroft_session_id,
                    skill_id=skill_id,
                )
                self.bus.emit(
                    Message(
                        "mycroft.skill.stop",
                        data={
                            "mycroft_session_id": mycroft_session_id,
                            "skill_id": skill_id,
                        },
                    )
                )
            else:
                # Return GUI to idle
                self._disable_idle_timeout()
                self.bus.emit(Message("mycroft.gui.idle"))

    def start_session(self, mycroft_session_id: str, **session_kwargs):
        if mycroft_session_id is None:
            mycroft_session_id = str(uuid4())

        LOG.debug("Starting session: %s", mycroft_session_id)
        session = Session(id=mycroft_session_id, **session_kwargs)
        self._sessions[session.id] = session
        session.started(self.bus)

    def abort_session(self, mycroft_session_id: str):
        LOG.warning("Aborted session: %s", mycroft_session_id)
        self.end_session(mycroft_session_id, aborted=True)

    def end_session(self, mycroft_session_id: str, aborted: bool = False):
        LOG.debug("Ending session: %s", mycroft_session_id)
        session = self._sessions.pop(mycroft_session_id, None)
        if session is not None:
            if aborted:
                session.aborted = True
            session.ended(self.bus)

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

    def _run_session(self, session: Session):
        self._disable_idle_timeout()
        for action in session.run(self.bus):
            LOG.debug("Completed action for session %s: %s", session.id, action)
            if isinstance(action, GetResponseAction):
                self._trigger_listen(session.id)
            elif isinstance(action, ShowPageAction):
                self._last_gui_session = session
            elif isinstance(action, (ClearDisplayAction, WaitForIdleAction)):
                if (self._last_gui_session is None) or (
                    self._last_gui_session.skill_id == session.skill_id
                ):
                    if isinstance(action, WaitForIdleAction):
                        timeout = IDLE_TIMEOUT
                    else:
                        timeout = IDLE_QUICK_TIMEOUT
                    self._set_idle_timeout(timeout)
                else:
                    self.log.debug(
                        "Skipping GUI clear for %s since GUI belongs to another session (%s)",
                        session.id,
                        self._last_gui_session.id,
                    )
            elif isinstance(action, MessageAction):
                if action.delay > 0:
                    # Send message later
                    with self._delayed_messages_lock:
                        self._delayed_messages.append(action)

    def handle_session_start(self, message: Message):
        mycroft_session_id = message.data["mycroft_session_id"]
        LOG.debug("Starting session: %s", mycroft_session_id)
        session = Session(
            id=mycroft_session_id,
            skill_id=message.data.get("skill_id"),
            will_continue=message.data.get("continue_session", False),
        )
        session.actions = Session.parse_actions(message.data.get("actions", []))

        with self._session_lock:
            self._sessions[mycroft_session_id] = session
            session.started(self.bus)
            self._run_session(session)

    def handle_session_continue(self, message: Message):
        mycroft_session_id = message.data["mycroft_session_id"]
        LOG.debug("Continuing session: %s", mycroft_session_id)

        with self._session_lock:
            session = self._sessions.get(mycroft_session_id)
            if session is not None:
                session.skill_id = message.data.get("skill_id", session.skill_id)
                session.state = message.data.get("state", session.state)
                session.will_continue = True

                # Session may already have pending actions
                actions = Session.parse_actions(message.data.get("actions", []))
                session.actions.extend(actions)

                self._run_session(session)

    def handle_session_end(self, message: Message):
        mycroft_session_id = message.data["mycroft_session_id"]
        LOG.debug("Requested session end: %s", mycroft_session_id)

        with self._session_lock:
            session = self._sessions.get(mycroft_session_id)
            if session is not None:
                session.will_continue = False
                session.skill_id = message.data.get("skill_id", session.skill_id)
                session.actions = Session.parse_actions(message.data.get("actions", []))
                self._run_session(session)

    def handle_session_ended(self, message: Message):
        with self._session_lock:
            mycroft_session_id = message.data.get("mycroft_session_id")
            LOG.debug("Cleaning up ended session: %s", mycroft_session_id)
            self._sessions.pop(mycroft_session_id, None)

            if (self._last_gui_session is not None) and (
                self._last_gui_session.id == mycroft_session_id
            ):
                self._last_gui_session = None

            if not self._sessions:
                self.bus.emit(Message("mycroft.session.no-active-sessions"))
                self._set_idle_timeout()

    def handle_tts_finished(self, message: Message):
        mycroft_session_id = message.data["mycroft_session_id"]
        LOG.debug("TTS finished: %s", mycroft_session_id)

        with self._session_lock:
            session = self._sessions.get(mycroft_session_id)
            if (session is not None) and session.waiting_for_tts:
                session.waiting_for_tts = False
                self._run_session(session)

    def handle_media_finished(self, message: Message):
        mycroft_session_id = message.data["mycroft_session_id"]
        LOG.debug("Audio finished: %s", mycroft_session_id)

        with self._session_lock:
            session = self._sessions.get(mycroft_session_id)
            if (session is not None) and session.waiting_for_audio:
                session.waiting_for_audio = False
                self._run_session(session)

    def _set_idle_timeout(self, idle_seconds: Optional[int] = None):
        if idle_seconds is None:
            idle_seconds = IDLE_TIMEOUT

        self._idle_seconds_left = idle_seconds
        LOG.debug("Idle timeout set for %s second(s)", self._idle_seconds_left)

    def _handle_get_response(self, message: Message) -> bool:
        """
        Check if this utterance was intended for a specific skill.
        This method avoids the race condition present in the previous "converse" implementation.
        """
        handled = False
        mycroft_session_id = message.data.get("mycroft_session_id")

        if mycroft_session_id is not None:
            with self._session_lock:
                for session in self._sessions.values():
                    if session.expect_response:
                        if session.id != mycroft_session_id:
                            self.log.warning(
                                "Response expected for session %s, but session %s is active",
                                session.id,
                                mycroft_session_id,
                            )
                            continue

                        session.expect_response = False
                        mycroft_session_id = session.id
                        self.bus.emit(
                            Message(
                                "mycroft.skill-response",
                                data={
                                    "mycroft_session_id": mycroft_session_id,
                                    "skill_id": session.skill_id,
                                    "utterances": message.data.get("utterances"),
                                    "state": session.state,
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
        interval = 0.1
        try:
            while True:
                if self._idle_seconds_left is not None:
                    self._idle_seconds_left -= interval
                    if self._idle_seconds_left <= 0:
                        self._idle_seconds_left = None
                        self._last_gui_session = None
                        self.bus.emit(Message("mycroft.gui.idle"))

                with self._delayed_messages_lock:
                    remove_actions = []
                    for action in self._delayed_messages:
                        action.delay -= interval
                        if action.delay <= 0:
                            remove_actions.append(action)
                            self.bus.emit(
                                Message(action.message_type, data=action.data)
                            )

                    for action in remove_actions:
                        self._delayed_messages.remove(action)

                time.sleep(interval)
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
