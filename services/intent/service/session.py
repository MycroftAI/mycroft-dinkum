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
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, Iterable, List, Optional

from mycroft_bus_client import Message, MessageBusClient


class BaseAction(ABC):
    @abstractmethod
    def do_action(self, session: "Session", bus: MessageBusClient):
        pass


@dataclass
class Session:
    id: str
    skill_id: Optional[str] = None
    will_continue: bool = False
    expect_response: bool = False
    actions: List[BaseAction] = field(default_factory=list)
    tick: int = field(default_factory=time.monotonic_ns)
    aborted: bool = False
    waiting_for_tts: bool = False
    waiting_for_audio: bool = False

    @property
    def is_waiting_for_action(self):
        """Session is currently waiting for an external action to complete"""
        return self.waiting_for_tts or self.waiting_for_audio

    def started(self, bus: MessageBusClient):
        bus.emit(
            Message(
                "mycroft.session.started",
                data={"mycroft_session_id": self.id, "skill_id": self.skill_id},
            )
        )

    def actions_completed(self, bus: MessageBusClient):
        bus.emit(
            Message(
                "mycroft.session.actions-completed",
                data={"mycroft_session_id": self.id},
            )
        )

    def continued(self, bus: MessageBusClient):
        bus.emit(
            Message(
                "mycroft.session.continued",
                data={"mycroft_session_id": self.id},
            )
        )

    def ended(self, bus: MessageBusClient):
        bus.emit(
            Message(
                "mycroft.session.ended",
                data={"mycroft_session_id": self.id, "aborted": self.aborted},
            )
        )

    def run(self, bus: MessageBusClient) -> Iterable[BaseAction]:
        if self.aborted:
            self.ended(bus)
        elif not self.is_waiting_for_action:
            while self.actions and (not self.is_waiting_for_action):
                next_action = self.actions[0]
                self.actions = self.actions[1:]
                next_action.do_action(self, bus)
                yield next_action

            if not self.actions:
                self.actions_completed(bus)
                if (not self.is_waiting_for_action) and (not self.will_continue):
                    self.ended(bus)

    @staticmethod
    def parse_actions(action_dicts: List[Dict[str, Any]]) -> List[BaseAction]:
        actions: List[BaseAction] = []

        for action_dict in action_dicts:
            action_type = action_dict.get("type")
            if action_type == SpeakAction.TYPE:
                actions.append(
                    SpeakAction(
                        utterance=action_dict.get("utterance", ""),
                        dialog=action_dict.get("dialog"),
                        wait=action_dict.get("wait", True),
                    )
                )
            elif action_type == MessageAction.TYPE:
                actions.append(
                    MessageAction(
                        message_type=action_dict.get("message_type", ""),
                        data=action_dict.get("data"),
                    )
                )
            elif action_type == ShowPageAction.TYPE:
                actions.append(
                    ShowPageAction(
                        namespace=action_dict.get("namespace", ""),
                        page=action_dict.get("page", ""),
                        data=action_dict.get("data"),
                    )
                )
            elif action_type == ClearDisplayAction.TYPE:
                actions.append(ClearDisplayAction())
            elif action_type == WaitForIdleAction.TYPE:
                actions.append(WaitForIdleAction())
            elif action_type == AudioAlertAction.TYPE:
                actions.append(
                    AudioAlertAction(
                        uri=action_dict.get("uri", ""),
                        wait=action_dict.get("wait", True),
                    )
                )
            elif action_type == StreamMusicAction.TYPE:
                actions.append(
                    StreamMusicAction(
                        uri=action_dict.get("uri", ""),
                    )
                )
            elif action_type == GetResponseAction.TYPE:
                actions.append(GetResponseAction())

        return actions


@dataclass
class SpeakAction(BaseAction):
    TYPE: ClassVar[str] = "speak"
    utterance: str
    dialog: Optional[str]
    wait: bool

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
    TYPE: ClassVar[str] = "message"
    message_type: str
    data: Optional[Dict[str, Any]] = None

    def do_action(self, session: Session, bus: MessageBusClient):
        bus.emit(Message(self.message_type, data=self.data))


@dataclass
class ShowPageAction(BaseAction):
    TYPE: ClassVar[str] = "show_page"
    namespace: str
    page: str
    data: Optional[Dict[str, Any]] = None

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
    TYPE: ClassVar[str] = "clear_display"

    def do_action(self, session: Session, bus: MessageBusClient):
        pass


@dataclass
class WaitForIdleAction(BaseAction):
    TYPE: ClassVar[str] = "wait_for_idle"

    def do_action(self, session: Session, bus: MessageBusClient):
        pass


@dataclass
class AudioAlertAction(BaseAction):
    TYPE: ClassVar[str] = "audio_alert"
    uri: str
    wait: bool

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
    TYPE: ClassVar[str] = "stream_music"
    uri: str

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
    TYPE: ClassVar[str] = "get_response"

    def do_action(self, session: Session, bus: MessageBusClient):
        session.expect_response = True
