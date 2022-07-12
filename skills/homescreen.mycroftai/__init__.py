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
"""Skill to display a home screen (a.k.a. idle screen) on a GUI enabled device."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from git import Git

from mycroft.messagebus.message import Message
from mycroft.skills import AdaptIntent, IdleDisplaySkill, intent_handler
from mycroft.util.format import nice_time, nice_date
from mycroft.util.time import now_local
from .skill import Wallpaper, WallpaperError

FIFTEEN_MINUTES = 900
MARK_II = "mycroft_mark_2"
ONE_HOUR = 3600
ONE_MINUTE = 60
TEN_SECONDS = 10


class HomescreenSkill(IdleDisplaySkill):
    """Skill to display a home screen (a.k.a. idle screen) on a GUI enabled device.

    Attributes:
        display_date: the date string currently being displayed on the screen
        display_time: the time string currently being displayed on the screen
        wallpaper: An instance of the class for managing wallpapers.
    """

    def __init__(self):
        super().__init__(name="HomescreenSkill")
        self.display_time = None
        self.display_date = None
        self.wallpaper = Wallpaper(self.root_dir, self.file_system.path)
        self.settings_change_callback = self._handle_settings_change

    @property
    def platform(self) -> Optional[str]:
        """The platform from the device configuration (e.g. "mycroft_mark_1")

        Returns:
            Platform identifier if one is defined, otherwise None.
        """
        platform = None
        if self.config_core and self.config_core.get("enclosure"):
            platform = self.config_core["enclosure"].get("platform")

        return platform

    @property
    def is_development_device(self):
        return self.config_core["enclosure"].get("development_device")

    def _handle_settings_change(self):
        """Reacts to changes in the user settings for this skill."""
        new_wallpaper_settings = self._check_for_wallpaper_setting_change()
        if self.gui.connected and new_wallpaper_settings:
            try:
                self.wallpaper.file_name_setting = self.settings.get("wallpaper_file")
                self.wallpaper.url_setting = self.settings.get("wallpaper_url")
                self.wallpaper.change()
            except WallpaperError:
                self.log.exception("An error occurred setting the wallpaper.")
                self.speak("wallpaper-error")
                self.gui["wallpaperPath"] = None
            else:
                self.gui["wallpaperPath"] = str(self.wallpaper.selected)
                self.bus.emit(
                    Message(
                        "homescreen.wallpaper.changed",
                        data={"name": self.wallpaper.file_name_setting},
                    )
                )

    def _check_for_wallpaper_setting_change(self):
        """Determine if the new settings are related to the wallpaper."""
        file_name_setting = self.settings.get("wallpaper_file")
        url_setting = self.settings.get("wallpaper_url")
        change_wallpaper = (
            file_name_setting != self.wallpaper.file_name_setting
            or url_setting != self.wallpaper.url_setting
        )

        return change_wallpaper

    def initialize(self):
        """Performs tasks after instantiation but before loading is complete."""
        super().initialize()
        self._load_resources()
        self._init_gui_attributes()
        self._schedule_clock_update()
        self._schedule_date_update()
        self.schedule_weather_request()
        self.query_active_alarms()
        self._schedule_skill_datetime_update()
        self.handle_initial_skill_load()
        self._add_event_handlers()

    def _load_resources(self):
        self.name_regex = self.resources.load_regex_file("name")

    def _init_gui_attributes(self):
        self.gui["showAlarmIcon"] = False
        self.gui["homeScreenTemperature"] = None
        self.gui["homeScreenWeatherCondition"] = None
        self.gui["isMuted"] = False

    def _init_wallpaper(self):
        """When the skill loads, determine the wallpaper to display"""
        self.wallpaper.file_name_setting = self.settings.get("wallpaper_file")
        self.wallpaper.url_setting = self.settings.get("wallpaper_url")
        try:
            self.wallpaper.set()
        except WallpaperError:
            self.log.exception("An error occurred setting the wallpaper.")
            self.gui["wallpaperPath"] = None
        else:
            self.gui["wallpaperPath"] = str(self.wallpaper.selected)

    def _schedule_clock_update(self):
        """Checks for a clock update every ten seconds; start on a minute boundary."""
        clock_update_start_time = datetime.now().replace(second=0, microsecond=0)
        clock_update_start_time += timedelta(minutes=1)
        self.schedule_repeating_event(
            self.update_clock, when=clock_update_start_time, frequency=TEN_SECONDS
        )

    def _schedule_date_update(self):
        """Checks for a date update every minute; start on a minute boundary."""
        date_update_start_time = datetime.now().replace(second=0, microsecond=0)
        date_update_start_time += timedelta(minutes=1)
        self.schedule_repeating_event(
            self.update_date, when=date_update_start_time, frequency=ONE_MINUTE
        )

    def schedule_weather_request(self):
        """Checks for a weather update every fifteen minutes."""
        self.schedule_repeating_event(
            self.request_weather, when=datetime.now(), frequency=FIFTEEN_MINUTES
        )

    def _schedule_skill_datetime_update(self):
        """Schedules an hourly check for skills being updated."""
        self.schedule_repeating_event(
            self.update_skill_datetime, when=datetime.now(), frequency=ONE_HOUR
        )

    def update_skill_datetime(self):
        """Sets the skill update date for display on the home screen.

        The Mycroft Skills Manager update system sets the modified date of a skill's
        __init__.py file to the time the skill was updated to force a reload. Leverage
        this to determine the last time MSM updated any skills.
        """
        if self.is_development_device:
            skills_repo = Git(f"{self.config_core['data_dir']}/.skills-repo")
            last_commit_timestamp = skills_repo.log("-1", "--format=%ct")
            last_commit_date_time = datetime.utcfromtimestamp(
                int(last_commit_timestamp)
            )
            self.gui["skillDateTime"] = last_commit_date_time.strftime("%Y-%m-%d %H:%M")

    def _add_event_handlers(self):
        """Defines the events this skill will listen for and their handlers."""
        self.add_event("mycroft.skills.initialized", self.handle_initial_skill_load)
        self.add_event("skill.alarm.query-active.response", self.handle_alarm_status)
        self.add_event("skill.alarm.status", self.handle_alarm_status)
        self.add_event(
            "skill.weather.local-forecast-obtained", self.handle_local_forecast_response
        )
        self.add_event("mycroft.mic.mute", self.handle_mute)
        self.add_event("mycroft.mic.unmute", self.handle_unmute)

    def handle_initial_skill_load(self):
        """Queries other skills for data to display and shows the resting screen.

        There is no guarantee of skill loading order.  These queries will ensure the
        home screen has the data it needs for the display when core is started or
        restarted.
        """
        self.request_weather()
        self.query_active_alarms()

    def query_active_alarms(self):
        """Emits a command over the message bus query for active alarms."""
        command = Message("skill.alarm.query-active")
        self.bus.emit(command)

    def request_weather(self):
        """Emits a command over the message bus to get the local weather forecast."""
        command = Message("skill.weather.request-local-forecast")
        self.bus.emit(command)

    def handle_local_forecast_response(self, event: Message):
        """Use the weather data from the event to populate the weather on the screen."""
        self.gui["homeScreenTemperature"] = event.data["temperature"]
        self.gui["homeScreenWeatherCondition"] = event.data["weather_condition"]

    def handle_alarm_status(self, event: Message):
        """Use the alarm data from the event to control visibility of the alarm icon."""
        self.gui["showAlarmIcon"] = event.data["active_alarms"]

    @intent_handler(AdaptIntent().require("show").require("home"))
    def show_homescreen(self, _):
        """Handles a user's request to show the home screen."""
        with self.activity():
            self._show_idle_screen()

    def _show_idle_screen(self):
        """Populates and shows the resting screen."""
        self.log.info("Displaying the Home Screen idle screen.")
        self._init_wallpaper()
        self.update_clock()
        self.update_date()
        self._set_build_datetime()
        self._show_page()

    def _set_build_datetime(self):
        """Sets the build date on the screen from a file, if it exists.

        The build date won't change without a reboot.  This only needs to occur once.
        """
        build_datetime = ""
        build_info_path = Path("/etc/mycroft/build-info.json")
        if self.is_development_device and build_info_path.is_file():
            with open(build_info_path) as build_info_file:
                build_info = json.loads(build_info_file.read())
                build_datetime = build_info.get("build_date", "")

        self.gui["buildDateTime"] = build_datetime[:-3]

    def _show_page(self):
        """Show the appropriate home screen based on the device platform."""
        if self.platform == MARK_II:
            page = "mark_ii_idle.qml"
        else:
            page = "scalable_idle.qml"
        self.gui.show_page(page)

    @intent_handler(AdaptIntent().require("change").one_of("background", "wallpaper"))
    def change_wallpaper(self, message):
        """Handles a user's request to change the wallpaper.

        Each time this intent is executed the next item in the list of collected
        wallpapers will be displayed and the skill setting will be updated.
        """
        with self.activity():
            utterance = message.data.get("utterance", "")
            wallpaper_name = self.wallpaper.extract_wallpaper_name(
                self.name_regex, utterance
            )
            if wallpaper_name:
                if not self.wallpaper.next_by_alias(wallpaper_name):
                    self.speak_dialog(
                        "wallpaper-not-found", data={"name": wallpaper_name}
                    )
                    return
            else:
                self.wallpaper.next()

            self.settings["wallpaper_file"] = self.wallpaper.file_name_setting
            self.gui["wallpaperPath"] = str(self.wallpaper.selected)
            self.bus.emit(
                Message(
                    "homescreen.wallpaper.changed",
                    data={"name": self.wallpaper.file_name_setting},
                )
            )
            self.log.info(
                "Home screen wallpaper changed to " + str(self.wallpaper.selected.name)
            )

    def update_date(self):
        """Formats the datetime object returned from the parser for display purposes."""
        formatted_date = nice_date(now_local())
        if self.display_date != formatted_date:
            self.display_date = formatted_date
            self._set_gui_date()

    def _set_gui_date(self):
        """Uses the data from the date skill to build the date as seen on the screen."""
        date_parts = self.display_date.split(", ")
        day_of_week = date_parts[0].title()
        month_day = date_parts[1].split()
        month = month_day[0][:3].title()
        day_of_month = now_local().strftime("%-d")
        gui_date = [day_of_week]
        if self.config_core.get("date_format") == "MDY":
            gui_date.extend([month, day_of_month])
        else:
            gui_date.extend([day_of_month, month])

        self.gui["homeScreenDate"] = " ".join(gui_date)

    def update_clock(self):
        """Broadcast the current local time in HH:MM format over the message bus.

        Provides a single place that determines the current local time and broadcasts
        it in the user-defined format (12 vs. 24 hour) for a clock implementation.
        """
        format_time_24_hour = self.config_core.get("time_format") == "full"
        formatted_time = nice_time(
            now_local(), speech=False, use_24hour=format_time_24_hour
        )
        if self.display_time != formatted_time:
            self.display_time = formatted_time
            self.gui["homeScreenTime"] = self.display_time

    def handle_mute(self, _message=None):
        self.gui["isMuted"] = True

    def handle_unmute(self, _message=None):
        self.gui["isMuted"] = False


def create_skill():
    """Boilerplate code to instantiate the skill."""
    return HomescreenSkill()
