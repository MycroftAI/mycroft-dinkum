import os
from abc import ABCMeta, abstractmethod

from .cache import TextToSpeechCache

class TTS(metaclass=ABCMeta):
    def __init__(
        self,
        lang,
        config,
        validator,
        audio_ext="wav",
        phonetic_spelling=True,
        ssml_tags=None,
    ):
        self.bus = None
        self.lang = lang or "en-us"
        self.config = config

        self.validator = validator
        self.phonetic_spelling = phonetic_spelling
        self.audio_ext = audio_ext
        self.ssml_tags = ssml_tags or []

        self.cache = TextToSpeechCache()

    def init(self, bus):
        self.bus = bus

    def stop(self):
        pass

    @abstractmethod
    def get_tts(self, sentence, wav_file):
        """Abstract method that a tts implementation needs to implement.

        Should get data from tts.

        Args:
            sentence(str): Sentence to synthesize
            wav_file(str): output file

        Returns:
            tuple: (wav_file, phoneme)
        """
        pass


class TTSValidator(metaclass=ABCMeta):
    def __init__(self, tts):
        self.tts = tts

    def validate(self):
        self.validate_dependencies()
        self.validate_instance()
        self.validate_filename()
        self.validate_lang()
        self.validate_connection()

    def validate_dependencies(self):
        """Determine if all the TTS's external dependencies are satisfied."""
        pass

    def validate_instance(self):
        clazz = self.get_tts_class()
        if not isinstance(self.tts, clazz):
            raise AttributeError("tts must be instance of " + clazz.__name__)

    def validate_filename(self):
        filename = self.tts.filename
        if not (filename and filename.endswith(".wav")):
            raise AttributeError(f"file: {filename} must be in .wav format!")

        dir_path = os.path.dirname(filename)
        if not (os.path.exists(dir_path) and os.path.isdir(dir_path)):
            raise AttributeError(f"filename: {filename} is not valid!")

    @abstractmethod
    def validate_lang(self):
        """Ensure the TTS supports current language."""

    @abstractmethod
    def validate_connection(self):
        """Ensure the TTS can connect to it's backend.

        This can mean for example being able to launch the correct executable
        or contact a webserver.
        """

    @abstractmethod
    def get_tts_class(self):
        """Return TTS class that this validator is for."""


