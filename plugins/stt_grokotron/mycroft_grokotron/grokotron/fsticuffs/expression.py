import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import IO, ClassVar, List, Optional, Union

from .parser import (
    GROUP_END,
    GROUP_START,
    OPT_END,
    OPT_START,
    RULE_END,
    RULE_START,
    SLOT_START,
    ParseChunk,
    ParseType,
    escape_text,
    next_chunk,
    remove_delimiters,
    remove_escapes,
)

# 0..100, -100..100
NUMBER_RANGE_PATTERN = re.compile(r"^(-?[0-9]+)\.\.(-?[0-9]+),?(?P<step>[0-9]+)?$")
NUMBER_PATTERN = re.compile(r"^(-?[0-9]+)(?P<sub>:.+)?$")
PAIR_CHARS = (("(", ")"), ("[", "]"), ("{", "}"), ("<", ">"))


@dataclass
class Substitutable(ABC):
    """Indicates an expression may be replaced with some text."""

    # Replacement text
    substitution: Optional[Union[str, List[str]]] = None

    # Names of converters to apply after substitution
    converters: List[str] = field(default_factory=list)

    def serialize_substitution(self, output: IO[str]):
        """Write text representation to a string"""
        if self.substitution == "":
            output.write(":")
        elif self.substitution:
            output.write(":(")
            if isinstance(self.substitution, str):
                # String
                output.write(escape_text(self.substitution))
            else:
                # List of strings
                output.write(" ".join(map(escape_text, self.substitution)))

            for converter in self.converters:
                output.write("!")
                output.write(escape_text(converter))
            output.write(")")


@dataclass
class Tag(Substitutable):
    """{tag} attached to an expression."""

    # Name of tag (entity)
    tag_text: str = ""

    def serialize(self, output: IO[str]):
        """Write text representation to a string"""
        output.write("{")
        output.write(escape_text(self.tag_text))
        output.write("}")


@dataclass
class Taggable(ABC):
    """Indicates an expression may be tagged."""

    # Tag to be applied
    tag: Optional[Tag] = None


@dataclass
class Expression(ABC):
    """Base class for most JSGF types."""

    @abstractmethod
    def serialize(self, output: IO[str]):
        """Write text representation to a string"""


@dataclass
class Word(Substitutable, Taggable, Expression):
    """Single word/token."""

    WILDCARD: ClassVar[str] = "*"

    # Text representation expression
    text: str = ""

    @property
    def is_wildcard(self) -> bool:
        """True if this word is a wildcard"""
        return self.text == Word.WILDCARD

    def is_empty(self) -> bool:
        """True if this word is empty"""
        return not self.text

    def serialize(self, output: IO[str]):
        output.write(escape_text(self.text))

        if self.substitution is not None:
            self.serialize_substitution(output)

        if self.tag:
            self.tag.serialize(output)

    @staticmethod
    def empty() -> "Word":
        return Word(text="")


class SequenceType(str, Enum):
    """Type of a sequence. Optionals are alternatives with an empty option."""

    # Sequence of expressions
    GROUP = "group"

    # Expressions where only one will be recognized
    ALTERNATIVE = "alternative"


@dataclass
class Sequence(Substitutable, Taggable, Expression):
    """Ordered sequence of expressions. Supports groups, optionals, and alternatives."""

    # Items in the sequence
    items: List[Expression] = field(default_factory=list)

    # Group or alternative
    type: SequenceType = SequenceType.GROUP

    def serialize(self, output: IO[str]):
        """Write text representation to a string"""
        last_idx = len(self.items) - 1

        if self.type == SequenceType.ALTERNATIVE:
            is_optional = any(
                word.is_empty() for word in self.items if isinstance(word, Word)
            )
            if is_optional:
                output.write("[")
            else:
                output.write("(")

            for item_idx, item in enumerate(self.items):
                if isinstance(item, Word) and item.is_empty():
                    continue

                item.serialize(output)
                if item_idx < last_idx:
                    output.write(" | ")

            if is_optional:
                output.write("]")
            else:
                output.write(")")
        else:
            output.write("(")
            for item_idx, item in enumerate(self.items):
                item.serialize(output)
                if item_idx < last_idx:
                    output.write(" ")
            output.write(")")

        if self.substitution is not None:
            self.serialize_substitution(output)

        if self.tag:
            self.tag.serialize(output)


@dataclass
class RuleReference(Taggable, Expression):
    """Reference to a rule by <name> or <intent.name>."""

    # Name of referenced rule
    rule_name: str = ""

    # Intent name of referenced rule
    intent_name: Optional[str] = None

    @property
    def full_rule_name(self) -> str:
        """Get fully qualified rule name."""
        if self.intent_name:
            return f"{self.intent_name}.{self.rule_name}"

        return self.rule_name

    def serialize(self, output: IO[str]):
        """Write text representation to a string"""
        output.write("<")
        output.write(escape_text(self.full_rule_name))
        output.write(">")

        if self.tag:
            self.tag.serialize(output)


@dataclass
class SlotReference(Substitutable, Taggable, Expression):
    """Reference to a slot by $name."""

    # Name of referenced slot
    slot_name: str = ""

    def serialize(self, output: IO[str]):
        output.write("$")
        output.write(escape_text(self.slot_name))

        if self.substitution is not None:
            self.serialize_substitution(output)

        if self.tag:
            self.tag.serialize(output)


@dataclass
class Number(Substitutable, Taggable, Expression):
    """Single number."""

    number: Optional[int] = None

    def serialize(self, output: IO[str]):
        if self.number is None:
            # Can't serialize
            return

        output.write(str(self.number))

        if self.substitution is not None:
            self.serialize_substitution(output)

        if self.tag:
            self.tag.serialize(output)


@dataclass
class NumberRange(Substitutable, Taggable, Expression):
    """Number range of the form N..M where N<M."""

    lower_bound: Optional[int] = None
    upper_bound: Optional[int] = None
    step: int = 1

    def serialize(self, output: IO[str]):
        if (self.lower_bound is None) or (self.upper_bound is None):
            # Can't serialize
            return

        output.write(f"{self.lower_bound}..{self.upper_bound}")
        if self.step is not None:
            output.write(",{self.step}")

        if self.substitution is not None:
            self.serialize_substitution(output)

        if self.tag:
            self.tag.serialize(output)


@dataclass
class ParseMetadata:
    """Debug metadata for more helpful parsing errors."""

    file_name: str
    line_number: int
    intent_name: Optional[str] = None


@dataclass
class Sentence(Sequence):
    """Sequence representing a complete sentence template."""

    @staticmethod
    def parse(text: str, metadata: Optional[ParseMetadata] = None) -> "Sentence":
        """Parse a single sentence."""
        text = text.strip()

        # Wrap in a group
        text = f"({text})"

        chunk = next_chunk(text)
        assert chunk is not None
        assert chunk.parse_type == ParseType.GROUP
        assert chunk.start_index == 0
        assert chunk.end_index == len(text)

        seq = parse_expression(chunk, metadata=metadata)
        assert isinstance(seq, Sequence)

        # Unpack redundant sequence
        if len(seq.items) == 1:
            first_item = seq.items[0]
            if isinstance(first_item, Sequence):
                seq = first_item

        return Sentence(
            type=seq.type,
            items=seq.items,
            substitution=seq.substitution,
            tag=seq.tag,
            converters=seq.converters,
        )

    def serialize(self, output: IO[str]):
        """Write text representation to a string"""
        super().serialize(output)
        print("", file=output)


@dataclass
class Rule:
    """Named rule with body."""

    RULE_DEFINITION = re.compile(r"^(public)?\s*<([^>]+)>\s*=\s*([^;]+)(;)?$")

    rule_name: str
    rule_body: Sentence
    intent_name: Optional[str] = None


class ParseExpressionError(Exception):
    def __init__(self, chunk: ParseChunk, metadata: Optional[ParseMetadata] = None):
        super().__init__()
        self.chunk = chunk
        self.metadata = metadata

    def __str__(self) -> str:
        return f"Error in chunk {self.chunk} at {self.metadata}"


def parse_substitution(
    chunk: Optional[ParseChunk], metadata: Optional[ParseMetadata] = None
) -> Optional[Union[str, List[str]]]:
    if chunk is None:
        return None

    if chunk.parse_type == ParseType.WORD:
        # Single word
        return remove_escapes(chunk.text)

    if chunk.parse_type == ParseType.GROUP:
        # Multiple words
        # Remove '(' and  ')'
        sub_text = remove_delimiters(chunk.text, GROUP_START, GROUP_END)
        sub_text = remove_escapes(sub_text)
        words = sub_text.split()
        return words

    raise ParseExpressionError(chunk, metadata=metadata)


def parse_tag(
    chunk: Optional[ParseChunk], metadata: Optional[ParseMetadata] = None
) -> Optional[Tag]:
    if chunk is None:
        return None

    if chunk.parse_type == ParseType.WORD:
        tag_text = remove_escapes(chunk.text)

        return Tag(tag_text=tag_text)

    raise ParseExpressionError(chunk, metadata=metadata)


def ensure_alternative(seq: Sequence):
    if seq.type != SequenceType.ALTERNATIVE:
        seq.type = SequenceType.ALTERNATIVE

        # Collapse items into a single group
        seq.items = [
            Sequence(
                type=SequenceType.GROUP,
                items=seq.items,
            )
        ]


def parse_group_or_alt(
    seq_chunk: ParseChunk, metadata: Optional[ParseMetadata] = None
) -> Sequence:
    seq = Sequence(type=SequenceType.GROUP)
    if seq_chunk.parse_type == ParseType.GROUP:
        seq_text = remove_delimiters(seq_chunk.text, GROUP_START, GROUP_END)
    elif seq_chunk.parse_type == ParseType.OPT:
        seq_text = remove_delimiters(seq_chunk.text, OPT_START, OPT_END)
    else:
        raise ParseExpressionError(seq_chunk, metadata=metadata)

    item_chunk = next_chunk(seq_text)
    last_seq_text = seq_text

    while item_chunk is not None:
        if item_chunk.parse_type in {
            ParseType.WORD,
            ParseType.GROUP,
            ParseType.OPT,
            ParseType.SLOT,
            ParseType.RULE,
        }:
            item = parse_expression(item_chunk, metadata=metadata)

            if seq.type == SequenceType.ALTERNATIVE:
                # Add to most recent group
                if not seq.items:
                    seq.items.append(Sequence(type=SequenceType.GROUP))

                # Must be group or alternative
                last_item = seq.items[-1]
                if not isinstance(last_item, Sequence):
                    raise ParseExpressionError(seq_chunk, metadata=metadata)

                last_item.items.append(item)
            else:
                # Add to parent group
                seq.items.append(item)
        elif item_chunk.parse_type == ParseType.ALT:
            ensure_alternative(seq)

            # Begin new group
            seq.items.append(Sequence(type=SequenceType.GROUP))
        else:
            raise ParseExpressionError(seq_chunk, metadata=metadata)

        # Next chunk
        seq_text = seq_text[item_chunk.end_index :]
        seq_text = seq_text.lstrip()

        if seq_text == last_seq_text:
            raise ParseExpressionError(seq_chunk, metadata=metadata)

        item_chunk = next_chunk(seq_text)
        last_seq_text = seq_text

    return seq


def parse_expression(
    chunk: ParseChunk, metadata: Optional[ParseMetadata] = None
) -> Expression:
    if chunk.parse_type == ParseType.WORD:
        match = NUMBER_RANGE_PATTERN.match(chunk.text)
        if match:
            # N..M
            return NumberRange(
                lower_bound=int(match.group(1)),
                upper_bound=int(match.group(2)),
                step=int(match.group("step") or 1),
                substitution=parse_substitution(chunk.substitution, metadata=metadata),
                tag=parse_tag(chunk.tag, metadata=metadata),
            )

        match = NUMBER_PATTERN.match(chunk.text)
        if match:
            # N
            return Number(
                number=int(chunk.text),
                substitution=parse_substitution(chunk.substitution, metadata=metadata),
                tag=parse_tag(chunk.tag, metadata=metadata),
            )

        # Parse as a word instead
        return Word(
            text=chunk.text,
            substitution=parse_substitution(chunk.substitution, metadata=metadata),
            tag=parse_tag(chunk.tag, metadata=metadata),
        )

    if chunk.parse_type == ParseType.GROUP:
        seq = parse_group_or_alt(chunk, metadata=metadata)
        seq.substitution = parse_substitution(chunk.substitution, metadata=metadata)
        seq.tag = parse_tag(chunk.tag, metadata=metadata)
        return seq

    if chunk.parse_type == ParseType.OPT:
        seq = parse_group_or_alt(chunk, metadata=metadata)
        seq.substitution = parse_substitution(chunk.substitution, metadata=metadata)
        seq.tag = parse_tag(chunk.tag, metadata=metadata)
        ensure_alternative(seq)
        seq.items.append(Word(text=""))
        return seq

    if chunk.parse_type == ParseType.SLOT:
        return SlotReference(
            slot_name=remove_delimiters(chunk.text, SLOT_START),
            substitution=parse_substitution(chunk.substitution, metadata=metadata),
            tag=parse_tag(chunk.tag, metadata=metadata),
        )

    if chunk.parse_type == ParseType.RULE:
        rule_name = remove_delimiters(
            chunk.text,
            RULE_START,
            RULE_END,
        )

        intent_name = metadata.intent_name if metadata is not None else None
        if "." in rule_name:
            intent_name, rule_name = rule_name.split(".", maxsplit=1)

        return RuleReference(
            rule_name=rule_name,
            intent_name=intent_name,
            tag=parse_tag(chunk.tag, metadata=metadata),
        )

    raise ParseExpressionError(chunk, metadata=metadata)
