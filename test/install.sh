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

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"

# Directory of repo
base_dir="$(realpath "${this_dir}/../")"

: "${XDG_CONFIG_HOME:=${HOME}/.config}"

# User-writable directory where virtual environment is stored
test_config_dir="${XDG_CONFIG_HOME}/mycroft/test"

echo "Installing to ${test_config_dir}"
mkdir -p "${test_config_dir}"

# Create virtual environment
venv_dir="${test_config_dir}/.venv"
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
requirements="${this_dir}/requirements/requirements.txt"
if [ -f "${requirements}" ]; then
    pip3 install -r "${requirements}"
fi
