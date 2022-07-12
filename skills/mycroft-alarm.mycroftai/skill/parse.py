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

from datetime import datetime
from typing import Optional, Tuple

from mycroft.util.log import LOG
from mycroft.util.parse import extract_datetime


def extract_alarm_datetime(utterance: str) -> Tuple[Optional[datetime], str]:
    """Extract datetime of Alarm expiry.

    Args:
        utterance: Full request, e.g. "set an alarm for 9 a.m."

    Returns
        The date and time requested (or None if no datetime was extracted),
        and remainder of utterance
    """
    extract_result = extract_datetime(utterance)
    if extract_result is None:
        alarm_datetime = None
        remaining_utterance = utterance
    else:
        alarm_datetime, remaining_utterance = extract_result
    if alarm_datetime is None:
        LOG.info("No alarm date and time found in request")
    else:
        LOG.info(f"Alarm date and time of {alarm_datetime} found in request")

    return alarm_datetime, remaining_utterance
