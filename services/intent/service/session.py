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
"""
Session support for Mycroft Core 1.

Sessions replace the speak, show_page, etc. skill commands with messages that
are handled by the intent service.

A session typically starts with an utterance, and is ended by a skill's intent
handler. The "mycroft.session.{start,continue,end}" messages may contain a list
of actions, such as speaking dialog, showing a GUI page, or clearing the GUI.
The intent service may opt to not execute a session's actions if, for example,
the session was cancelled by something that is higher priority.

Multiple sessions may be active at once, waiting on various actions to complete
(usually TTS or audio). However, only one session at a time may control the GUI
or TTS output. The most recent session gets priority if it contains a TTS or GUI
action.

A session may be continued, optionally with an expectation of a user response
(expect_response=True). In this case, the next utterance will be forwarded to
that skill's raw_utterance method.
"""
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, Iterable, List, Optional

from mycroft_bus_client import Message, MessageBusClient


class BaseAction(ABC):
    """Base class for a session action"""

    @abstractmethod
    def do_action(self, session: "Session", bus: MessageBusClient):
        """Perform the session action"""
        pass


@dataclass
class Session:
    """State of a session"""

    id: str
    """Globally unique id of session"""

    skill_id: Optional[str] = None
    """Skill id associated with this session"""

    will_continue: bool = False
    """True if the session will continue after actions are completed (i.e., don't end it)"""

    expect_response: bool = False
    """True if a response from the user is expected next"""

    actions: List[BaseAction] = field(default_factory=list)
    """List of actions that should be executed before this session is ended (or continued)"""

    tick: int = field(default_factory=time.monotonic_ns)
    """Time when this session was created"""

    aborted: bool = False
    """True if the session was cancelled by something that was higher priority"""

    waiting_for_tts: bool = False
    """True if a TTS session needs to finish before the session can continue"""

    waiting_for_audio: bool = False
    """True if a media session needs to finish before the session can continue"""

    state: Optional[Dict[str, Any]] = None
    """Optional state passed from mycroft.session.continue into raw_utterance"""

    dont_clear_gui: bool = True
    """True if GUI should not be cleared until a new session takes over"""

    @property
    def is_waiting_for_action(self) -> bool:
        """Session is currently waiting for an external action to complete"""
        return self.waiting_for_tts or self.waiting_for_audio or self.expect_response

    @property
    def has_gui_actions(self) -> bool:
        """Session has at least one GUI action"""
        return any(
            isinstance(action, (ShowPageAction, ClearDisplayAction, WaitForIdleAction))
            for action in self.actions
        )

    def started(self, bus: MessageBusClient):
        """Report session has started"""
        bus.emit(
            Message(
                "mycroft.session.started",
                data={
                    "mycroft_session_id": self.id,
                    "skill_id": self.skill_id,
                    "state": self.state,
                },
            )
        )

    def actions_completed(self, bus: MessageBusClient):
        """Report that session's actions have all been completed"""
        bus.emit(
            Message(
                "mycroft.session.actions-completed",
                data={"mycroft_session_id": self.id},
            )
        )

    def continued(self, bus: MessageBusClient):
        """Report that this session is continuing (will not be ended automatically)"""
        bus.emit(
            Message(
                "mycroft.session.continued",
                data={
                    "mycroft_session_id": self.id,
                    "skill_id": self.skill_id,
                    "state": self.state,
                },
            )
        )

    def ended(self, bus: MessageBusClient):
        """Report that this session has ended"""
        bus.emit(
            Message(
                "mycroft.session.ended",
                data={
                    "mycroft_session_id": self.id,
                    "aborted": self.aborted,
                    "state": self.state,
                },
            )
        )

    def run(self, bus: MessageBusClient) -> Iterable[BaseAction]:
        """Execute a session's actions until there aren't any more or one requires waiting (e.g., TTS)"""
        if self.aborted:
            self.ended(bus)
        elif not self.is_waiting_for_action:
            while self.actions and (not self.is_waiting_for_action):
                next_action = self.actions[0]
                self.actions = self.actions[1:]
                next_action.do_action(self, bus)

                # Actions are caught in the intent service for additional processing
                yield next_action

            if not self.actions:
                # Finished all actions
                self.actions_completed(bus)
                if not self.is_waiting_for_action:
                    if self.will_continue:
                        # Session will continue for at least one more turn
                        self.will_continue = False
                        self.continued(bus)
                    else:
                        self.ended(bus)

    @staticmethod
    def parse_actions(action_dicts: List[Dict[str, Any]]) -> List[BaseAction]:
        """Convert list of actions from a messagebus message to dataclasses"""
        actions: List[BaseAction] = []

        for action_dict in action_dicts:
            action_type = action_dict.get("type")
            if action_type == SpeakAction.TYPE:
                # Speak dialog or an arbitrary utterance
                actions.append(
                    SpeakAction(
                        utterance=action_dict.get("utterance", ""),
                        dialog=action_dict.get("dialog"),
                        wait=action_dict.get("wait", True),
                    )
                )
            elif action_type == MessageAction.TYPE:
                # Send a message at the beginning or end of a session
                actions.append(
                    MessageAction(
                        message_type=action_dict.get("message_type", ""),
                        data=action_dict.get("data"),
                        delay=action_dict.get("delay", 0.0),
                    )
                )
            elif action_type == ShowPageAction.TYPE:
                # Show a GUI page
                actions.append(
                    ShowPageAction(
                        namespace=action_dict.get("namespace", ""),
                        page=action_dict.get("page", ""),
                        data=action_dict.get("data"),
                    )
                )
            elif action_type == ClearDisplayAction.TYPE:
                # Clear GUI right now
                actions.append(ClearDisplayAction())
            elif action_type == WaitForIdleAction.TYPE:
                # Clear GUI after idle timeout
                actions.append(WaitForIdleAction())
            elif action_type == AudioAlertAction.TYPE:
                # Play a short sound effect to alert the user
                actions.append(
                    AudioAlertAction(
                        uri=action_dict.get("uri", ""),
                        wait=action_dict.get("wait", True),
                    )
                )
            elif action_type == StreamMusicAction.TYPE:
                # Stream music from a URI in the background
                actions.append(
                    StreamMusicAction(
                        uri=action_dict.get("uri", ""),
                    )
                )
            elif action_type == GetResponseAction.TYPE:
                # Request response from the user
                actions.append(GetResponseAction())

        return actions


@dataclass
class SpeakAction(BaseAction):
    """Speak dialog or an arbitrary utterance"""

    TYPE: ClassVar[str] = "speak"

    utterance: str
    """Text to speak"""

    dialog: Optional[str]
    """Name of dialog file associated with spoken text"""

    wait: bool
    """True if session should pause until speaking is complete"""

    def do_action(self, session: Session, bus: MessageBusClient):
        bus.emit(
            Message(
                "speak",
                data={
                    "mycroft_session_id": session.id,
                    "utterance": self.utterance,
                    "meta": {
                        "dialog": self.dialog,
                        "skill_id": session.skill_id,
                    },
                },
            )
        )

        if self.wait:
            # Cache the next TTS utterance while this one is being spoken
            for next_action in session.actions:
                if isinstance(next_action, SpeakAction):
                    bus.emit(
                        Message(
                            "speak.cache",
                            data={
                                "mycroft_session_id": session.id,
                                "utterance": next_action.utterance,
                            },
                        )
                    )
                    break

            # Will be called back when TTS is finished
            session.waiting_for_tts = True


@dataclass
class MessageAction(BaseAction):
    """Send a message at the beginning or end of a session"""

    TYPE: ClassVar[str] = "message"

    message_type: str
    """Message type"""

    data: Optional[Dict[str, Any]] = None
    """Message data"""

    delay: float = 0.0
    """Delay in seconds before sending the message"""

    def do_action(self, session: Session, bus: MessageBusClient):
        if self.delay <= 0:
            # Send message now
            bus.emit(Message(self.message_type, data=self.data))


@dataclass
class ShowPageAction(BaseAction):
    """Show a GUI page"""

    TYPE: ClassVar[str] = "show_page"

    namespace: str
    """{skill_id}.{page_name}"""

    page: str
    """URI of page"""

    data: Optional[Dict[str, Any]] = None
    """GUI values for page"""

    def do_action(self, session: Session, bus: MessageBusClient):
        bus.emit(
            Message(
                "gui.page.show",
                {
                    "namespace": self.namespace,
                    "page": self.page,
                    "data": self.data,
                    "skill_id": session.skill_id,
                },
            )
        )


@dataclass
class ClearDisplayAction(BaseAction):
    """Clear GUI right now"""

    TYPE: ClassVar[str] = "clear_display"

    def do_action(self, session: Session, bus: MessageBusClient):
        """Handled outside in intent service"""
        session.dont_clear_gui = False


@dataclass
class WaitForIdleAction(BaseAction):
    """Clear GUI after idle timeout"""

    TYPE: ClassVar[str] = "wait_for_idle"

    def do_action(self, session: Session, bus: MessageBusClient):
        """Handled outside in intent service"""
        session.dont_clear_gui = False


@dataclass
class AudioAlertAction(BaseAction):
    """Play a short sound effect to alert the user"""

    TYPE: ClassVar[str] = "audio_alert"

    uri: str
    """URI of sound to play (must be file URI)"""

    wait: bool
    """True if session should pause until sound is finished playing"""

    def do_action(self, session: Session, bus: MessageBusClient):
        bus.emit(
            Message(
                "mycroft.audio.play-sound",
                data={"uri": self.uri, "mycroft_session_id": session.id},
            )
        )
        if self.wait:
            # Will be called back when audio is finished
            session.waiting_for_audio = True


@dataclass
class StreamMusicAction(BaseAction):
    """Stream music from a URI in the background"""

    TYPE: ClassVar[str] = "stream_music"

    uri: str
    """URI of audio stream"""

    def do_action(self, session: Session, bus: MessageBusClient):
        bus.emit(
            Message(
                "mycroft.audio.service.play",
                data={
                    "tracks": [self.uri],
                    "mycroft_session_id": session.id,
                },
            )
        )


@dataclass
class GetResponseAction(BaseAction):
    """Request response from the user"""

    TYPE: ClassVar[str] = "get_response"

    def do_action(self, session: Session, bus: MessageBusClient):
        # Intent service will trigger listen outside
        session.expect_response = True
