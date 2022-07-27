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
from datetime import datetime

from skill.parse import fuzzy_match, utterance_has_midnight

THRESHOLD = 0.7


class TestFuzzyMatch(unittest.TestCase):
    def test_basic_fuzzy_matching(self):
        self.assertTrue(
            fuzzy_match(word="foo", phrase="this is foo bar", threshold=THRESHOLD)
        )


class TestUtteranceHasMidnight(unittest.TestCase):
    def test_utterance_has_midnight(self):
        midnight_datetime = datetime(2021, 3, 10, 0, 0, 0)
        self.assertTrue(
            utterance_has_midnight(
                utterance="set an alarm for midnight",
                init_time=midnight_datetime,
                threshold=THRESHOLD,
            )
        )
