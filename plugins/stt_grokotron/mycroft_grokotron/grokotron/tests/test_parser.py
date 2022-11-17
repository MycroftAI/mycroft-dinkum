import unittest

from fsticuffs.parser import next_chunk, ParseChunk, ParseType


class WordTestCase(unittest.TestCase):
    def test_word(self):
        text = "test"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="test",
                parse_type=ParseType.WORD,
                start_index=0,
                end_index=len(text),
            ),
        )

    def test_word_sub(self):
        text = "test:test2"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="test",
                parse_type=ParseType.WORD,
                start_index=0,
                end_index=len(text),
                substitution=ParseChunk(
                    text="test2",
                    parse_type=ParseType.WORD,
                    start_index=text.find(":"),
                    end_index=len(text),
                ),
            ),
        )

    def test_word_sub_empty(self):
        text = "test:"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="test",
                parse_type=ParseType.WORD,
                start_index=0,
                end_index=len(text),
                substitution=ParseChunk(
                    text="",
                    parse_type=ParseType.WORD,
                    start_index=text.find(":"),
                    end_index=len(text),
                ),
            ),
        )

    def test_word_sub_group(self):
        text = "test:(test2 test3)"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="test",
                parse_type=ParseType.WORD,
                start_index=0,
                end_index=len(text),
                substitution=ParseChunk(
                    text="(test2 test3)",
                    parse_type=ParseType.GROUP,
                    start_index=text.find(":"),
                    end_index=len(text),
                ),
            ),
        )

    def test_word_escape(self):
        text = "test\\(2\\)"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="test(2)",
                parse_type=ParseType.WORD,
                start_index=0,
                end_index=len(text),
            ),
        )

    def test_word_sub_escape(self):
        text = "test:test\\(2\\)"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="test",
                parse_type=ParseType.WORD,
                start_index=0,
                end_index=len(text),
                substitution=ParseChunk(
                    text="test(2)",
                    parse_type=ParseType.WORD,
                    start_index=text.find(":"),
                    end_index=len(text),
                ),
            ),
        )

    def test_word_quote(self):
        text = '"test(2)"'
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="test(2)",
                parse_type=ParseType.WORD,
                start_index=0,
                end_index=len(text),
            ),
        )

    def test_word_quote_escape(self):
        text = '"test\\"2\\""'
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text='test"2"',
                parse_type=ParseType.WORD,
                start_index=0,
                end_index=len(text),
            ),
        )


# -----------------------------------------------------------------------------


class SequenceTestCase(unittest.TestCase):
    def test_group(self):
        text = "(test test2)"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="(test test2)",
                parse_type=ParseType.GROUP,
                start_index=0,
                end_index=len(text),
            ),
        )

    def test_optional(self):
        text = "[test test2]"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="[test test2]",
                parse_type=ParseType.OPT,
                start_index=0,
                end_index=len(text),
            ),
        )

    def test_group_sub_group(self):
        text = "(test test2):(test3 test4)"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="(test test2)",
                parse_type=ParseType.GROUP,
                start_index=0,
                end_index=len(text),
                substitution=ParseChunk(
                    text="(test3 test4)",
                    parse_type=ParseType.GROUP,
                    start_index=text.find(":"),
                    end_index=len(text),
                ),
            ),
        )

    def test_opt_sub_group(self):
        text = "[test test2]:(test3 test4)"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="[test test2]",
                parse_type=ParseType.OPT,
                start_index=0,
                end_index=len(text),
                substitution=ParseChunk(
                    text="(test3 test4)",
                    parse_type=ParseType.GROUP,
                    start_index=text.find(":"),
                    end_index=len(text),
                ),
            ),
        )

    def test_group_sub_empty(self):
        text = "(test test2):"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="(test test2)",
                parse_type=ParseType.GROUP,
                start_index=0,
                end_index=len(text),
                substitution=ParseChunk(
                    text="",
                    parse_type=ParseType.WORD,
                    start_index=text.find(":"),
                    end_index=len(text),
                ),
            ),
        )

    def test_group_opt_empty(self):
        text = "[test test2]:"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="[test test2]",
                parse_type=ParseType.OPT,
                start_index=0,
                end_index=len(text),
                substitution=ParseChunk(
                    text="",
                    parse_type=ParseType.WORD,
                    start_index=text.find(":"),
                    end_index=len(text),
                ),
            ),
        )

    def test_group_tag(self):
        text = "(test test2){test3}"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="(test test2)",
                parse_type=ParseType.GROUP,
                start_index=0,
                end_index=len(text),
                tag=ParseChunk(
                    text="test3",
                    parse_type=ParseType.WORD,
                    start_index=text.find("{"),
                    end_index=len(text),
                ),
            ),
        )

    def test_opt_tag(self):
        text = "[test test2]{test3}"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="[test test2]",
                parse_type=ParseType.OPT,
                start_index=0,
                end_index=len(text),
                tag=ParseChunk(
                    text="test3",
                    parse_type=ParseType.WORD,
                    start_index=text.find("{"),
                    end_index=len(text),
                ),
            ),
        )


# -----------------------------------------------------------------------------


class ReferenceTestCase(unittest.TestCase):
    def test_slot_reference(self):
        text = "$test"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="$test",
                parse_type=ParseType.SLOT,
                start_index=0,
                end_index=len(text),
            ),
        )

    def test_slot_escape(self):
        text = "\\$test"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="$test",
                parse_type=ParseType.WORD,
                start_index=0,
                end_index=len(text),
            ),
        )

    def test_rule_reference(self):
        text = "<test>"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="<test>",
                parse_type=ParseType.RULE,
                start_index=0,
                end_index=len(text),
            ),
        )

    def test_rule_escape(self):
        text = "\\<test\\>"
        self.assertEqual(
            next_chunk(text),
            ParseChunk(
                text="<test>",
                parse_type=ParseType.WORD,
                start_index=0,
                end_index=len(text),
            ),
        )
