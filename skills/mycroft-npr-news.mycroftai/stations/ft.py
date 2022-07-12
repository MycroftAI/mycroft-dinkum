# Copyright 2020 Mycroft AI Inc.
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

from bs4 import BeautifulSoup
from urllib.request import urlopen


def get_ft_url():
    """Custom news fetcher for Financial Times daily news briefing.
    
    Fetches latest episode link from FT website."""
    url = 'https://www.ft.com/newsbriefing'
    page = urlopen(url)

    # Use bs4 to parse website and get mp3 link
    soup = BeautifulSoup(page, features='html.parser')
    result = soup.find('time')
    target_div = result.parent.find_next('div')
    target_url = 'http://www.ft.com' + target_div.a['href']
    mp3_page = urlopen(target_url)
    mp3_soup = BeautifulSoup(mp3_page, features='html.parser')
    mp3_url = mp3_soup.find('source')['src']

    return mp3_url