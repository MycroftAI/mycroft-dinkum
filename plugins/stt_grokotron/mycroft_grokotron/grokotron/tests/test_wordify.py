import unittest

from fsticuffs.wordify import NumberLanguage, integer_to_words, IntegerType


class EnglishTestCase(unittest.TestCase):
    def test_single(self):
        self.assertEqual(integer_to_words(7), ["seven"])

    def test_teen(self):
        self.assertEqual(integer_to_words(15), ["fifteen"])

    def test_double(self):
        self.assertEqual(integer_to_words(42), ["forty", "two"])

    def test_100(self):
        self.assertEqual(integer_to_words(142), ["one", "hundred", "forty", "two"])

    def test_1000(self):
        self.assertEqual(
            integer_to_words(3_142),
            ["three", "thousand", "one", "hundred", "forty", "two"],
        )

    def test_10_000(self):
        self.assertEqual(
            integer_to_words(83_142),
            ["eighty", "three", "thousand", "one", "hundred", "forty", "two"],
        )

    def test_100_000(self):
        self.assertEqual(
            integer_to_words(683_142),
            [
                "six",
                "hundred",
                "eighty",
                "three",
                "thousand",
                "one",
                "hundred",
                "forty",
                "two",
            ],
        )

    def test_1_000_000(self):
        self.assertEqual(
            integer_to_words(2_683_142),
            [
                "two",
                "million",
                "six",
                "hundred",
                "eighty",
                "three",
                "thousand",
                "one",
                "hundred",
                "forty",
                "two",
            ],
        )

    def test_10_000_000(self):
        self.assertEqual(
            integer_to_words(20_683_142),
            [
                "twenty",
                "million",
                "six",
                "hundred",
                "eighty",
                "three",
                "thousand",
                "one",
                "hundred",
                "forty",
                "two",
            ],
        )

    def test_100_000_000(self):
        self.assertEqual(
            integer_to_words(520_683_142),
            [
                "five",
                "hundred",
                "twenty",
                "million",
                "six",
                "hundred",
                "eighty",
                "three",
                "thousand",
                "one",
                "hundred",
                "forty",
                "two",
            ],
        )

    def test_1_000_000_000(self):
        self.assertEqual(
            integer_to_words(4_520_683_142),
            [
                "four",
                "billion",
                "five",
                "hundred",
                "twenty",
                "million",
                "six",
                "hundred",
                "eighty",
                "three",
                "thousand",
                "one",
                "hundred",
                "forty",
                "two",
            ],
        )

    def test_digits(self):
        self.assertEqual(
            integer_to_words(1234, number_type=IntegerType.DIGITS),
            ["one", "two", "three", "four"],
        )
