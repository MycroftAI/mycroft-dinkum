# Copyright 2017 Mycroft AI Inc.
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
"""Keep the settingsmeta.json and settings.json files in sync with the backend.

The SkillSettingsMeta and SkillSettings classes run a synchronization every
minute to ensure the device and the server have the same values.

The settingsmeta.json file (or settingsmeta.yaml, if you prefer working with
yaml) in the skill's root directory contains instructions for the Selene UI on
how to display and update a skill's settings, if there are any.

For example, you might have a setting named "username".  In the settingsmeta
you can describe the interface to edit that value with:
    ...
    "fields": [
        {
            "name": "username",
            "type": "email",
            "label": "Email address to associate",
            "placeholder": "example@mail.com",
            "value": ""
        }
    ]
    ...

When the user changes the setting via the web UI, it will be sent down to all
the devices related to an account and automatically placed into
settings['username'].  Any local changes made to the value (e.g. via a verbal
interaction) will also be synchronized to the server to show on the web
interface.

The settings.json file contains name/value pairs for each setting.  There can
be entries in settings.json that are not related to those the user can
manipulate on the web.  There is logic in the SkillSettings class to ensure
these "hidden" settings are not affected when the synchronization occurs.  A
skill can define a function that will be called when any settings change.

SkillSettings Usage Example:
    from mycroft.skill.settings import SkillSettings

        s = SkillSettings('./settings.json', 'ImportantSettings')
        s.skill_settings['meaning of life'] = 42
        s.skill_settings['flower pot sayings'] = 'Not again...'
        s.save_settings()  # This happens automagically in a MycroftSkill
"""
import json
import os
import re
from http import HTTPStatus
from pathlib import Path
from threading import Timer

import requests
import yaml
from mycroft.api import DeviceApi
from mycroft.identity import IdentityManager
from mycroft.util.log import LOG
from mycroft.util.string_utils import camel_case_split
from mycroft_bus_client import Message, MessageBusClient

ONE_MINUTE = 60


def get_local_settings(skill_dir, skill_name) -> dict:
    """Build a dictionary using the JSON string stored in settings.json."""
    skill_settings = {}
    settings_path = Path(skill_dir).joinpath("settings.json")
    LOG.info(settings_path)
    if settings_path.exists():
        with open(str(settings_path)) as settings_file:
            settings_file_content = settings_file.read()
        if settings_file_content:
            try:
                skill_settings = json.loads(settings_file_content)
            # TODO change to check for JSONDecodeError in 19.08
            except Exception:
                log_msg = "Failed to load {} settings from settings.json"
                LOG.exception(log_msg.format(skill_name))

    return skill_settings


def save_settings(skill_dir, skill_settings):
    """Save skill settings to file."""
    settings_path = Path(skill_dir).joinpath("settings.json")

    # Either the file already exists in /opt, or we are writing
    # to XDG_CONFIG_DIR and always have the permission to make
    # sure the file always exists
    if not Path(settings_path).exists():
        settings_path.touch(mode=0o644)

    with open(str(settings_path), "w") as settings_file:
        try:
            json.dump(skill_settings, settings_file)
        except Exception:
            LOG.exception("error saving skill settings to " "{}".format(settings_path))
        else:
            LOG.info("Skill settings successfully saved to " "{}".format(settings_path))


def get_display_name(skill_name: str):
    """Splits camelcase and removes leading/trailing "skill"."""
    skill_name = re.sub(r"(^[Ss]kill|[Ss]kill$)", "", skill_name)
    return camel_case_split(skill_name)


# -----------------------------------------------------------------------------


class SettingsMetaUploader:
    """Synchronize the contents of the settingsmeta.json file with the backend.

    The settingsmeta.json (or settingsmeta.yaml) file is defined by the skill
    author.  It defines the user-configurable settings for a skill and contains
    instructions for how to display the skill's settings in the Selene web
    application (https://account.mycroft.ai).
    """

    _settings_meta_path = None

    def __init__(self, skill_directory: str, skill_name: str):
        self.skill_directory = Path(skill_directory)
        self.skill_name = skill_name
        self.json_path = self.skill_directory.joinpath("settingsmeta.json")
        self.yaml_path = self.skill_directory.joinpath("settingsmeta.yaml")
        self.settings_meta = {}
        self.api = None
        self.upload_timer = None
        self._stopped = None

        # Property placeholders
        self._skill_gid = None

    @property
    def skill_gid(self):
        return self.skill_name

    @property
    def settings_meta_path(self):
        """Fully qualified path to the settingsmeta file."""
        if self._settings_meta_path is None:
            if self.yaml_path.is_file():
                self._settings_meta_path = self.yaml_path
            else:
                self._settings_meta_path = self.json_path

        return self._settings_meta_path

    def upload(self):
        """Upload the contents of the settingsmeta file to Mycroft servers.

        The settingsmeta file does not change often, if at all.  Only perform
        the upload if a change in the file is detected.
        """
        synced = False
        identity = IdentityManager().get()
        if identity.uuid:
            self.api = DeviceApi()
            settings_meta_file_exists = (
                self.json_path.is_file() or self.yaml_path.is_file()
            )
            if settings_meta_file_exists:
                self._load_settings_meta_file()

            self._update_settings_meta()
            LOG.debug("Uploading settings meta for " + self.skill_gid)
            synced = self._issue_api_call()
        else:
            LOG.debug("settingsmeta.json not uploaded - no identity")

        if not synced and not self._stopped:
            LOG.debug("Scheduling manifest upload in %s second(s)", ONE_MINUTE)
            self.upload_timer = Timer(ONE_MINUTE, self.upload)
            self.upload_timer.daemon = True
            self.upload_timer.start()

    def stop(self):
        """Stop upload attempts if Timer is running."""
        if self.upload_timer:
            self.upload_timer.cancel()
        # Set stopped flag if upload is running when stop is called.
        self._stopped = True

    def _load_settings_meta_file(self):
        """Read the contents of the settingsmeta file into memory."""
        _, ext = os.path.splitext(str(self.settings_meta_path))
        is_json_file = self.settings_meta_path.suffix == ".json"
        try:
            with open(str(self.settings_meta_path)) as meta_file:
                if is_json_file:
                    self.settings_meta = json.load(meta_file)
                else:
                    self.settings_meta = yaml.safe_load(meta_file)
        except requests.HTTPError as http_error:
            if http_error.response.status_code == HTTPStatus.UNAUTHORIZED:
                LOG.warning("Settings not uploaded - device not paired")
            else:
                LOG.exception("Settings not uploaded")
        except Exception:
            log_msg = "Failed to load settingsmeta file: "
            LOG.exception(log_msg + str(self.settings_meta_path))

    def _update_settings_meta(self):
        """Make sure the skill gid and name are included in settings meta.

        Even if a skill does not have a settingsmeta file, we will upload
        settings meta JSON containing a skill gid and name
        """
        # Insert skill_gid and display_name
        self.settings_meta.update(
            skill_gid=self.skill_gid,
            display_name=(
                self.settings_meta.get("name") or get_display_name(self.skill_name)
            ),
        )
        for deprecated in ("color", "identifier", "name"):
            if deprecated in self.settings_meta:
                log_msg = (
                    'DEPRECATION WARNING: The "{}" attribute in the '
                    "settingsmeta file is no longer supported."
                )
                LOG.warning(log_msg.format(deprecated))
                del self.settings_meta[deprecated]

    def _issue_api_call(self):
        """Use the API to send the settings meta to the server."""
        try:
            self.api.upload_skill_metadata(self.settings_meta)
        except Exception:
            LOG.exception(
                "Failed to upload skill settings meta " "for {}".format(self.skill_gid)
            )
            success = False
        else:
            success = True

        return success


# -----------------------------------------------------------------------------


class SkillSettingsDownloader:
    """Manages download of skill settings.

    Performs settings download on a repeating Timer. If a change is seen
    the data is sent to the relevant skill.
    """

    def __init__(self, bus: MessageBusClient, remote_cache_path: Path):
        self.bus = bus
        self.continue_downloading = True

        self.remote_cache_path = Path(remote_cache_path)
        self.last_download_result = {}

        if self.remote_cache_path.exists():
            LOG.debug("Loading remote skill settings from %s", self.remote_cache_path)
            with open(
                self.remote_cache_path, "r", encoding="utf-8"
            ) as remote_cache_file:
                self.last_download_result = json.load(remote_cache_file)

        self.api = DeviceApi()
        self.download_timer = None

    def stop_downloading(self):
        """Stop synchronizing backend and core."""
        self.continue_downloading = False
        if self.download_timer:
            self.download_timer.cancel()

    # TODO: implement as websocket
    def download(self, message=None):
        """Download the settings stored on the backend and check for changes

        When used as a messagebus handler a message is passed but not used.
        """
        remote_settings = self._get_remote_settings()
        if remote_settings:
            settings_changed = self.last_download_result != remote_settings
            if settings_changed:
                LOG.debug("Skill settings changed since last download")
                self._emit_settings_change_events(remote_settings)
                self.last_download_result = remote_settings
            else:
                LOG.debug("No skill settings changes since last download")
        # If this method is called outside of the timer loop, ensure the
        # existing timer is canceled before starting a new one.
        if self.download_timer:
            self.download_timer.cancel()

        if self.continue_downloading:
            LOG.debug("Scheduling settings download in %s second(s)", ONE_MINUTE)
            self.download_timer = Timer(ONE_MINUTE, self.download)
            self.download_timer.daemon = True
            self.download_timer.start()

    def _get_remote_settings(self):
        """Get the settings for this skill from the server

        Returns:
            skill_settings (dict or None): returns a dict on success, else None
        """
        remote_settings = None
        try:
            remote_settings = self.api.get_skill_settings()

            # Save settings to cache
            self.remote_cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(
                self.remote_cache_path, "w", encoding="utf-8"
            ) as remote_cache_file:
                json.dump(remote_settings, remote_cache_file)

            LOG.debug("Wrote remote skill settings to %s", self.remote_cache_path)
        except requests.HTTPError as http_error:
            if http_error.response.status_code == HTTPStatus.UNAUTHORIZED:
                LOG.warning("Settings not downloaded - device not paired")
            else:
                LOG.exception("Settings not downloaded")
        except Exception:
            LOG.exception("Failed to download remote settings from server.")

        return remote_settings

    def _emit_settings_change_events(self, remote_settings):
        """Emit changed settings events for each affected skill."""
        changed_data = {}
        for skill_gid, skill_settings in remote_settings.items():
            settings_changed = False
            try:
                previous_settings = self.last_download_result.get(skill_gid)
            except Exception:
                LOG.exception("error occurred handling setting change events")
            else:
                if previous_settings != skill_settings:
                    changed_data[skill_gid] = skill_settings

        if changed_data:
            # Only send one message
            message = Message("mycroft.skills.settings.changed", data=changed_data)
            self.bus.emit(message)
