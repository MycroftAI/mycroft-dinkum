# Copyright 2022 Mycroft AI Inc.
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
from datetime import timedelta
from pathlib import Path

import lingua_franca
from skill import CountdownTimer, TimerMatcher

_DIR = Path(__file__).parent


class TestTimerMatcher:
    """Test TimerMatcherClass"""

    def setup_class(self):
        """Load files for U.S. English"""
        lingua_franca.load_language("en")

        self.regex_file_path = _DIR.parent.parent / "locale" / "en-us" / "name.rx"
        assert self.regex_file_path.is_file(), f"Missing: {self.regex_file_path}"

    def test_stt_errors(self):
        """Verify that STT oddities still match timer names"""
        # Timer 1..5
        timers = [
            CountdownTimer(duration=timedelta(minutes=t), name=f"timer {t}")
            for t in range(1, 6)
        ]

        # Should matcher timer 2
        matcher = TimerMatcher("timer to", timers, self.regex_file_path)
        matcher.match()
        assert matcher.matches, "No matches for 'timer to'"
        assert matcher.matches[0].name == "timer 2"

        # Should matcher timer 4
        matcher = TimerMatcher("timer for", timers, self.regex_file_path)
        matcher.match()
        assert matcher.matches, "No matches for 'timer for'"
        assert matcher.matches[0].name == "timer 4"
