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
# Installs a service by id.
#
# Expects the directory <repo>/services/<service_id> to exist and look like:
# service/
#   requirements/
#     requirements.txt
#
set -eo pipefail

function usage {
    echo "Usage: $(basename "$0") service_dir"
}

if [ -z "$1" ]; then
    usage;
    exit 1;
fi

service_dir="$1"
service_id="$(basename "${service_dir}")"

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"

# Directory of repo
base_dir="$(realpath "${this_dir}/../")"
repo_venv="${base_dir}/.venv"

if [ ! -d "${service_dir}" ]; then
    echo "Missing service directory at ${service_dir}";
    exit 1;
fi

: "${XDG_CONFIG_HOME:=${HOME}/.config}"

# User-writable directory where virtual environment is stored
if [ -n "${DINKUM_SHARED_VENV}" ]; then
    # Shared virtual enviroment
    service_config_dir="${XDG_CONFIG_HOME}/mycroft"
elif [ -d "${repo_venv}" ]; then
    service_config_dir="${base_dir}"
else
    # Isolated service virtual enviroment
    service_config_dir="${XDG_CONFIG_HOME}/mycroft/services/${service_id}"
fi

echo "Installing ${service_id} to ${service_config_dir}"
mkdir -p "${service_config_dir}"

# Create virtual environment
venv_dir="${service_config_dir}/.venv"
if [ ! -d "${venv_dir}" ]; then
    echo "Creating virtual environment in ${venv_dir}"
    python3 -m venv "${venv_dir}" "$@"

    # Upgrade default packages
    source "${venv_dir}/bin/activate"
    pip3 install --upgrade pip
    pip3 install --upgrade wheel setuptools
else
    source "${venv_dir}/bin/activate"
fi

# Install shared code
pip3 install -e "${base_dir}/shared"

# Install requirements
requirements="${service_dir}/requirements/requirements.txt"
if [ -f "${requirements}" ]; then
    pip3 install -r "${requirements}"
fi
