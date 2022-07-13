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
from threading import Event, Lock, Thread
from time import sleep, monotonic
from queue import Empty, Queue
from typing import Optional, Set

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


class VoightKampffClient:
    def __init__(self):
        self.bus = MessageBusClient()

        self._activity_ids: Set[str] = set()
        self._tts_session_ids: Set[str] = set()
        self._activities_ended = Event()
        self._speaking_finished = Event()
        self._speak_queue: "Queue[Message]" = Queue(maxsize=1)

        self._connect_to_bus()

    def _connect_to_bus(self):
        self.bus.run_in_thread()

        LOG.debug("Connecting to message bus")
        self.bus.connected_event.wait()

        self.bus.on("speak", self._handle_speak)
        self.bus.on("mycroft.tts.speaking-finished", self._handle_speaking_finished)
        self.bus.on("complete_intent_failure", self._handle_intent_failure)
        self.bus.on("skill.started", self._handle_skill_started)
        self.bus.on("skill.ended", self._handle_skill_ended)

    def say_utterance(self, text: str):
        self.bus.emit(
            Message(
                "recognizer_loop:utterance",
                data={
                    "utterances": [text],
                },
            )
        )

    def wait_for_skill(self):
        if self._tts_session_ids:
            self._speaking_finished.wait(timeout=10)

        if self._activity_ids:
            self._activities_ended.wait(timeout=10)

    def get_next_speak(self, timeout=10) -> Optional[Message]:
        message: Optional[Message] = None
        try:
            message = self._speak_queue.get(timeout=timeout)
        except Empty:
            pass

        return message

    def reset_state(self):
        self._activity_ids.clear()
        self._activities_ended.clear()
        self._tts_session_ids.clear()
        self._speaking_finished.clear()

        while not self._speak_queue.empty():
            self._speak_queue.get()

    def shutdown(self):
        self.bus.close()

    def _handle_speak(self, message: Message):
        session_id = message.data.get("session_id")
        if session_id:
            self._tts_session_ids.add(session_id)

        self._speak_queue.put_nowait(message)

    def _handle_skill_started(self, message: Message):
        activity_id = message.data.get("activity_id")
        if activity_id:
            self._activity_ids.add(activity_id)

    def _handle_skill_ended(self, message: Message):
        activity_id = message.data.get("activity_id")
        if activity_id:
            self._activity_ids.discard(activity_id)

        if not self._activity_ids:
            self._activities_ended.set()

    def _handle_speaking_finished(self, message: Message):
        session_id = message.data.get("session_id")
        if session_id:
            self._tts_session_ids.discard(session_id)

        if not self._tts_session_ids:
            self._speaking_finished.set()

    def _handle_intent_failure(self, _message: Message):
        # Flush any waiters
        self._activities_ended.set()
        self._speaking_finished.set()
        self.reset_state()


class InterceptAllBusClient(MessageBusClient):
    """Bus Client storing all messages received.

    This allows read back of older messages and non-event-driven operation.
    """

    def __init__(self):
        super().__init__()
        self.messages = []
        self.message_lock = Lock()
        self.new_message_available = Event()
        self._processed_messages = 0

    def on_message(self, _, message):
        """Extends normal operation by storing the received message.

        Args:
            message (Message): message from the Mycroft bus
        """
        with self.message_lock:
            self.messages.append(Message.deserialize(message))
        self.new_message_available.set()
        super().on_message(_, message)

    def get_messages(self, msg_type):
        """Get messages from received list of messages.

        Args:
            msg_type (None,str): string filter for the message type to extract.
                                 if None all messages will be returned.
        """
        with self.message_lock:
            self._processed_messages = len(self.messages)
            if msg_type is None:
                return [m for m in self.messages]
            else:
                return [m for m in self.messages if m.msg_type == msg_type]

    def remove_message(self, msg):
        """Remove a specific message from the list of messages.

        Args:
            msg (Message): message to remove from the list
        """
        with self.message_lock:
            if msg not in self.messages:
                raise ValueError(
                    f"{msg.msg_type} was not found in " "the list of messages."
                )
            # Update processed message count if a read message was removed
            if self.messages.index(msg) < self._processed_messages:
                self._processed_messages -= 1

            self.messages.remove(msg)

    def clear_messages(self):
        """Clear all messages that has been fetched at least once."""
        with self.message_lock:
            self.messages = self.messages[self._processed_messages :]
            self._processed_messages = 0

    def clear_all_messages(self):
        """Clear all messages."""
        with self.message_lock:
            self.messages = []
            self._processed_messages = 0


def before_all(context):
    # log = create_voight_kampff_logger()
    # bus = InterceptAllBusClient()
    # bus_connected = Event()
    # bus.once("open", bus_connected.set)

    # Thread(target=bus.run_forever, daemon=True).start()

    # Wait for connection
    # log.info("Waiting for messagebus connection...")
    # bus_connected.wait()

    # log.info('Waiting for skills to be loaded...')
    # start = monotonic()
    # while True:
    #     response = bus.wait_for_response(Message('mycroft.skills.all_loaded'))
    #     if response and response.data['status']:
    #         break
    #     elif monotonic() - start >= 2 * 60:
    #         raise Exception('Timeout waiting for skills to become ready.')
    #     else:
    #         sleep(1)

    # context.bus = bus
    # context.step_timeout = 10  # Reset the step_timeout to 10 seconds
    # context.matched_message = None
    # context.log = log
    # context.config = Configuration.get()
    context.client = VoightKampffClient()


def after_step(context, step):
    context.client.wait_for_skill()
    context.client.reset_state()


def before_feature(context, feature):
    # We are seeing the first tests in Timer and Volume fail for no reason.
    # So let the system rest for a moment...
    # sleep(5)

    LOG.info("Starting tests for {}".format(feature.name))


def after_all(context):
    context.client.shutdown()


def after_feature(context, feature):
    LOG.info("Result: {} ({:.2f}s)".format(str(feature.status.name), feature.duration))


def after_scenario(context, scenario):
    """Wait for mycroft completion and reset any changed state."""
    # TODO wait for skill handler complete
    # context.bus.clear_all_messages()
    # context.matched_message = None
    # context.step_timeout = 10  # Reset the step_timeout to 10 seconds
    pass
