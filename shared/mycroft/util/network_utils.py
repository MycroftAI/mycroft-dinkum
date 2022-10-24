# Copyright 2021 Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Utilities for network and internet detection."""
import subprocess

import requests

from .log import get_mycroft_logger

_log = get_mycroft_logger(__name__)


def check_system_clock_sync_status() -> bool:
    """Returns True if the system clock has been synchronized with NTP."""
    clock_synchronized = False

    try:
        timedatectl_result = subprocess.check_output(
            ["timedatectl", "show"], stderr=subprocess.STDOUT
        )
        timedatectl_stdout = timedatectl_result.decode().splitlines()

        for line in timedatectl_stdout:
            if line.strip() == "NTPSynchronized=yes":
                clock_synchronized = True
                break
    except subprocess.CalledProcessError as error:
        _log.exception("error while checking system clock sync: %s", error.output)

    return clock_synchronized


def check_captive_portal() -> bool:
    """Returns True if a captive portal page is detected."""
    from bs4 import BeautifulSoup

    captive_portal = False

    try:
        # We need to check a site that doesn't use HTTPS
        html_doc = requests.get("http://start.mycroft.ai/portal-check.html").text
        soup = BeautifulSoup(html_doc)
        title = soup.title.string if soup.title else ""

        _log.info(title)

        # If something different is in the title, we likely were redirected
        # to the portal page.
        if title.lower().strip() != "portal check":
            captive_portal = True
    except Exception:
        _log.exception("Error checking for captive portal")

    return captive_portal
