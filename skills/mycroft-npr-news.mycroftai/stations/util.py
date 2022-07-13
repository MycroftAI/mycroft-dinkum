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

from shutil import SpecialFileError, copyfile

import requests
from mycroft.util.log import LOG


def find_mime_type(url: str) -> str:
    """Determine the mime type of a file at the given url.

    Args:
        url: remote url to check
    Returns:
        Mime type - defaults to 'audio/mpeg'
    """
    mime = "audio/mpeg"
    response = requests.Session().head(url, allow_redirects=True)
    if 200 <= response.status_code < 300:
        mime = response.headers["content-type"]
    return mime


def contains_html(file: str) -> bool:
    """Reads file and reports if a <html> tag is contained.

    Makes a temporary copy of the file to prevent locking downloads in
    progress. This should not be considered a robust method of testing if a
    file is a HTML document, but sufficient for this purpose.

    Args:
        file: path of file

    Returns:
        Whether a <html> tag was found
    """
    found_html = False
    tmp_file = "/tmp/mycroft-news-html-check"
    try:
        # Copy file to prevent locking larger file being downloaded
        copyfile(file, tmp_file)
        with open(tmp_file, mode="r", encoding="utf-8") as f:
            for line in f:
                if "<html>" in line:
                    found_html = True
                    break
    except SpecialFileError as error:
        if "is a named pipe" in error.args[0]:
            LOG.debug('File is a "named pipe" as expected.')
    return found_html
