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
"""A skill to set one or more timers for things like a kitchen timer."""
import pickle
import time
from collections import namedtuple
from datetime import timedelta
from pathlib import Path
from typing import List, Optional
from enum import Enum

from mycroft.messagebus.message import Message
from mycroft.skills import MycroftSkill, intent_handler, GuiClear
from mycroft.skills.intent_service import AdaptIntent
from mycroft.util.format import join_list, nice_duration, pronounce_number
from mycroft.util.parse import extract_duration
from mycroft.util.time import now_local, now_utc

from .skill import (
    CountdownTimer,
    FaceplateRenderer,
    TimerDialog,
    TimerMatcher,
    extract_timer_duration,
    extract_timer_name,
    remove_conjunction,
)

ONE_DAY = 86400
ONE_HOUR = 3600
ONE_MINUTE = 60

StaticResources = namedtuple(
    "StaticResources",
    [
        "all_words",
        "and_word",
        "dismiss_words",
        "hours_word",
        "minutes_word",
        "name_regex",
        "timers_word",
    ],
)


class TimerValidationException(Exception):
    """This is not really for errors, just a handy way to tidy up the initial checks."""

    pass


class State(str, Enum):
    """State used to process raw_utterance"""

    STARTING_TIMER = "starting_timer"
    CANCELLING_TIMER = "cancelling_timer"


class TimerSkill(MycroftSkill):
    def __init__(self):
        """Constructor"""
        super().__init__(self.__class__.__name__)
        self.active_timers = []
        self.sound_file_path = (
            Path(__file__).parent.joinpath("sounds", "two-beep.wav").absolute()
        )
        self.sound_uri: Optional[str] = None
        if self.sound_file_path:
            self.sound_uri = f"file://{self.sound_file_path}"

        self.timer_index = 0
        self.display_group = 0
        self.save_path = Path(self.file_system.path).joinpath("save_timers")
        self.showing_expired_timers = False

        self._expired_session_id: Optional[str] = None

        self._state: Optional[State] = None
        self._partial_timer = {}
        self._cancel_matches = None

    @property
    def expired_timers(self):
        return [timer for timer in self.active_timers if timer.expired]

    def initialize(self):
        """Initialization steps to execute after the skill is loaded."""
        self._load_timers()
        self._reset_timer_index()
        self._initialize_active_timers()
        self._load_resources()

        # To prevent beeping while listening
        self.add_event("recognizer_loop:wakeword", self.handle_wake_word_detected)
        self.add_event(
            "mycroft.session.actions-completed", self.handle_session_actions_completed
        )
        self.add_event("mycroft.session.ended", self.handle_session_ended)

    def _load_resources(self):
        """Gets a set of static words in the language specified in the configuration."""
        self.static_resources = StaticResources(
            all_words=self.resources.load_list_file("all"),
            and_word=self.resources.load_word_file("and"),
            dismiss_words=self.resources.load_list_file("dismiss"),
            hours_word=self.resources.load_word_file("hours"),
            minutes_word=self.resources.load_word_file("minutes"),
            name_regex=self.resources.load_regex_file("name"),
            timers_word=self.resources.load_word_file("timers"),
        )

    def shutdown(self):
        """Perform any cleanup tasks before skill shuts down."""
        self.cancel_scheduled_event("UpdateTimerDisplay")
        self.cancel_scheduled_event("ExpirationCheck")
        if self.active_timers:
            self.active_timers = []

    def handle_mycroft_ready(self, _):
        self._clear_expired_timers()
        self._initialize_active_timers()

    def _initialize_active_timers(self):
        self.log.info("Loaded %s active timers", len(self.active_timers))
        self._start_display_update()
        self._start_expiration_check()

    def handle_session_actions_completed(self, message: Message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id == self._expired_session_id:
            if self.expired_timers:
                # Beep again
                dialog = None
                for timer in self.expired_timers:
                    if not timer.expiration_announced:
                        timer.expiration_announced = True
                        timer_dialog = TimerDialog(timer, self.lang)
                        timer_dialog.build_expiration_announcement_dialog(
                            len(self.active_timers)
                        )
                        dialog = (timer_dialog.name, timer_dialog.data)

                        # Only speak one timer at time
                        break

                self.bus.emit(
                    self.continue_session(
                        mycroft_session_id=self._expired_session_id,
                        audio_alert=self.sound_uri,
                        dialog=dialog,
                        gui_clear=GuiClear.NEVER,
                    )
                )
            else:
                self._expired_session_id = None

    def handle_session_ended(self, message: Message):
        mycroft_session_id = message.data.get("mycroft_session_id")
        if mycroft_session_id == self._expired_session_id:
            self._expired_session_id = None

    # -------------------------------------------------------------------------

    @intent_handler(
        AdaptIntent()
        .require("start")
        .require("timer")
        .optionally("duration")
        .optionally("name")
        .exclude("query")
    )
    def handle_start_timer(self, message: Message):
        """Common handler for start_timer intent.

        Args:
            message: Message Bus event information from the intent parser
        """
        self.log.info("Handling Adapt start timer intent")

        utterance = message.data["utterance"]
        duration, remaining_utterance = self._determine_timer_duration(utterance)
        name = self._determine_timer_name(remaining_utterance)

        if duration is None:
            self._partial_timer = {"name": name}
            self._state = State.STARTING_TIMER
            return self.continue_session(dialog="ask-how-long", expect_response=True)

        timer = self._start_new_timer(duration, name)
        return self.end_session(
            dialog=self._speak_new_timer(timer),
            gui=("timer_mark_ii.qml", self._get_gui_data()),
            gui_clear=GuiClear.NEVER,
        )

    def raw_utterance(self, utterance: Optional[str]) -> Optional[Message]:
        if self.voc_match(utterance, "cancel"):
            self.log.debug("Cancelled duration request")
            return

        if self._state == State.STARTING_TIMER:
            # Start timer command that's missing a duration
            name = self._partial_timer.pop("name", None)
            duration, _rest = self._determine_timer_duration(utterance)
            if duration is not None:
                timer = self._start_new_timer(duration, name)
                return self.end_session(
                    dialog=self._speak_new_timer(timer),
                    gui=("timer_mark_ii.qml", self._get_gui_data()),
                    gui_clear=GuiClear.NEVER,
                )

            self.log.debug("Invalid duration '%s' in '%s'", duration, utterance)
        elif self._state == State.CANCELLING_TIMER:
            # Cancel timer command that needs disambiguation
            matcher = TimerMatcher(utterance, self.active_timers, self.static_resources)
            if matcher.no_match_criteria:
                dialog = "timer-not-found"
            elif matcher.requested_all:
                duration, _ = extract_timer_duration(utterance)
                if duration:
                    dialog = self._cancel_all_duration(duration)
                else:
                    dialog = self._cancel_each_and_every_one()
            else:
                matcher.match()
                matches = matcher.matches
                dialog = self._cancel_requested_timers(matches)

            if self.active_timers:
                gui_clear = GuiClear.NEVER
            else:
                gui_clear = GuiClear.AFTER_SPEAK

            return self.end_session(dialog=dialog, gui_clear=gui_clear)

    def _start_new_timer(self, duration, name):
        timer = self._build_timer(duration, name)
        self.active_timers.append(timer)
        self._save_timers()
        self._start_display_update()
        self._start_expiration_check()
        return timer

    @intent_handler("start.timer.intent")
    def handle_start_timer_padatious(self, message: Message):
        """Handles custom timer start phrases (e.g. "ping me in 5 minutes").

        Args:
            message: Message Bus event information from the intent parser
        """
        self.log.info("Handling Padatious start timer intent")
        return self.handle_start_timer(message)

    @intent_handler("timer.status.intent")
    def handle_status_timer_padatious(self, message: Message):
        """Handles custom status phrases (e.g. "How much time left?").

        Args:
            message: Message Bus event information from the intent parser
        """
        return self.handle_query_status_timer(message)

    @intent_handler(
        AdaptIntent()
        .optionally("query")
        .optionally("status")
        .require("timer")
        .optionally("all")
        .optionally("duration")
        .optionally("name")
    )
    def handle_query_status_timer(self, message: Message):
        """Handles timer status requests (e.g. "what is the status of the timers").

        Args:
            message: Message Bus event information from the intent parser
        """
        utterance = message.data["utterance"]
        dialog = self._communicate_timer_status(utterance)
        return self.end_session(dialog=dialog)

    @intent_handler(AdaptIntent().require("cancel").require("timer").optionally("all"))
    def handle_cancel_timer(self, message: Message):
        """Handles cancelling active timers.

        Args:
            message: Message Bus event information from the intent parser
        """
        self.log.info("Handling Adapt cancel timer intent")
        if self.active_timers:
            utterance = message.data["utterance"]
            duration, _ = self._determine_timer_duration(utterance)
            matcher = TimerMatcher(utterance, self.active_timers, self.static_resources)

            dialog = None
            if matcher.requested_all:
                if duration:
                    # cancel all 5 minute timers
                    dialog = self._cancel_all_duration(duration)
                else:
                    # cancel all timers
                    dialog = self._cancel_each_and_every_one()
            elif matcher.no_match_criteria:
                # cancel timer(s)
                if self.expired_timers:
                    dialog = self._cancel_expired_timers()
                elif len(self.active_timers) == 1:
                    self.active_timers = list()
                    dialog = "cancelled-single-timer"
                else:
                    # Need a timer name
                    dialog = self._ask_which_timer(
                        self.active_timers, "ask-which-timer-cancel"
                    )
                    self._cancel_matches = None
                    self._state = State.CANCELLING_TIMER
                    return self.continue_session(dialog=dialog, expect_response=True)
            else:
                # Name or duration is present
                matcher.match()
                matches = matcher.matches
                if matches:
                    if len(matches) > 1:
                        # Multiple matches, need to ask user for clarification
                        self._cancel_matches = matches
                        self._state = State.CANCELLING_TIMER
                        dialog = self._ask_which_timer(
                            self.active_timers, "ask-which-timer-cancel"
                        )
                        return self.continue_session(
                            dialog=dialog, expect_response=True
                        )

                    # Single match
                    dialog = self._cancel_requested_timers(matches)
                else:
                    self.log.debug("No timers matched: %s", utterance)

            self._save_timers()
        else:
            dialog = "no-active-timer"

        if self.active_timers:
            gui_clear = GuiClear.NEVER
        else:
            gui_clear = GuiClear.AFTER_SPEAK

        return self.end_session(dialog=dialog, gui_clear=gui_clear)

    def _cancel_all_duration(self, duration: timedelta):
        """Cancels all timers with an original duration matching the utterance.

        Args:
            duration: the amount of time a timer was set for
        """
        timers = [timer for timer in self.active_timers if timer.duration == duration]
        self.log.info(
            "Cancelling all (%s) timers with a duration of %s", len(timers), duration
        )
        for timer in timers:
            self.active_timers.remove(timer)

        speakable_duration = self._build_speakable_duration(duration)
        return ("cancel-all-duration", dict(duration=speakable_duration))

    def _cancel_each_and_every_one(self):
        """Cancels every active timer."""
        if len(self.active_timers) == 1:
            dialog = "cancelled-single-timer"
        else:
            dialog = ("cancel-all", dict(count=len(self.active_timers)))
        self.active_timers = list()
        return dialog

    @intent_handler(AdaptIntent().require("show").require("timer"))
    def handle_show_timers(self, _message: Message):
        """Handles showing the timers screen if it is hidden."""
        self.log.info("Handling show timer intent")
        dialog = None
        gui = None
        if self.active_timers:
            gui = ("timer_mark_ii.qml", self._get_gui_data())
        else:
            dialog = "no-active-timer"

        return self.end_session(dialog=dialog, gui=gui, gui_clear=GuiClear.NEVER)

    @intent_handler(AdaptIntent().require("showtimers"))
    def handle_showtimers(self, message):
        """Hack for STT giving 'showtimers' for 'show timers'"""
        self.log.info("Handling Adapt showtimers intent")
        return self.handle_show_timers(message)

    def _determine_timer_duration(self, utterance: str):
        """Interrogate the utterance to determine the duration of the timer.

        If the duration of the timer cannot be determined when interrogating the
        initial utterance, the user will be asked to specify one.

        Args:
            utterance: the text representing the user's request for a timer

        Returns:
            The duration of the timer and the remainder of the utterance after the
            duration has been extracted.

        Raises:
            TimerValidationException when no duration can be determined.
        """
        duration, remaining_utterance = extract_timer_duration(utterance)
        if duration == 1:  # prevent "set one timer" doing 1 sec timer
            duration, remaining_utterance = extract_timer_duration(remaining_utterance)
        # if duration is None:
        #     duration = self._request_duration()
        # else:
        if duration is not None:
            conjunction = self.static_resources.and_word
            remaining_utterance = remove_conjunction(conjunction, remaining_utterance)

        return duration, remaining_utterance

    def _determine_timer_name(self, remaining_utterance):
        timer_name = extract_timer_name(remaining_utterance, self.static_resources)
        if timer_name is None:
            timer_name = self._assign_timer_name()

        return timer_name

    def _check_for_duplicate_name(self, timer_name: str) -> Optional[CountdownTimer]:
        """Determine if the requested timer name is already in use.

        Args:
            timer_name: The name of the newly requested timer

        Returns:
            The timer with the same name as the requested timer or None if there is
            no duplicate.
        """
        duplicate_timer = None
        if timer_name is not None:
            for timer in self.active_timers:
                if timer_name.lower() == timer.name.lower():
                    duplicate_timer = timer

        return duplicate_timer

    def _handle_duplicate_name_error(self, duplicate_timer: CountdownTimer):
        """Communicate the duplicated timer name error to the user.

        Args:
            duplicate_timer: The timer that has the same name as the requested timer.

        Raises:
            TimerValidationError so that no more validations are done.
        """
        time_remaining = duplicate_timer.expiration - now_utc()
        dialog_data = dict(
            name=duplicate_timer.name, duration=nice_duration(time_remaining)
        )
        self.speak_dialog("timer-duplicate-name", data=dialog_data, wait=True)
        raise TimerValidationException("Requested timer name already exists")

    def _convert_to_alarm(self, duration: timedelta):
        """Generate a message bus event to pass the user's request to the alarm skill.

        Args:
            duration: timer duration requested by user

        Raises:
            TimerValidationError indicating that the user's request was converted
            to an alarm.
        """
        # TODO: add name of alarm if available?
        alarm_time = now_local() + duration
        alarm_data = dict(
            date=alarm_time.strftime("%B %d %Y"), time=alarm_time.strftime("%I:%M%p")
        )
        phrase = self.translate("set-alarm", alarm_data)
        message = Message(
            "recognizer_loop:utterance", dict(utterances=[phrase], lang="en-us")
        )
        self.bus.emit(message)
        raise TimerValidationException("Timer converted to alarm")

    def _build_timer(self, duration: timedelta, requested_name: str) -> CountdownTimer:
        """Generate a timer object based on the validated user request.

        Args:
            duration: amount of time requested for the timer
            requested_name: name requested for the timer

        Returns:
            Newly generated timer object.
        """
        self.timer_index += 1
        timer = CountdownTimer(duration, requested_name)
        if timer.name is None:
            timer.name = self._assign_timer_name()
        timer.index = self.timer_index
        timer.ordinal = self._calculate_ordinal(timer.duration)

        return timer

    def _assign_timer_name(self) -> str:
        """Assign a name to a timer when the user does not specify one.

        All timers will have a name. If the user does not request one, assign a name
        using the "Timer <unnamed timer number>" convention.

        When there is only one timer active and it is assigned a name, the name
        "Timer" will be used.  If another timer without a requested name is added,
        the timer named "Timer" will have its name changed to "Timer 1" and the new
        timer will be named "Timer 2"

        Returns:
            The name assigned to the timer.
        """
        if self.active_timers:
            max_assigned_number = 0
            for timer in self.active_timers:
                if timer.name == "timer":
                    timer.name = "timer 1"
                    max_assigned_number = 1
                elif timer.name.startswith("timer "):
                    _, name_number = timer.name.split()
                    name_number = int(name_number)
                    if name_number > max_assigned_number:
                        max_assigned_number = name_number
            new_timer_number = max_assigned_number + 1
            timer_name = "timer " + str(new_timer_number)
        else:
            timer_name = "timer"

        return timer_name

    def _calculate_ordinal(self, duration: timedelta) -> int:
        """Get ordinal based on existing timer durations.

        Args:
            duration: amount of time requested for the timer

        Returns:
            The ordinal of the new timer based on other active timers with the
            same duration
        """
        timer_count = sum(
            1 for timer in self.active_timers if timer.duration == duration
        )

        return timer_count + 1

    def _speak_new_timer(self, timer: CountdownTimer):
        """Speak a confirmation to the user that the new timer has been added.

        Args:
            timer: new timer requested by the user
        """
        dialog = TimerDialog(timer, self.lang)
        timer_count = len(self.active_timers)
        dialog.build_add_dialog(timer_count)
        return (dialog.name, dialog.data)

    def _communicate_timer_status(self, utterance: str):
        """Speak response to the user's request for status of timer(s).

        Args:
            utterance: request spoken by user
        """
        if self.active_timers:
            matches = self.active_timers
            if len(self.active_timers) > 1:
                matcher = TimerMatcher(
                    utterance, self.active_timers, self.static_resources
                )
                matcher.match()
                if matcher.matches:
                    matches = matcher.matches
            dialog = self._speak_timer_status_matches(matches)
        else:
            dialog = "no-active-timer"

        return dialog

    def _speak_timer_status_matches(self, matches: List[CountdownTimer]):
        """Constructs and speaks the dialog(s) communicating timer status to the user.

        Args:
            matches: the active timers that matched the user's request for timer status
        """
        dialog = None
        if matches:
            number_of_timers = len(matches)
            dialogs = []
            if number_of_timers > 1:
                speakable_number = pronounce_number(number_of_timers)
                dialog_data = dict(number=speakable_number)
                dialogs.append(("number-of-timers", dialog_data))
            for timer in matches:
                dialogs.append(self._speak_timer_status(timer))
            dialog = dialogs
        else:
            dialog = "timer-not-found"

        return dialog

    def _speak_timer_status(self, timer: CountdownTimer):
        """Speaks the status of an individual timer - remaining or elapsed.

        Args:
            timer: timer the status will be communicated for
        """
        dialog = TimerDialog(timer, self.lang)
        dialog.build_status_dialog()
        return (dialog.name, dialog.data)

    def _cancel_expired_timers(self):
        """Cancels all expired timers if a user says "cancel timers"."""
        self.log.info("Cancelling expired timers")
        if len(self.expired_timers) == 1:
            dialog = "cancelled-single-timer"
            self.active_timers.remove(self.expired_timers[0])
        else:
            dialog = ("cancel-all", dict(count=len(self.expired_timers)))
            for timer in self.expired_timers:
                self.active_timers.remove(timer)

        return dialog

    def _build_speakable_duration(self, duration: timedelta) -> str:
        """Builds a string representing the timer duration that can be passed to TTS.

        Args:
            duration: the amount of time a timer was set for

        Returns:
            a string representation of the duration for STT purposes.
        """
        hours = int(duration.total_seconds() / ONE_HOUR)
        minutes = int((duration.total_seconds() - (hours * ONE_HOUR)) / ONE_MINUTE)
        if hours and minutes:
            speakable_duration = (
                f"{hours} {self.static_resources.hours_word} "
                f"{self.static_resources.and_word} {minutes} "
                f"{self.static_resources.minutes_word}"
            )
        elif hours and not minutes:
            speakable_duration = f"{hours} {self.static_resources.hours_word}"
        else:
            speakable_duration = f"{minutes} {self.static_resources.minutes_word}"

        return speakable_duration

    def _cancel_requested_timers(self, matches: List[CountdownTimer]):
        """Cancels the timers that matched the user's requests.

        Args:
            matches: the timers that matched the request
        """
        if len(matches) == 1:
            timer = matches[0]
            dialog = ("cancelled-timer-named", dict(name=timer.spoken_name))
            self.log.info("Cancelling timer %s", timer.name)
            self.active_timers.remove(timer)
        else:
            dialog = "timer-not-found"

        return dialog

    def _ask_which_timer(self, timers: List[CountdownTimer], question: str):
        """Ask the user to provide more information about the timer(s) requested.

        Args:
            timers: list of timers that needs to be filtered using the answer
            question: name of the dialog file containing the question to be asked
        """
        speakable_matches = self._get_speakable_timer_details(timers)
        return (question, dict(count=len(timers), names=speakable_matches))

    def _get_speakable_timer_details(self, timers: List[CountdownTimer]) -> str:
        """Get timer list as speakable string.

        Args:
            timers: the timers to be converted

        Returns:
            names of the specified timers to be passed to TTS engine for speaking
        """
        speakable_timer_details = []
        for timer in timers:
            dialog = TimerDialog(timer, self.lang)
            dialog.build_details_dialog()
            speakable_timer_details.append(
                self.dialog_renderer.render(dialog.name, dialog.data)
            )
        timer_names = join_list(speakable_timer_details, self.static_resources.and_word)

        return timer_names

    def _get_gui_data(self):
        """Display active timers on a device that supports the QT GUI framework."""
        timers_to_display = self._select_timers_to_display(display_max=4)
        display_data = [timer.display_data for timer in timers_to_display]
        gui_data = {"activeTimers": {}, "activeTimerCount": 0}
        if timers_to_display:
            gui_data["activeTimers"] = dict(timers=display_data)
            gui_data["activeTimerCount"] = len(timers_to_display)

        return gui_data

    def update_display(self):
        gui_data = self._get_gui_data()
        self.update_gui_values("timer_mark_ii.qml", gui_data)

    def _select_timers_to_display(self, display_max: int) -> List[CountdownTimer]:
        """Determine which timers will populate the display.

        If there are more timers than fit on a screen or faceplate, change which
        timers are displayed every ten seconds.

        Args:
            display_max: maximum number of timers that can be displayed at once

        Returns:
            The timer(s) to be displayed.
        """
        if len(self.active_timers) <= display_max:
            timers_to_display = self.active_timers
        else:
            if not now_utc().second % 10:
                if (self.display_group * display_max) < len(self.active_timers):
                    self.display_group += 1
                else:
                    self.display_group = 1

            start_index = (self.display_group - 1) * display_max
            end_index = self.display_group * display_max
            timers_to_display = self.active_timers[start_index:end_index]

        return timers_to_display

    def check_for_expired_timers(self):
        """Provide a audible and visual indicator when one or more timers expire.

        Runs once every two seconds via a repeating event.
        """
        if self.expired_timers and (self._expired_session_id is None):
            dialog = None
            gui = ("timer_mark_ii.qml", self._get_gui_data())
            self._expired_session_id = self.emit_start_session(
                audio_alert=self.sound_uri,
                # dialog=dialog,
                gui=gui,
                gui_clear=GuiClear.NEVER,
                continue_session=True,
            )

    # def _speak_expired_timer(self, expired_timers):
    #     """Announce the expiration of any timers not already announced.

    #     This occurs every two seconds, so only announce one expired timer per pass.
    #     Pause the expiration check so the expired timer is not beeping while the
    #     expiration announcement is being spoken.

    #     On the Mark I, pause the display of any active timers so that the mouth can
    #     do the "talking".
    #     """
    #     dialog = None
    #     for timer in expired_timers:
    #         if not timer.expiration_announced:
    #             dialog = TimerDialog(timer, self.lang)
    #             dialog.build_expiration_announcement_dialog(len(self.active_timers))
    #             # self._stop_expiration_check()

    #             dialog = (dialog.name, dialog.data)
    #             timer.expiration_announced = True
    #             break

    #     return dialog

    def stop(self):
        """Handle a stop command issued by the user.

        When a user says "stop" while one or more expired timers are beeping, cancel
        the expired timers.  If there are no expired timers, but some active timers,
        ask the user if the stop command was intended to cancel all active timers.

        Returns:
            A boolean indicating if the stop message was consumed by this skill.
        """
        dialog = None
        if self.expired_timers:
            self._clear_expired_timers()
            if not self.active_timers:
                self._reset()
        elif self.active_timers:
            if len(self.active_timers) == 1:
                self.active_timers = list()
                dialog = "cancelled-single-timer"
                self._save_timers()
            else:
                # Need a timer name
                dialog = self._ask_which_timer(
                    self.active_timers, "ask-which-timer-cancel"
                )
                self._cancel_matches = None
                self._state = State.CANCELLING_TIMER
                return self.continue_session(dialog=dialog, expect_response=True)

        return self.end_session(dialog=dialog, gui_clear=GuiClear.AFTER_SPEAK)

    def _clear_expired_timers(self):
        """The user wants the beeping to stop so cancel all expired timers."""
        for timer in self.expired_timers:
            self.active_timers.remove(timer)
        self._save_timers()

    def _reset(self):
        """There are no active timers so reset all the stateful things."""
        self._stop_display_update()
        self._stop_expiration_check()
        self.timer_index = 0

    def handle_wake_word_detected(self, _):
        """React to the device detecting the wake word spoken by the user.

        On any device, the expiration check should be canceled so that expired timers
        stop beeping while the device handles the request from the user.

        The Mark I performs display events while listening and thinking.  Pause the
        display of the timer to allow these events to display instead.
        """
        if self.active_timers:
            self._stop_expiration_check()

    def _start_display_update(self):
        """Start an event repeating every second to update the timer display."""
        if self.active_timers:
            self.log.info("starting repeating event to update timer display")
            self.schedule_repeating_event(
                self.update_display, None, 1, name="UpdateTimerDisplay"
            )

    def _stop_display_update(self):
        """Stop the repeating event that updates the timer on the display."""
        self.log.info("stopping repeating event to update timer display")
        self.cancel_scheduled_event("UpdateTimerDisplay")

    def _start_expiration_check(self):
        """Start an event repeating every two seconds to check for expired timers."""
        self.showing_expired_timers = False
        if self.active_timers:
            self.log.info("starting repeating event to check for timer expiration")
            self.schedule_repeating_event(
                self.check_for_expired_timers, None, 2, name="ExpirationCheck"
            )

    def _stop_expiration_check(self):
        """Stop the repeating event that checks for expired timers."""
        self.log.info("stopping repeating event to check for timer expiration")
        self.cancel_scheduled_event("ExpirationCheck")

    def _reset_timer_index(self):
        """Use the timers loaded from skill storage to determine the timer index."""
        if self.active_timers:
            timer_with_max_index = max(
                self.active_timers, key=lambda timer: timer.index
            )
            self.timer_index = timer_with_max_index.index
        else:
            self.timer_index = 0

    def _save_timers(self):
        """Write a serialized version of the data to the specified file name."""
        if self.active_timers:
            with open(self.save_path, "wb") as data_file:
                pickle.dump(self.active_timers, data_file, pickle.HIGHEST_PROTOCOL)
        else:
            if self.save_path.exists():
                self.save_path.unlink()

            self._stop_display_update()
            self._stop_expiration_check()

    def _load_timers(self):
        """Load any saved timers into the active timers list.

        Returns:
            None if the file does not exist or the deserialized data in the file.
        """
        self.active_timers = list()
        if self.save_path.exists():
            try:
                with open(self.save_path, "rb") as data_file:
                    self.active_timers = pickle.load(data_file)
            except Exception:
                self.log.exception("Failed to load active timers: %s", self.save_path)


def create_skill():
    """Instantiate the timer skill."""
    return TimerSkill()
