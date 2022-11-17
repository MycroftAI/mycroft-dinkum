import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

GROUP_START = "("
GROUP_END = ")"
OPT_START = "["
OPT_END = "]"
TAG_START = "{"
TAG_END = "}"
RULE_START = "<"
RULE_END = ">"

DELIM_START = {
    GROUP_START: GROUP_END,
    OPT_START: OPT_END,
    TAG_START: TAG_END,
    RULE_START: RULE_END,
}
DELIM_END = {v: k for k, v in DELIM_START.items()}

SUB_SEP = ":"
WORD_SEP = " "
ALT_SEP = "|"
# CONV_SEP = "!"
SLOT_START = "$"
QUOTE_START = '"'
ESCAPE_CHAR = "\\"


class ParseType(Enum):
    GROUP = auto()
    OPT = auto()
    ALT = auto()
    SUB = auto()
    RULE = auto()
    TAG = auto()
    SLOT = auto()
    WORD = auto()
    QUOTE = auto()
    WHITESPACE = auto()
    END = auto()


#     CONV = auto()


@dataclass
class ParseChunk:
    text: str
    start_index: int
    end_index: int
    parse_type: ParseType
    substitution: "Optional[ParseChunk]" = None
    tag: "Optional[ParseChunk]" = None
    # converters: "Optional[List[str]]" = None


def find_end_delimiter(
    text: str, start_index: int, start_char: str, end_char: str
) -> Optional[int]:
    if start_index > 0:
        text = text[start_index:]

    stack = 1
    is_escaped = False
    for i, c in enumerate(text):
        if is_escaped:
            is_escaped = False
            continue

        if c == ESCAPE_CHAR:
            is_escaped = True
            continue

        if c == end_char:
            stack -= 1
            if stack < 0:
                return None

            if stack == 0:
                return start_index + i + 1

        if c == start_char:
            stack += 1

    return None


def find_end_word(text: str, start_index: int) -> Optional[int]:
    if start_index > 0:
        text = text[start_index:]

    is_escaped = False
    for i, c in enumerate(text):
        if is_escaped:
            is_escaped = False
            continue

        if c == ESCAPE_CHAR:
            is_escaped = True
            continue

        if (c in {SUB_SEP, WORD_SEP, TAG_START}) or (c in DELIM_END):
            return start_index + i

    if text:
        # Entire text is a word
        return start_index + len(text)

    return None


def find_end_quote(
    text: str,
    start_index: int,
) -> Optional[int]:
    if start_index > 0:
        text = text[start_index:]

    is_escaped = False
    for i, c in enumerate(text):
        if is_escaped:
            is_escaped = False
            continue

        if c == ESCAPE_CHAR:
            is_escaped = True
            continue

        if c == QUOTE_START:
            return start_index + i + 1

    return None


def peek_type(text, start_index: int) -> ParseType:
    if start_index >= len(text):
        return ParseType.END

    c = text[start_index]
    if c == GROUP_START:
        return ParseType.GROUP

    if c == OPT_START:
        return ParseType.OPT

    if c == ALT_SEP:
        return ParseType.ALT

    if c == TAG_START:
        return ParseType.TAG

    if c == RULE_START:
        return ParseType.RULE

    if c == SLOT_START:
        return ParseType.SLOT

    if c == SUB_SEP:
        return ParseType.SUB

    if c == QUOTE_START:
        return ParseType.QUOTE

    if c.isspace():
        return ParseType.WHITESPACE

    #     if c == CONV_SEP:
    #         return ParseType.CONV

    return ParseType.WORD


class ParseError(Exception):
    pass


def skip_text(text: str, start_index: int, skip: str) -> int:
    if start_index > 0:
        text = text[start_index:]

    if not text:
        raise ParseError(text)

    text_index = 0
    for c_text in text:
        if c_text == ESCAPE_CHAR:
            text_index += 1
            continue

        if c_text != skip[0]:
            break

        text_index += 1
        skip = skip[1:]

        if not skip:
            break

    if skip:
        raise ParseError(text)

    return start_index + text_index


# def find_end_converters(text: str, start_index: int = 0) -> Optional[int]:
#     conv_end_index: Optional[int] = None

#     end_index_offset = 0
#     conv_text = text
#     next_type = peek_type(conv_text)
#     while next_type == ParseType.CONV:
#         # Skip '!'
#         conv_text = skip_text(conv_text, CONV_SEP)
#         end_index_offset += 1

#         conv_end_index = find_end_word(conv_text)
#         if conv_end_index is None:
#             raise ParseError(conv_text)

#         # Skip converter name
#         conv_text = conv_text[conv_end_index:]
#         end_index_offset += conv_end_index

#         # Check for more converters
#         next_type = peek_type(conv_text)

#     if end_index_offset > 0:
#         return start_index + end_index_offset

#     # No converters
#     return None


def next_substitution(text: str, start_index: int) -> Optional[ParseChunk]:
    if peek_type(text, start_index) == ParseType.SUB:
        # Skip ':'
        sub_start_index = skip_text(text, start_index, SUB_SEP)
        sub_type = peek_type(text, sub_start_index)

        if sub_type == ParseType.WORD:
            # Single word
            sub_end_index = find_end_word(text, sub_start_index)
            if sub_end_index is None:
                raise ParseError(text)

            return ParseChunk(
                text=remove_escapes(text[start_index + 1 : sub_end_index]),
                start_index=start_index,
                end_index=sub_end_index,
                parse_type=ParseType.WORD,
            )

        if sub_type == ParseType.GROUP:
            # Multiple words
            # Skip '('
            sub_start_index = skip_text(text, sub_start_index, GROUP_START)
            sub_end_index = find_end_delimiter(
                text, sub_start_index, GROUP_START, GROUP_END
            )
            if sub_end_index is None:
                raise ParseError(text)

            return ParseChunk(
                text=remove_escapes(text[start_index + 1 : sub_end_index]),
                start_index=start_index,
                end_index=sub_end_index,
                parse_type=ParseType.GROUP,
                # converters=converters,
            )

        if sub_type == ParseType.QUOTE:
            # One or more quoted words
            # Skip '"'
            sub_start_index = skip_text(text, sub_start_index, QUOTE_START)
            sub_end_index = find_end_quote(
                text,
                sub_start_index,
            )
            if sub_end_index is None:
                raise ParseError(text)

            return ParseChunk(
                text=remove_escapes(text[start_index + 1 : sub_end_index]),
                start_index=start_index,
                end_index=sub_end_index,
                parse_type=ParseType.QUOTE,
                # converters=converters,
            )

        if sub_type in {ParseType.WHITESPACE, ParseType.END}:
            # Empty substitution (drop)
            return ParseChunk(
                text="",
                start_index=start_index,
                end_index=sub_start_index,
                parse_type=ParseType.WORD,
            )

        raise ParseError(text)

    # No substitution
    return None


def next_tag(text: str, start_index: int) -> Optional[ParseChunk]:
    if peek_type(text, start_index) == ParseType.TAG:
        # Skip '{'
        tag_start_index = skip_text(text, start_index, TAG_START)
        tag_end_index = find_end_delimiter(text, tag_start_index, TAG_START, TAG_END)
        if tag_end_index is None:
            raise ParseError(text)

        # Exclude {}
        tag_text = remove_delimiters(
            text[start_index:tag_end_index], TAG_START, TAG_END
        )
        tag_text = remove_escapes(tag_text)

        return ParseChunk(
            text=tag_text,
            start_index=start_index,
            end_index=tag_end_index,
            parse_type=ParseType.WORD,
        )

    # No tag
    return None


def next_chunk(text: str, start_index: int = 0) -> Optional[ParseChunk]:
    next_type = peek_type(text, start_index)

    if next_type in {ParseType.WORD, ParseType.QUOTE}:
        # Single word. May also have:
        # - A substitution, e.g. a:b or a:(b c)
        # - A tag, e.g. a{b}
        #
        # This "word" may also be a number or number range like 1..10

        if next_type == ParseType.QUOTE:
            word_start_index = skip_text(text, start_index, QUOTE_START)
            word_end_index = find_end_quote(text, word_start_index)

            if word_end_index is None:
                raise ParseError(text)

            # Exclude quotes
            word_text = remove_escapes(text[start_index:word_end_index])
            word_text = remove_delimiters(word_text, QUOTE_START, QUOTE_START)
        else:
            word_end_index = find_end_word(text, start_index)
            if word_end_index is None:
                raise ParseError(text)

            word_text = remove_escapes(text[start_index:word_end_index])

        # Substitution
        substitution = next_substitution(text, word_end_index)
        if substitution is not None:
            word_end_index = substitution.end_index

        # Tag
        # text = text.lstrip()  # Optional whitespace before tag
        # tag = next_tag(after_word_text, word_end_index)

        return ParseChunk(
            text=word_text,
            start_index=start_index,
            end_index=word_end_index,
            parse_type=ParseType.WORD,
            substitution=substitution,
            # tag=tag,
        )

    if next_type == ParseType.GROUP:
        # Skip '('
        group_start_index = skip_text(text, start_index, GROUP_START)
        group_end_index = find_end_delimiter(
            text, group_start_index, GROUP_START, GROUP_END
        )
        if group_end_index is None:
            raise ParseError(text)

        group_text = remove_escapes(text[start_index:group_end_index])

        # Substitution
        substitution = next_substitution(text, group_end_index)
        if substitution is not None:
            group_end_index = substitution.end_index

        # Tag
        tag = next_tag(text, group_end_index)
        if tag is not None:
            group_end_index = tag.end_index

        return ParseChunk(
            text=group_text,
            start_index=start_index,
            end_index=group_end_index,
            parse_type=ParseType.GROUP,
            substitution=substitution,
            tag=tag,
        )

    if next_type == ParseType.OPT:
        # Skip '['
        opt_start_index = skip_text(text, start_index, OPT_START)
        opt_end_index = find_end_delimiter(text, opt_start_index, OPT_START, OPT_END)
        if opt_end_index is None:
            raise ParseError(text)

        opt_text = remove_escapes(text[start_index:opt_end_index])

        # Substitution
        substitution = next_substitution(text, opt_end_index)
        if substitution is not None:
            opt_end_index = substitution.end_index

        # Tag
        tag = next_tag(text, opt_end_index)
        if tag is not None:
            opt_end_index = tag.end_index

        return ParseChunk(
            text=opt_text,
            start_index=start_index,
            end_index=opt_end_index,
            parse_type=ParseType.OPT,
            substitution=substitution,
            tag=tag,
        )

    if next_type == ParseType.SLOT:
        # Skip '$'
        slot_start_index = skip_text(text, start_index, SLOT_START)
        slot_end_index = find_end_word(text, slot_start_index)
        if slot_end_index is None:
            raise ParseError(text)

        return ParseChunk(
            text=remove_escapes(text[start_index:slot_end_index]),
            start_index=start_index,
            end_index=slot_end_index,
            parse_type=ParseType.SLOT,
        )

    if next_type == ParseType.RULE:
        # Skip '<'
        rule_start_index = skip_text(text, start_index, RULE_START)
        rule_end_index = find_end_delimiter(
            text, rule_start_index, RULE_START, RULE_END
        )
        if rule_end_index is None:
            raise ParseError(text)

        return ParseChunk(
            text=remove_escapes(text[start_index:rule_end_index]),
            start_index=start_index,
            end_index=rule_end_index,
            parse_type=ParseType.RULE,
        )

    if next_type == ParseType.ALT:
        return ParseChunk(
            text=text[start_index : start_index + 1],
            start_index=start_index,
            end_index=start_index + 1,
            parse_type=ParseType.ALT,
        )

    return None


def remove_delimiters(
    text: str, start_char: str, end_char: Optional[str] = None
) -> str:
    if end_char is None:
        assert len(text) > 1, "Text is too short"
        assert text[0] == start_char, "Wrong start char"
        return text[1:]

    assert len(text) > 2, "Text is too short"
    assert text[0] == start_char, "Wrong start char"
    assert text[-1] == end_char, "Wrong end char"
    return text[1:-1]


def remove_escapes(text: str) -> str:
    """Remove backslash escape sequences"""
    return re.sub(r"\\(.)", r"\1", text)


def escape_text(text: str) -> str:
    """Escape parentheses, etc."""
    return re.sub(r"([()\[\]{}<>])", r"\\\1", text)
