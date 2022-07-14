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

from mycroft.messagebus.message import Message
from mycroft.skills import MycroftSkill, intent_handler
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
MARK_I = "mycroft_mark_1"
MARK_II = "mycroft_mark_2"

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


class TimerSkill(MycroftSkill):
    def __init__(self):
        """Constructor"""
        super().__init__(self.__class__.__name__)
        self.active_timers = []
        self.sound_file_path = Path(__file__).parent.joinpath("sounds", "two-beep.wav")
        self.platform = self.config_core["enclosure"].get("platform", "unknown")
        self.timer_index = 0
        self.display_group = 0
        self.save_path = Path(self.file_system.path).joinpath("save_timers")
        self.showing_expired_timers = False

    @property
    def expired_timers(self):
        return [timer for timer in self.active_timers if timer.expired]

    def initialize(self):
        """Initialization steps to execute after the skill is loaded."""
        self._load_timers()
        self._reset_timer_index()
        if self.active_timers:
            if self.skill_service_initializing:
                self.add_event("mycroft.ready", self.handle_mycroft_ready)
            else:
                self._initialize_active_timers()
        self._load_resources()

        # To prevent beeping while listening
        self.add_event("recognizer_loop:wakeword", self.handle_wake_word_detected)
        self.add_event(
            "mycroft.speech.recognition.unknown", self.handle_speech_recognition_unknown
        )
        self.add_event("speak", self.handle_speak)
        self.add_event("skill.timer.stop", self.handle_timer_stop)

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

    def handle_mycroft_ready(self, _):
        self._clear_expired_timers()
        self._initialize_active_timers()

    def _initialize_active_timers(self):
        self.log.info("Loaded {} active timers".format(str(len(self.active_timers))))
        self._show_gui()
        self._start_display_update()
        self._start_expiration_check()

    @intent_handler(AdaptIntent().require("start").require("timer").exclude("query"))
    def handle_start_timer_generic(self, message: Message):
        """Start a timer with no name or duration.

        Args:
            message: Message Bus event information from the intent parser
        """
        with self.activity():
            self.log.info("Handling Adapt start generic timer intent")
            self._start_new_timer(message)

    @intent_handler(
        AdaptIntent().require("start").require("timer").require("name").exclude("query")
    )
    def handle_start_timer_named(self, message: Message):
        """Start a timer with no name or duration.

        Args:
            message: Message Bus event information from the intent parser
        """
        with self.activity():
            self.log.info("Handling Adapt start named timer intent")
            self._start_new_timer(message)

    @intent_handler(
        AdaptIntent()
        .require("start")
        .require("timer")
        .require("duration")
        .optionally("name")
        .exclude("query")
    )
    def handle_start_timer(self, message: Message):
        """Common handler for start_timer intent.

        Args:
            message: Message Bus event information from the intent parser
        """
        with self.activity():
            self.log.info("Handling Adapt start timer intent")
            self._start_new_timer(message)

    @intent_handler("start.timer.intent")
    def handle_start_timer_padatious(self, message: Message):
        """Handles custom timer start phrases (e.g. "ping me in 5 minutes").

        Args:
            message: Message Bus event information from the intent parser
        """
        with self.activity():
            self.log.info("Handling Padatious start timer intent")
            self._start_new_timer(message)

    @intent_handler("timer.status.intent")
    def handle_status_timer_padatious(self, message: Message):
        """Handles custom status phrases (e.g. "How much time left?").

        Args:
            message: Message Bus event information from the intent parser
        """
        with self.activity():
            utterance = message.data["utterance"]
            self._communicate_timer_status(utterance)

    @intent_handler(
        AdaptIntent()
        .require("query")
        .optionally("status")
        .require("timer")
        .optionally("all")
    )
    def handle_query_status_timer(self, message: Message):
        """Handles timer status requests (e.g. "what is the status of the timers").

        Args:
            message: Message Bus event information from the intent parser
        """
        with self.activity():
            utterance = message.data["utterance"]
            self._communicate_timer_status(utterance)

    @intent_handler(
        AdaptIntent()
        .optionally("query")
        .require("status")
        .require("timer")
        .optionally("all")
        .optionally("duration")
        .optionally("name")
    )
    def handle_status_timer(self, message: Message):
        """Handles timer status requests (e.g. "timer status", "status of timers").

        Args:
            message: Message Bus event information from the intent parser
        """
        with self.activity():
            self.log.info("Handling Adapt timer status intent")
            utterance = message.data["utterance"]
            self._communicate_timer_status(utterance)

    @intent_handler(AdaptIntent().require("cancel").require("timer").optionally("all"))
    def handle_cancel_timer(self, message: Message):
        """Handles cancelling active timers.

        Args:
            message: Message Bus event information from the intent parser
        """
        with self.activity():
            self.log.info("Handling Adapt cancel timer intent")
            utterance = message.data["utterance"]
            self._cancel_timers(utterance)

    @intent_handler(AdaptIntent().require("show").require("timer"))
    def handle_show_timers(self, _):
        """Handles showing the timers screen if it is hidden."""
        with self.activity():
            self.log.info("Handling show timer intent")
            if self.active_timers:
                self._show_gui()
            else:
                self.speak_dialog("no-active-timer", wait=True)

    @intent_handler(AdaptIntent().require("showtimers"))
    def handle_showtimers(self, message):
        """Hack for STT giving 'showtimers' for 'show timers'"""
        self.log.info("Handling Adapt showtimers intent")
        self.handle_show_timers(message)

    def shutdown(self):
        """Perform any cleanup tasks before skill shuts down."""
        self.cancel_scheduled_event("UpdateTimerDisplay")
        self.cancel_scheduled_event("ExpirationCheck")
        if self.active_timers:
            self.active_timers = []

    def _start_new_timer(self, message):
        """Start a new timer as requested by the user.

        Args:
            message: Message Bus event information from the intent parser
        """
        utterance = message.data["utterance"]
        try:
            duration, name = self._validate_requested_timer(utterance)
        except TimerValidationException as exc:
            self.log.info(str(exc))
        else:
            # duration should only be None here if the user was asked for
            # timer duration and responded with "nevermind"
            if duration is not None:
                timer = self._build_timer(duration, name)
                self.active_timers.append(timer)
                self.gui.clear()
                self._show_gui()
                if len(self.active_timers) == 1:
                    # the expiration checker isn't started here because it is started
                    # in a speech event handler and the new timer is not spoken until
                    # after the display starts.
                    self._start_display_update()
                self._speak_new_timer(timer)
                self._save_timers()

    def _validate_requested_timer(self, utterance: str):
        """Don't create a timer unless the request has the necessary information.

        Args:
            utterance: the text representing the user's request for a timer

        Returns:
            The duration of the timer and the name, if one is specified.

        Raises:
            TimerValidationError when any of the checks do not pass.
        """
        duration, remaining_utterance = self._determine_timer_duration(utterance)
        name = self._determine_timer_name(remaining_utterance)
        duplicate_timer = self._check_for_duplicate_name(name)
        if duplicate_timer:
            self._handle_duplicate_name_error(duplicate_timer)
        if duration is not None and duration.total_seconds() >= ONE_DAY:
            answer = self.ask_yesno("timer-too-long-alarm-instead")
            if answer == "yes":
                self._convert_to_alarm(duration)

        return duration, name

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
        if duration is None:
            duration = self._request_duration()
        else:
            conjunction = self.translate("and")
            remaining_utterance = remove_conjunction(conjunction, remaining_utterance)

        return duration, remaining_utterance

    def _request_duration(self) -> timedelta:
        """The utterance did not include a timer duration so ask for one.

        Allows the user to respond with "cancel" if the skill was invoked
        by accident or user changes their mind.

        Returns:
            amount of time specified by the user

        Raises:
            TimerValidationException when the user does not supply a duration
        """

        def validate_duration(string):
            """Check that extract_duration returns a valid duration."""
            extracted_duration = None
            extract = extract_duration(string, self.lang)
            if extract is not None:
                extracted_duration = extract[0]

            return extracted_duration is not None

        response = self.get_response("ask-how-long", validator=validate_duration)
        if response is None:
            raise TimerValidationException("No response to request for timer duration.")
        else:
            duration, _ = extract_timer_duration(response)
            if duration is None:
                raise TimerValidationException("No duration specified")

        return duration

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
        self.speak_dialog("timer-duplicate-name", data=dialog_data)
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
        self.speak_dialog(dialog.name, dialog.data, wait=True)

    def _communicate_timer_status(self, utterance: str):
        """Speak response to the user's request for status of timer(s).

        Args:
            utterance: request spoken by user
        """
        if self.active_timers:
            matches = self._get_timer_status_matches(utterance)
            if matches is not None:
                self._speak_timer_status_matches(matches)
        else:
            self.speak_dialog("no-active-timer", wait=True)

    def _get_timer_status_matches(self, utterance: str) -> List[CountdownTimer]:
        """Determine which active timer(s) match the user's status request.

        Args:
            utterance: The user's request for status of timer(s)

        Returns:
            Active timer(s) matching the user's request
        """
        if len(self.active_timers) == 1:
            matches = self.active_timers
        else:
            matcher = TimerMatcher(utterance, self.active_timers, self.static_resources)
            matcher.match()
            matches = matcher.matches or self.active_timers
        while matches is not None and len(matches) > 2:
            matches = self._ask_which_timer(matches, question="ask-which-timer")

        return matches

    def _speak_timer_status_matches(self, matches: List[CountdownTimer]):
        """Constructs and speaks the dialog(s) communicating timer status to the user.

        Args:
            matches: the active timers that matched the user's request for timer status
        """
        if matches:
            number_of_timers = len(matches)
            if number_of_timers > 1:
                speakable_number = pronounce_number(number_of_timers)
                dialog_data = dict(number=speakable_number)
                self.speak_dialog("number-of-timers", dialog_data, wait=True)
            for timer in matches:
                self._speak_timer_status(timer)
        else:
            self.speak_dialog("timer-not-found", wait=True)

    def _speak_timer_status(self, timer: CountdownTimer):
        """Speaks the status of an individual timer - remaining or elapsed.

        Args:
            timer: timer the status will be communicated for
        """
        # TODO: speak_dialog should have option to not show mouth
        #   For now, just deactivate.  The sleep() is to allow the
        #   message to make it across the bus first.
        self.enclosure.deactivate_mouth_events()
        # time.sleep(0.25)
        dialog = TimerDialog(timer, self.lang)
        dialog.build_status_dialog()
        self.speak_dialog(dialog.name, dialog.data, wait=True)
        self.enclosure.activate_mouth_events()

    def _cancel_timers(self, utterance: str):
        """Handles a user's request to cancel one or more timers.

        Args:
            utterance: cancel timer request spoken by user
        """
        if self.active_timers:
            matches = self._determine_which_timers_to_cancel(utterance)
            if matches is not None:
                self._cancel_requested_timers(matches)
            self._save_timers()
            if not self.active_timers:
                self._reset()
        else:
            self.speak_dialog("no-active-timer", wait=True)

    def _determine_which_timers_to_cancel(self, utterance: str):
        """Cancels timer(s) based on the user's request.

        Args:
            utterance: The timer cancellation request made by the user.
        """
        matches = None
        matcher = TimerMatcher(utterance, self.active_timers, self.static_resources)
        if matcher.no_match_criteria:
            if self.expired_timers:
                self._cancel_expired_timers()
            elif len(self.active_timers) == 1:
                self.active_timers = list()
                self.speak_dialog("cancelled-single-timer")
            else:
                matches = self._disambiguate_request(question="ask-which-timer-cancel")
        elif matcher.requested_all:
            self._cancel_all(utterance)
        else:
            matcher.match()
            matches = matcher.matches
            if len(matches) > 1:
                matches = self._disambiguate_request(question="ask-which-timer-cancel")

        return matches

    def _cancel_expired_timers(self):
        """Cancels all expired timers if a user says "cancel timers"."""
        self.log.info("Cancelling expired timers")
        if len(self.expired_timers) == 1:
            self.speak_dialog("cancelled-single-timer")
            self.active_timers.remove(self.expired_timers[0])
        else:
            self.speak_dialog("cancel-all", data=dict(count=len(self.expired_timers)))
            for timer in self.expired_timers:
                self.active_timers.remove(timer)

    def _disambiguate_request(self, question):
        """Disambiguate a generic user request.

        Args:
            question: the disambiguation question to ask the user
        """
        matches = None
        reply = self._ask_which_timer(self.active_timers, question)
        if reply is not None:
            matcher = TimerMatcher(reply, self.active_timers, self.static_resources)
            if matcher.no_match_criteria:
                self.speak_dialog("timer-not-found")
            elif matcher.requested_all:
                self._cancel_all(reply)
            else:
                matcher.match()
                matches = matcher.matches

        return matches

    def _cancel_all(self, utterance):
        """Handles a user's request to cancel all active timers."""
        duration, _ = extract_timer_duration(utterance)
        if duration:
            self._cancel_all_duration(duration)
        else:
            self._cancel_each_and_every_one()

    def _cancel_all_duration(self, duration: timedelta):
        """Cancels all timers with an original duration matching the utterance.

        Args:
            duration: the amount of time a timer was set for
        """
        timers = [timer for timer in self.active_timers if timer.duration == duration]
        self.log.info(
            f"Cancelling all ({len(timers)}) timers with a duration of {duration}"
        )
        for timer in timers:
            self.active_timers.remove(timer)
        speakable_duration = self._build_speakable_duration(duration)
        self.speak_dialog("cancel-all-duration", data=dict(duration=speakable_duration))

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
            dialog = "cancelled-timer-named"
            self.speak_dialog(dialog, data=dict(name=timer.spoken_name))
            self.log.info(f"Cancelling timer {timer.name}")
            self.active_timers.remove(timer)
        else:
            self.speak_dialog("timer-not-found")

    def _ask_which_timer(
        self, timers: List[CountdownTimer], question: str
    ) -> Optional[str]:
        """Ask the user to provide more information about the timer(s) requested.

        Args:
            timers: list of timers that needs to be filtered using the answer
            question: name of the dialog file containing the question to be asked

        Returns:
            timers filtered based on the answer to the question.
        """
        speakable_matches = self._get_speakable_timer_details(timers)
        reply = self.get_response(
            dialog=question, data=dict(count=len(timers), names=speakable_matches)
        )
        if reply is not None:
            if reply in self.static_resources.dismiss_words:
                reply = None

        return reply

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
            speakable_timer_details.append(self.translate(dialog.name, dialog.data))
        timer_names = join_list(speakable_timer_details, self.translate("and"))

        return timer_names

    def _show_gui(self):
        """Update the device's display to show the status of active timers.

        Runs once a second via a repeating event to keep the information on the display
        accurate.
        """
        if self.gui.connected:
            self._update_gui()
            if self.platform == MARK_II:
                page = "timer_mark_ii.qml"
            else:
                page = "timer_scalable.qml"
            self.gui.show_page(page, override_idle=True)

    def update_display(self):
        """Update the device's display to show the status of active timers.

        Runs once a second via a repeating event to keep the information on the display
        accurate.
        """
        if self.gui.connected:
            self._update_gui()
        elif self.platform == MARK_I:
            self._display_timers_on_faceplate()

    def _update_gui(self):
        """Display active timers on a device that supports the QT GUI framework."""
        timers_to_display = self._select_timers_to_display(display_max=4)
        display_data = [timer.display_data for timer in timers_to_display]
        if timers_to_display:
            self.gui["activeTimers"] = dict(timers=display_data)
            self.gui["activeTimerCount"] = len(timers_to_display)

    def _display_timers_on_faceplate(self):
        """Display one timer on a device that supports and Arduino faceplate."""
        faceplate_user = self.enclosure.display_manager.get_active()
        if faceplate_user == "TimerSkill":
            previous_display_group = self.display_group
            timers_to_display = self._select_timers_to_display(display_max=1)
            if self.display_group != previous_display_group:
                self.enclosure.mouth_reset()
            if timers_to_display:
                timer_to_display = timers_to_display[0]
                renderer = FaceplateRenderer(self.enclosure, timer_to_display)
                if len(self.active_timers) > 1:
                    renderer.multiple_active_timers = True
                renderer.render()

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
        if self.expired_timers:
            # Only call _show_gui once until no more expired timers.
            if not self.showing_expired_timers and self.gui.connected:
                self._show_gui()
                self.showing_expired_timers = True

            sound_uri = f"file://{self.sound_file_path}"
            self.play_sound_uri(sound_uri)

            if self.platform == MARK_I:
                self._flash_eyes()
            self._speak_expired_timer(self.expired_timers)
        else:
            self.showing_expired_timers = False

    def _flash_eyes(self):
        """Flash the eyes (if supported) as a visual indicator that a timer expired."""
        if 1 <= now_utc().second % 4 <= 2:
            self.enclosure.eyes_on()
        else:
            self.enclosure.eyes_off()

    def _speak_expired_timer(self, expired_timers):
        """Announce the expiration of any timers not already announced.

        This occurs every two seconds, so only announce one expired timer per pass.
        Pause the expiration check so the expired timer is not beeping while the
        expiration announcement is being spoken.

        On the Mark I, pause the display of any active timers so that the mouth can
        do the "talking".
        """
        for timer in expired_timers:
            if not timer.expiration_announced:
                dialog = TimerDialog(timer, self.lang)
                dialog.build_expiration_announcement_dialog(len(self.active_timers))
                self._stop_expiration_check()
                if self.platform == MARK_I:
                    self._stop_display_update()
                # time.sleep(1)  # give the scheduled event a second to clear
                self.speak_dialog(dialog.name, dialog.data, wait=True)
                timer.expiration_announced = True
                break

    def stop(self) -> bool:
        """Handle a stop command issued by the user.

        When a user says "stop" while one or more expired timers are beeping, cancel
        the expired timers.  If there are no expired timers, but some active timers,
        ask the user if the stop command was intended to cancel all active timers.

        Returns:
            A boolean indicating if the stop message was consumed by this skill.
        """
        stop_handled = False
        if self.expired_timers:
            self._clear_expired_timers()
            if not self.active_timers:
                self._reset()
            stop_handled = True
        elif self.active_timers:
            # We shouldn't initiate dialog during Stop handling because there is
            # a conflict between stopping speech and starting new conversations.
            # Instead, we'll just consider this Stop consumed and emit an event.
            # The event handler will ask the user if they want to cancel active timers.
            self.bus.emit(Message("skill.timer.stop"))
            stop_handled = True

        return stop_handled

    def _clear_expired_timers(self):
        """The user wants the beeping to stop so cancel all expired timers."""
        for timer in self.expired_timers:
            self.active_timers.remove(timer)
        self._save_timers()

    def handle_timer_stop(self, _):
        """Event handler for the stop command when timers are active.

        This is a little odd. This actually does the work for the Stop command/button,
        which prevents blocking during the Stop handler when input from the
        user is needed.
        """
        if len(self.active_timers) == 1:
            question = "ask-cancel-running-single"
        else:
            question = "ask-cancel-running-multiple"
        answer = self.ask_yesno(question)
        if answer == "yes":
            self._cancel_each_and_every_one()
            self._reset()

    def _cancel_each_and_every_one(self):
        """Cancels every active timer."""
        if len(self.active_timers) == 1:
            self.speak_dialog("cancelled-single-timer")
        else:
            self.speak_dialog(
                "cancel-all", data=dict(count=len(self.active_timers)), wait=True
            )
        self.active_timers = list()

    def _reset(self):
        """There are no active timers so reset all the stateful things."""
        self.gui.release()
        self._stop_display_update()
        self._stop_expiration_check()
        self.timer_index = 0
        if self.platform == MARK_I:
            self.enclosure.eyes_reset()
            self.enclosure.mouth_reset()

    def handle_wake_word_detected(self, _):
        """React to the device detecting the wake word spoken by the user.

        On any device, the expiration check should be canceled so that expired timers
        stop beeping while the device handles the request from the user.

        The Mark I performs display events while listening and thinking.  Pause the
        display of the timer to allow these events to display instead.
        """
        if self.active_timers:
            self._stop_expiration_check()
            if self.platform == MARK_I:
                self._stop_display_update()

    def handle_speech_recognition_unknown(self, _):
        """React to no request being spoken after the wake word is activated.

        When the wake word is detected, but no request is uttered by the user, resume
        checking for expired timers.

        The Mark I display was being used to show listening and thinking events.
        Resume showing the active timer(s).
        """
        self._start_expiration_check()
        if self.platform == MARK_I:
            self._start_display_update()

    def handle_speak(self, _):
        """Handle the device speaking a response to a user request.

        Once the device stops speaking, it has finished answering the user's request.
        Resume checking for expired timers.
        The Mark I needs to wait for two seconds after the speaking is done to display
        the active timer(s) because there is an automatic display reset at that time.
        """
        self.wait_while_speaking()
        self._start_expiration_check()

    def _start_display_update(self):
        """Start an event repeating every second to update the timer display."""
        if self.active_timers:
            self.log.info("starting repeating event to update timer display")
            if self.platform == MARK_I:
                self.enclosure.mouth_reset()
            self.schedule_repeating_event(
                self.update_display, None, 1, name="UpdateTimerDisplay"
            )

    def _stop_display_update(self):
        """Stop the repeating event that updates the timer on the display."""
        self.log.info("stopping repeating event to update timer display")
        self.cancel_scheduled_event("UpdateTimerDisplay")
        if self.platform == MARK_I:
            self.enclosure.mouth_reset()

    def _start_expiration_check(self):
        """Start an event repeating every two seconds to check for expired timers."""
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

        # self._cache_cancel_timer_tts()

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

        # self._cache_cancel_timer_tts()

    # def _cache_cancel_timer_tts(self):
    #     """Cache utterance that asks which timer to cancel when there are 2+ timers."""
    #     timers = self.active_timers
    #     if len(timers) > 1:
    #         cache_key = f"{self.skill_id}.cancel-timer"
    #         speakable_matches = self._get_speakable_timer_details(timers)
    #         self.cache_dialog(
    #             "ask-which-timer-cancel",
    #             data=dict(count=len(timers), names=speakable_matches),
    #         )


def create_skill():
    """Instantiate the timer skill."""
    return TimerSkill()
