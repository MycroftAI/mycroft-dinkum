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

import pytest
import unittest
from datetime import datetime, timezone

from mycroft.util.parse import extract_datetime
from mycroft.util.time import now_local, now_utc, to_local, to_utc
from lingua_franca import set_default_lang

from skill.alarm import (
    alarm_log_dump,
    curate_alarms,
    get_alarm_local,
    get_next_repeat,
    has_expired_alarm,
)

set_default_lang("en-us")

RRULE_DAILY = "FREQ=WEEKLY;INTERVAL=1;BYDAY=SU,SA,WE,MO,FR,TH,TU"
RRULE_WEEKDAYS = "FREQ=WEEKLY;INTERVAL=1;BYDAY=WE,MO,FR,TH,TU"


def _get_timestamp(when):
    extracted_dt, _ = extract_datetime(when) or (None, None)
    return extracted_dt.timestamp()


class TestCurateAlarms(unittest.TestCase):
    def test_remove_expired_alarm(self):
        alarms = [
            {
                "timestamp": _get_timestamp("yesterday at 7pm"),
                "repeat_rule": None,
                "name": "",
            }
        ]
        curated_alarms = curate_alarms(alarms)
        self.assertEqual(curated_alarms, [])

    def test_reschedule_recurring_alarm(self):
        expired_alarm = {
            "timestamp": _get_timestamp("yesterday at 7pm"),
            "repeat_rule": RRULE_DAILY,
            "name": "",
        }
        rescheduled_alarm = get_next_repeat(expired_alarm)
        curated_alarms = curate_alarms([expired_alarm])
        self.assertEqual(curated_alarms, [rescheduled_alarm])

    def test_return_future_alarms(self):
        """Ensure future alarms are not modified."""
        alarms = [
            {
                "timestamp": _get_timestamp("tomorrow at 7pm"),
                "repeat_rule": None,
                "name": "",
            }
        ]
        curated_alarms = curate_alarms(alarms)
        self.assertEqual(curated_alarms, alarms)

    @pytest.mark.skip("Test not yet implemented")
    def test_snoozed_alarms(self):
        pass

    @pytest.mark.skip("Test not yet implemented")
    def test_alarm_meta_not_modified(self):
        pass


class TestGetAlarmLocal(unittest.TestCase):
    def test_get_local_time_of_alarm(self):
        alarm_dt = _get_timestamp("tomorrow at 7pm")
        alarm = {"timestamp": alarm_dt, "repeat_rule": None, "name": ""}
        alarm_local_dt = get_alarm_local(alarm)
        expected_dt = to_local(extract_datetime("tomorrow at 7pm")[0])
        self.assertEqual(alarm_local_dt, expected_dt)

    def test_get_local_time_of_timestamp(self):
        timestamp = _get_timestamp("tomorrow at 7pm")
        alarm_local_dt = get_alarm_local(timestamp=timestamp)
        expected_dt = to_local(extract_datetime("tomorrow at 7pm")[0])
        self.assertEqual(alarm_local_dt, expected_dt)


class TestGetNextRepeat(unittest.TestCase):
    @pytest.mark.skip("Failing")
    def test_get_next_repeat(self):
        expired_alarm = {
            "timestamp": _get_timestamp("yesterday at 7pm"),
            "repeat_rule": RRULE_DAILY,
            "name": "",
        }
        rescheduled_alarm = get_next_repeat(expired_alarm)
        if now_local().hour < 19:
            expected_timestamp = _get_timestamp("today at 7pm")
        else:
            expected_timestamp = _get_timestamp("tomorrow at 7pm")
        # print(now_utc())
        # print(datetime.fromtimestamp(expired_alarm['timestamp'], timezone.utc))
        # print(datetime.fromtimestamp(rescheduled_alarm['timestamp'], timezone.utc))
        # print(datetime.fromtimestamp(expected_timestamp, timezone.utc))
        self.assertEqual(rescheduled_alarm["timestamp"], expected_timestamp)


class TestHasExpiredAlarm(unittest.TestCase):
    def test_has_expired_alarm(self):
        alarms = [
            {
                "timestamp": _get_timestamp("yesterday at 7pm"),
                "repeat_rule": RRULE_DAILY,
                "name": "",
            },
            {
                "timestamp": _get_timestamp("tomorrow at 10:30am"),
                "repeat_rule": None,
                "name": "",
            },
        ]
        alarm_expired = has_expired_alarm(alarms)
        self.assertTrue(alarm_expired)

    def test_no_expired_alarm(self):
        alarms = [
            {
                "timestamp": _get_timestamp("tomorrow at 10:30am"),
                "repeat_rule": None,
                "name": "",
            }
        ]
        alarm_expired = has_expired_alarm(alarms)
        self.assertFalse(alarm_expired)
