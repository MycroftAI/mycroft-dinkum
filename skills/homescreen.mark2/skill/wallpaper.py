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
"""Wallpaper management for the home screen."""
import imghdr
import random
import typing
from pathlib import Path

import requests
from mycroft.skills.skill_data import RegexExtractor
from mycroft.util.log import LOG

DEFAULT_WALLPAPER = "blackwater-river.png"
CUSTOM_WALLPAPER = "custom-wallpaper.jpg"
WALLPAPER_ALIASES = {
    "blackwater-river.png": ["blackwater", "river", "default"],
    "blue.png": ["blue"],
    "chukchi-sea.png": ["sea", "ocean", "water"],
    "earth-night.png": ["earth", "night", "tonight"],
    "green.png": ["green"],
    "moon.png": ["moon"],
    "nebula.png": ["nebula", "space"],
    "orange.png": ["orange"],
    "tokyo-night.png": ["city", "night", "tonight"],
}


def _download_from_url(wallpaper_url):
    """Download an image file for use as a wallpaper."""
    LOG.info("Downloading wallpaper from " + wallpaper_url)
    try:
        response = requests.get(wallpaper_url)
    except requests.exceptions.HTTPError as exc:
        error_message = "Attempt to download image failed."
        if exc.response is not None:
            error_message += f" HTTP error code {exc.response.status_code}"
        raise WallpaperError(error_message)

    return response.content


class WallpaperError(Exception):
    """Raised when an error occurs when loading a wallpaper."""

    pass


class Wallpaper:
    """
    Attributes:
        collection: a list of paths to wallpaper files found on the device
        selected: the currently active (selected) wallpaper
        skill_directory: the wallpaper directory in the home screen skill
        skill_data_directory: a directory on the device for storing user-defined wallpapers
    """

    def __init__(self, skill_root_dir: str, skill_data_dir: str):
        self.skill_directory = Path(skill_root_dir).joinpath("ui/wallpapers")
        self.skill_data_directory = Path(skill_data_dir).joinpath("wallpapers")
        self._ensure_user_directory_exists()
        self.file_name_setting = None
        self.url_setting = None
        self.selected = None
        self.collection = []
        self.collect()

    def _ensure_user_directory_exists(self):
        """Ensures the directory for user-defined wallpapers exists."""
        if not self.skill_data_directory.exists():
            self.skill_data_directory.mkdir()

    def collect(self):
        """Builds a list of wallpapers provided by the skill and added by the user."""
        for wallpaper_path in self.skill_directory.iterdir():
            self.collection.append(wallpaper_path)
        for wallpaper_path in self.skill_data_directory.iterdir():
            self.collection.append(wallpaper_path)

    def change(self):
        """Change the wallpaper based on new skill settings values."""
        if self.file_name_setting == CUSTOM_WALLPAPER:
            self._add_custom()
        else:
            self.selected = self.skill_directory.joinpath(self.file_name_setting)
            if not self.selected.exists():
                raise WallpaperError("file name in skill settings does not exist.")

    def next(self):
        """Selects the next wallpaper in the collection for display.

        Starts over the beginning of the list after the last in the collection.  If
        the "selected" attribute contains a value not in the collection, the default
        is selected.
        """
        if self.selected in self.collection:
            if self.selected == self.collection[-1]:
                self.selected = self.collection[0]
            else:
                index_of_selected = self.collection.index(self.selected)
                self.selected = self.collection[index_of_selected + 1]
        else:
            self.selected = self.collection[0]

        self.file_name_setting = self.selected.name

    def extract_wallpaper_name(
        self, name_regex, utterance: str
    ) -> typing.Optional[str]:
        name_extractor = RegexExtractor("Name", name_regex)
        match = name_extractor.extract(utterance)
        if match:
            return match.strip()

        return None

    def next_by_alias(self, alias: str) -> bool:
        alias = alias.lower().strip()
        file_names = set()

        for file_name, aliases in WALLPAPER_ALIASES.items():
            if alias in aliases:
                file_names.add(file_name)

        if len(file_names) > 1:
            # If there are multiple possibilities, choose one that isn't
            # currently selected.
            file_names.discard(self.file_name_setting)

        if file_names:
            next_file_name = random.choice(list(file_names))
            for path in self.collection:
                if path.name == next_file_name:
                    LOG.info("Alias %s matched %s", alias, path.name)
                    self.selected = path
                    self.file_name_setting = self.selected.name
                    return True

        LOG.info("Alias %s did not match any wallpapers", alias)

        return False

    def _add_custom(self):
        """Adds a new wallpaper to the collection and selects it for display."""
        image = _download_from_url(self.url_setting)
        file_path = self.skill_data_directory.joinpath(CUSTOM_WALLPAPER)
        with open(file_path, "wb") as wallpaper_file:
            wallpaper_file.write(image)
        self._validate_custom()
        self.collect()
        self.selected = file_path

    def set(self):
        """Used to set the wallpaper on boot or skill reload."""
        file_path = self._determine_wallpaper_path()
        if file_path.exists():
            self.selected = file_path
            LOG.info("Home screen wallpaper set to " + str(file_path))
        else:
            raise WallpaperError(
                "no wallpaper exists matching the wallpaper current settings"
            )
        if file_path.name == CUSTOM_WALLPAPER:
            self._validate_custom()

    def _determine_wallpaper_path(self):
        """Build the right file path for the wallpaper in use."""
        if self.file_name_setting is None:
            file_path = self.skill_directory.joinpath(DEFAULT_WALLPAPER)
        elif self.file_name_setting == CUSTOM_WALLPAPER:
            file_path = self.skill_data_directory.joinpath(CUSTOM_WALLPAPER)
        else:
            file_path = self.skill_directory.joinpath(self.file_name_setting)

        return file_path

    def _validate_custom(self):
        """Ensure that a downloaded wallpaper is a valid image file."""
        file_path = self.skill_data_directory.joinpath(CUSTOM_WALLPAPER)
        if imghdr.what(file_path) != "jpeg":
            raise WallpaperError("Custom wallpaper is not an image file")
