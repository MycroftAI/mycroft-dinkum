# Copyright 2021, Mycroft AI Inc.
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

from wiki.util import remove_nested_parentheses


class TestUtil(unittest.TestCase):
    def test_remove_nested_parentheses(self):
        test_strings = [
            ["No change", "No change"],
            ["a (simple) one", "a  one"],
            ["Ləmurs (/ˈliːmər/ (listen) LEE-mər)", "Ləmurs "],
            ["No (end (parentheses)", "No "],
        ]
        for input, expected in test_strings:
            output = remove_nested_parentheses(input)
            self.assertEqual(output, expected)
