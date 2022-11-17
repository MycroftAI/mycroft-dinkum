import unittest

from fsticuffs.grammar import Grammar, Intent
from fsticuffs.expression import Sentence, Word, Sequence, SequenceType, Word


class GrammarTestCase(unittest.TestCase):
    def test_parse(self):
        ini_text = """
        [TestIntent1]
        this is a test

        [TestIntent2]
        this is another test
        """

        grammar = Grammar.parse_string(ini_text)
        self.assertEqual(
            grammar.intents,
            {
                "TestIntent1": Intent(
                    name="TestIntent1",
                    sentences=[
                        Sentence(
                            items=[
                                w(text="this"),
                                w(text="is"),
                                w(text="a"),
                                w(text="test"),
                            ],
                        )
                    ],
                ),
                "TestIntent2": Intent(
                    name="TestIntent2",
                    sentences=[
                        Sentence(
                            items=[
                                w(text="this"),
                                w(text="is"),
                                w(text="another"),
                                w(text="test"),
                            ],
                        )
                    ],
                ),
            },
        )

    def test_escape(self):
        """Test escaped optional."""
        ini_text = """
        [TestIntent1]
        \\[this] is a test
        """

        grammar = Grammar.parse_string(ini_text)
        self.assertEqual(
            grammar.intents,
            {
                "TestIntent1": Intent(
                    name="TestIntent1",
                    sentences=[
                        Sentence(
                            items=[
                                alt(
                                    items=[
                                        group(items=[Word(text="this")]),
                                        Word.empty(),
                                    ]
                                ),
                                Word(text="is"),
                                Word(text="a"),
                                Word(text="test"),
                            ]
                        )
                    ],
                ),
            },
        )


# -----------------------------------------------------------------------------


def w(**kwargs):
    return Word(**kwargs)


def group(**kwargs):
    return Sequence(type=SequenceType.GROUP, **kwargs)


def alt(**kwargs):
    return Sequence(type=SequenceType.ALTERNATIVE, **kwargs)
