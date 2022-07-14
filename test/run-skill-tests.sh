#!/usr/bin/env bash
# Copyright 2022 Mycroft AI Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# -----------------------------------------------------------------------------
#
# Runs a skill's Voight Kampff.
#
set -eo pipefail

function usage {
    echo "Usage: $(basename "$0") skill_directory ..."
}

if [ -z "$1" ]; then
    usage;
    exit 1;
fi

skill_dir="$1"
skill_id="$(basename "${skill_dir}")"
skill_features_dir="${skill_dir}/test/behave"

shift 1

if [ ! -d "${skill_features_dir}" ]; then
    echo "Missing behave tests for skill (expected in ${skill_features_dir})";
    exit 1;
fi

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"

# Directory of repo
base_dir="$(realpath "${this_dir}/../")"

: "${XDG_CONFIG_HOME:=${HOME}/.config}"

# User-writable directory where virtual environment is stored
test_config_dir="${XDG_CONFIG_HOME}/mycroft/test"
venv_dir="${test_config_dir}/.venv"

if [ ! -d "${venv_dir}" ]; then
    echo "Missing virtual environment at ${venv_dir}";
    echo 'Did you run test/install.sh?';
    exit 1;
fi

# Prepare test directory
skill_test_dir="${test_config_dir}/${skill_id}"
rm -rf "${skill_test_dir}"
mkdir -p "${skill_test_dir}"

# Copy Mycroft test environment
cp -R "${this_dir}/integrationtests/voight_kampff/features"/* "${skill_test_dir}/"

# Copy skill test environment
cp -R "${skill_features_dir}"/* "${skill_test_dir}/"

# Run tests
source "${venv_dir}/bin/activate"

cd "${skill_test_dir}" && \
    PYTHONPATH="${base_dir}:${PYTHONPATH}" \
    behave "$@"
