#!/usr/bin/env bash

if [ -z "$1" ]; then
    echo 'Usage: test.sh <wav>'
    exit 1
fi

wav_path="$(realpath "$1")"
this_dir="$( cd "$( dirname "$0" )" && pwd )"
kaldi_base="${this_dir}/kaldi"

PATH="${kaldi_base}/bin:${PATH}" \
online2-wav-nnet3-latgen-faster \
    --online=true \
    --do-endpointing=false \
    --config="${this_dir}/output/acoustic_model/online/conf/online.conf" \
    --max-active=7000 \
    --lattice-beam=8.0 \
    --acoustic-scale=1.0 \
    --beam=24.0 \
    --word-symbol-table="${this_dir}/output/graph/words.txt" \
    "${this_dir}/output/acoustic_model/model/final.mdl" \
    "${this_dir}/output/graph/HCLG.fst" \
    'ark:echo utt1 utt1|' \
    "scp:echo utt1 ${wav_path}|" \
    'ark:/dev/null'  2>&1 | \
    grep '^utt1 ' | \
    cut -d' ' -f2- | \
    PYTHONPATH="${this_dir}:${PYTHONPATH}" \
    python3 -m fsticuffs_kaldi.decode --flatten
