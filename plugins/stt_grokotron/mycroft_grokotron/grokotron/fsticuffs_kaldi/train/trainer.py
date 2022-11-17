import base64
import io
import logging
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Callable, Dict, Iterable, List, Optional, Set, Tuple, Union
from xml.sax.saxutils import quoteattr

from fsticuffs.expression import (
    Expression,
    Number,
    NumberRange,
    ParseMetadata,
    Rule,
    RuleReference,
    Sentence,
    Sequence,
    SequenceType,
    SlotReference,
    Substitutable,
    Taggable,
    Word,
)
from fsticuffs.grammar import Grammar
from fsticuffs.wordify import integer_to_words

from .vocabulary import SqliteDictionary, read_dictionary

_LOGGER = logging.getLogger("trainer")

_NONTERM_BEGIN = "#nonterm_begin"
_NONTERM_END = "#nonterm_end"
_DEFAULT_PROBABILITY = 0.0

_INITIALISM_PATTERN = re.compile(r"^\s*[A-Z]{2,}\s*$")
_INITIALISM_DOTS_PATTERN = re.compile(r"^(?:\s*[a-zA-Z]\.){1,}\s*$")


def _G2P_IDENTITY(s: str) -> str:
    return s


@dataclass
class KaldiTrainer:
    input_dir: Path
    output_dir: Path

    kaldi_steps: Path
    kaldi_utils: Path

    vocabulary: Set[str] = field(default_factory=set)
    output_words: Set[str] = field(default_factory=set)

    used_slots: Set[str] = field(default_factory=set)
    rules: Dict[str, Rule] = field(default_factory=dict)

    slots_dir: Optional[Path] = None

    eps: str = "<eps>"
    sil: str = "<sil>"
    sil_phone: str = "SIL"
    spn_phone: str = "SPN"
    unk: str = "<unk>"

    number_language: str = "en"
    g2p_transform: Callable[[str], str] = _G2P_IDENTITY

    _kaldi_env: Optional[Dict[str, str]] = None
    _slot_values: Dict[str, List[Sentence]] = field(default_factory=dict)

    def __post_init__(self):
        # Ensure paths are absolute because they may be written to Kaldi output
        # files during training.
        self.input_dir = self.input_dir.absolute()
        self.output_dir = self.output_dir.absolute()
        self.kaldi_steps = self.kaldi_steps.absolute()
        self.kaldi_utils = self.kaldi_utils.absolute()

    @property
    def input_model_dir(self) -> Path:
        return self.input_dir / "acoustic_model"

    @property
    def output_model_dir(self) -> Path:
        return self.output_dir / "acoustic_model"

    @property
    def lexicon_db(self) -> Path:
        return self.input_dir / "lexicon.db"

    @property
    def custom_words(self) -> Path:
        return self.output_dir / "custom_words.txt"

    @property
    def g2p_model(self) -> Path:
        return self.input_dir / "g2p.fst"

    @property
    def kaldi_env(self) -> Dict[str, str]:
        # Extend PATH
        if self._kaldi_env is None:
            self._kaldi_env = os.environ.copy()
            self._kaldi_env["PATH"] = (
                str(self.kaldi_utils)
                + ":"
                + str(self._kaldi_env)
                + ":"
                + self._kaldi_env["PATH"]
            )

        return self._kaldi_env

    @property
    def kaldi_data(self) -> Path:
        return self.output_model_dir / "data"

    @property
    def kaldi_lang(self) -> Path:
        return self.kaldi_data / "lang"

    @property
    def kaldi_data_local(self) -> Path:
        return self.kaldi_data / "local"

    @property
    def kaldi_dict_local(self) -> Path:
        return self.kaldi_data_local / "dict"

    @property
    def kaldi_lang_local(self) -> Path:
        return self.kaldi_data_local / "lang"

    # -------------------------------------------------------------------------

    def train(self, grammar: Grammar):
        intents = grammar.intents.values()

        _LOGGER.info("Creating output directory at %s", self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        _LOGGER.info("Copying acoustic model to output directory")
        self._copy_acoustic_model()

        for intent in intents:
            _LOGGER.info("Preprocessing intent: %s", intent.name)
            for rule in intent.rules.values():
                self._preprocess_expression(intent.name, rule)

            for sentence in intent.sentences:
                self._preprocess_expression(intent.name, sentence)

        _LOGGER.debug("Used slots: %s", self.used_slots)

        # for slot_name in self.used_slots:
        #     _LOGGER.info("Converting slot to FST: %s", slot_name)
        #     slot_output_path = self.get_output_slot_path(slot_name)
        #     self._write_nonterminal_slot_fst(
        #         slot_name, self.get_slot_values(slot_output_path)
        #     )

        # for intent in intents:
        #     _LOGGER.info("Converting intent to FST: %s", intent.name)
        #     self._write_nonterminal_intent_fst(
        #         intent.name,
        #         [s for s in intent.sentences if isinstance(s, Sentence)],
        #     )

        # self._write_outer_fst(grammar.intents.keys())
        fst_path = self.output_dir / "graph.fst.txt"
        with open(fst_path, "w", encoding="utf-8") as fst_file:
            new_state = FstState()
            graph_start_state = new_state()
            graph_end_state = new_state()

            for intent in grammar.intents.values():
                intent_start_state = new_state()
                print(
                    graph_start_state,
                    intent_start_state,
                    self.eps,
                    self.make_output_tag("intent", name=intent.name),
                    _DEFAULT_PROBABILITY,
                    file=fst_file,
                )

                for sentence in intent.sentences:
                    intent_end_state = self._expression_to_fst(
                        intent.name,
                        sentence,
                        fst_file,
                        intent_start_state,
                        new_state,
                    )
                    print(
                        intent_end_state,
                        graph_end_state,
                        self.eps,
                        self.make_output_tag("/intent"),
                        _DEFAULT_PROBABILITY,
                        file=fst_file,
                    )

            graph_final_state = new_state()
            print(
                graph_end_state,
                graph_final_state,
                self.eps,
                self.eps,
                _DEFAULT_PROBABILITY,
                file=fst_file,
            )
            print(graph_final_state, file=fst_file)

        self.setup_kaldi_environment()
        self.prepare_lang(grammar)
        self.compile_subgraph(
            self.output_dir / "graph.fst.txt",
            self.kaldi_lang,
            self.output_dir / "graph",
        )

        self.train_prepare_online_decoding()

    # -------------------------------------------------------------------------

    def number_to_words(self, number: int) -> List[str]:
        return integer_to_words(number, language=self.number_language)

    def guess_phonemes(
        self, words: Iterable[str], num_guesses: int = 1
    ) -> Iterable[Tuple[str, str]]:
        """Guess pronunciations with phonetisaurus"""
        word_map: Dict[str, str] = {}
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w+") as words_file:
            for word in words:
                transformed_word = self.g2p_transform(word)
                word_map[transformed_word] = word
                print(transformed_word, file=words_file)

            words_file.seek(0)
            with subprocess.Popen(
                [
                    "phonetisaurus-apply",
                    "--model",
                    str(self.g2p_model),
                    "--nbest",
                    str(num_guesses),
                    "--word_list",
                    words_file.name,
                ],
                universal_newlines=True,
                stdout=subprocess.PIPE,
            ) as proc:
                assert proc.stdout is not None

                # Output is:
                # word P1 P2 P3...
                # word P1 P2 P3...
                for line in proc.stdout:
                    line = line.strip()
                    if not line:
                        continue

                    transformed_word, phonemes_str = line.split(maxsplit=1)
                    word = word_map.get(transformed_word, transformed_word)
                    yield word, phonemes_str

    def get_input_slot_path(self, slot_name: str) -> Path:
        assert (
            self.slots_dir is not None
        ), f"Values for slot {slot_name} was requested, but slots directory was not provided"

        return self.slots_dir / slot_name

    def get_output_slot_path(self, slot_name: str) -> Path:
        return self.output_dir / "slots" / slot_name / "values.txt"

    def get_slot_values(self, slot_path: Path) -> Iterable[Sentence]:
        slot_path_str = str(slot_path)
        slot_values = self._slot_values.get(slot_path_str)

        if slot_values is None:
            slot_values = []
            self._slot_values[slot_path_str] = slot_values

            metadata = ParseMetadata(file_name=slot_path_str, line_number=0)
            with open(slot_path, "r", encoding="utf-8") as slot_file:
                for line_index, line in enumerate(slot_file):
                    line = line.strip()
                    if (not line) or line.startswith("#"):
                        # Skip blank lines and comments
                        continue

                    # For error messages
                    metadata.line_number = line_index + 1

                    # yield Sentence.parse(line, metadata=metadata)
                    slot_values.append(Sentence.parse(line, metadata=metadata))

        return slot_values

    # -------------------------------------------------------------------------
    # Preprocess
    # -------------------------------------------------------------------------

    def _preprocess_expression(
        self, intent_name: str, expression: Union[Rule, Expression]
    ):
        # TODO: Casing
        if isinstance(expression, Sequence):
            # Group, optional, or alternative
            seq: Sequence = expression
            for item in seq.items:
                # Descend into sequence item
                self._preprocess_expression(intent_name, item)
        elif isinstance(expression, SlotReference):
            # $slot
            slot_ref: SlotReference = expression
            if slot_ref.slot_name in self.used_slots:
                return

            self.used_slots.add(slot_ref.slot_name)

            # Descend into slot values
            slot_input_path = self.get_input_slot_path(slot_ref.slot_name)
            for slot_value in self.get_slot_values(slot_input_path):
                self._preprocess_expression(intent_name, slot_value)

            # Copy to output directory
            slot_output_path = self.get_output_slot_path(slot_ref.slot_name)
            slot_output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(slot_input_path, slot_output_path)
        elif isinstance(expression, RuleReference):
            # <rule>
            rule_ref: RuleReference = expression

            if rule_ref.intent_name:
                full_rule_name = f"{rule_ref.intent_name}.{rule_ref.rule_name}"
            else:
                full_rule_name = f"{intent_name}.{rule_ref.rule_name}"

            # Rule references are pseudo-slots under rhasspy/rule
            slot_name = f"rhasspy/rule,{full_rule_name}"
            self.used_slots.add(slot_name)
        elif isinstance(expression, Rule):
            # rule = body
            rule: Rule = expression
            full_rule_name = f"{intent_name}.{rule.rule_name}"

            if full_rule_name in self.rules:
                return

            self.rules[full_rule_name] = rule
            slot_name = f"rhasspy/rule,{full_rule_name}"
            self.used_slots.add(slot_name)

            # Descend into rule body
            self._preprocess_expression(intent_name, rule.rule_body)

            # Copy to output directory
            slot_output_path = self.get_output_slot_path(slot_name)
            slot_output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(slot_output_path, "w", encoding="utf-8") as slot_output_file:
                rule.rule_body.serialize(slot_output_file)
        elif isinstance(expression, NumberRange):
            number_range: NumberRange = expression
            assert (
                self.number_language is not None
            ), "Number language required to expand number ranges"
            assert (
                number_range.lower_bound is not None
            ), f"No lower bound: {number_range}"
            assert (
                number_range.upper_bound is not None
            ), f"No upper bound: {number_range}"

            # Number ranges are treated as pseudo-slots under rhasspy/number
            step = 1 if number_range.step is None else number_range.step
            slot_name = ",".join(
                (
                    "rhasspy/number",
                    str(number_range.lower_bound),
                    str(number_range.upper_bound),
                    str(step),
                    self.number_language,
                )
            )

            if slot_name in self.used_slots:
                return

            self.used_slots.add(slot_name)

            # Expand range
            slot_output_path = self.get_output_slot_path(slot_name)
            slot_output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(slot_output_path, "w", encoding="utf-8") as slot_output_file:
                for number_value in range(
                    number_range.lower_bound,
                    number_range.upper_bound + 1,
                    step,
                ):
                    number_sentence = Sentence(
                        items=[
                            Word(text=word_text)
                            for word_text in self.number_to_words(number_value)
                        ],
                        substitution=str(number_value),
                        # converters=["int"],
                    )
                    number_sentence.serialize(slot_output_file)

                    # Descend into sentence
                    self._preprocess_expression(intent_name, number_sentence)

    # -------------------------------------------------------------------------
    # FST conversion
    # -------------------------------------------------------------------------

    # def _write_nonterminal_slot_fst(
    #     self, slot_name: str, sentences: Iterable[Sentence]
    # ):
    #     fst_path = self.output_dir / "slots" / slot_name / "nonterminal_fst.txt"
    #     fst_path.parent.mkdir(parents=True, exist_ok=True)

    #     with open(fst_path, "w", encoding="utf-8") as fst_file:
    #         # Enter/exit nonterminal
    #         new_state = FstState()
    #         start_state = new_state()
    #         begin_words = new_state()

    #         # <slot name="...">
    #         print(
    #             start_state,
    #             begin_words,
    #             _NONTERM_BEGIN,
    #             self.eps,
    #             # self.make_output_tag("slot", name=slot_name),
    #             _DEFAULT_PROBABILITY,
    #             file=fst_file,
    #         )

    #         end_words = new_state()
    #         for sentence in sentences:
    #             sentence_state = self._expression_to_fst(
    #                 None,
    #                 sentence,
    #                 fst_file,
    #                 source_state=begin_words,
    #                 new_state=new_state,
    #             )
    #             print(
    #                 sentence_state,
    #                 end_words,
    #                 self.eps,
    #                 self.eps,
    #                 _DEFAULT_PROBABILITY,
    #                 file=fst_file,
    #             )

    #         # </slot>
    #         final_state = new_state()
    #         print(
    #             end_words,
    #             final_state,
    #             _NONTERM_END,
    #             self.eps,
    #             # self.make_output_tag("/slot"),
    #             _DEFAULT_PROBABILITY,
    #             file=fst_file,
    #         )

    #         # Final state
    #         print(final_state, file=fst_file)

    # def _write_nonterminal_intent_fst(
    #     self, intent_name: str, sentences: Iterable[Sentence]
    # ):
    #     fst_path = self.output_dir / "intents" / intent_name / "nonterminal_fst.txt"
    #     fst_path.parent.mkdir(parents=True, exist_ok=True)

    #     with open(fst_path, "w", encoding="utf-8") as fst_file:
    #         # Enter/exit nonterminal
    #         new_state = FstState()
    #         start_state = new_state()
    #         begin_words = new_state()
    #         end_words = new_state()

    #         # <intent name="...">
    #         print(
    #             start_state,
    #             begin_words,
    #             _NONTERM_BEGIN,
    #             # self.eps,
    #             self.make_output_tag("intent", name=intent_name),
    #             _DEFAULT_PROBABILITY,
    #             file=fst_file,
    #         )

    #         for sentence in sentences:
    #             sentence_state = self._expression_to_fst(
    #                 intent_name,
    #                 sentence,
    #                 fst_file,
    #                 source_state=begin_words,
    #                 new_state=new_state,
    #             )
    #             print(
    #                 sentence_state,
    #                 end_words,
    #                 self.eps,
    #                 self.eps,
    #                 _DEFAULT_PROBABILITY,
    #                 file=fst_file,
    #             )

    #         # </intent>
    #         end_intent = new_state()
    #         print(
    #             end_words,
    #             end_intent,
    #             self.eps,
    #             # self.eps,
    #             self.make_output_tag("/intent"),
    #             _DEFAULT_PROBABILITY,
    #             file=fst_file,
    #         )

    #         final_state = new_state()
    #         print(
    #             end_intent,
    #             final_state,
    #             _NONTERM_END,
    #             self.eps,
    #             _DEFAULT_PROBABILITY,
    #             file=fst_file,
    #         )

    #         # Final state
    #         print(final_state, file=fst_file)

    def _expression_to_fst(
        self,
        intent_name: Optional[str],
        expression: Expression,
        fst_file: IO[str],
        source_state: int,
        new_state: Callable[[], int],
    ) -> int:
        has_tag = False
        has_sub = False

        if isinstance(expression, Taggable) and (expression.tag is not None):
            # <tag name="...">
            has_tag = True
            next_state = new_state()
            print(
                source_state,
                next_state,
                self.eps,
                self.make_output_tag("tag", name=expression.tag.tag_text),
                _DEFAULT_PROBABILITY,
                file=fst_file,
            )
            source_state = next_state

        if isinstance(expression, Substitutable) and (
            expression.substitution is not None
        ):
            # <sub value="...">
            has_sub = True
            next_state = new_state()
            sub_value = (
                expression.substitution
                if isinstance(expression.substitution, str)
                else " ".join(expression.substitution)
            )
            print(
                source_state,
                next_state,
                self.eps,
                self.make_output_tag("sub", value=sub_value),
                _DEFAULT_PROBABILITY,
                file=fst_file,
            )
            source_state = next_state

        if isinstance(expression, Word):
            word: Word = expression
            if word.text:
                word_text = word.text
                self.vocabulary.add(word.text)
            else:
                word_text = self.eps

            # Input word
            next_state = new_state()
            print(
                source_state,
                next_state,
                word_text,
                word_text,
                _DEFAULT_PROBABILITY,
                file=fst_file,
            )
            source_state = next_state
        elif isinstance(expression, Sequence):
            seq: Sequence = expression

            if seq.type == SequenceType.ALTERNATIVE:
                # Optional or alternative
                exit_state = new_state()
                for item in seq.items:
                    next_state = self._expression_to_fst(
                        intent_name,
                        item,
                        fst_file,
                        source_state,
                        new_state,
                    )
                    print(
                        next_state,
                        exit_state,
                        self.eps,
                        self.eps,
                        _DEFAULT_PROBABILITY,
                        file=fst_file,
                    )

                source_state = exit_state
            else:
                # Group
                for item in seq.items:
                    source_state = self._expression_to_fst(
                        intent_name,
                        item,
                        fst_file,
                        source_state,
                        new_state,
                    )
        elif isinstance(expression, SlotReference):
            # Assume slot has already been converted to a nonterminal FST
            slot_ref: SlotReference = expression
            # slot_nonterm = f"#nonterm:slots/{slot_ref.slot_name}"
            # next_state = new_state()
            # print(
            #     source_state,
            #     next_state,
            #     slot_nonterm,
            #     self.eps,
            #     _DEFAULT_PROBABILITY,
            #     file=fst_file,
            # )
            # source_state = next_state
            slot_path = self.get_output_slot_path(slot_ref.slot_name)
            slot_enter_state = new_state()
            print(
                source_state,
                slot_enter_state,
                self.eps,
                self.make_output_tag("slot", name=slot_ref.slot_name),
                _DEFAULT_PROBABILITY,
                file=fst_file,
            )

            slot_exit_state = new_state()
            for value in self.get_slot_values(slot_path):
                value_state = self._expression_to_fst(
                    intent_name,
                    value,
                    fst_file,
                    slot_enter_state,
                    new_state,
                )
                print(
                    value_state,
                    slot_exit_state,
                    self.eps,
                    self.eps,
                    _DEFAULT_PROBABILITY,
                    file=fst_file,
                )

            slot_tag_state = new_state()
            print(
                slot_exit_state,
                slot_tag_state,
                self.eps,
                self.make_output_tag("/slot"),
                _DEFAULT_PROBABILITY,
                file=fst_file,
            )
            source_state = slot_tag_state
        elif isinstance(expression, RuleReference):
            # Assume rule has already been converted to a nonterminal FST (pseudo-slot)
            rule_ref: RuleReference = expression
            if rule_ref.intent_name:
                full_rule_name = f"{rule_ref.intent_name}.{rule_ref.rule_name}"
            else:
                assert intent_name, f"Unresolved rule reference: {rule_ref}"
                full_rule_name = f"{intent_name}.{rule_ref.rule_name}"

            slot_name = f"rhasspy/rule,{full_rule_name}"
            source_state = self._expression_to_fst(
                intent_name,
                SlotReference(slot_name=slot_name),
                fst_file,
                source_state,
                new_state,
            )

            # slot_nonterm = f"#nonterm:slots/{slot_name}"
            # next_state = new_state()
            # print(
            #     source_state,
            #     next_state,
            #     slot_nonterm,
            #     self.eps,
            #     _DEFAULT_PROBABILITY,
            #     file=fst_file,
            # )
            # source_state = next_state
        elif isinstance(expression, NumberRange):
            number_range: NumberRange = expression
            assert (
                self.number_language is not None
            ), "Number language required to expand number ranges"
            assert (
                number_range.lower_bound is not None
            ), f"No lower bound: {number_range}"
            assert (
                number_range.upper_bound is not None
            ), f"No upper bound: {number_range}"

            # Number ranges are treated as pseudo-slots under rhasspy/number
            step = 1 if number_range.step is None else number_range.step
            slot_name = ",".join(
                (
                    "rhasspy/number",
                    str(number_range.lower_bound),
                    str(number_range.upper_bound),
                    str(step),
                    self.number_language,
                )
            )
            source_state = self._expression_to_fst(
                intent_name,
                SlotReference(slot_name=slot_name),
                fst_file,
                source_state,
                new_state,
            )
            # slot_nonterm = f"#nonterm:slots/{slot_name}"

            # next_state = new_state()
            # print(
            #     source_state,
            #     next_state,
            #     slot_nonterm,
            #     self.eps,
            #     _DEFAULT_PROBABILITY,
            #     file=fst_file,
            # )
            # source_state = next_state
        elif isinstance(expression, Number):
            number: Number = expression
            assert number.number is not None, f"Missing number: {number}"

            number_words = self.number_to_words(number.number)
            output_word = str(number.number)
            last_word_idx = len(number_words) - 1

            for word_idx, word_text in enumerate(number_words):
                next_state = new_state()
                print(
                    source_state,
                    next_state,
                    word_text,
                    output_word if word_idx == last_word_idx else self.eps,
                    _DEFAULT_PROBABILITY,
                    file=fst_file,
                )
                source_state = next_state
                self.vocabulary.add(word_text)

            self.output_words.add(output_word)
        else:
            assert False, f"Unsupported expression: {expression}"

        if has_sub:
            # </sub>
            next_state = new_state()
            print(
                source_state,
                next_state,
                self.eps,
                self.make_output_tag("/sub"),
                _DEFAULT_PROBABILITY,
                file=fst_file,
            )
            source_state = next_state

        if has_tag:
            # </tag>
            next_state = new_state()
            print(
                source_state,
                next_state,
                self.eps,
                self.make_output_tag("/tag"),
                _DEFAULT_PROBABILITY,
                file=fst_file,
            )
            source_state = next_state

        return source_state

    def _write_outer_fst(self, intent_names: Iterable[str]):
        fst_path = self.output_dir / "graph.fst.txt"
        with open(fst_path, "w", encoding="utf-8") as fst_file:
            graph_start_state = 0
            graph_final_state = 1

            for intent_name in intent_names:
                print(
                    graph_start_state,
                    graph_final_state,
                    f"#nonterm:intents/{intent_name}",
                    self.eps,
                    _DEFAULT_PROBABILITY,
                    file=fst_file,
                )

            print(graph_final_state, file=fst_file)

    def make_output_tag(self, tag_name: str, **attributes) -> str:
        # tag_bytes = ET.tostring(ET.Element(tag_name, attrib=attributes))
        with io.StringIO() as tag_io:
            print("<", tag_name, sep="", end="", file=tag_io)
            for key, value in attributes.items():
                print(" ", key, "=", quoteattr(value), sep="", end="", file=tag_io)
            print(">", end="", file=tag_io)
            tag_str = tag_io.getvalue()
            tag_bytes = tag_str.encode()

        b64_bytes = base64.b64encode(tag_bytes)
        output_word = "__" + b64_bytes.decode().strip()
        self.output_words.add(output_word)

        return output_word

    # -------------------------------------------------------------------------
    # Kaldi
    # -------------------------------------------------------------------------

    def setup_kaldi_environment(self):
        # Create empty path.sh
        path_sh = self.output_model_dir / "path.sh"
        if not path_sh.is_file():
            path_sh.write_text("")

        # Delete existing data/graph
        if self.kaldi_data.exists():
            shutil.rmtree(self.kaldi_data)

        # Create utils link
        model_utils_link = self.output_model_dir / "utils"

        if not model_utils_link.is_dir():
            try:
                # Can't use missing_ok in 3.6
                model_utils_link.unlink()
            except Exception:
                pass

            model_utils_link.symlink_to(self.kaldi_utils, target_is_directory=True)

    def prepare_lang(self, grammar: Grammar):
        _LOGGER.debug("Generating lexicon")
        self.kaldi_dict_local.mkdir(parents=True, exist_ok=True)

        # Copy phones
        phones_dir = self.input_model_dir / "phones"
        for phone_file in phones_dir.glob("*.txt"):
            shutil.copy(phone_file, self.kaldi_dict_local / phone_file.name)

        # Connect to lexicon database
        base_lexicon = SqliteDictionary(self.lexicon_db)

        # Write dictionary
        lexicon_path = self.kaldi_dict_local / "lexicon.txt"
        custom_words: Set[str] = set()
        missing_words: Set[str] = set()
        with open(lexicon_path, "w", encoding="utf-8") as lexicon_file:
            # Use custom words first
            if self.custom_words.exists():
                _LOGGER.info("Adding custom words from %s", self.custom_words)
                with open(
                    self.custom_words, "r", encoding="utf-8"
                ) as custom_words_file:
                    custom_dict = read_dictionary(custom_words_file)
                    for word, word_phonemes in custom_dict.items():
                        print(word, *word_phonemes, file=lexicon_file)
                        custom_words.add(word)

            # Load pronunciations from base lexicon
            for word_text in self.vocabulary:
                # Try exact match and lower case
                word_prons = base_lexicon.get_pronunciations(
                    word_text
                ) or base_lexicon.get_pronunciations(word_text.lower())

                if word_prons:
                    for word_pron in word_prons:
                        print(word_text, *word_pron.phonemes, file=lexicon_file)
                else:
                    # Check if this is an initialism
                    letters: Optional[List[str]] = None
                    if _INITIALISM_PATTERN.match(word_text):
                        letters = list(word_text)
                    elif _INITIALISM_DOTS_PATTERN.match(word_text):
                        letters = list(word_text.replace(".", ""))

                    if letters:
                        # Handle as initialism
                        _LOGGER.debug("Detected initialism: %s", word_text)
                        letter_phonemes = []
                        for letter in letters:
                            letter_pron = (
                                base_lexicon.get_pronunciations(letter, role="letter")
                                or base_lexicon.get_pronunciations(
                                    letter.lower(), role="letter"
                                )
                                or base_lexicon.get_pronunciations(letter)
                                or base_lexicon.get_pronunciations(letter.lower())
                            )

                            assert (
                                letter_pron
                            ), f"Missing pronunciation for letter '{letter}' in base lexicon"

                            letter_phonemes.extend(letter_pron[0].phonemes)

                        print(word_text, *letter_phonemes, file=lexicon_file)
                    elif word_text not in custom_words:
                        # Handle as missing word
                        missing_words.add(word_text)

            if missing_words:
                _LOGGER.warning(
                    "Guessing pronunciations for %s word(s)", len(missing_words)
                )
                failed_words = set(missing_words)
                with open(
                    self.output_dir / "missing_words.txt", "w", encoding="utf-8"
                ) as missing_words_file:
                    for word, word_phonemes_str in self.guess_phonemes(missing_words):
                        print(word, word_phonemes_str, file=lexicon_file)
                        print(word, word_phonemes_str, file=missing_words_file)
                        failed_words.discard(word)

                assert (
                    not failed_words
                ), f"Failed to guess pronunciations for {len(failed_words)} word(s): {failed_words}"

            # Write output words
            for word_text in self.output_words:
                print(word_text, self.sil_phone, file=lexicon_file)

            # <unk> SPN
            print(self.unk, self.spn_phone, file=lexicon_file)

        # Write nonterminals
        # _LOGGER.debug("%s non-terminal(s)", len(self.used_slots))
        # nonterminals_path = self.kaldi_dict_local / "nonterminals.txt"
        # with open(nonterminals_path, "w", encoding="utf-8") as nonterminals_file:
        #     for slot_name in self.used_slots:
        #         print(f"#nonterm:slots/{slot_name}", file=nonterminals_file)

        #     for intent_name in grammar.intents.keys():
        #         print(f"#nonterm:intents/{intent_name}", file=nonterminals_file)

        self.run_kaldi_command(
            [
                "bash",
                str(self.kaldi_utils / "prepare_lang.sh"),
                str(self.kaldi_dict_local),
                self.unk,
                str(self.kaldi_lang_local),
                str(self.kaldi_lang),
            ]
        )

    # def mkgraphs(self):
    #     graph_dir = self.output_dir / "graph"
    #     self.compile_subgraph(
    #         self.output_dir / "graph.fst.txt",
    #         self.kaldi_lang,
    #         graph_dir,
    #     )

    #     nonterm_offset: Optional[int] = None
    #     nonterm_graph_dirs: Dict[int, Path] = {}

    #     with open(self.kaldi_lang / "phones.txt", "r", encoding="utf-8") as phones_file:
    #         for line in phones_file:
    #             line = line.strip()
    #             if not line:
    #                 continue

    #             phone, phone_num = line.split(maxsplit=1)
    #             if phone == "#nonterm_bos":
    #                 nonterm_offset = int(phone_num)
    #             elif phone.startswith("#nonterm:"):
    #                 nonterm_name = phone.split(":", maxsplit=1)[-1]
    #                 nonterm_dir = self.output_dir / nonterm_name

    #                 nonterm_lang_dir = nonterm_dir / "lang"
    #                 if nonterm_lang_dir.is_dir():
    #                     shutil.rmtree(nonterm_lang_dir)

    #                 shutil.copytree(self.kaldi_lang, nonterm_lang_dir)
    #                 nonterm_graph_dir = nonterm_dir / "graph"
    #                 nonterm_fst = nonterm_dir / "nonterminal_fst.txt"
    #                 assert nonterm_fst.exists(), nonterm_fst

    #                 self.compile_subgraph(
    #                     nonterm_fst,
    #                     nonterm_lang_dir,
    #                     nonterm_graph_dir,
    #                 )

    #                 nonterm_graph_dirs[int(phone_num)] = nonterm_graph_dir

    #     assert nonterm_offset is not None

    #     make_grammar = [
    #         "make-grammar-fst",
    #         f"--nonterm-phones-offset={nonterm_offset}",
    #         str(graph_dir / "HCLG.fst"),
    #     ]

    #     for nonterm_int, nonterm_graph_dir in nonterm_graph_dirs.items():
    #         make_grammar.extend([str(nonterm_int), str(nonterm_graph_dir / "HCLG.fst")])

    #     make_grammar.append(str(self.output_dir / "HCLG.fst"))
    #     self.run_kaldi_command(make_grammar)

    def compile_subgraph(
        self,
        fst_text_path: Path,
        lang_dir: Path,
        graph_dir: Path,
    ):
        words_text = self.kaldi_lang / "words.txt"
        self.run_kaldi_command(
            [
                "fstcompile",
                f"--isymbols={words_text}",
                f"--osymbols={words_text}",
                "--keep_isymbols=false",
                "--keep_osymbols=false",
                str(fst_text_path),
                str(lang_dir / "G.fst.unsorted"),
            ]
        )
        self.run_kaldi_command(
            [
                "fstarcsort",
                "--sort_type=ilabel",
                str(lang_dir / "G.fst.unsorted"),
                str(lang_dir / "G.fst"),
            ]
        )

        self.run_kaldi_command(
            [
                "bash",
                str(self.kaldi_utils / "mkgraph.sh"),
                "--self-loop-scale",
                "1.0",
                str(lang_dir),
                str(self.output_model_dir / "model"),
                str(graph_dir),
            ]
        )

    def train_prepare_online_decoding(self):
        """Prepare model for online decoding."""
        extractor_dir = self.output_model_dir / "extractor"
        if extractor_dir.is_dir():
            # Generate online.conf
            mfcc_conf = self.output_model_dir / "conf" / "mfcc_hires.conf"
            self.run_kaldi_command(
                [
                    "bash",
                    str(
                        self.kaldi_steps
                        / "online"
                        / "nnet3"
                        / "prepare_online_decoding.sh"
                    ),
                    "--mfcc-config",
                    str(mfcc_conf),
                    str(self.kaldi_lang),
                    str(extractor_dir),
                    str(self.output_model_dir / "model"),
                    str(self.output_model_dir / "online"),
                ]
            )

    def run_kaldi_command(self, command: List[str]):
        _LOGGER.debug(command)
        subprocess.check_call(command, cwd=self.output_model_dir, env=self.kaldi_env)

    def _copy_acoustic_model(self):
        """
        Copy Kaldi acoustic model to output directory.

        This needs to be done because the training process will write hard-coded
        paths in the various .conf files.
        """
        if self.output_model_dir.is_dir():
            shutil.rmtree(self.output_model_dir)

        shutil.copytree(self.input_model_dir, self.output_model_dir)


@dataclass
class FstState:
    _next_state: int = 0

    def __call__(self) -> int:
        next_state = self._next_state
        self._next_state += 1
        return next_state
