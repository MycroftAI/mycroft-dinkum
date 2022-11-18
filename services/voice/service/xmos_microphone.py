#!/usr/bin/env python3
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
import json
import subprocess
import sys
import time
from typing import Optional

from mycroft.util.log import get_mycroft_logger

_log = get_mycroft_logger(__name__)


class XmosMicrophone:
    def _get_parameter(self, name: str) -> Optional[str]:
        try:
            xmos_name = f"GET_{name.upper()}"
            command = ["vfctrl_i2c", "--no-check-version", xmos_name]
            lines = subprocess.check_output(
                command, universal_newlines=True
            ).splitlines()
            for line in lines:
                line = line.strip()
                if line.startswith(f"{xmos_name}:"):
                    return line.split(":", maxsplit=1)[-1].strip()
        except Exception:
            _log.exception("Error getting parameter: %s", name)

        return None

    @property
    def gain_ch0_agc(self) -> Optional[float]:
        value = self._get_parameter("GAIN_CH0_AGC")
        if value is not None:
            return float(value)

        return None

    @property
    def adapt_ch0_agc(self) -> Optional[bool]:
        value = self._get_parameter("ADAPT_CH0_AGC")
        if value is not None:
            return value == "1"

        return None

    @property
    def lc_enabled_ch0_agc(self) -> Optional[bool]:
        value = self._get_parameter("LC_ENABLED_CH0_AGC")
        if value is not None:
            return value == "1"

        return None

    @property
    def max_gain_ch0_agc(self) -> Optional[bool]:
        value = self._get_parameter("MAX_GAIN_CH0_AGC")
        if value is not None:
            return float(value)

        return None

    @property
    def upper_threshold_ch0_agc(self) -> Optional[bool]:
        value = self._get_parameter("UPPER_THRESHOLD_CH0_AGC")
        if value is not None:
            return float(value)

        return None

    @property
    def lower_threshold_ch0_agc(self) -> Optional[bool]:
        value = self._get_parameter("LOWER_THRESHOLD_CH0_AGC")
        if value is not None:
            return float(value)

        return None

    @property
    def increment_gain_stepsize_ch0_agc(self) -> Optional[bool]:
        value = self._get_parameter("INCREMENT_GAIN_STEPSIZE_CH0_AGC")
        if value is not None:
            return float(value)

        return None

    @property
    def decrement_gain_stepsize_ch0_agc(self) -> Optional[bool]:
        value = self._get_parameter("DECREMENT_GAIN_STEPSIZE_CH0_AGC")
        if value is not None:
            return float(value)

        return None


def main():
    mic = XmosMicrophone()
    while True:
        json.dump(
            {
                "GAIN_CH0_AGC": mic.gain_ch0_agc,
                "ADAPT_CH0_AGC": mic.adapt_ch0_agc,
                "MAX_GAIN_CH0_AGC": mic.max_gain_ch0_agc,
                "LC_ENABLED_CH0_AGC": mic.lc_enabled_ch0_agc,
                "LOWER_THRESHOLD_CH0_AGC": mic.lower_threshold_ch0_agc,
                "UPPER_THRESHOLD_CH0_AGC": mic.upper_threshold_ch0_agc,
                "INCREMENT_GAIN_STEPSIZE_CH0_AGC": mic.increment_gain_stepsize_ch0_agc,
                "DECREMENT_GAIN_STEPSIZE_CH0_AGC": mic.decrement_gain_stepsize_ch0_agc,
            },
            sys.stdout,
        )
        print("", flush=True)
        time.sleep(0.25)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
