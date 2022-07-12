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

import unittest
from datetime import timedelta

from mycroft.util.time import now_local

from skill.format import nice_relative_time


class TestNiceRelativeTime(unittest.TestCase):
    def test_format_nice_relative_time(self):
        now = now_local()
        two_hours_from_now = now + timedelta(hours=2)
        self.assertEqual(
            nice_relative_time(when=two_hours_from_now, relative_to=now),
            "2 hours"
        )
        seconds_from_now = now + timedelta(seconds=47)
        self.assertEqual(
            nice_relative_time(when=seconds_from_now, relative_to=now),
            "47 seconds"
        )
        days_from_now = now + timedelta(days=3)
        self.assertEqual(
            nice_relative_time(when=days_from_now, relative_to=now),
            "3 days"
        )
