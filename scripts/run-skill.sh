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
# Runs a skill by id.
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

# Remaining arguments are passed to service
shift 1

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"

# Directory of repo
base_dir="$(realpath "${this_dir}/../")"

service_code_dir="${base_dir}/services/skills"

if [ ! -d "${skill_dir}" ]; then
    echo "Missing skill directory at ${skill_dir}";
    exit 1;
fi

: "${XDG_CONFIG_HOME:=${HOME}/.config}"

# User-writable directory where virtual environment is stored
service_config_dir="${XDG_CONFIG_HOME}/mycroft/skills/${skill_id}"
venv_dir="${service_config_dir}/.venv"

if [ ! -d "${venv_dir}" ]; then
    echo "Missing virtual environment at ${venv_dir}";
    echo 'Did you run install-skill.sh?';
    exit 1;
fi

source "${venv_dir}/bin/activate"

PYTHONPATH="${service_code_dir}:${PYTHONPATH}" \
    python3 -m 'service' \
    --skill-directory "${skill_dir}" \
    --skill-id "${skill_id}" "$@"
