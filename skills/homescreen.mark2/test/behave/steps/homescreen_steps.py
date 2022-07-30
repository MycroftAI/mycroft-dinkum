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
"""Step functions for the Home Screen Skill behave tests."""
from pathlib import Path

from behave import then


@then("the wallpaper should be changed")
def check_wallpaper_changed(context):
    """When the wallpaper changes, an event is emitted on the bus."""
    message = context.client.wait_for_message("homescreen.wallpaper.changed")
    assert message is not None, "Wallpaper was not changed"


@then("the wallpaper should be changed to {name}")
def check_wallpaper_changed_green(context, name):
    """When the wallpaper changes, an event is emitted on the bus with the name."""
    # Strip quotes
    name = name.replace('"', "")
    message = context.client.wait_for_message("homescreen.wallpaper.changed")
    assert message is not None, "Wallpaper was not changed"

    actual_name = message.data.get("name")
    if actual_name:
        actual_name = Path(actual_name).stem

    assert actual_name == name, f"Expected '{name}', got '{actual_name}'"
