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

import re


class EnglishQuestionParser(object):
    """Simplistic English question parser for use with WolframAlpha.

    It is not even close to conclusive, but appears to construct some decent
    WolframAlpha queries and responses.
    """

    def __init__(self):
        self.regexes = [
            # Match things like:
            #    * when X was Y, e.g. "tell me when america was founded"
            #    how X is Y, e.g. "how tall is mount everest"
            re.compile(
                r".*(?P<QuestionWord>who|what|when|where|why|which|whose) "
                r"(?P<Query1>.*) (?P<QuestionVerb>is|are|was|were) "
                r"(?P<Query2>.*)",
                re.IGNORECASE,
            ),
            # Match:
            #    how X Y, e.g. "how do crickets chirp"
            re.compile(
                r".*(?P<QuestionWord>who|what|when|where|why|which|how) "
                r"(?P<QuestionVerb>\w+) (?P<Query>.*)",
                re.IGNORECASE,
            ),
        ]

    def _normalize(self, groupdict):
        if "Query" in groupdict:
            return groupdict
        elif "Query1" and "Query2" in groupdict:
            # Join the two parts into a single 'Query'
            return {
                "QuestionWord": groupdict.get("QuestionWord"),
                "QuestionVerb": groupdict.get("QuestionVerb"),
                "Query": " ".join([groupdict.get("Query1"), groupdict.get("Query2")]),
            }

    def parse(self, utterance):
        for regex in self.regexes:
            match = regex.match(utterance)
            if match:
                return self._normalize(match.groupdict())
        return None
