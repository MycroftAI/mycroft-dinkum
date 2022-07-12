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
"""Logic to find words in a utterance that match a regular expression."""
import re
from pathlib import Path
from typing import List

from mycroft.util.log import LOG

COMMENT = "#"


# TODO: Move to core as reusable skill code.
class UtteranceRegexMatcher:
    """Attempt to find words in an utterance matching regular expressions."""

    def __init__(self, utterance: str, regex_file_path: Path):
        self.utterance = utterance
        self.regex_file_path = regex_file_path
        self.match = None

    def find_match_in_utterance(self):
        """Attempt to find a timer name in a user request."""
        regex_patterns = self._get_search_patterns()
        self._search_for_match(regex_patterns)

    def _get_search_patterns(self) -> List[str]:
        """Read a file containing one or more regular expressions.

        Returns:
            List of all regular expressions found in the file.
        """
        regex_patterns = []
        with open(self.regex_file_path) as regex_file:
            for pattern in regex_file.readlines():
                pattern = pattern.strip()
                if pattern and not pattern.startswith(COMMENT):
                    regex_patterns.append(pattern)

        return regex_patterns

    def _search_for_match(self, regex_patterns: List[str]):
        """Match regular expressions found in file to utterance.

        Args:
            regex_patterns: regular expressions found in a .rx file.
        """
        for pattern in regex_patterns:
            pattern_match = re.search(pattern, self.utterance)
            if pattern_match:
                self._handle_pattern_match(pattern_match)
                if self.match is not None:
                    break
        self._log_extraction_result()

    def _handle_pattern_match(self, pattern_match):
        """Extract words matching the regular expression from the utterance.

        Args:
            pattern_match: results of a regular expression search
        """
        try:
            match = pattern_match.group("location").strip()
        except IndexError:
            pass
        else:
            self.match = match if match else None

    def _log_extraction_result(self):
        """Log the results of the matching."""
        file_name = str(self.regex_file_path.name)
        if self.match is None:
            log_msg = "No regular expressions in {} matched utterance"
        else:
            log_msg = "Regular expression in {} matched utterance: " + self.match
        LOG.info(log_msg.format(file_name))


def find_in_utterance(utterance: str, regex_file_path: Path) -> str:
    """Helper function to match an utterance to the contents of a .rx file.

    Args:
        utterance: User request from intent match event.
        regex_file_path: absolute path to the regular expression (.rx) file

    Returns:
        Words in the utterance that match the regular expressions in the .rx
        file or None if no match is found.
    """
    extractor = UtteranceRegexMatcher(utterance, regex_file_path)
    extractor.find_match_in_utterance()

    return extractor.match
