# Copyright 2018 Mycroft AI Inc.
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
from typing import Dict

from mycroft.api import get_pantacor_device_id
from mycroft.messagebus.message import Message
from mycroft.skills import GuiClear, MycroftSkill

from .skill.device_id import get_device_name
from .skill.versions import get_mycroft_build_datetime


class Mark2(MycroftSkill):
    """
    The Mark2 skill handles much of the gui activities related to Mycroft's
    core functionality.

    This currently includes showing system loading screens, and handling system
    signals. Thinking and Speaking animations are also available.

    # TODO move most things to enclosure / HAL. Only voice interaction should
    reside in the Skill.
    """

    def __init__(self, skill_id: str):
        super().__init__(skill_id=skill_id, name="Mark2")

        # self.settings["auto_brightness"] = False
        # self.settings["use_listening_beep"] = True

        # self.has_show_page = False  # resets with each handler
        # self.override_animations = False
        # self.auto_brightness = None

    def initialize(self):
        """Perform initalization.

        Registers messagebus handlers and sets default gui values.
        """
        self.add_event("mycroft.device.settings", self.show_device_settings_about)
        # self.add_event("mycroft.device.settings", self.handle_device_settings)
        self.gui.register_handler(
            "mycroft.device.settings.close",
            "all.qml",
            self.handle_close_device_settings,
        )
        # self.gui.register_handler(
        #     "mycroft.device.settings.about",
        #     "all.qml",
        #     self.show_device_settings_about,
        # )
        # self.gui.register_handler(
        #     "mycroft.device.settings", "all.qml", self.handle_device_settings
        # )

        # self.brightness_dict = self.translate_namedvalues("brightness.levels")
        # self.gui["volume"] = 0

        # # Prepare GUI Viseme structure
        # self.gui["viseme"] = {"start": 0, "visemes": []}

        # try:
        #     # Handle network connection events
        #     self.add_event("mycroft.internet.connected", self.handle_internet_connected)

        #     # Handle the 'busy' visual
        #     self.bus.on("mycroft.skill.handler.start", self.on_handler_started)
        #     self.bus.on("enclosure.mouth.reset", self.on_handler_mouth_reset)
        #     self.bus.on("recognizer_loop:audio_output_end", self.on_handler_mouth_reset)
        #     self.bus.on("enclosure.mouth.viseme_list", self.on_handler_speaking)
        #     self.bus.on("gui.page.show", self.on_gui_page_show)

        #     # Handle device settings events
        #     self.add_event("mycroft.device.settings", self.handle_device_settings)
        #     self.gui.register_handler(
        #         "mycroft.device.settings.close", self.handle_close_device_settings
        #     )

        #     # Use Legacy for QuickSetting delegate
        #     self.gui.register_handler(
        #         "mycroft.device.settings", self.handle_device_settings
        #     )
        #     self.gui.register_handler(
        #         "mycroft.device.settings.reset",
        #         self.handle_device_factory_reset_settings,
        #     )
        #     self.gui.register_handler(
        #         "mycroft.device.settings.update", self.handle_device_update_settings
        #     )
        #     self.gui.register_handler(
        #         "mycroft.device.settings.about", self.show_device_settings_about
        #     )

        #     # System events
        #     self.add_event("system.reboot", self.handle_system_reboot)
        #     self.add_event("system.shutdown", self.handle_system_shutdown)

        #     self.add_event("mycroft.started", self.handle_started)

        #     # Show loading screen while starting up skills.
        #     # self.gui['state'] = 'loading'
        #     # self.gui.show_page('all.qml')

        # except Exception:
        #     LOG.exception("In Mark 2 Skill")

        # # Update use of wake-up beep
        # self._sync_wake_beep_setting()

        # self.settings_change_callback = self.on_websettings_changed

    ###################################################################
    # System events
    # def handle_system_reboot(self, _):
    #     self.speak_dialog("rebooting", wait=True)
    #     subprocess.call(["/usr/bin/systemctl", "reboot"])

    # def handle_system_shutdown(self, _):
    #     subprocess.call(["/usr/bin/systemctl", "poweroff"])

    # def stop(self, _=None):
    #     """Clear override_idle and stop visemes."""
    #     self.log.debug("Stop received")
    #     self.gui["viseme"] = {"start": 0, "visemes": []}
    #     return False

    # def shutdown(self):
    #     """Cleanly shutdown the Skill removing any manual event handlers"""
    #     # Gotta clean up manually since not using add_event()
    #     self.bus.remove("mycroft.skill.handler.start", self.on_handler_started)
    #     self.bus.remove("enclosure.mouth.reset", self.on_handler_mouth_reset)
    #     self.bus.remove("recognizer_loop:audio_output_end", self.on_handler_mouth_reset)
    #     self.bus.remove("enclosure.mouth.viseme_list", self.on_handler_speaking)
    #     self.bus.remove("gui.page.show", self.on_gui_page_show)

    #####################################################################
    # Manage "busy" visual

    # def on_handler_started(self, message):
    #     handler = message.data.get("handler", "")
    #     # Ignoring handlers from this skill and from the background clock
    #     if "Mark2" in handler:
    #         return
    #     if "TimeSkill.update_display" in handler:
    #         return

    # def on_gui_page_show(self, message):
    #     if "mark-2" not in message.data.get("__from", ""):
    #         # Some skill other than the handler is showing a page
    #         self.has_show_page = True

    #         # If a skill overrides the animations do not show any
    #         override_animations = message.data.get("__animations", False)
    #         if override_animations:
    #             # Disable animations
    #             self.log.debug("Disabling all animations for page")
    #             self.override_animations = True
    #         else:
    #             self.log.debug("Displaying all animations for page")
    #             self.override_animations = False

    # def on_handler_mouth_reset(self, _):
    #     """Restore viseme to a smile."""
    #     pass

    # def on_handler_complete(self, message):
    #     """When a skill finishes executing clear the showing page state."""
    #     handler = message.data.get("handler", "")
    #     # Ignoring handlers from this skill and from the background clock
    #     if "Mark2" in handler:
    #         return
    #     if "TimeSkill.update_display" in handler:
    #         return

    #     self.has_show_page = False

    #     try:
    #         if self.hourglass_info[handler] == -1:
    #             self.enclosure.reset()
    #         del self.hourglass_info[handler]
    #     except Exception:
    #         # There is a slim chance the self.hourglass_info might not
    #         # be populated if this skill reloads at just the right time
    #         # so that it misses the mycroft.skill.handler.start but
    #         # catches the mycroft.skill.handler.complete
    #         pass

    # #####################################################################
    # # Manage "speaking" visual

    # def on_handler_speaking(self, message):
    #     """Show the speaking page if no skill has registered a page
    #     to be shown in it's place.
    #     """
    #     self.gui["viseme"] = message.data
    #     if not self.has_show_page:
    #         self.gui["state"] = "speaking"
    #         self.gui.show_page("all.qml")
    #         # Show idle screen after the visemes are done (+ 2 sec).
    #         viseme_time = message.data["visemes"][-1][1] + 5
    #         # self.start_idle_event(viseme_time)

    # #####################################################################
    # # Manage network

    # def handle_internet_connected(self, _):
    #     """System came online later after booting."""
    #     self.enclosure.mouth_reset()

    # #####################################################################
    # # Web settings

    # def on_websettings_changed(self):
    #     """Update use of wake-up beep."""
    #     self._sync_wake_beep_setting()

    # def _sync_wake_beep_setting(self):
    #     """Update "use beep" global config from skill settings."""
    #     config = Configuration.get()
    #     use_beep = self.settings.get("use_listening_beep", False)
    #     if not config["confirm_listening"] == use_beep:
    #         # Update local (user) configuration setting
    #         new_config = {"confirm_listening": use_beep}
    #         user_config = LocalConf(USER_CONFIG)
    #         user_config.merge(new_config)
    #         user_config.store()
    #         self.bus.emit(Message("configuration.updated"))

    # #####################################################################
    # # Brightness intent interaction

    # def percent_to_level(self, percent):
    #     """Converts the brigtness value from percentage to a
    #     value the Arduino can read

    #     Arguments:
    #         percent (int): interger value from 0 to 100

    #     return:
    #         (int): value form 0 to 30
    #     """
    #     return int(float(percent) / float(100) * 30)

    # def parse_brightness(self, brightness):
    #     """Parse text for brightness percentage.

    #     Arguments:
    #         brightness (str): string containing brightness level

    #     Returns:
    #         (int): brightness as percentage (0-100)
    #     """

    #     try:
    #         # Handle "full", etc.
    #         name = normalize(brightness)
    #         if name in self.brightness_dict:
    #             return self.brightness_dict[name]

    #         if "%" in brightness:
    #             brightness = brightness.replace("%", "").strip()
    #             return int(brightness)
    #         if "percent" in brightness:
    #             brightness = brightness.replace("percent", "").strip()
    #             return int(brightness)

    #         i = int(brightness)
    #         if i < 0 or i > 100:
    #             return None

    #         if i < 30:
    #             # Assmume plain 0-30 is "level"
    #             return int((i * 100.0) / 30.0)

    #         # Assume plain 31-100 is "percentage"
    #         return i
    #     except Exception:
    #         return None  # failed in an int() conversion

    # def set_screen_brightness(self, level, speak=True):
    #     """Actually change screen brightness.

    #     Arguments:
    #         level (int): 0-30, brightness level
    #         speak (bool): when True, speak a confirmation
    #     """
    #     # TODO CHANGE THE BRIGHTNESS
    #     if speak:
    #         percent = int(float(level) * float(100) / float(30))
    #         self.speak_dialog("brightness.set", data={"val": str(percent) + "%"})

    # def _set_brightness(self, brightness):
    #     # brightness can be a number or word like "full", "half"
    #     percent = self.parse_brightness(brightness)
    #     if percent is None:
    #         self.speak_dialog("brightness.not.found.final")
    #     elif int(percent) == -1:
    #         self.handle_auto_brightness(None)
    #     else:
    #         self.auto_brightness = False
    #         self.set_screen_brightness(self.percent_to_level(percent))

    # @intent_handler("brightness.intent")
    # def handle_brightness(self, message):
    #     """Intent handler to set custom screen brightness.

    #     Arguments:
    #         message (dict): messagebus message from intent parser
    #     """
    #     brightness = message.data.get("brightness", None) or self.get_response(
    #         "brightness.not.found"
    #     )
    #     if brightness:
    #         self._set_brightness(brightness)

    # def _get_auto_time(self):
    #     """Get dawn, sunrise, noon, sunset, and dusk time.

    #     Returns:
    #         times (dict): dict with associated (datetime, level)
    #     """
    #     tz_code = self.location["timezone"]["code"]
    #     lat = self.location["coordinate"]["latitude"]
    #     lon = self.location["coordinate"]["longitude"]
    #     ast_loc = astral.Location()
    #     ast_loc.timezone = tz_code
    #     ast_loc.lattitude = lat
    #     ast_loc.longitude = lon

    #     user_set_tz = timezone(tz_code).localize(datetime.now()).strftime("%Z")
    #     device_tz = time.tzname

    #     if user_set_tz in device_tz:
    #         sunrise = ast_loc.sun()["sunrise"]
    #         noon = ast_loc.sun()["noon"]
    #         sunset = ast_loc.sun()["sunset"]
    #     else:
    #         secs = int(self.location["timezone"]["offset"]) / -1000
    #         sunrise = (
    #             arrow.get(ast_loc.sun()["sunrise"])
    #             .shift(seconds=secs)
    #             .replace(tzinfo="UTC")
    #             .datetime
    #         )
    #         noon = (
    #             arrow.get(ast_loc.sun()["noon"])
    #             .shift(seconds=secs)
    #             .replace(tzinfo="UTC")
    #             .datetime
    #         )
    #         sunset = (
    #             arrow.get(ast_loc.sun()["sunset"])
    #             .shift(seconds=secs)
    #             .replace(tzinfo="UTC")
    #             .datetime
    #         )

    #     return {
    #         "Sunrise": (sunrise, 20),  # high
    #         "Noon": (noon, 30),  # full
    #         "Sunset": (sunset, 5),  # dim
    #     }

    # def schedule_brightness(self, time_of_day, pair):
    #     """Schedule auto brightness with the event scheduler.

    #     Arguments:
    #         time_of_day (str): Sunrise, Noon, Sunset
    #         pair (tuple): (datetime, brightness)
    #     """
    #     d_time = pair[0]
    #     brightness = pair[1]
    #     now = arrow.now()
    #     arw_d_time = arrow.get(d_time)
    #     data = (time_of_day, brightness)
    #     if now.timestamp > arw_d_time.timestamp:
    #         d_time = arrow.get(d_time).shift(hours=+24)
    #         self.schedule_event(
    #             self._handle_screen_brightness_event,
    #             d_time,
    #             data=data,
    #             name=time_of_day,
    #         )
    #     else:
    #         self.schedule_event(
    #             self._handle_screen_brightness_event,
    #             d_time,
    #             data=data,
    #             name=time_of_day,
    #         )

    # @intent_handler("brightness.auto.intent")
    # def handle_auto_brightness(self, _):
    #     """brightness varies depending on time of day

    #     Arguments:
    #         message (Message): messagebus message from intent parser
    #     """
    #     self.auto_brightness = True
    #     auto_time = self._get_auto_time()
    #     nearest_time_to_now = (float("inf"), None, None)
    #     for time_of_day, pair in auto_time.items():
    #         self.schedule_brightness(time_of_day, pair)
    #         now = arrow.now().timestamp
    #         timestamp = arrow.get(pair[0]).timestamp
    #         if abs(now - timestamp) < nearest_time_to_now[0]:
    #             nearest_time_to_now = (abs(now - timestamp), pair[1], time_of_day)
    #     self.set_screen_brightness(nearest_time_to_now[1], speak=False)

    # def _handle_screen_brightness_event(self, message):
    #     """Wrapper for setting screen brightness from eventscheduler

    #     Arguments:
    #         message (Message): messagebus message
    #     """
    #     if self.auto_brightness:
    #         time_of_day = message.data[0]
    #         level = message.data[1]
    #         self.cancel_scheduled_event(time_of_day)
    #         self.set_screen_brightness(level, speak=False)
    #         pair = self._get_auto_time()[time_of_day]
    #         self.schedule_brightness(time_of_day, pair)

    # #####################################################################
    # # Device Settings

    def handle_device_settings(self, _message):
        """Display device settings page."""
        self.emit_start_session(
            gui=("all.qml", {"state": "settings/settingspage"}),
            gui_clear=GuiClear.NEVER,
        )

    def handle_close_device_settings(self, _message):
        """Close the device settings GUI."""
        self.bus.emit(Message("mycroft.gui.idle"))

    # @intent_handler("device.reset.settings.intent")
    # def handle_device_factory_reset_settings(self, _):
    #     """Display device factory reset settings page."""
    #     self.gui["state"] = "settings/factoryreset_settings"
    #     self.gui.show_page("all.qml", override_idle=True)

    # def handle_device_update_settings(self, _):
    #     """Display device update settings page."""
    #     self.gui["state"] = "settings/updatedevice_settings"
    #     self.gui.show_page("all.qml", override_idle=True)

    def show_device_settings_about(self, _):
        """Display device update settings page."""
        # self.gui["mycroftCoreVersion"] = get_mycroft_core_version()
        # self.gui["mycroftCoreCommit"] = get_mycroft_core_commit()
        # skills_repo_path = f"{self.config_core['data_dir']}/.skills-repo"
        # self.gui["mycroftSkillsUpdateDate"] = get_skill_update_datetime(
        #     skills_repo_path
        # )
        # self.gui["deviceName"] = get_device_name()
        # self.gui["mycroftUUID"] = get_mycroft_uuid()
        # self.gui["pantacorDeviceId"] = get_pantacor_device_id() or "unknown"
        # self.gui["state"] = "settings/about"
        # self.gui.show_page("all.qml", override_idle=True)

        device_name = get_device_name()
        # mycroft_uuid = get_mycroft_uuid()
        pantacor_device_id = get_pantacor_device_id()

        network_addresses = self._request_addresses()
        network_addresses_str = "\n".join(
            f"{interface}: {address}"
            for interface, address in sorted(network_addresses.items())
        )

        self.emit_start_session(
            gui=(
                "all.qml",
                {
                    "state": "settings/about",
                    "deviceName": device_name,
                    # "mycroftUUID": mycroft_uuid,
                    "mycroftContainerBuildDate": get_mycroft_build_datetime(),
                    "pantacorDeviceId": pantacor_device_id,
                    "networkAddresses": network_addresses_str,
                },
            ),
            gui_clear=GuiClear.NEVER,
        )

    def _request_addresses(self) -> Dict[str, str]:
        addresses = {}
        response = self.bus.wait_for_response(Message("skill.ip.request-addresses"))
        if response:
            addresses = response.data

        return addresses


def create_skill(skill_id: str):
    return Mark2(skill_id=skill_id)
