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
# Runs a service by id.
#
# Expects the directory <repo>/services/<service_id> to exist and look like:
# service/
#   __init__.py
#   __main__.py
#
set -eo pipefail

function usage {
    echo "Usage: $(basename "$0") service_dir ..."
}

if [ -z "$1" ]; then
    usage;
    exit 1;
fi

service_dir="$1"
service_id="$(basename "${service_dir}")"

# Remaining arguments are passed to service
shift 1

if [ ! -d "${service_dir}" ]; then
    echo "Missing service directory at ${service_dir}";
    exit 1;
fi

: "${XDG_CONFIG_HOME:=${HOME}/.config}"

# User-writable directory where virtual environment is stored
service_config_dir="${XDG_CONFIG_HOME}/mycroft/services/${service_id}"
venv_dir="${service_config_dir}/.venv"

if [ ! -d "${venv_dir}" ]; then
    echo "Missing virtual environment at ${venv_dir}";
    echo 'Did you run install-service.sh?';
    exit 1;
fi

source "${venv_dir}/bin/activate"

PYTHONPATH="${service_dir}:${PYTHONPATH}" \
    python3 -m 'service' "$@"
