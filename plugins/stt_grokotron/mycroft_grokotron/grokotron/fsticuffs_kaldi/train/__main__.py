#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path

from .trainer import KaldiTrainer
from .utils import parse_ini_files

_LOGGER = logging.getLogger("train")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        "--ini-file",
        action="append",
        default=[],
        required=True,
        help="Path to sentences files (.ini) in the Rhasspy Template Language format",
    )
    parser.add_argument(
        "-i",
        "--input-dir",
        required=True,
        help="Directory with base dictionary, acoustic model, and g2p model",
    )
    parser.add_argument("-s", "--slots-dir", help="Directory with slot lists")
    parser.add_argument(
        "-o",
        "--output-dir",
        required=True,
        help="Directory to write generated Kaldi model",
    )
    parser.add_argument(
        "--kaldi-steps",
        help="Directory with Kaldi WSJ steps (default: kaldi_dir/egs/wsj/s5/steps)",
        required=True,
    )
    parser.add_argument(
        "--kaldi-utils",
        help="Directory with Kaldi WSJ utils (default: kaldi_dir/egs/wsj/s5/utils)",
        required=True,
    )
    parser.add_argument(
        "--number-language",
        default="en",
        help="Language used for Lingua Franca to convert numbers to words",
    )
    parser.add_argument(
        "--empty-word",
        default="<eps>",
        help="Word used for empty transitions (default: <eps>)",
    )
    parser.add_argument(
        "--silence-phone",
        default="SIL",
        help="Kaldi phone used for silence (default: SIL)",
    )
    parser.add_argument(
        "--silence-word",
        default="<sil>",
        help="Word used for silence (default: <sil>)",
    )
    parser.add_argument(
        "--spoken-noise-phone",
        default="SPN",
        help="Kaldi phone used for spoken noise (default: SPN)",
    )
    parser.add_argument(
        "--unknown-word",
        default="<unk>",
        help="Word used for unknown (default: <unk>)",
    )
    parser.add_argument(
        "--g2p-casing",
        default="keep",
        choices=("keep", "lower", "upper"),
        help="Casing applied to words before guessing their pronunciations (default: keep)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)

    # Convert to paths and verify
    args.output_dir = Path(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.slots_dir is not None:
        args.slots_dir = Path(args.slots_dir)

    args.input_dir = Path(args.input_dir)

    kaldi_steps_dir = Path(args.kaldi_steps)
    kaldi_utils_dir = Path(args.kaldi_utils)

    # -------------------------------------------------------------------------

    _LOGGER.info("Parsing sentence templates: %s", args.ini_file)
    intents = parse_ini_files(args.ini_file)

    trainer = KaldiTrainer(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        slots_dir=args.slots_dir,
        kaldi_steps=kaldi_steps_dir,
        kaldi_utils=kaldi_utils_dir,
    )

    if args.g2p_casing == "lower":
        trainer.g2p_transform = str.lower
    elif args.g2p_casing == "upper":
        trainer.g2p_transform = str.upper

    trainer.train(intents)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
