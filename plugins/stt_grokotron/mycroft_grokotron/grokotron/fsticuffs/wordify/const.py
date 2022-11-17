from enum import Enum, auto


class NumberLanguage(str, Enum):
    EN = "en"


class IntegerType(Enum):
    CARDINAL = auto()
    DIGITS = auto()


class UnsupportedLanguageError(Exception):
    def __init__(self, language: str):
        super().__init__(f"Unsupported language: {language}")


class UnsupportedNumberType(Exception):
    def __init__(self, number_type: str):
        super().__init__(f"Unsupported number type: {number_type}")
