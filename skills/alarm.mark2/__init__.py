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
"""Defines a skill for setting one-time or repeating alarms."""
import dataclasses
import pickle
from collections import namedtuple
from datetime import date, datetime, time, timedelta
from enum import Enum
from pathlib import Path
from time import sleep
from typing import Any, Dict, List, Optional

from mycroft.messagebus.message import Message
from mycroft.skills import (
    AdaptIntent,
    GuiClear,
    MycroftSkill,
    intent_handler,
    skill_api_method,
)
from mycroft.skills.skill_data import RegexExtractor
from mycroft.util.format import date_time_format, join_list, nice_time
from mycroft.util.parse import extract_datetime, extract_number
from mycroft.util.time import now_local, to_system

from .skill import (
    Alarm,
    AlarmMatcher,
    Alarms,
    StaticResources,
    build_day_of_week_repeat_rule,
    determine_next_occurrence,
    extract_repeat_rule,
    nice_relative_time,
)

BEEP_GAP = 10
DEFAULT_SOUND = "constant_beep"
FIVE_MINUTES = 300
USE_24_HOUR = "full"
TEN_MINUTES = 600


# TODO: Context - save the alarm found in queries as context
#   When is the next alarm
#   >  7pm tomorrow
#   Cancel it


class State(str, Enum):
    """State used to process raw_utterance"""

    SET_MISSING_TIME = "set_missing_time"
    SET_MISSING_REPEAT = "set_missing_repeat"
    CANCELLING_ALARM = "cancelling_alarm"


class AlarmValidationException(Exception):
    """This is not really for errors, just a handy way to tidy up the initial checks."""

    pass


class AlarmSkill(MycroftSkill):
    """The official Alarm Skill for Mycroft AI.

    Attributes:
        active_alarms: all alarms that have not expired or have expired and not cleared
        beep_start_time: date and time that the alarm sound began to play
        flash_state: controls the flashing of the alarm time on a Mark I
        save_path: fully qualified path of the file containing saved alarms
        sound_duration: amount of time it takes to play each sound
            The key must match an option from the 'sound' value in
            settingmeta.json, which also corresponds to the name of an mp3
            file in the sounds directory
        static_resources: words and phrases used by the skill in the configured language
    """

    def __init__(self):
        super().__init__()
        self.beep_start_time = None
        self.flash_state = 0
        self.static_resources = None
        # self.active_alarms = []
        self.active_alarms = Alarms()
        self.save_path = Path(self.file_system.path).joinpath("saved_alarms")
        self.sound_duration = dict(
            bell=5,
            escalate=32,
            constant_beep=5,
            beep4=4,
            chimes=22,
        )
        # self._state: Optional[State] = None
        self._partial_alarm: Optional[Alarm] = None
        # self._cancel_matches = None
        # self._init_skill_control()

    @property
    def expired_alarms(self) -> List[Alarm]:
        """Filters expired alarms from active alarms."""
        return list(self.active_alarms.expired)

    @property
    def alarm_sound_name(self) -> str:
        """Defines the name of the sound that will play when an alarm expires."""
        sound_name = self.settings.get("sound", DEFAULT_SOUND)
        if sound_name not in self.sound_duration:
            sound_name = DEFAULT_SOUND

        return sound_name

    @property
    def alarm_sound_path(self) -> Path:
        """Defines the location in the skill directory of the alarm sound file."""
        alarm_sound_dir = Path(__file__).parent.joinpath("sounds")
        alarm_sound_path = alarm_sound_dir.joinpath(self.alarm_sound_name + ".mp3")

        return alarm_sound_path

    @property
    def use_24_hour(self) -> bool:
        """Extracts config value indicating if 24 hour time format should be used."""
        return self.config_core.get("time_format") == USE_24_HOUR

    @property
    def _init_skill_control(self):
        """Initializes the attributes used for skill state tracking."""
        self.skill_control.category = "system"
        self.skill_control.states = dict(
            inactive=[
                "handle_wake_me",
                "handle_set_alarm",
                "handle_status",
                "handle_cancel_alarm",
                "handle_change_alarm_sound",
            ],
            active=["handle_cancel_alarm", "handle_snooze_alarm"],
            wait_reply=[],
            wait_confirm=[],
        )
        self.skill_control.state = "inactive"

    def initialize(self):
        """Executes immediately the constructor for further initialization."""
        self._load_resources()
        self._load_alarms()
        # if self.active_alarms:
        #     if self.skill_service_initializing:
        #         self.add_event("mycroft.ready", self.handle_mycroft_ready, once=True)
        #     else:
        #         self._initialize_active_alarms()
        self._initialize_active_alarms()

        # TODO: remove the "private.mycroftai.has_alarm" event in favor of the
        #   "skill.alarm.query-active" event.
        self.add_event("private.mycroftai.has_alarm", self.handle_has_alarm)
        self.add_event("skill.alarm.query-active", self.handle_active_alarm_query)
        self.add_event("skill.alarm.query-expired", self.handle_expired_alarm_query)

    def handle_mycroft_ready(self):
        """Does the things that need to happen when the device is ready for use."""
        self._clear_expired_alarms()
        self._schedule_next_alarm()
        self._send_alarm_status()

    def _initialize_active_alarms(self):
        """Shows expired alarms and schedules the next alarm when the skill loads."""
        self._clear_expired_alarms()
        self._schedule_next_alarm()
        self._send_alarm_status()

    def _load_resources(self):
        """Gets a set of static words in the language specified in the configuration."""
        date_time_format.cache(self.lang)
        date_time_translations = date_time_format.lang_config[self.lang]
        self.static_resources = StaticResources(
            all_words=self.resources.load_list_file("all"),
            and_word=self.resources.load_dialog_file("and"),
            dismiss_words=self.resources.load_list_file("dismiss"),
            midnight_words=self.resources.load_list_file("midnight"),
            months=list(date_time_translations["month"].values()),
            name_regex=self.resources.load_regex_file("name"),
            next_words=self.resources.load_list_file("next"),
            repeat_phrases=self.resources.load_vocabulary_file("recurring"),
            repeat_rules=self.resources.load_named_value_file("recurring"),
            today=self.resources.load_dialog_file("today"),
            tonight=self.resources.load_dialog_file("tonight"),
            weekdays=list(date_time_translations["weekday"].values()),
        )

    def handle_has_alarm(self, message: Message):
        """Reply to requests for alarm on/off status.

        Args:
            message: the message that triggered this event
        """
        total = len(self.active_alarms)
        self.bus.emit(message.response(data={"active_alarms": total}))

    def handle_active_alarm_query(self, message: Message):
        """Emits an event indicating whether or not there are any active alarms.

        In this case, an "active alarm" is defined as any alarms that exist for a time
        in the future.

        Args:
            message: the message that triggered this event
        """
        self.log.info(
            f"Responding to active alarm query with: {bool(self.active_alarms)}"
        )
        event_data = {"active_alarms": bool(self.active_alarms)}
        event = message.response(data=event_data)
        self.bus.emit(event)

    def handle_expired_alarm_query(self, message: Message):
        """Emits an event indicating whether or not there are any expired alarms.

        In this case, an "expired alarm" is defined as any alarms that have passed
        their trigger time and not yet been cleared.

        Args:
            message: the message that triggered this event
        """
        self.log.info(
            f"Responding to expired alarm query with: {bool(self.expired_alarms)}"
        )
        event_data = {"expired_alarms": bool(self.expired_alarms)}
        event = message.response(data=event_data)
        self.bus.emit(event)

    # -------------------------------------------------------------------------

    @intent_handler(
        AdaptIntent("")
        .require("alarm")
        .require("set")
        .optionally("recurring")
        .optionally("recurrence")
        .exclude("query")
    )
    def handle_set_alarm(self, message: Message):
        """Handles request to set alarm from utterance like "set an alarm for...".

        Args:
            message: information about the intent from the intent parser
        """
        utterance = message.data["utterance"]
        dialog = None
        gui = None

        alarm = Alarm.from_utterance(utterance, self.static_resources)
        self._partial_alarm = alarm
        self.log.debug(alarm)

        if self.active_alarms.is_duplicate_name(alarm.name):
            # Duplicate name
            dialog = "alarm-exists"
        elif not alarm.has_datetime:
            # Missing date/time
            return self.continue_session(
                dialog="ask-alarm-time",
                expect_response=True,
                state={"state": State.SET_MISSING_TIME},
            )
        elif alarm.is_missing_repeat_rule:
            # Missing a repeat rule
            return self.continue_session(
                dialog="ask-alarm-recurrence",
                expect_response=True,
                state={"state": State.SET_MISSING_REPEAT},
            )
        else:
            # We have everything we need to schedule the alarm
            self.active_alarms.add_alarm(alarm, self._build_alarm_description)
            self._save_alarms()
            self._schedule_next_alarm()
            self._send_alarm_status()

            dialog = self._speak_new_alarm(alarm)
            gui = self._display_alarms([alarm])

        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent("")
        .require("wake-me")
        .optionally("recurring")
        .optionally("recurrence")
    )
    def handle_wake_me(self, message: Message):
        """Handles request to set an alarm from utterance like "wake me at...".

        Args:
            message: information about the intent from the intent parser
        """
        return self.handle_set_alarm(message)

    @intent_handler(
        AdaptIntent("")
        .require("delete")
        .require("alarm")
        .optionally("recurring")
        .optionally("recurrence")
    )
    def handle_cancel_alarm(self, message: Message):
        """Handles request to cancel one or more alarms.

        Args:
            message: information about the intent from the intent parser
        """
        dialog = None
        gui = None

        self.log.info("Handling request to cancel alarms")
        utterance = message.data["utterance"]
        if not self.active_alarms:
            self.log.info("No active alarms to cancel")
            dialog = "no-active-alarms"
        else:
            # Determine alarms to cancel based on the utterance
            matcher = AlarmMatcher(utterance, self.active_alarms, self.static_resources)
            matches = []
            if matcher.no_match_criteria:
                # Nothing to go off of, so guess
                if self.expired_alarms:
                    self._stop_expired_alarms()
                    matches = []
                elif len(self.active_alarms) == 1:
                    # Only one alarm, so that must be it
                    matches = [self.active_alarms[0]]
                else:
                    # Need to ask user
                    alarm_descriptions = [a.description for a in self.active_alarms]
                    return self.continue_session(
                        dialog=(
                            "ask-which-alarm-delete",
                            dict(
                                number=len(self.active_alarms),
                                list=join_list(
                                    alarm_descriptions,
                                    self.static_resources.and_word[0],
                                ),
                            ),
                        ),
                        state={"state": State.CANCELLING_ALARM.value},
                        expect_response=True,
                    )
            else:
                # Match against alarms
                matcher.match()
                matches = matcher.matches

            if matches:
                if len(matches) == 1:
                    # Only one match
                    alarm = matches[0]
                    dialog_name = (
                        "cancelled-single"
                        if alarm.repeat_rule is None
                        else "cancelled-single-recurring"
                    )
                    dialog = (dialog_name, dict(desc=alarm.description))
                else:
                    # Multiple matches
                    dialog = ("cancelled-multiple", dict(count=len(matches)))

                gui = self._display_alarms(matches)
                for alarm in matches:
                    self.active_alarms.remove_alarm(alarm)
                    if alarm.expired:
                        self._stop_beeping()

                self._save_alarms()
                self._schedule_next_alarm()
                self._send_alarm_status()
            else:
                dialog = "alarm-not-found"

        return self.end_session(dialog=dialog, gui=gui)

    @intent_handler(
        AdaptIntent("")
        .require("query")
        .optionally("next")
        .require("alarm")
        .optionally("recurring")
    )
    def handle_status(self, message):
        """Report the alarms meeting the requested criteria in the utterance.

        Args:
            message: information about the intent from the intent parser
        """
        self.log.info("Handling request for alarm status")
        utterance = message.data["utterance"]
        dialog, gui = self._report_alarm_status(utterance)

        return self.end_session(dialog=dialog, gui=gui)

    def _report_alarm_status(self, utterance: str):
        """Communicates alarms that meet the request to the user

        Args:
            utterance: the status request spoken by the user
        """
        dialog = None
        gui = None

        # self.change_state("active")
        if self.active_alarms:
            matches = self._determine_which_alarms_to_report(utterance)
            if matches is not None:
                dialog, gui = self._report_matched_alarms(matches)
        else:
            dialog = "no-active-alarms"
        # self.change_state("inactive")

        return dialog, gui

    def _determine_which_alarms_to_report(self, utterance: str) -> List[Alarm]:
        """Determines which alarm(s) match the user's status request.

        Args:
            utterance: the alarm status request made by the user.

        Returns:
            all alarms that match the criteria specified by the user
        """
        matcher = AlarmMatcher(utterance, self.active_alarms, self.static_resources)
        if matcher.no_match_criteria:
            matches = self.active_alarms
        else:
            matcher.match()
            matches = matcher.matches

        return matches

    def _report_matched_alarms(self, matches: List[Alarm]):
        """Speaks and displays the alarms that match the user's status request.

        Args:
            matches: alarms that matched the user's request
        """
        dialog = None
        gui = None

        if not matches:
            dialog = "alarms.not.found"
        elif len(matches) == 1:
            dialog_name = "single-active-alarm"
            alarm = matches[0]
            relative_time = nice_relative_time(alarm.date_time)
            dialog_data = dict(item=alarm.description, duration=relative_time)
            dialog = (dialog_name, dialog_data)
        else:
            descriptions = [alarm.description for alarm in matches]
            dialog_data = dict(count=len(matches), items=descriptions)
            dialog = ("multiple-active-alarms", dialog_data)

        gui = self._display_alarms(matches)
        return dialog, gui

    # # @intent_handler("snooze.intent")
    # @intent_handler(AdaptIntent("snooze"))
    # def handle_snooze_alarm(self, message: Message):
    #     """Snooze an expired alarm for the requested time.

    #     If no time provided by user, defaults to 9 mins.
    #     """
    #     with self.activity():
    #         if self.expired_alarms:
    #             utterance = message.data["utterance"]
    #             self._snooze_alarm(utterance)

    @intent_handler(AdaptIntent().require("show").require("alarm"))
    def handle_show_alarms(self, _):
        """Handles showing the alarms screen if it is hidden."""
        dialog = None
        gui = None
        gui_clear = GuiClear.AUTO

        if self.active_alarms:
            gui = self._display_alarms(self.active_alarms)
            gui_clear = GuiClear.NEVER
        else:
            dialog = "no-active-alarms"

        return self.end_session(dialog=dialog, gui=gui, gui_clear=gui_clear)

    # -------------------------------------------------------------------------

    def _build_alarm_description(self, alarm):
        dialog_name, dialog_data = alarm.build_description_dialog(
            self.static_resources, self.use_24_hour
        )
        dialogs = self.resources.load_dialog_file(dialog_name, dialog_data)

        return dialogs[0]

    def _speak_new_alarm(self, alarm: Alarm):
        """Speaks confirmation to user that alarm was set.

        Args:
            alarm: the alarm that was set
        """
        relative_time = nice_relative_time(alarm.date_time)
        if alarm.repeat_rule is None:
            dialog = (
                "alarm-scheduled",
                {"time": alarm.description, "rel": relative_time},
            )
        else:
            dialog = (
                "alarm-scheduled-recurring",
                dict(time=alarm.description, rel=relative_time),
            )

        return dialog

    def _snooze_alarm(self, utterance: str):
        """Snoozes an alarm based on the user's request.

        Args:
            utterance: the user's snooze request
        """
        self._stop_expired_alarms()
        snooze_minutes = extract_number(utterance)
        if not snooze_minutes:
            snooze_minutes = 9
        for alarm in self.expired_alarms:
            alarm.snooze = alarm.date_time + timedelta(minutes=snooze_minutes)

    def _schedule_snooze(self):
        """Schedule the alarm to sound when the snooze time expires."""
        for alarm in self.expired_alarms:
            self.cancel_scheduled_event("SnoozeAlarm")
            if alarm.snooze:
                self.log.info("Snoozing alarm: %s", alarm.description)
                self.schedule_event(
                    self._expire_alarm, to_system(alarm.snooze), name="SnoozeAlarm"
                )
                break

    # def stop(self):
    #     """Respond to system stop commands."""
    #     if self.expired_alarms:
    #         self._stop_expired_alarms()
    #         return True
    #     else:
    #         return False

    def _display_expired_alarms(self):
        """Displays the alarms that have expired upon their expiration."""
        gui = self._display_alarms(self.expired_alarms)
        self.emit_start_session(gui=gui)

    def _display_alarms(self, alarms: List[Alarm]):
        """Displays the alarms matching a set, cancel or status request.

        Args:
            alarms: the alarms to display
        """
        gui_page = "alarm_mark_ii.qml"
        gui_data = {}

        display_data = []
        for index, alarm in enumerate(alarms):
            alarm_display = alarm.format_for_display(
                index, self.static_resources, use_24_hour=self.use_24_hour
            )
            display_data.append(alarm_display)
        if alarms:
            gui_data["activeAlarms"] = dict(alarms=display_data)
            gui_data["activeAlarmCount"] = len(alarms)

        return gui_page, gui_data

    def _pause_expired_alarms(self):
        """Pause showing expired alarms when snoozing."""
        self.log.info("Stopping expired alarm")
        self._stop_beeping()
        self._save_alarms()

    def _stop_expired_alarms(self):
        """Stop communicating expired alarms to the user."""
        self.log.info("Stopping expired alarm")
        self._stop_beeping()
        self._clear_expired_alarms()
        self._schedule_next_alarm()
        self._save_alarms()
        self._send_alarm_status()

    def _stop_beeping(self):
        """Stop playing the beeping sound that plays when an alarm expires."""
        self.log.info("Stopping expired alarm sound")
        self.cancel_scheduled_event("AlarmBeep")
        self.beep_start_time = None

    def _clear_expired_alarms(self):
        """The remove expired alarms from the list of active alarms."""
        self.active_alarms.clear_expired()
        # for alarm in self.expired_alarms:
        #     if alarm.repeat_rule is None:
        #         self.active_alarms.remove(alarm)
        #     else:
        #         alarm.date_time = determine_next_occurrence(
        #             alarm.repeat_rule, alarm.date_time
        #         )
        # self.active_alarms.sort(key=lambda _alarm: _alarm.date_time)

    def _schedule_next_alarm(self):
        local_date_time = now_local()
        for alarm in self.active_alarms:
            self.cancel_scheduled_event("NextAlarm")
            if alarm.date_time > local_date_time:
                self.log.info(f"Scheduling alarm: {alarm.description}")
                self.schedule_event(
                    self._expire_alarm, to_system(alarm.date_time), name="NextAlarm"
                )
                self._send_alarm_status()
                break

    def _expire_alarm(self):
        """When an alarm expires, show it on the display and play a sound."""
        # self.change_state("active")
        expired_alarm = self.expired_alarms[-1]
        self.log.info(f"Alarm expired at {expired_alarm.date_time.time()}")
        self._schedule_alarm_sound()
        self._display_expired_alarms()
        self._schedule_next_alarm()
        # self.change_state("inactive")

    def _schedule_alarm_sound(self):
        """Schedules and event to play the sound configured by the user."""
        self.cancel_scheduled_event("AlarmBeep")
        self.beep_start_time = datetime.now()
        self.schedule_repeating_event(
            self._play_alarm_sound,
            when=datetime.now(),
            frequency=self.sound_duration[self.alarm_sound_name] + BEEP_GAP,
            name="AlarmBeep",
        )

    def _play_alarm_sound(self):
        """Plays the alarm sound for an expired alarm."""
        self._send_beep_playing_event()
        stop_beeping = self._check_max_beeping_time()
        if stop_beeping:
            self._stop_expired_alarms()
        else:
            alarm_uri = f"file://{self.alarm_sound_path}"
            self.play_sound_uri(alarm_uri)

    def _send_beep_playing_event(self):
        """Emits an event on the message bus indicating the beep is playing."""
        beeping_message = Message(
            "mycroft.alarm.beeping",
            data=dict(time=datetime.now().strftime("%m/%d/%Y, %H:%M:%S")),
        )
        self.bus.emit(beeping_message)

    def _check_max_beeping_time(self):
        """Stops the alarm beeping loop after a period of time."""
        # TODO: make max beeping time configurable
        elapsed_beep_time = (datetime.now() - self.beep_start_time).total_seconds()
        if elapsed_beep_time > TEN_MINUTES:
            self.log.info(
                "Maximum alarm sound time exceeded, automatically quieting alarm"
            )
            stop_beeping = True
        else:
            stop_beeping = False

        return stop_beeping

    def _send_alarm_status(self):
        """Emits a message on the bus communicating the existence of active alarms."""
        event_data = {"active_alarms": bool(self.active_alarms)}
        event = Message("skill.alarm.status", data=event_data)
        self.bus.emit(event)

    def _load_alarms(self):
        """Load any saved alarms into the active alarms list."""
        # self.active_alarms = list()
        # if self.save_path.exists():
        #     with open(self.save_path, "rb") as data_file:
        #         self.active_alarms = pickle.load(data_file)
        self.active_alarms = Alarms.load(self.save_path)

    def _save_alarms(self):
        self.active_alarms.save(self.save_path)

    # -------------------------------------------------------------------------

    def raw_utterance(
        self, utterance: Optional[str], state: Optional[Dict[str, Any]]
    ) -> Optional[Message]:
        if self.voc_match(utterance, "cancel"):
            self.log.debug("Cancelled user response")
            return

        dialog = None
        gui = None

        state = state or {}
        state_name = state.get("state")

        alarm_complete = False
        if state_name in {State.SET_MISSING_TIME, State.SET_MISSING_REPEAT}:
            # Setting an alarm, but we're missing some information
            if state_name == State.SET_MISSING_TIME:
                # Fill in missing date/time.
                # May still be missing repeat rule.
                (
                    self._partial_alarm.date_time,
                    _remaining_utterance,
                ) = Alarm.datetime_from_utterance(utterance, self.static_resources)
                self.log.debug(self._partial_alarm)

                if not self._partial_alarm.has_datetime:
                    # Failed to parse date/time
                    dialog = "alarm-not-scheduled"
                elif self._partial_alarm.is_missing_repeat_rule:
                    # Still missing a repeat rule
                    return self.continue_session(
                        dialog="ask-alarm-recurrence",
                        expect_response=True,
                        state={"state": State.SET_MISSING_REPEAT},
                    )
                else:
                    alarm_complete = True
            elif state_name == State.SET_MISSING_REPEAT:
                # Fill in missing repeat rule
                self._partial_alarm.repeat_rule = build_day_of_week_repeat_rule(
                    utterance, self.static_resources.repeat_rules
                )
                self.log.debug(self._partial_alarm)

                if not self._partial_alarm.has_repeat_rule:
                    # Failed to parse repeat rule
                    dialog = "alarm-not-scheduled"
                else:
                    alarm_complete = True

            if alarm_complete:
                # We have enough information to schedule the alarm
                alarm = self._partial_alarm
                self._partial_alarm = None

                self.active_alarms.add_alarm(alarm, self._build_alarm_description)
                self._save_alarms()
                self._schedule_next_alarm()
                self._send_alarm_status()

                dialog = self._speak_new_alarm(alarm)
                gui = self._display_alarms([alarm])
        elif state_name == State.CANCELLING_ALARM:
            # Cancelling an alarm, but it's ambiguous which one
            matcher = AlarmMatcher(utterance, self.active_alarms, self.static_resources)
            matcher.match()
            matches = matcher.matches
            if matches:
                if len(matches) == 1:
                    alarm = matches[0]
                    dialog_name = (
                        "cancelled-single"
                        if alarm.repeat_rule is None
                        else "cancelled-single-recurring"
                    )
                    dialog = (dialog_name, dict(desc=alarm.description))
                else:
                    dialog = ("cancelled-multiple", dict(count=len(matches)))

                gui = self._display_alarms(matches)
                for alarm in matches:
                    self.active_alarms.remove_alarm(alarm)
                    if alarm.expired:
                        self._stop_beeping()

                self._save_alarms()
                self._schedule_next_alarm()
                self._send_alarm_status()
            else:
                # No matches
                dialog = "alarms.not.found"

        return self.end_session(dialog=dialog, gui=gui)

    ####################################################
    #### SKILL API METHODS FOR VOIGHT KAMPF TESTING ####
    ####################################################

    # @skill_api_method
    # def _create_single_test_alarm(self, utterance: str):
    #     """For test setup only - create a single alarm.

    #     This replicates `_set_new_alarm` but:
    #     - does not speak or display anything
    #     - does not save the created alarms to disk
    #     - does not pre-cache TTS for follow up queries.

    #     It should only be used in Given VK steps as this sets the state of the
    #     system for the test. It should never be used in a When or Then step.

    #     Args:
    #         utterance: detail of alarm to create
    #     """
    #     self.change_state("active")
    #     try:
    #         alarm = self._build_alarm(utterance)
    #     except AlarmValidationException as exc:
    #         self.log.error(str(exc))
    #         self.change_state("inactive")
    #     else:
    #         # alarm datetime should only be None here if the user was asked for
    #         # the date and time of the alarm and responded with "nevermind"
    #         if alarm.date_time is not None:
    #             self.active_alarms.append(alarm)
    #             self.active_alarms.sort(key=lambda _alarm: _alarm.date_time)
    #             self._schedule_next_alarm()
    #         self.change_state("inactive")

    # @skill_api_method
    # def _cancel_all_alarms(self):
    #     """For test setup only - cancel all alarms that exist.

    #     This replicates a particular flow of `_cancel_alarms` but:
    #     - does not speak or display anything
    #     - does not save changes to disk
    #     - does not update pre-cached TTS.

    #     It should only be used in Given VK steps as this sets the state of the
    #     system for the test. It should never be used in a When or Then step.
    #     """
    #     self.change_state("active")
    #     self._stop_beeping()
    #     self.active_alarms = []
    #     self.cancel_scheduled_event("NextAlarm")
    #     self._send_alarm_status()
    #     self.change_state("inactive")

    @skill_api_method
    def get_number_of_active_alarms(self) -> int:
        """Get the number of active alarms."""
        return len(self.active_alarms)


def create_skill():
    """Create the Alarm Skill for Mycroft."""
    return AlarmSkill()
