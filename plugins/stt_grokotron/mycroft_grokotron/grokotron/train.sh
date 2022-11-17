#!/usr/bin/env bash

if [ -z "$1" ]; then
    echo 'Usage: train.sh <ini>'
    exit 1
fi

ini_path="$(realpath "$1")"
this_dir="$( cd "$( dirname "$0" )" && pwd )"
kaldi_base="${this_dir}/kaldi"

PATH="${kaldi_base}/bin:${PATH}" \
PYTHONPATH="${this_dir}:${PYTHONPATH}" \
python3 -m fsticuffs_kaldi.train \
    --ini-file "${ini_path}" \
    --input-dir "${this_dir}/data/en-us" \
    --slots-dir "${this_dir}/slots" \
    --output-dir "${this_dir}/output" \
    --kaldi-steps "${kaldi_base}/egs/wsj/s5/steps" \
    --kaldi-utils "${kaldi_base}/egs/wsj/s5/utils" \
    --g2p-casing 'lower'
