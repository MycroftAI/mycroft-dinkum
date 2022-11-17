from math import floor, log10
from typing import List

from .const import IntegerType, UnsupportedNumberType

_NAMES = {
    0: "zero",
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
    17: "seventeen",
    18: "eighteen",
    19: "nineteen",
    20: "twenty",
    30: "thirty",
    40: "forty",
    50: "fifty",
    60: "sixty",
    70: "seventy",
    80: "eighty",
    90: "ninety",
    100: "hundred",
    1_000: "thousand",
    1_000_000: "million",
    1_000_000_000: "billion",
    1_000_000_000_000: "trillion",
    # https://en.wikipedia.org/wiki/Names_of_large_numbers
    1_000_000_000_000_000: "quadrillion",
    1_000_000_000_000_000_000: "quintillion",
    1_000_000_000_000_000_000_000: "sextillion",
    1_000_000_000_000_000_000_000_000: "septillion",
    1_000_000_000_000_000_000_000_000_000: "octillion",
    1_000_000_000_000_000_000_000_000_000_000: "nonillion",
    1_000_000_000_000_000_000_000_000_000_000_000: "decillion",
    1_000_000_000_000_000_000_000_000_000_000_000_000: "undecillion",
    1_000_000_000_000_000_000_000_000_000_000_000_000_000: "duodecillion",
    1_000_000_000_000_000_000_000_000_000_000_000_000_000_000: "tredecillion",
    1_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000: "quattuordecillion",
    1_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000: "quindecillion",
    1_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000: "sexdecillion",
    1_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000: "septendecillion",
    1_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000: "octodecillion",
    1_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000: "novemdecillion",
    1_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000: "vigintillion",
    1_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000_000: "centillion",
}


def en_integer_to_words(
    number: int, number_type: IntegerType = IntegerType.CARDINAL
) -> List[str]:
    if number_type == IntegerType.CARDINAL:
        return _to_cardinal(number)

    if number_type == IntegerType.DIGITS:
        return _to_digits(number)

    raise UnsupportedNumberType(str(number_type))


def _to_cardinal(number: int) -> List[str]:
    if number < 100:
        name = _NAMES.get(number)
        if name is not None:
            return [name]

        unit = number % 10
        if unit == 0:
            # Don't add "zero" at the end
            return [_NAMES[number - unit]]

        return [_NAMES[number - unit], _NAMES[unit]]

    if number < 1000:
        base = 100
    else:
        order = int(floor(log10(number)))
        order_remainder = order % 3
        base = int(pow(10, order - order_remainder))

    first = int(number / base)
    rest = number % base

    if rest == 0:
        # Don't add "zero" at the end
        return _to_cardinal(first) + [_NAMES[base]]

    return _to_cardinal(first) + [_NAMES[base]] + _to_cardinal(rest)


def _to_digits(number: int) -> List[str]:
    digits: List[str] = []

    for digit_str in str(number):
        digit = int(digit_str)
        digits.append(_NAMES[digit])

    return digits
