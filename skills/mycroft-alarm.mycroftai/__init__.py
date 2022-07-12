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
import pickle
from collections import namedtuple
from datetime import date, datetime, timedelta, time
from pathlib import Path
from time import sleep
from typing import List, Optional

from mycroft.messagebus.message import Message
from mycroft.skills import AdaptIntent, intent_handler, MycroftSkill, skill_api_method
from mycroft.skills.skill_data import RegexExtractor
from mycroft.util.format import nice_time, join_list, date_time_format
from mycroft.util.parse import extract_datetime, extract_number
from mycroft.util.time import now_local, to_system

from .skill import (
    Alarm,
    AlarmMatcher,
    build_day_of_week_repeat_rule,
    determine_next_occurrence,
    nice_relative_time,
)

BEEP_GAP = 10
DEFAULT_SOUND = "constant_beep"
FIVE_MINUTES = 300
MARK_I = "mycroft_mark_1"
MARK_II = "mycroft_mark_2"
USE_24_HOUR = "full"
TEN_MINUTES = 600

StaticResources = namedtuple(
    "StaticResources",
    [
        "all_words",
        "and_word",
        "dismiss_words",
        "midnight_words",
        "months",
        "name_regex",
        "next_words",
        "repeat_phrases",
        "repeat_rules",
        "today",
        "tonight",
        "weekdays",
    ],
)

# TODO: Context - save the alarm found in queries as context
#   When is the next alarm
#   >  7pm tomorrow
#   Cancel it


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
        self.active_alarms = []
        self.save_path = Path(self.file_system.path).joinpath("saved_alarms")
        self.sound_duration = dict(
            bell=5,
            escalate=32,
            constant_beep=5,
            beep4=4,
            chimes=22,
        )
        self._init_skill_control()

    @property
    def expired_alarms(self) -> List[Alarm]:
        """Filters expired alarms from active alarms."""
        return [alarm for alarm in self.active_alarms if alarm.expired]

    @property
    def alarm_sound_name(self) -> str:
        """Defines the name of the sound that will play when an alarm expires."""
        sound_name = self.settings["sound"]
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
        return self.config_core.get("time_format") == "full"

    @property
    def platform(self) -> str:
        """Extracts the name of the device platform from the configuration."""
        return self.config_core["enclosure"].get("platform", "unknown")

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
        if self.active_alarms:
            if self.skill_service_initializing:
                self.add_event("mycroft.ready", self.handle_mycroft_ready, once=True)
            else:
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
        if self.expired_alarms:
            self._display_expired_alarms()
        self._schedule_next_alarm()

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
        with self.activity():
            utterance = message.data["utterance"]
            self._set_new_alarm(utterance)

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
        with self.activity():
            utterance = message.data["utterance"]
            self._set_new_alarm(utterance)

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
        with self.activity():
            self.log.info("Handling request to cancel alarms")
            utterance = message.data["utterance"]
            self._cancel_alarms(utterance)

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
        with self.activity():
            self.log.info("Handling request for alarm status")
            utterance = message.data["utterance"]
            self._report_alarm_status(utterance)

    # @intent_handler("snooze.intent")
    @intent_handler(AdaptIntent("snooze"))
    def handle_snooze_alarm(self, message: Message):
        """Snooze an expired alarm for the requested time.

        If no time provided by user, defaults to 9 mins.
        """
        with self.activity():
            if self.expired_alarms:
                utterance = message.data["utterance"]
                self._snooze_alarm(utterance)

    @intent_handler("change.alarm.sound.intent")
    def handle_change_alarm_sound(self, _):
        """Handles requests to change the alarm sound.

        Note: This functionality is not yet supported. Directs users to Skill
        settings on home.mycroft.ai.
        """
        with self.activity():
            self.speak_dialog("change-sound", wait=True)

    @intent_handler(AdaptIntent().require("show").require("alarm"))
    def handle_show_alarms(self, _):
        """Handles showing the alarms screen if it is hidden."""
        with self.activity():
            if self.active_alarms:
                self._display_alarms(self.active_alarms)
            else:
                self.speak_dialog("no-active-alarms", wait=True)

    def _set_new_alarm(self, utterance):
        """Start a new alarm as requested by the user.

        Args:
            utterance: the request uttered by the user
        """
        self.change_state("active")
        try:
            alarm = self._build_alarm(utterance)
        except AlarmValidationException as exc:
            self.log.info(str(exc))
            self.speak_dialog("alarm-not-scheduled", wait=True)
        else:
            # alarm datetime should only be None here if the user was asked for
            # the date and time of the alarm and responded with "nevermind"
            if alarm.date_time is not None:
                self.active_alarms.append(alarm)
                self.active_alarms.sort(key=lambda _alarm: _alarm.date_time)
                self._speak_new_alarm(alarm)
                self._display_alarms([alarm])
                self._clear_display_after_speaking()
                self._schedule_next_alarm()
                self._save_alarms()
        finally:
            self.change_state("inactive")

    def _build_alarm(self, utterance: str) -> Alarm:
        """Build an alarm from a validated request for a new alarm.

        Args:
            utterance: the text representing the user's request for a alarm

        Returns:
            The duration of the alarm and the name, if one is specified.

        Raises:
            AlarmValidationError when any of the checks do not pass.
        """
        alarm_datetime, remaining_utterance = self._determine_alarm_datetime(utterance)
        self._check_for_alarm_in_past(utterance, alarm_datetime)
        alarm_name = self._determine_alarm_name(remaining_utterance)
        alarm_repeat_rule = self._check_for_repeat(utterance)
        alarm = Alarm(alarm_name, alarm_datetime, alarm_repeat_rule)
        alarm.description = self._build_alarm_description(alarm)
        self._check_for_duplicate(alarm)

        return alarm

    def _determine_alarm_datetime(self, utterance: str):
        """Interrogate the utterance to determine the duration of the alarm.

        If the duration of the alarm cannot be determined when interrogating the
        initial utterance, the user will be asked to specify one.

        Args:
            utterance: the text representing the user's request for a alarm

        Returns:
            The duration of the alarm and the remainder of the utterance after the
            duration has been extracted.

        Raises:
            AlarmValidationException when no duration can be determined.
        """
        extract = extract_datetime(utterance)
        if extract is None:
            alarm_datetime = self._request_alarm_datetime()
            remaining_utterance = utterance
        else:
            alarm_datetime, remaining_utterance = extract
            if alarm_datetime.time() == time(0):
                midnight_in_utterance = self._check_for_midnight(
                    utterance, alarm_datetime
                )
                if not midnight_in_utterance:
                    alarm_datetime = self._request_alarm_datetime()

        self._check_for_alarm_in_past(utterance, alarm_datetime)
        # Lingua Franca will return a date of today if no date is specified.
        # If user says "set an alarm for 10:00 AM" and it is noon, assume the user
        # meant tomorrow at 10:00 AM
        if alarm_datetime <= now_local():
            alarm_datetime += timedelta(days=1)
        self.log.info(f"Alarm date and time requested by user: {alarm_datetime}")
        return alarm_datetime, remaining_utterance

    def _check_for_midnight(self, utterance: str, alarm_datetime: datetime) -> bool:
        """Determines if the user requested a midnight alarm.

        If the user requested a repeating alarm but did not specify the time (e.g.
        "set an alarm for Wednesdays"), the time portion of the alarm datetime would
        be zero.  In this scenario, check that the user didn't specify a midnight alarm.

        Args:
            utterance: utterance from user
            alarm_datetime: datetime extracted from utterance

        Returns:
            Boolean indicating whether user requested an alarm be set for midnight
        """
        # TODO extract_datetime from utterance rather than passing it in
        midnight_requested = any(
            [word in utterance for word in self.static_resources.midnight_words]
        )
        matched = (alarm_datetime.time() == time(0)) and midnight_requested

        return matched

    def _request_alarm_datetime(self) -> datetime:
        """The utterance did not include the date and time of the alarm so ask for it.

        Returns:
            date and time of alarm as specified by the user

        Raises:
            AlarmValidationException when the user does not supply a date and/or time
        """
        response = self.get_response(
            "ask-alarm-time", validator=self._validate_response_has_datetime
        )
        if response is None:
            raise AlarmValidationException("No duration specified")
        else:
            extract = extract_datetime(response)
            if extract is None:
                alarm_datetime = None
            else:
                alarm_datetime = extract[0]

            if alarm_datetime is None:
                raise AlarmValidationException("No duration specified")

        return alarm_datetime

    def _validate_response_has_datetime(self, utterance: str) -> bool:
        """Validate a response contains an extractable datetime or dismissal.

        Note: Using extract_datetime directly as a validator prevents the use
        of custom dismissal vocab. General terms included in core like
        'cancel' will work, but this validator adds anything in dismiss.list
        """
        extracted_dt = extract_datetime(utterance) is not None
        dismissed = any(
            [word in utterance for word in self.static_resources.dismiss_words]
        )
        return extracted_dt or dismissed

    def _check_for_alarm_in_past(self, utterance: str, alarm_datetime: datetime):
        """Determines if the requested alarm date and time is in the past

        Args:
            utterance:  alarm request spoken by user
            alarm_datetime: the date and time extracted from the utterance

        Raises:
            AlarmValidationException if the request was for a date and time in the past
        """
        alarm_in_past = False
        if alarm_datetime <= now_local():
            if alarm_datetime.date() == date.today():
                today_in_utterance = (
                    self.static_resources.today[0] in utterance
                    or self.static_resources.tonight[0] in utterance
                )
                if today_in_utterance:
                    alarm_in_past = True
            else:
                alarm_in_past = True
        if alarm_in_past:
            self.speak_dialog("alarm-in-past")
            raise AlarmValidationException("Requested alarm in the past")

    def _determine_alarm_name(self, remaining_utterance):
        name_extractor = RegexExtractor("name", self.static_resources.name_regex)
        alarm_name = name_extractor.extract(remaining_utterance)
        if alarm_name is None:
            alarm_name = self._assign_alarm_name()

        return alarm_name

    def _assign_alarm_name(self) -> str:
        """Assign a name to a alarm when the user does not specify one.

        All alarms will have a name. If the user does not request one, assign a name
        using the "Alarm <unnamed alarm number>" convention.

        When there is only one alarm active and it is assigned a name, the name
        "Alarm" will be used.  If another alarm without a requested name is added,
        the alarm named "Alarm" will have its name changed to "Alarm 1" and the new
        alarm will be named "Alarm 2"

        Returns:
            The name assigned to the alarm.
        """
        if self.active_alarms:
            max_assigned_number = 0
            for alarm in self.active_alarms:
                if alarm.name == "alarm":
                    # Change existing alarm to alarm 1
                    alarm.name = "alarm 1"
                    alarm.description = self._build_alarm_description(alarm)
                    max_assigned_number = 1
                elif alarm.name.startswith("alarm "):
                    _, name_number = alarm.name.split()
                    name_number = int(name_number)
                    if name_number > max_assigned_number:
                        max_assigned_number = name_number
            new_alarm_number = max_assigned_number + 1
            alarm_name = "alarm " + str(new_alarm_number)
        else:
            alarm_name = "alarm"

        return alarm_name

    def _check_for_repeat(self, utterance):
        """Get repeat pattern from user utterance.

        Most of the time the user will specify which days the alarm should recur
        in the request to set the alarm. There are a couple of ways a user could
        request a recurring alarm ambiguously (e.g. "set a recurring alarm").
        So, we check for the existence of recurrence first, then ask for disambiguation
        if necessary.
        """
        repeat_rule = None
        repeat_in_utterance = any(
            [repeat[0] in utterance for repeat in self.static_resources.repeat_phrases]
        )
        if repeat_in_utterance:
            repeat_rule = build_day_of_week_repeat_rule(
                utterance, self.static_resources.repeat_rules
            )
            if repeat_rule is None:
                response = self.get_response("ask-alarm-recurrence")
                if response:
                    repeat_rule = build_day_of_week_repeat_rule(
                        response, self.static_resources.repeat_rules
                    )

        # TODO: remove days following an "except" in the utterance
        if self.voc_match(utterance, "except"):
            self.speak_dialog("no-exceptions-yet", wait=True)

        return repeat_rule

    def _check_for_duplicate(self, alarm: Alarm):
        """Determine if the requested alarm duplicates an existing alarm.

        No two alarms can be named the same and no two alarms can have the same
        datetime and repeat values

        Args:
            alarm: The alarm requested by the user

        Raises:
            AlarmValidationException if duplication is found
        """
        duplicate_alarm_found = False
        duplicate_name_found = False
        for existing in self.active_alarms:
            if alarm.name is not None and existing.name == alarm.name:
                duplicate_name_found = True
            duplicate_alarm_found = (
                existing.date_time == alarm.date_time
                and existing.repeat_rule == alarm.repeat_rule
            )
            if duplicate_alarm_found or duplicate_name_found:
                break

        if duplicate_alarm_found:
            self.speak_dialog("alarm-exists", wait=True)
            raise AlarmValidationException("Requested alarm already exists")

        if duplicate_name_found:
            self.speak_dialog("alarm-exists", wait=True)
            raise AlarmValidationException(f"Alarm named '{alarm.name}' already exists")

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
            self.speak_dialog(
                "alarm-scheduled",
                data={"time": alarm.description, "rel": relative_time},
            )
        else:
            self.speak_dialog(
                "alarm-scheduled-recurring",
                data=dict(time=alarm.description, rel=relative_time),
            )

    def _cancel_alarms(self, utterance: str):
        """Handle a user's request to cancel one or more alarms.

        Args:
            utterance: the user's request
        """
        self.change_state("active")
        try:
            if self.active_alarms:
                matches = self._determine_which_alarms_to_cancel(utterance)
                if matches is not None:
                    self._cancel_requested_alarms(matches)
                    self._save_alarms()
                    if self.active_alarms:
                        self._schedule_next_alarm()
                    else:
                        self.cancel_scheduled_event("NextAlarm")
                        self._send_alarm_status()
            else:
                self.log.info("No active alarms to cancel")
                self.speak_dialog("no-active-alarms", wait=True)
        except Exception:
            pass
        finally:
            self.change_state("inactive")

    def _determine_which_alarms_to_cancel(self, utterance: str) -> List[Alarm]:
        """Determines which alarm(s) match the user's cancel request.

        Args:
            utterance: The alarm cancellation request made by the user.

        Returns:
            All alarms that match the criteria specified by the user.
        """
        matcher = AlarmMatcher(utterance, self.active_alarms, self.static_resources)
        if matcher.no_match_criteria:
            if self.expired_alarms:
                self._stop_expired_alarms()
                matches = []
            elif len(self.active_alarms) == 1:
                matches = [self.active_alarms[0]]
            else:
                matches = self._disambiguate_request(question="ask-which-alarm-delete")
        else:
            matcher.match()
            matches = matcher.matches

        return matches

    def _cancel_requested_alarms(self, matches: List[Alarm]):
        """Cancels the alarms that matched the user's requests.

        Args:
            matches: the alarms that matched the request
        """
        if not matches:
            self.speak_dialog("alarms.not.found")
        elif len(matches) == 1:
            self._cancel_one(matches[0])
        else:
            self._cancel_multiple(matches)

    def _cancel_one(self, alarm: Alarm):
        """Cancel a single alarm.

        Args:
            alarm: the alarm to cancel
        """
        if alarm.repeat_rule is None:
            dialog = "cancelled-single"
        else:
            dialog = "cancelled-single-recurring"
        self.speak_dialog(dialog, data=dict(desc=alarm.description))
        self._display_alarms([alarm])
        self.log.info(f"Cancelling alarm {alarm.description}")
        if alarm in self.expired_alarms:
            self._stop_beeping()
        self.active_alarms.remove(alarm)
        self._clear_display_after_speaking()

    def _cancel_multiple(self, alarms: List[Alarm]):
        """Cancels multiple alarms.

        Args:
            alarms: the alarms to cancel
        """
        self.speak_dialog("cancelled-multiple", data=dict(count=len(alarms)))
        self._display_alarms(alarms)
        for alarm in alarms:
            self.log.info(f"Cancelling alarm {alarm.description}")
            if alarm in self.expired_alarms:
                self._stop_beeping()
            self.active_alarms.remove(alarm)
        self._clear_display_after_speaking()

    def _report_alarm_status(self, utterance: str):
        """Communicates alarms that meet the request to the user

        Args:
            utterance: the status request spoken by the user
        """
        self.change_state("active")
        if self.active_alarms:
            matches = self._determine_which_alarms_to_report(utterance)
            if matches is not None:
                self._report_matched_alarms(matches)
        else:
            self.speak_dialog("no-active-alarms")
        self.change_state("inactive")

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
        if not matches:
            self.speak_dialog("alarms.not.found")
        elif len(matches) == 1:
            dialog_name = "single-active-alarm"
            alarm = matches[0]
            relative_time = nice_relative_time(alarm.date_time)
            dialog_data = dict(item=alarm.description, duration=relative_time)
            self.speak_dialog(dialog_name, dialog_data)
        else:
            descriptions = [alarm.description for alarm in matches]
            dialog_data = dict(count=len(matches), items=descriptions)
            self.speak_dialog("multiple-active-alarms", dialog_data)
        self._display_alarms(matches)
        self._clear_display_after_speaking()

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
                self.log.info(f"Snoozing alarm: {alarm.description}")
                self.schedule_event(
                    self._expire_alarm, to_system(alarm.snooze), name="SnoozeAlarm"
                )
                break

    def stop(self):
        """Respond to system stop commands."""
        if self.expired_alarms:
            self._stop_expired_alarms()
            return True
        else:
            return False

    def _disambiguate_request(self, question):
        """Disambiguate a generic user request.

        Args:
            question: the disambiguation question to ask the user
        """
        matches = None
        reply = self._ask_which_alarm(self.active_alarms, question)
        if reply is not None:
            matcher = AlarmMatcher(reply, self.active_alarms, self.static_resources)
            if matcher.no_match_criteria:
                self.speak_dialog("alarm-not-found")
            else:
                matcher.match()
                matches = matcher.matches

        return matches

    def _ask_which_alarm(self, alarms: List[Alarm], question: str) -> Optional[str]:
        """Asks the user to provide more information about the alarm(s) requested.

        Args:
            alarms: list of alarms that needs to be filtered using the answer
            question: name of the dialog file containing the question to be asked

        Returns:
            the reply given by the user
        """
        alarm_descriptions = [alarm.description for alarm in alarms]
        dialog_data = dict(
            number=len(alarms),
            list=join_list(alarm_descriptions, self.static_resources.and_word[0]),
        )
        reply = self.get_response(dialog=question, data=dialog_data)

        if reply is not None:
            if any(word in reply for word in self.static_resources.dismiss_words):
                reply = None

        return reply

    def _display_expired_alarms(self):
        """Displays the alarms that have expired upon their expiration."""
        self._display_alarms(self.expired_alarms)

    def _display_alarms(self, alarms: List[Alarm]):
        """Displays the alarms matching a set, cancel or status request.

        Args:
            alarms: the alarms to display
        """
        if self.platform == MARK_I:
            self._show_on_faceplate(alarms[0])
        elif self.gui.connected:
            self._show_on_screen(alarms)

    def _clear_display_after_speaking(self):
        """Clears the GUI displaying on the screen after the dialog has been spoken."""
        if self.gui.connected:
            # TODO
            # wait_while_speaking()
            self.gui.release()

    def _show_on_faceplate(self, alarm):
        """Animated confirmation of the alarm.

        Args:
            alarm: the alarm to display on the faceplate
        """
        self.enclosure.deactivate_mouth_events()
        self.enclosure.mouth_reset()
        self._render_time_on_faceplate(alarm.date_time)
        sleep(2)
        self.enclosure.mouth_reset()
        self._show_alarm_animation()
        self.enclosure.mouth_reset()

    def _render_time_on_faceplate(self, alarm_datetime):
        """Show the time in numbers (e.g. "8:00 AM") on a faceplate.

        Args:
            alarm_datetime: the date and time of the alarm to display
        """
        display_time = nice_time(
            alarm_datetime, speech=False, use_ampm=True, use_24hour=self.use_24_hour
        )
        x_coordinate = 16 - ((len(display_time) * 4) // 2)  # centers on display
        if not self.use_24_hour:
            x_coordinate += 1  # account for wider letters P and M, offset by the colon

        for character in display_time:
            if character == ":":
                image = "colon.png"
                character_width = 2
            elif character == " ":
                image = "blank.png"
                character_width = 2
            elif character in ("A", "P", "M"):
                image = character + ".png"
                character_width = 5
            else:
                image = character + ".png"
                character_width = 4

            image_file = Path(__file__).parent.joinpath("anim", image)
            self.enclosure.mouth_display_png(
                image_file, x=x_coordinate, y=2, refresh=False
            )
            x_coordinate += character_width

    def _show_alarm_animation(self):
        # Show an animation
        # TODO: mouth_display_png() is choking images > 8x8
        #       (likely on the enclosure side)
        image_dir = Path(__file__).parent
        display_kwargs = dict(x=0, y=0, refresh=False, invert=True)
        for index in range(1, 16):
            image_path = image_dir.joinpath("anim", "Alarm-" + str(index) + "-2.png")
            if index < 8:
                display_kwargs.update(x=8)
                self.enclosure.mouth_display_png(image_path, **display_kwargs)
            image_path = image_dir.joinpath("anim", "Alarm-" + str(index) + "-3.png")
            display_kwargs.update(x=16)
            self.enclosure.mouth_display_png(image_path, **display_kwargs)
            image_path = image_dir.joinpath("anim", "Alarm-" + str(index) + "-4.png")
            display_kwargs.update(x=24)
            self.enclosure.mouth_display_png(image_path, **display_kwargs)
            if index == 4:
                sleep(1)
            else:
                sleep(0.15)

    def _show_on_screen(self, alarms: List[Alarm]):
        """Update the device's display to show the status of active alarms.

        Args:
            alarms: the alarms to show on the display
        """
        display_data = []
        for index, alarm in enumerate(alarms):
            alarm_display = alarm.format_for_display(
                index, self.static_resources, use_24_hour=self.use_24_hour
            )
            display_data.append(alarm_display)
        if alarms:
            self.gui["activeAlarms"] = dict(alarms=display_data)
            self.gui["activeAlarmCount"] = len(alarms)
        if self.platform == MARK_II:
            page = "alarm_mark_ii.qml"
        else:
            page = "alarm_scalable.qml"
        self.gui.show_page(page, override_idle=True)

    def _pause_expired_alarms(self):
        """Pause showing expired alarms when snoozing."""
        self.log.info("Stopping expired alarm")
        self._stop_beeping()
        self._clear_expired_alarm_display()
        self._save_alarms()

    def _stop_expired_alarms(self):
        """Stop communicating expired alarms to the user."""
        self.log.info("Stopping expired alarm")
        self._stop_beeping()
        self._clear_expired_alarm_display()
        self._clear_expired_alarms()
        self._schedule_next_alarm()
        self._save_alarms()
        self._send_alarm_status()

    def _stop_beeping(self):
        """Stop playing the beeping sound that plays when an alarm expires."""
        self.log.info("Stopping expired alarm sound")
        self.cancel_scheduled_event("AlarmBeep")
        self.beep_start_time = None

    def _clear_expired_alarm_display(self):
        """Remove expired alarms from the display."""
        if self.platform == MARK_I:
            self.log.info("Stopping faceplate flashing")
            self.cancel_scheduled_event("Flash")
            self.enclosure.mouth_reset()
            self.enclosure.activate_mouth_events()
        elif self.gui.connected:
            self.gui.release()

    def _clear_expired_alarms(self):
        """The remove expired alarms from the list of active alarms."""
        for alarm in self.expired_alarms:
            if alarm.repeat_rule is None:
                self.active_alarms.remove(alarm)
            else:
                alarm.date_time = determine_next_occurrence(
                    alarm.repeat_rule, alarm.date_time
                )
        self.active_alarms.sort(key=lambda _alarm: _alarm.date_time)

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
        self.change_state("active")
        expired_alarm = self.expired_alarms[-1]
        self.log.info(f"Alarm expired at {expired_alarm.date_time.time()}")
        self._schedule_alarm_sound()
        self._display_expired_alarms()
        if self.platform == MARK_I:
            self._schedule_faceplate_flashing()
        self._schedule_next_alarm()
        self.change_state("inactive")

    def _schedule_faceplate_flashing(self):
        """Schedules an event to flash the alarm on the faceplate once a second."""
        self.flash_state = 0
        self.schedule_repeating_event(
            self._flash_faceplate, when=None, frequency=1, name="Flash"
        )

    def _flash_faceplate(self):
        """Flashes the time on the faceplate on and off when an alarm is expired."""
        if self.flash_state < 3:
            if self.flash_state == 0:
                self._render_time_on_faceplate(self.expired_alarms[0].date_time)
            self.flash_state += 1
        else:
            self.enclosure.mouth_reset()
            self.flash_state = 0

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
            alarm_uri = f"file://{str(self.alarm_sound_path)}"
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

    def _save_alarms(self):
        """Write a serialized version of the data to the specified file name."""
        if self.active_alarms:
            with open(self.save_path, "wb") as data_file:
                pickle.dump(self.active_alarms, data_file, pickle.HIGHEST_PROTOCOL)
        else:
            if self.save_path.exists():
                self.save_path.unlink()

        # Non-blocking execution of caching
        now = 0
        self.schedule_event(self._cache_cancel_alarm_tts, now)

    def _load_alarms(self):
        """Load any saved alarms into the active alarms list."""
        self.active_alarms = list()
        if self.save_path.exists():
            with open(self.save_path, "rb") as data_file:
                self.active_alarms = pickle.load(data_file)

        self._cache_cancel_alarm_tts()

    def _cache_cancel_alarm_tts(self):
        alarms = self.active_alarms
        if len(alarms) > 1:
            cache_key = f"{self.skill_id}.cancel-alarm"
            alarm_descriptions = [alarm.description for alarm in alarms]
            dialog_data = dict(
                number=len(alarms),
                list=join_list(alarm_descriptions, self.static_resources.and_word[0]),
            )
            self.cache_dialog(
                "ask-which-alarm-delete", data=dialog_data, cache_key=cache_key
            )

    ####################################################
    #### SKILL API METHODS FOR VOIGHT KAMPF TESTING ####
    ####################################################

    @skill_api_method
    def _create_single_test_alarm(self, utterance: str):
        """For test setup only - create a single alarm.

        This replicates `_set_new_alarm` but:
        - does not speak or display anything
        - does not save the created alarms to disk
        - does not pre-cache TTS for follow up queries.

        It should only be used in Given VK steps as this sets the state of the
        system for the test. It should never be used in a When or Then step.

        Args:
            utterance: detail of alarm to create
        """
        self.change_state("active")
        try:
            alarm = self._build_alarm(utterance)
        except AlarmValidationException as exc:
            self.log.error(str(exc))
            self.change_state("inactive")
        else:
            # alarm datetime should only be None here if the user was asked for
            # the date and time of the alarm and responded with "nevermind"
            if alarm.date_time is not None:
                self.active_alarms.append(alarm)
                self.active_alarms.sort(key=lambda _alarm: _alarm.date_time)
                self._schedule_next_alarm()
            self.change_state("inactive")

    @skill_api_method
    def _cancel_all_alarms(self):
        """For test setup only - cancel all alarms that exist.

        This replicates a particular flow of `_cancel_alarms` but:
        - does not speak or display anything
        - does not save changes to disk
        - does not update pre-cached TTS.

        It should only be used in Given VK steps as this sets the state of the
        system for the test. It should never be used in a When or Then step.
        """
        self.change_state("active")
        self._stop_beeping()
        self.active_alarms = []
        self.cancel_scheduled_event("NextAlarm")
        self._send_alarm_status()
        self.change_state("inactive")

    @skill_api_method
    def get_number_of_active_alarms(self) -> int:
        """Get the number of active alarms."""
        return len(self.active_alarms)


def create_skill():
    """Create the Alarm Skill for Mycroft."""
    return AlarmSkill()
