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

import json
from datetime import datetime
from pathlib import Path

# from git import Git
# from mycroft import MYCROFT_ROOT_PATH
# from mycroft.version import CORE_VERSION_STR


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


# def get_mycroft_core_commit():
#     """Get the latest commit info for Mycroft-Core."""
#     commit_string = ""
#     core_repo = Git(MYCROFT_ROOT_PATH)
#     branch = core_repo.branch("--show-current")
#     if not branch:
#         # It's in a detached head state so is not reporting branch.
#         branch = "feature/mark-2"
#     commit_hash = core_repo.log("-n 1", "--pretty=format:%h")[:7]
#     commit_string = f"{branch}@{commit_hash}"
#     return commit_string


def get_mycroft_core_version():
    """Get the reported version number for Mycroft-Core.

    Note: if running off a feature branch or dev,
    the last point release of core will be returned.
    """
    return CORE_VERSION_STR


# def get_skill_update_datetime(skills_repo_path):
#     """Get the date the Skills Marketplace last updated."""
#     skills_repo = Git(skills_repo_path)
#     last_commit_timestamp = skills_repo.log("-1", "--format=%ct")
#     last_commit_date_time = datetime.utcfromtimestamp(int(last_commit_timestamp))
#     return last_commit_date_time.strftime("%Y-%m-%d %H:%M")
