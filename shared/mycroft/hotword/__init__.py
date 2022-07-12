from abc import ABCMeta, abstractmethod


class HotWordEngine(metaclass=ABCMeta):
    def __init__(self, key_phrase="hey mycroft", config=None, lang="en-us"):
        self.config = config or {}

    @abstractmethod
    def found_wake_word(self, frame_data) -> bool:
        """frame_data is unused"""
        return False

    @abstractmethod
    def update(self, chunk):
        pass

    def shutdown(self):
        pass
