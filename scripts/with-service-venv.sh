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
# Installs a plugin into a service's virtual environment
#
# Expects a virtual environment at:
# ${XDG_CONFIG_HOME}/mycroft/services/<service_id>
#
set -eo pipefail

function usage {
    echo "Usage: $(basename "$0") service_id plugin ..."
}

if [ -z "$2" ]; then
    usage;
    exit 1;
fi

service_id="$1"

# Remaining arguments are passed to pip
shift 1

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

# Install plugin
pip3 install "$@"
