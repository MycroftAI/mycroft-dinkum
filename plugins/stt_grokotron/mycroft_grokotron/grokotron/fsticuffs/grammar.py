import configparser
import io
from dataclasses import dataclass, field
from typing import IO, Dict, List

from .expression import ParseMetadata, Rule, Sentence


@dataclass
class Intent:
    name: str
    sentences: List[Sentence] = field(default_factory=list)
    rules: Dict[str, Rule] = field(default_factory=dict)


@dataclass
class Grammar:
    intents: Dict[str, Intent] = field(default_factory=dict)
    rules: Dict[str, Rule] = field(default_factory=dict)

    @staticmethod
    def parse_file(ini_file: IO[str], file_name: str = "<unknown>") -> "Grammar":
        grammar = Grammar()

        # Create ini parser
        config = configparser.ConfigParser(
            allow_no_value=True, strict=False, delimiters=["="]
        )

        # case sensitive
        config.optionxform = str  # type: ignore
        config.read_file(ini_file)

        # Parse each section (intent)
        metadata = ParseMetadata(file_name=file_name, line_number=1)
        for sec_name in config.sections():
            # Section header
            metadata.line_number += 1

            intent = Intent(name=sec_name)
            grammar.intents[intent.name] = intent
            metadata.intent_name = intent.name

            # Processs settings (sentences/rules)
            for k, v in config[sec_name].items():
                if v is None:
                    # Collect non-valued keys as sentences
                    sentence = k.strip()

                    # Fix \[ escape sequence
                    sentence = sentence.replace("\\[", "[")

                    intent.sentences.append(Sentence.parse(sentence, metadata=metadata))
                else:
                    rule_name = k.strip()
                    sentence = v.strip()
                    rule = Rule(
                        rule_name=rule_name,
                        intent_name=intent.name,
                        rule_body=Sentence.parse(sentence, metadata=metadata),
                    )
                    intent.rules[rule.rule_name] = rule

                    full_rule_name = f"{intent.name}.{rule.rule_name}"
                    grammar.rules[full_rule_name] = rule

                # Sentence
                metadata.line_number += 1

            # Blank line
            metadata.line_number += 1

        return grammar

    @staticmethod
    def parse_string(ini_text: str, file_name: str = "<string>") -> "Grammar":
        with io.StringIO(ini_text) as ini_file:
            return Grammar.parse_file(ini_file)
