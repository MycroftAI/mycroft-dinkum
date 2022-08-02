# Copyright 2019 Mycroft AI Inc.
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
"""The fallback skill implements a special type of skill handling
utterances not handled by the intent system.
"""
from typing import Callable, Dict, Optional
from uuid import uuid4

from mycroft.messagebus.message import Message
from mycroft.util.log import LOG

from .mycroft_skill import MycroftSkill

FallbackHandler = Callable[[Message], bool]


class FallbackSkill(MycroftSkill):
    """Fallbacks come into play when no skill matches an Adapt or closely with
    a Padatious intent.  All Fallback skills work together to give them a
    view of the user's utterance.  Fallback handlers are called in an order
    determined the priority provided when the the handler is registered.

    ========   ========   ================================================
    Priority   Who?       Purpose
    ========   ========   ================================================
       1-4     RESERVED   Unused for now, slot for pre-Padatious if needed
         5     MYCROFT    Padatious near match (conf > 0.8)
      6-88     USER       General
        89     MYCROFT    Padatious loose match (conf > 0.5)
     90-99     USER       Uncaught intents
       100+    MYCROFT    Fallback Unknown or other future use
    ========   ========   ================================================

    Handlers with the numerically lowest priority are invoked first.
    Multiple fallbacks can exist at the same priority, but no order is
    guaranteed.

    A Fallback can either observe or consume an utterance. A consumed
    utterance will not be see by any other Fallback handlers.
    """

    def __init__(self, skill_id: str, name=None, bus=None, use_settings=True):
        super().__init__(skill_id, name, bus, use_settings)

        self._handlers: Dict[str, FallbackHandler] = {}

    def initialize(self):
        self.bus.on("mycroft.skills.handle-fallback", self._handle_fallback)
        super().initialize()

    def _handle_fallback(self, message: Message):
        name = message.data["name"]
        mycroft_session_id = message.data.get("mycroft_session_id")
        handled = False
        response_message: Optional[Message] = None
        handler = self._handlers.get(name)

        if handler:
            self._mycroft_session_id = mycroft_session_id
            try:
                # Handler may return a boolean value indicating if the message
                # was handled, or a (handled, message) tuple.
                result = handler(message)
                if isinstance(result, tuple):
                    handled, response_message = result
                else:
                    handled = bool(result)
                    if handled:
                        # Automatically close session
                        response_message = self.end_session()
            except Exception:
                LOG.exception("Unexpected error in fallback handler")

            self.bus.emit(
                message.response(
                    data={
                        "mycroft_session_id": mycroft_session_id,
                        "handled": handled,
                        "skill_id": self.skill_id,
                    }
                )
            )

            if response_message is not None:
                self.bus.emit(response_message)

    def register_fallback(self, handler: FallbackHandler, priority: int):
        """Register a fallback with the list of fallback handlers and with the
        list of handlers registered by this instance
        """

        handler_name = str(uuid4())
        self.bus.emit(
            Message(
                "mycroft.skills.register-fallback",
                data={
                    "name": handler_name,
                    "priority": priority,
                    "skill_id": self.skill_id,
                },
            )
        )
        self._handlers[handler_name] = handler

    def default_shutdown(self):
        for handler_name in self._handlers:
            self.bus.emit(
                Message(
                    "mycroft.skills.unregister-fallback",
                    data={"name": handler_name, "skill_id": self.skill_id},
                )
            )

        super().default_shutdown()
