#
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
import unittest

import requests
from stations.abc import abc


class ABCAustralia(unittest.TestCase):
    def test_matches(self):
        url = abc()
        print(url)
        self.assertIsInstance(url, str)
        self.assertEqual(url[-4:], ".mp3")
        response = requests.get(url)
        self.assertEqual(response.status_code, 200)
