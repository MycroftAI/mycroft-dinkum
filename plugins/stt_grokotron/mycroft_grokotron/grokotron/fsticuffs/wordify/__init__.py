from typing import List, Union

from .const import IntegerType, NumberLanguage, UnsupportedLanguageError
from .en import en_integer_to_words


def integer_to_words(
    number: int,
    language: Union[str, NumberLanguage] = NumberLanguage.EN,
    number_type: IntegerType = IntegerType.CARDINAL,
) -> List[str]:
    if language == NumberLanguage.EN:
        return en_integer_to_words(number, number_type)

    if isinstance(language, NumberLanguage):
        language = language.value

    raise UnsupportedLanguageError(language)
