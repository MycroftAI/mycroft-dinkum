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
features_dir="${skill_dir}/test/behave"


: "${XDG_CONFIG_HOME:=${HOME}/.config}"

# User-writable directory where virtual environment is stored
test_config_dir="${XDG_CONFIG_HOME}/mycroft/test"
venv_dir="${test_config_dir}/.venv"

if [ ! -d "${venv_dir}" ]; then
    echo "Missing virtual environment at ${venv_dir}";
    echo 'Did you run install.sh?';
    exit 1;
fi

source "${venv_dir}/bin/activate"

PYTHONPATH="${test_code_dir}:${PYTHONPATH}" \
    python3 -m test.integrationtests.voight_kampff "$@"
