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
# Generates systemd unit files for services and skills.
#
# Unit files will be stored in: ${XDG_CONFIG_HOME}/systemd/user
# To run:
# systemctl --user start mycroft.target
#
# For each service, expects the directory <repo>/services/<service_id> to exist
# and look like:
#
# service/
#   __init__.py
#   __main__.py
#
set -eo pipefail

function usage {
    echo "Usage: $(basename "$0") service_id [service_id] ..."
}

if [ -z "$1" ]; then
    usage;
    exit 1;
fi

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"

# Directory of repo
base_dir="$(realpath "${this_dir}/../")"

: "${XDG_CONFIG_HOME:=${HOME}/.config}"

unit_dir="${XDG_CONFIG_HOME}/systemd/user"
mkdir -p "${unit_dir}"

service_ids=('messagebus')

while [ -n "$1" ]; do
    service_ids+=("$1")
    shift 1
done

services=()
for service_id in "${service_ids[@]}"; do
    service_code_dir="${base_dir}/services/${service_id}"

    if [ ! -d "${service_code_dir}" ]; then
        echo "Missing service directory at ${service_code_dir}";
        exit 1;
    fi

    # User-writable directory where virtual environment is stored
    service_config_dir="${XDG_CONFIG_HOME}/mycroft/services/${service_id}"
    venv_dir="${service_config_dir}/.venv"

    if [ ! -d "${venv_dir}" ]; then
        echo "Missing virtual environment at ${venv_dir}";
        echo 'Did you run install-service.sh?';
        exit 1;
    fi

    # Generate systemd unit
    unit_file="${unit_dir}/mycroft-${service_id}.service"

    if [ "${service_id}" = 'messagebus' ]; then
        service_after='';
    else
        service_after='After=mycroft-messagebus.service';
    fi

    export service_after
    cat > "${unit_file}" <<EOF
[Unit]
Description=Mycroft ${service_id} service
PartOf=mycroft.target
${service_after}

[Service]
Type=notify
Environment=PYTHONPATH=${service_code_dir}
ExecStart=${venv_dir}/bin/python -m service
Restart=always
RestartSec=1
TimeoutSec=10
WatchdogSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=mycroft.target

EOF

    services+=("mycroft-${service_id}.service")
done

# Generate mycroft.target
target_file="${unit_dir}/mycroft.target"
cat > "${target_file}" <<EOF
[Unit]
Description=mycroft target
Requires=${services[@]}

EOF

systemctl --user daemon-reload
