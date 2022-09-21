from abc import ABCMeta, abstractmethod
from typing import Any, Dict

from mycroft.util.log import LOG
from mycroft.util.plugins import load_plugin


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


def load_hotword_module(config: Dict[str, Any]) -> HotWordEngine:
    wake_word = config["listener"]["wake_word"]
    hotword_config = config["hotwords"][wake_word]
    module_name = hotword_config["module"]

    LOG.debug("Loading wake word module: %s", module_name)
    module = load_plugin("mycroft.plugin.wake_word", module_name)
    assert module, f"Failed to load {module_name}"
    hotword = module(config=hotword_config)
    LOG.info("Loaded wake word module: %s", module_name)

    return hotword
