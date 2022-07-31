# Copyright 2020 Mycroft AI Inc, daemon=True..start()
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
import logging
from collections import defaultdict
from threading import Event, Lock, Thread
from time import sleep, monotonic
from queue import Empty, Queue
from typing import Dict, List, Optional, Set, Union
from pathlib import Path
from uuid import uuid4

from mycroft.configuration import Configuration
from mycroft.messagebus.client import MessageBusClient
from mycroft.messagebus import Message


def create_voight_kampff_logger():
    fmt = logging.Formatter("{asctime} | {name} | {levelname} | {message}", style="{")
    handler = logging.StreamHandler()
    handler.setFormatter(fmt)
    log = logging.getLogger("Voight Kampff")
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    return log


LOG = create_voight_kampff_logger()


class InterceptAllBusClient(MessageBusClient):
    """Bus Client storing all messages received.

    This allows read back of older messages and non-event-driven operation.
    """

    def __init__(self, message_callback):
        super().__init__()
        self._message_callback = message_callback

    def on_message(self, _, message):
        self._message_callback(Message.deserialize(message))
        super().on_message(_, message)


class VoightKampffClient:
    def __init__(self):
        self.bus = InterceptAllBusClient(self._on_message)

        self._tts_session_ids: Set[str] = set()
        self._speaking_finished = Event()
        self._speak_queue: "Queue[Message]" = Queue()

        self._active_sessions: Set[str] = set()
        self._session_ended = Event()
        self._mycroft_session_id: Optional[str] = None

        # event type -> [messages]
        self.messages: Dict[str, List[Message]] = defaultdict(list)
        self._message_queues: Dict[str, "Queue[Message]"] = defaultdict(Queue)

        self._connect_to_bus()

    def _on_message(self, message: Message):
        self.messages[message.msg_type].append(message)
        self._message_queues[message.msg_type].put_nowait(message)

    def _connect_to_bus(self):
        self.bus.run_in_thread()

        LOG.debug("Connecting to message bus")
        self.bus.connected_event.wait()

        self.bus.on("speak", self._handle_speak)
        self.bus.on("mycroft.tts.speaking-finished", self._handle_speaking_finished)
        self.bus.on("complete_intent_failure", self._handle_intent_failure)
        self.bus.on("mycroft.session.started", self._handle_session_started)
        self.bus.on("mycroft.session.ended", self._handle_session_ended)

    def say_utterance(self, text: str, mycroft_session_id: Optional[str] = None):
        LOG.debug("say: %s (session=%s)", text, mycroft_session_id)
        self.bus.emit(
            Message(
                "recognizer_loop:utterance",
                data={
                    "utterances": [text],
                    "mycroft_session_id": mycroft_session_id,
                },
            )
        )

    def wait_for_speak(self):
        if self._tts_session_ids:
            LOG.info("Waiting on TTS: %s", self._tts_session_ids)
            self._speaking_finished.wait(timeout=10)

    def wait_for_session(self):
        if self._active_sessions:
            LOG.info("Waiting on session(s): %s", self._active_sessions)
            self._session_ended.wait(timeout=30)

    def wait_for_message(self, message_type: str, timeout=5) -> Optional[Message]:
        maybe_message: Optional[Message] = None
        try:
            maybe_message = self._message_queues[message_type].get(timeout=timeout)
        except Empty:
            pass

        return maybe_message

    def match_dialogs_or_fail(
        self, dialogs: Union[str, List[str]], skill_id: Optional[str] = None
    ):
        passed = True
        assert_message = ""

        if isinstance(dialogs, str):
            dialogs = dialogs.split(";")

        # Strip '.dialog'
        dialog_stems = {Path(d.strip()).stem for d in dialogs}

        maybe_message = self.get_next_speak()
        if maybe_message is not None:
            meta = maybe_message.data.get("meta", {})
            actual_skill = meta.get("skill_id")

            if skill_id is not None:
                if skill_id != actual_skill:
                    passed = False
                    assert_message = (
                        f"Expected skill '{skill_id}', got '{actual_skill}'"
                    )

            if passed:
                actual_dialog = meta.get("dialog", "")
                if actual_dialog not in dialog_stems:
                    assert_message = f"Expected dialog '{dialog_stems}', got '{actual_dialog}' from '{actual_skill}'"
                    passed = False

            if not passed:
                assert_message = "\n".join((assert_message, str(maybe_message.data)))
        else:
            passed = False
            assert_message = "Mycroft didn't respond"

        assert passed, assert_message

    def get_next_speak(self, timeout=10) -> Optional[Message]:
        message: Optional[Message] = None
        try:
            message = self._speak_queue.get(timeout=timeout)
        except Empty:
            pass

        return message

    def reset_state(self):
        self.messages.clear()
        self._message_queues.clear()

        self._tts_session_ids.clear()
        self._session_ended.clear()
        self._speaking_finished.clear()

        while not self._speak_queue.empty():
            self._speak_queue.get()

    def shutdown(self):
        self.bus.close()

    def _handle_speak(self, message: Message):
        tts_session_id = message.data.get("tts_session_id")
        if tts_session_id:
            self._tts_session_ids.add(tts_session_id)

        self._speak_queue.put_nowait(message)

    def _handle_speaking_finished(self, message: Message):
        # if message.data.get("mycroft_session_id") in self._active_sessions:
        tts_session_id = message.data.get("tts_session_id")
        if tts_session_id is not None:
            self._tts_session_ids.discard(tts_session_id)

        if not self._tts_session_ids:
            self._speaking_finished.set()

    def _handle_intent_failure(self, message: Message):
        # Flush any waiters
        self._speaking_finished.set()
        self._session_ended.set()
        self.reset_state()

    def _handle_session_started(self, message: Message):
        self._mycroft_session_id = message.data.get("mycroft_session_id")
        self._active_sessions.add(self._mycroft_session_id)

    def _handle_session_ended(self, message: Message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        LOG.debug("Ended: %s", mycroft_session_id)
        self._active_sessions.discard(mycroft_session_id)
        if not self._active_sessions:
            self._session_ended.set()


def before_all(context):
    context.client = VoightKampffClient()


def before_feature(context, feature):
    LOG.info("Starting tests for {}".format(feature.name))


def after_all(context):
    context.client.shutdown()


def after_feature(context, feature):
    LOG.info("Result: {} ({:.2f}s)".format(str(feature.status.name), feature.duration))


def before_scenario(context, scenario):
    context.client.reset_state()


def after_scenario(context, scenario):
    """Wait for mycroft completion and reset any changed state."""
    context.client.wait_for_session()
    LOG.info("End scenario: %s", scenario)


def after_step(context, step):
    context.client.wait_for_speak()
