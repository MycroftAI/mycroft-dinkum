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
import json
from pathlib import Path


def get_mycroft_build_datetime():
    """Get the Mycroft container build date from a file, if it exists."""
    build_datetime = ""
    build_info_path = Path("/etc/mycroft/build-info.json")
    if build_info_path.is_file():
        with open(build_info_path) as build_info_file:
            build_info = json.loads(build_info_file.read())
            build_datetime = build_info.get("build_date", "")
    # Do not include seconds in timestamp
    return build_datetime[:-3]
