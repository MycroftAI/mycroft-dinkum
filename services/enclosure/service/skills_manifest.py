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
import json
from pathlib import Path
from typing import Any, Dict

_DIR = Path(__file__).parent


def get_skills_manifest() -> Dict[str, Any]:
    """Load hard-coded skills.json file for Mark II"""
    with open(_DIR / "skills.json") as skills_file:
        skills_manifest = json.load(skills_file)

    # Add all the "required" fields
    for skill_dict in skills_manifest["skills"]:
        skill_dict["origin"] = "https://github.com/MycroftAI"
        skill_dict["beta"] = False
        skill_dict["installed"] = 1
        skill_dict["updated"] = 1
        skill_dict["installation"] = "installed"
        skill_dict["status"] = "active"

    return skills_manifest
