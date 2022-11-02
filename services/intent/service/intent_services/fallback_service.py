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
"""Intent service for Mycroft's fallback system."""
import operator
from collections import defaultdict, namedtuple
from typing import Dict, Optional, Set

from mycroft.messagebus.message import Message
from mycroft.util.log import get_mycroft_logger

_log = get_mycroft_logger(__name__)

from .base import IntentMatch

FallbackRange = namedtuple("FallbackRange", ["start", "stop"])


class FallbackService:
    """Intent Service handling fallback skills."""

    def __init__(self, bus):
        self.bus = bus
        self.session_id: Optional[str] = None
        self._fallback_handlers: Dict[int, Set[str]] = defaultdict(set)

        self.bus.on("mycroft.skills.register-fallback", self._register_fallback)
        self.bus.on("mycroft.skills.unregister-fallback", self._unregister_fallback)

    def _register_fallback(self, message):
        """Register a fallback handler by priority/name"""
        name = message.data["name"]
        priority = message.data["priority"]
        skill_id = message.data["skill_id"]
        self._fallback_handlers[priority].add(name)
        _log.info(
            "Registered fallback for %s (priority=%s, id=%s)", skill_id, priority, name
        )

    def _unregister_fallback(self, message):
        """Unregister a fallback handler by name"""
        name = message.data["name"]
        skill_id = message.data["skill_id"]

        for handler_names in self._fallback_handlers.values():
            handler_names.discard(name)

        _log.info("Unregistered fallback for %s (id=%s)", skill_id, name)

    def _fallback_range(self, utterances, lang, message, fb_range: FallbackRange):
        """Send fallback request for a specified priority range.

        Args:
            utterances (list): List of tuples,
                               utterances and normalized version
            lang (str): Langauge code
            message: Message for session context
            fb_range (FallbackRange): fallback order start and stop.

        Returns:
            IntentMatch or None
        """
        sorted_handlers = sorted(
            self._fallback_handlers.items(), key=operator.itemgetter(0)
        )
        for priority, handler_names in sorted_handlers:
            if (priority < fb_range.start) or (priority >= fb_range.stop):
                continue
            _log.info(
                "Trying %s fallback handler(s) at priority %s",
                len(handler_names),
                priority,
            )
            for handler in handler_names:
                reply = self.bus.wait_for_response(
                    Message(
                        "mycroft.skills.handle-fallback",
                        data={
                            "name": handler,
                            "utterance": utterances[0][0],
                            "lang": lang,
                            "fallback_range": (fb_range.start, fb_range.stop),
                            "mycroft_session_id": self.session_id,
                        },
                    ),
                    timeout=5,
                )

                if reply and reply.data.get("handled", False):
                    skill_id = reply.data["skill_id"]
                    _log.info(
                        "Handled by fallback skill %s at priority %s",
                        skill_id,
                        priority,
                    )
                    return IntentMatch("Fallback", None, {}, skill_id)

        return None

    def high_prio(self, utterances, lang, message):
        """Pre-padatious fallbacks."""
        return self._fallback_range(utterances, lang, message, FallbackRange(0, 5))

    def medium_prio(self, utterances, lang, message):
        """General fallbacks."""
        return self._fallback_range(utterances, lang, message, FallbackRange(5, 90))

    def low_prio(self, utterances, lang, message):
        """Low prio fallbacks with general matching such as chat-bot."""
        return self._fallback_range(utterances, lang, message, FallbackRange(90, 101))
