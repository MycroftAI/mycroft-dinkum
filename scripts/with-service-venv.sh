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
# Runs a command in a service's virtual environment
#
# Expects a virtual environment at:
# ${XDG_CONFIG_HOME}/mycroft/services/<service_id>
#
set -eo pipefail

function usage {
    echo "Usage: $(basename "$0") service_dir ..."
}

if [ -z "$2" ]; then
    usage;
    exit 1;
fi

service_dir="$1"
service_id="$(basename "${service_dir}")"

# Remaining arguments are command
shift 1

: "${XDG_CONFIG_HOME:=${HOME}/.config}"

# User-writable directory where virtual environment is stored
if [ -n "${DINKUM_SHARED_VENV}" ]; then
    # Shared virtual enviroment
    service_config_dir="${XDG_CONFIG_HOME}/mycroft"
else
    # Isolated service virtual enviroment
    service_config_dir="${XDG_CONFIG_HOME}/mycroft/skills/${skill_id}"
fi

venv_dir="${service_config_dir}/.venv"

if [ ! -d "${venv_dir}" ]; then
    echo "Missing virtual environment at ${venv_dir}";
    echo 'Did you run install-service.sh?';
    exit 1;
fi

source "${venv_dir}/bin/activate"

# Run command
"$@"
