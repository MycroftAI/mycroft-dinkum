import logging
from enum import Enum

LOG = logging.getLogger("vad")


class VadState(str, Enum):
    STARTED = "started"
    IN_COMMAND = "in_command"


class VadCommand:
    def __init__(self, speech_begin: float, silence_end: float, timeout: float):
        self.speech_begin = speech_begin
        self.silence_end = silence_end
        self.timeout = timeout

        self._state = VadState.STARTED
        self._speech_seconds_left = self.speech_begin
        self._silence_seconds_left = self.silence_end
        self._timeout_seconds_left = self.timeout

    def reset(self):
        self._state = VadState.STARTED
        self._speech_seconds_left = self.speech_begin
        self._silence_seconds_left = self.silence_end
        self._timeout_seconds_left = self.timeout

    def process(self, is_speech: bool, seconds: float) -> bool:
        self._timeout_seconds_left -= seconds
        if self._timeout_seconds_left <= 0:
            LOG.warning("Timeout")
            return True

        is_complete = False
        if self._state == VadState.STARTED:
            # Voice command has not begun yet
            if is_speech:
                # Speech
                self._speech_seconds_left -= seconds
                if self._speech_seconds_left <= 0:
                    # Begin voice command
                    LOG.debug("Begin voice command")
                    self._silence_seconds_left = self.silence_end
                    self._state = VadState.IN_COMMAND
            else:
                # Silence (reset)
                self._speech_seconds_left = self.speech_begin
        elif self._state == VadState.IN_COMMAND:
            # Inside voice command
            if is_speech:
                # Speech (reset)
                self._silence_seconds_left = self.silence_end
            else:
                # Silence
                self._silence_seconds_left -= seconds
                if self._silence_seconds_left <= 0:
                    # End voice command
                    LOG.debug("End voice command")
                    is_complete = True

        return is_complete
