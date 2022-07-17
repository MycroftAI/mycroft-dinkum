# Copyright 2019 Mycroft AI Inc.
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
"""Common functionality relating to the implementation of mycroft skills."""
import itertools
import logging
import re
import sys
import traceback
import typing
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from itertools import chain
from os import walk
from os.path import abspath, basename, dirname, exists, join
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Timer
from typing import Any, Dict, List, Optional, Tuple, Union
from unittest.mock import MagicMock
from uuid import uuid4

import mycroft.dialog
from adapt.intent import Intent, IntentBuilder
from mycroft.api import DeviceApi
from mycroft.configuration import Configuration
from mycroft.dialog import load_dialogs
from mycroft.enclosure.gui import SkillGUI
from mycroft.filesystem import FileSystemAccess
from mycroft.messagebus.message import Message
from mycroft.util import camel_case_split, resolve_resource_file
from mycroft.util.format import join_list, pronounce_number
from mycroft.util.log import LOG
from mycroft.util.parse import extract_number, match_one
from xdg import BaseDirectory

from ..event_scheduler import EventSchedulerInterface
from ..intent_service_interface import IntentServiceInterface
from ..settings import get_local_settings, save_settings
from ..skill_data import ResourceFile, SkillResources, munge_intent_parser, munge_regex
from .event_container import (
    EventContainer,
    create_wrapper,
    get_handler_name,
    unmunge_message,
)
from .skill_control import SkillControl

SessionDialogDataType = Optional[Dict[str, Any]]
SessionDialogType = Union[str, Tuple[str, SessionDialogDataType]]
SessionDialogsType = Union[SessionDialogType, List[SessionDialogType]]

SessionGuiDataType = Optional[Dict[str, Any]]
SessionGuiType = Union[str, Tuple[str, SessionGuiDataType]]
SessionGuisType = Union[SessionGuiType, List[SessionGuiType]]


def simple_trace(stack_trace):
    """Generate a simplified traceback.

    Args:
        stack_trace: Stack trace to simplify

    Returns: (str) Simplified stack trace.
    """
    stack_trace = stack_trace[:-1]
    tb = "Traceback:\n"
    for line in stack_trace:
        if line.strip():
            tb += line
    return tb


def get_non_properties(obj):
    """Get attibutes that are not properties from object.

    Will return members of object class along with bases down to MycroftSkill.

    Args:
        obj: object to scan

    Returns:
        Set of attributes that are not a property.
    """

    def check_class(cls):
        """Find all non-properties in a class."""
        # Current class
        d = cls.__dict__
        np = [k for k in d if not isinstance(d[k], property)]
        # Recurse through base classes excluding MycroftSkill and object
        for b in [b for b in cls.__bases__ if b not in (object, MycroftSkill)]:
            np += check_class(b)
        return np

    return set(check_class(obj.__class__))


class MycroftSkill:
    """Base class for mycroft skills providing common behaviour and parameters
    to all Skill implementations.

    For information on how to get started with creating mycroft skills see
    https://mycroft.ai/documentation/skills/introduction-developing-skills/

    Args:
        name (str): skill name
        bus (MycroftWebsocketClient): Optional bus connection
        use_settings (bool): Set to false to not use skill settings at all
    """

    _resources = None

    def __init__(self, name=None, bus=None, use_settings=True):
        self.name = name or self.__class__.__name__
        self.skill_id = ""  # will be set from the path, so guaranteed unique
        self.settings_meta = None  # set when skill is loaded in SkillLoader
        self.skill_service_initializing = False

        # For get_response
        self._response_queue: "Queue[str]" = Queue()
        self._mycroft_session_id: typing.Optional[str] = None
        self._session_lock = Lock()

        # Get directory of skill
        #: Member variable containing the absolute path of the skill's root
        #: directory. E.g. /opt/mycroft/skills/my-skill.me/
        self.root_dir = dirname(abspath(sys.modules[self.__module__].__file__))

        self.gui = SkillGUI(self)

        self._bus = None
        self._enclosure = MagicMock()

        #: Mycroft global configuration. (dict)
        self.config_core = Configuration.get()

        self.settings = None
        self.settings_write_path = None

        if use_settings:
            self._init_settings()

        #: Set to register a callback method that will be called every time
        #: the skills settings are updated. The referenced method should
        #: include any logic needed to handle the updated settings.
        self.settings_change_callback = None

        self.dialog_renderer = None

        #: Filesystem access to skill specific folder.
        #: See mycroft.filesystem for details.
        self.file_system = FileSystemAccess(join("skills", self.name))

        self.log = logging.getLogger(self.name)  #: Skill logger instance
        self.reload_skill = True  #: allow reloading (default True)

        self.events = EventContainer(bus)
        self.voc_match_cache = {}

        # Delegator classes
        self.event_scheduler = EventSchedulerInterface(self.name)
        self.intent_service = IntentServiceInterface()

        # Skill Public API
        self.public_api = {}

        self.skill_control = SkillControl()

        # Unique id generated for every started/ended
        self._activity_id: str = ""

        # Session id from last speak()
        self._tts_session_id: typing.Optional[str] = None
        self._tts_speak_finished = Event()

        # Should be last to avoid race conditions where event handlers try to
        # access attributes that have yet to be initialized.
        self.bind(bus)

    def change_state(self, new_state):
        """change skill state to new value.
        does nothing except log a warning
        if the new state is invalid"""
        self.log.debug(
            "change_state() skill:%s - changing state from %s to %s"
            % (self.skill_id, self.skill_control.state, new_state)
        )

        if self.skill_control.states is None:
            return

        if new_state not in self.skill_control.states:
            self.log.warning(
                "invalid state change, from %s to %s"
                % (self.skill_control.state, new_state)
            )
            return

        if new_state != self.skill_control.state:

            for intent in self.skill_control.states[self.skill_control.state]:
                self.disable_intent(intent)

            self.skill_control.state = new_state

            for intent in self.skill_control.states[self.skill_control.state]:
                self.enable_intent(intent)

            if new_state == "inactive":
                self.log.debug("send msg: deactivate %s" % (self.skill_id,))
                self.bus.emit(
                    Message("deactivate_skill_request", {"skill_id": self.skill_id})
                )

            if new_state == "active":
                self.log.debug("send msg: activate %s" % (self.skill_id,))
                self.bus.emit(
                    Message(
                        "active_skill_request",
                        {
                            "skill_id": self.skill_id,
                            "skill_cat": self.skill_control.category,
                        },
                    )
                )

    def _init_settings(self):
        """Setup skill settings."""

        # To not break existing setups,
        # save to skill directory if the file exists already
        self.settings_write_path = Path(self.root_dir)

        # Otherwise save to XDG_CONFIG_DIR
        if not self.settings_write_path.joinpath("settings.json").exists():
            self.settings_write_path = Path(
                BaseDirectory.save_config_path(
                    "mycroft", "skills", basename(self.root_dir)
                )
            )

        # To not break existing setups,
        # read from skill directory if the settings file exists there
        settings_read_path = Path(self.root_dir)

        # Then, check XDG_CONFIG_DIR
        if not settings_read_path.joinpath("settings.json").exists():
            for dir in BaseDirectory.load_config_paths(
                "mycroft", "skills", basename(self.root_dir)
            ):
                path = Path(dir)
                # If there is a settings file here, use it
                if path.joinpath("settings.json").exists():
                    settings_read_path = path
                    break

        self.settings = get_local_settings(settings_read_path, self.name)
        self._initial_settings = deepcopy(self.settings)

    @property
    def enclosure(self):
        if self._enclosure:
            return self._enclosure
        else:
            LOG.error(
                "Skill not fully initialized. Move code "
                + "from  __init__() to initialize() to correct this."
            )
            LOG.error(simple_trace(traceback.format_stack()))
            raise Exception("Accessed MycroftSkill.enclosure in __init__")

    @property
    def bus(self):
        if self._bus:
            return self._bus
        else:
            LOG.error(
                "Skill not fully initialized. Move code "
                + "from __init__() to initialize() to correct this."
            )
            LOG.error(simple_trace(traceback.format_stack()))
            raise Exception("Accessed MycroftSkill.bus in __init__")

    @property
    def location(self):
        """Get the JSON data struction holding location information."""
        # TODO: Allow Enclosure to override this for devices that
        # contain a GPS.
        return self.config_core.get("location")

    @property
    def location_pretty(self):
        """Get a more 'human' version of the location as a string."""
        loc = self.location
        if type(loc) is dict and loc["city"]:
            return loc["city"]["name"]
        return None

    @property
    def location_timezone(self):
        """Get the timezone code, such as 'America/Los_Angeles'"""
        loc = self.location
        if type(loc) is dict and loc["timezone"]:
            return loc["timezone"]["code"]
        return None

    @property
    def lang(self):
        """Get the configured language."""
        return self.config_core.get("lang")

    @property
    def alphanumeric_skill_id(self):
        return "".join(char if char.isalnum() else "_" for char in str(self.skill_id))

    @property
    def resources(self):
        if self._resources is None:
            self._resources = SkillResources(
                self.root_dir, self.lang, self.dialog_renderer
            )

        return self._resources

    def bind(self, bus):
        """Register messagebus emitter with skill.

        Args:
            bus: Mycroft messagebus connection
        """
        if bus:
            self._bus = bus
            self.events.set_bus(bus)
            self.intent_service.set_bus(bus)
            self.event_scheduler.set_bus(bus)
            self.event_scheduler.set_id(self.skill_id)
            self._register_system_event_handlers()
            # Initialize the SkillGui
            self.gui.setup_default_handlers()

            self._register_public_api()

            # Unblock wait_while_speaking
            # self._bus.on(
            #     "mycroft.tts.speaking-finished", self._handle_speaking_finished
            # )

            # # For get_response
            # self._bus.on("mycroft.skill-response", self._handle_skill_response)

            # self._bus.on("mycroft.session.started", self._handle_session_started)
            # self._bus.on("mycroft.session.ended", self._handle_session_ended)
            self._bus.on("mycroft.skill-response", self._handle_skill_response)

    def _register_public_api(self):
        """Find and register api methods.
        Api methods has been tagged with the api_method member, for each
        method where this is found the method a message bus handler is
        registered.
        Finally create a handler for fetching the api info from any requesting
        skill.
        """

        def wrap_method(func):
            """Boiler plate for returning the response to the sender."""

            def wrapper(message):
                result = func(*message.data["args"], **message.data["kwargs"])
                self.bus.emit(message.response(data={"result": result}))

            return wrapper

        methods = [
            attr_name
            for attr_name in get_non_properties(self)
            if hasattr(getattr(self, attr_name), "__name__")
        ]

        for attr_name in methods:
            method = getattr(self, attr_name)

            if hasattr(method, "api_method"):
                doc = method.__doc__ or ""
                name = method.__name__
                self.public_api[name] = {
                    "help": doc,
                    "type": "{}.{}".format(self.skill_id, name),
                    "func": method,
                }
        for key in self.public_api:
            if "type" in self.public_api[key] and "func" in self.public_api[key]:
                LOG.debug(
                    "Adding api method: " "{}".format(self.public_api[key]["type"])
                )

                # remove the function member since it shouldn't be
                # reused and can't be sent over the messagebus
                func = self.public_api[key].pop("func")
                self.add_event(self.public_api[key]["type"], wrap_method(func))

        if self.public_api:
            self.add_event("{}.public_api".format(self.skill_id), self._send_public_api)

    def _register_system_event_handlers(self):
        """Add all events allowing the standard interaction with the Mycroft
        system.
        """

        def stop_is_implemented():
            return self.__class__.stop is not MycroftSkill.stop

        # Only register stop if it's been implemented
        if stop_is_implemented():
            self.add_event("mycroft.stop", self.__handle_stop)

        self.add_event("mycroft.skills.initialized", self.handle_skills_initialized)
        self.add_event("mycroft.skill.enable_intent", self.handle_enable_intent)
        self.add_event("mycroft.skill.disable_intent", self.handle_disable_intent)
        self.add_event("mycroft.skill.set_cross_context", self.handle_set_cross_context)
        self.add_event(
            "mycroft.skill.remove_cross_context", self.handle_remove_cross_context
        )
        self.events.add("mycroft.skills.settings.changed", self.handle_settings_change)

    def handle_skills_initialized(self, _):
        self.skill_service_initializing = False

    def handle_settings_change(self, message):
        """Update settings if the remote settings changes apply to this skill.

        The skill settings downloader uses a single API call to retrieve the
        settings for all skills.  This is done to limit the number API calls.
        A "mycroft.skills.settings.changed" event is emitted for each skill
        that had their settings changed.  Only update this skill's settings
        if its remote settings were among those changed
        """
        if self.settings_meta is None or self.settings_meta.skill_gid is None:
            LOG.error(
                "The skill_gid was not set when " "{} was loaded!".format(self.name)
            )
        else:
            remote_settings = message.data.get(self.settings_meta.skill_gid)
            if remote_settings is not None:
                LOG.info("Updating settings for skill " + self.name)
                self.settings.update(**remote_settings)
                save_settings(self.settings_write_path, self.settings)
                if self.settings_change_callback is not None:
                    self.settings_change_callback()

    def detach(self):
        for (name, _) in self.intent_service:
            name = "{}:{}".format(self.skill_id, name)
            self.intent_service.detach_intent(name)

    def initialize(self):
        """Perform any final setup needed for the skill.

        Invoked after the skill is fully constructed and registered with the
        system.
        """
        pass

    def _send_public_api(self, message):
        """Respond with the skill's public api."""
        self.bus.emit(message.response(data=self.public_api))

    def get_intro_message(self):
        """Get a message to speak on first load of the skill.

        Useful for post-install setup instructions.

        Returns:
            str: message that will be spoken to the user
        """
        return None

    def converse(self, message=None):
        """Handle conversation.

        This method gets a peek at utterances before the normal intent
        handling process after a skill has been invoked once.

        To use, override the converse() method and return True to
        indicate that the utterance has been handled.

        utterances and lang are depreciated

        Args:
            message:    a message object containing a message type with an
                        optional JSON data packet

        Returns:
            bool: True if an utterance was handled, otherwise False
        """
        return False

    # def get_response(
    #     self, dialog="", data=None, validator=None, on_fail=None, num_retries=-1
    # ):
    #     """Get response from user.

    #     If a dialog is supplied it is spoken, followed immediately by listening
    #     for a user response. If the dialog is omitted listening is started
    #     directly.

    #     The response can optionally be validated before returning.

    #     Example::

    #         color = self.get_response('ask.favorite.color')

    #     Args:
    #         dialog (str): Optional dialog to speak to the user
    #         data (dict): Data used to render the dialog
    #         validator (any): Function with following signature::

    #             def validator(utterance):
    #                 return utterance != "red"

    #         on_fail (any):
    #             Dialog or function returning dialog to speak on
    #             invalid input. For example::

    #                 def on_fail(utterance):
    #                     return "pick-another"

    #         num_retries (int): Times to ask user for input, -1 for infinite
    #             NOTE: User can not respond and timeout or say "cancel" to stop

    #     Returns:
    #         str: User's reply or None if timed out or canceled
    #     """
    #     data = data or {}

    #     # Clear response queue
    #     while not self._response_queue.empty():
    #         self._response_queue.get()

    #     def on_fail_default(utterance):
    #         LOG.debug("Response failure: %s", utterance)
    #         return on_fail or dialog

    #     def is_cancel(utterance):
    #         return self.voc_match(utterance, "cancel")

    #     def validator_default(utterance):
    #         # accept anything except 'cancel'
    #         return not is_cancel(utterance)

    #     on_fail_fn = on_fail if callable(on_fail) else on_fail_default
    #     validator = validator or validator_default

    #     # Speak query and wait for user response
    #     dialog_exists = self.dialog_renderer.render(dialog, data)
    #     if dialog_exists:
    #         self.speak_dialog(
    #             dialog,
    #             data,
    #             expect_response=True,
    #             wait=True,
    #             response_skill_id=self.skill_id,
    #         )
    #     else:
    #         self.bus.emit(
    #             Message(
    #                 "mycroft.mic.listen",
    #                 data={
    #                     "response_skill_id": self.skill_id,
    #                     "mycroft_session_id": self._mycroft_session_id,
    #                 },
    #             )
    #         )

    #     return self._wait_response(is_cancel, validator, on_fail_fn, num_retries, data)

    # def _wait_response(self, is_cancel, validator, on_fail, num_retries, data):
    #     """Loop until a valid response is received from the user or the retry
    #     limit is reached.

    #     Args:
    #         is_cancel (callable): function checking cancel criteria
    #         validator (callbale): function checking for a valid response
    #         on_fail (callable): function handling retries

    #     """
    #     num_fails = 0
    #     while True:
    #         # Wait for "mycroft.skill-response"
    #         try:
    #             response = self._response_queue.get(timeout=20)
    #         except Empty:
    #             response = None

    #         if response is None:
    #             # if nothing said, prompt one more time
    #             num_none_fails = 1 if num_retries < 0 else num_retries
    #             if num_fails >= num_none_fails:
    #                 return None
    #         else:
    #             if validator(response):
    #                 return response

    #             # catch user saying 'cancel'
    #             if is_cancel(response):
    #                 return None

    #         num_fails += 1
    #         if 0 < num_retries < num_fails:
    #             return None

    #         dialog = on_fail(response)
    #         if dialog:
    #             self.speak_dialog(
    #                 dialog, expect_response=True, response_skill_id=self.skill_id
    #             )
    #         else:
    #             self.bus.emit(
    #                 Message(
    #                     "mycroft.mic.listen",
    #                     data={
    #                         "response_skill_id": self.skill_id,
    #                         "mycroft_session_id": self._mycroft_session_id,
    #                     },
    #                 )
    #             )

    # def ask_yesno(self, prompt, data=None):
    #     """Read prompt and wait for a yes/no answer

    #     This automatically deals with translation and common variants,
    #     such as 'yeah', 'sure', etc.

    #     Args:
    #           prompt (str): a dialog id or string to read
    #           data (dict): response data
    #     Returns:
    #           string:  'yes', 'no' or whatever the user response if not
    #                    one of those, including None
    #     """
    #     resp = self.get_response(dialog=prompt, data=data)

    #     if self.voc_match(resp, "yes"):
    #         return "yes"
    #     elif self.voc_match(resp, "no"):
    #         return "no"
    #     else:
    #         return resp

    # def ask_selection(
    #     self, options, dialog="", data=None, min_conf=0.65, numeric=False
    # ):
    #     """Read options, ask dialog question and wait for an answer.

    #     This automatically deals with fuzzy matching and selection by number
    #     e.g.

    #     * "first option"
    #     * "last option"
    #     * "second option"
    #     * "option number four"

    #     Args:
    #           options (list): list of options to present user
    #           dialog (str): a dialog id or string to read AFTER all options
    #           data (dict): Data used to render the dialog
    #           min_conf (float): minimum confidence for fuzzy match, if not
    #                             reached return None
    #           numeric (bool): speak options as a numeric menu
    #     Returns:
    #           string: list element selected by user, or None
    #     """
    #     assert isinstance(options, list)

    #     if not len(options):
    #         return None
    #     elif len(options) == 1:
    #         return options[0]

    #     if numeric:
    #         for idx, opt in enumerate(options):
    #             opt_str = "{number}, {option_text}".format(
    #                 number=pronounce_number(idx + 1, self.lang), option_text=opt
    #             )

    #             self.speak(opt_str, wait=True)
    #     else:
    #         opt_str = join_list(options, "or", lang=self.lang) + "?"
    #         self.speak(opt_str, wait=True)

    #     resp = self.get_response(dialog=dialog, data=data)

    #     if resp:
    #         match, score = match_one(resp, options)
    #         if score < min_conf:
    #             if self.voc_match(resp, "last"):
    #                 resp = options[-1]
    #             else:
    #                 num = extract_number(resp, ordinals=True, lang=self.lang)
    #                 resp = None
    #                 if num and num <= len(options):
    #                     resp = options[num - 1]
    #         else:
    #             resp = match
    #     return resp

    def voc_match(self, utt, voc_filename, lang=None, exact=False):
        """Determine if the given utterance contains the vocabulary provided.

        By default the method checks if the utterance contains the given vocab
        thereby allowing the user to say things like "yes, please" and still
        match against "Yes.voc" containing only "yes". An exact match can be
        requested.

        The method first checks in the current Skill's .voc files and secondly
        in the "res/text" folder of mycroft-core. The result is cached to
        avoid hitting the disk each time the method is called.

        Args:
            utt (str): Utterance to be tested
            voc_filename (str): Name of vocabulary file (e.g. 'yes' for
                                'res/text/en-us/yes.voc')
            lang (str): Language code, defaults to self.long
            exact (bool): Whether the vocab must exactly match the utterance

        Returns:
            bool: True if the utterance has the given vocabulary it
        """
        match = False
        lang = lang or self.lang
        cache_key = lang + voc_filename
        if cache_key not in self.voc_match_cache:
            vocab = self.resources.load_vocabulary_file(voc_filename)
            self.voc_match_cache[cache_key] = list(chain(*vocab))
        if utt:
            if exact:
                # Check for exact match
                match = any(i.strip() == utt for i in self.voc_match_cache[cache_key])
            else:
                # Check for matches against complete words
                match = any(
                    [
                        re.match(r".*\b" + i + r"\b.*", utt)
                        for i in self.voc_match_cache[cache_key]
                    ]
                )

        return match

    def report_metric(self, name, data):
        """Report a skill metric to the Mycroft servers.

        Args:
            name (str): Name of metric. Must use only letters and hyphens
            data (dict): JSON dictionary to report. Must be valid JSON
        """
        # report_metric("{}:{}".format(basename(self.root_dir), name), data)

    def send_email(self, title, body):
        """Send an email to the registered user's email.

        Args:
            title (str): Title of email
            body  (str): HTML body of email. This supports
                         simple HTML like bold and italics
        """
        DeviceApi().send_email(title, body, basename(self.root_dir))

    def make_active(self):
        """Bump skill to active_skill list in intent_service.

        This enables converse method to be called even without skill being
        used in last 5 minutes.
        """
        if self.skill_control.category == "undefined":
            self.bus.emit(Message("active_skill_request", {"skill_id": self.skill_id}))

    def _register_decorated(self):
        """Register all intent handlers that are decorated with an intent.

        Looks for all functions that have been marked by a decorator
        and read the intent data from them.  The intent handlers aren't the
        only decorators used.  Skip properties as calling getattr on them
        executes the code which may have unintended side-effects
        """
        for attr_name in get_non_properties(self):
            method = getattr(self, attr_name)
            if hasattr(method, "intents"):
                for intent in getattr(method, "intents"):
                    self.register_intent(intent, method)

            if hasattr(method, "intent_files"):
                for intent_file in getattr(method, "intent_files"):
                    self.register_intent_file(intent_file, method)

    def translate(self, text, data=None):
        """Deprecated method for translating a dialog file."""
        return self.resources.render_dialog(text, data)

    def find_resource(self, res_name, res_dirname=None):
        """Find a resource file.

        Searches for the given filename using this scheme:
            1. Search the resource lang directory:
                <skill>/<res_dirname>/<lang>/<res_name>
            2. Search the resource directory:
                <skill>/<res_dirname>/<res_name>

            3. Search the locale lang directory or other subdirectory:
                <skill>/locale/<lang>/<res_name> or
                <skill>/locale/<lang>/.../<res_name>

        Args:
            res_name (string): The resource name to be found
            res_dirname (string, optional): A skill resource directory, such
                                            'dialog', 'vocab', 'regex' or 'ui'.
                                            Defaults to None.

        Returns:
            string: The full path to the resource file or None if not found
        """
        result = self._find_resource(res_name, self.lang, res_dirname)
        if not result and self.lang != "en-us":
            # when resource not found try fallback to en-us
            LOG.warning(
                "Resource '{}' for lang '{}' not found: trying 'en-us'".format(
                    res_name, self.lang
                )
            )
            result = self._find_resource(res_name, "en-us", res_dirname)
        return result

    def _find_resource(self, res_name, lang, res_dirname=None):
        """Finds a resource by name, lang and dir"""
        if res_dirname:
            # Try the old translated directory (dialog/vocab/regex)
            path = join(self.root_dir, res_dirname, lang, res_name)
            if exists(path):
                return path

            # Try old-style non-translated resource
            path = join(self.root_dir, res_dirname, res_name)
            if exists(path):
                return path

        # New scheme:  search for res_name under the 'locale' folder
        root_path = join(self.root_dir, "locale", lang)
        for path, _, files in walk(root_path):
            if res_name in files:
                return join(path, res_name)

        # Not found
        return None

    def translate_namedvalues(self, name, delim=","):
        """Deprecated method for translating a name/value file."""
        return self.resources.load_named_value_file(name, delim)

    def translate_list(self, list_name, data=None):
        """Deprecated method for translating a list."""
        return self.resources.load_list_file(list_name, data)

    def translate_template(self, template_name, data=None):
        """Deprecated method for translating a template file"""
        return self.resources.load_template_file(template_name, data)

    def add_event(self, name, handler, handler_info=None, once=False):
        """Create event handler for executing intent or other event.

        Args:
            name (string): IntentParser name
            handler (func): Method to call
            handler_info (string): Base message when reporting skill event
                                   handler status on messagebus.
            once (bool, optional): Event handler will be removed after it has
                                   been run once.
        """
        skill_data = {"name": get_handler_name(handler), "skill_id": self.skill_id}

        def on_error(e):
            """Speak and log the error."""
            # Convert "MyFancySkill" to "My Fancy Skill" for speaking
            handler_name = camel_case_split(self.name)
            msg_data = {"skill": handler_name}
            msg = mycroft.dialog.get("skill.error", self.lang, msg_data)
            # self.speak(msg)
            LOG.exception(msg)
            # append exception information in message
            skill_data["exception"] = repr(e)

        def on_start(message):
            """Indicate that the skill handler is starting."""
            if handler_info:
                # Indicate that the skill handler is starting if requested
                msg_type = handler_info + ".start"
                self.bus.emit(message.forward(msg_type, skill_data))

        def on_end(message):
            """Store settings and indicate that the skill handler has completed"""
            if self.settings != self._initial_settings:
                save_settings(self.settings_write_path, self.settings)
                self._initial_settings = deepcopy(self.settings)
            if handler_info:
                msg_type = handler_info + ".complete"
                self.bus.emit(message.forward(msg_type, skill_data))

        wrapper = create_wrapper(handler, self.skill_id, on_start, on_end, on_error)
        return self.events.add(name, wrapper, once)

    def remove_event(self, name):
        """Removes an event from bus emitter and events list.

        Args:
            name (string): Name of Intent or Scheduler Event
        Returns:
            bool: True if found and removed, False if not found
        """
        return self.events.remove(name)

    def _add_intent_handler(self, name, handler):
        def _handle_intent(message: Message):
            self._mycroft_session_id = message.data.get("mycroft_session_id")
            result_message: Optional[Message] = None
            try:
                message = unmunge_message(message, self.skill_id)
                result_message = handler(message)
            except Exception:
                LOG.exception("Error in intent handler: %s", name)

                # Speak error
                self.start_session(
                    dialog=("skill.error", {"skill": camel_case_split(self.name)})
                )

            if result_message is None:
                result_message = self.end_session()

            self.bus.emit(result_message)

        self._bus.on(name, _handle_intent)

    def _register_adapt_intent(self, intent_parser, handler):
        """Register an adapt intent.

        Args:
            intent_parser: Intent object to parse utterance for the handler.
            handler (func): function to register with intent
        """
        # Default to the handler's function name if none given
        name = intent_parser.name or handler.__name__
        munge_intent_parser(intent_parser, name, self.skill_id)
        self.intent_service.register_adapt_intent(name, intent_parser)
        if handler:
            # self.add_event(
            #     intent_parser.name,
            #     handler,
            #     "mycroft.skill.handler",
            # )
            self._add_intent_handler(intent_parser.name, handler)

    def register_intent(self, intent_parser, handler):
        """Register an Intent with the intent service.

        Args:
            intent_parser: Intent, IntentBuilder object or padatious intent
                           file to parse utterance for the handler.
            handler (func): function to register with intent
        """
        if isinstance(intent_parser, IntentBuilder):
            intent_parser = intent_parser.build()
        if isinstance(intent_parser, str) and intent_parser.endswith(".intent"):
            return self.register_intent_file(intent_parser, handler)
        if isinstance(intent_parser, str) and intent_parser.endswith(".rx"):
            return self.register_regex_intent(intent_parser, handler)
        elif not isinstance(intent_parser, Intent):
            raise ValueError('"' + str(intent_parser) + '" is not an Intent')

        return self._register_adapt_intent(intent_parser, handler)

    def register_intent_file(self, intent_file, handler):
        """Register an Intent file with the intent service.

        For example:
            food.order.intent:
                Order some {food}.
                Order some {food} from {place}.
                I'm hungry.
                Grab some {food} from {place}.

        Optionally, you can also use <register_entity_file>
        to specify some examples of {food} and {place}

        In addition, instead of writing out multiple variations
        of the same sentence you can write:
            food.order.intent:
                (Order | Grab) some {food} (from {place} | ).
                I'm hungry.

        Args:
            intent_file: name of file that contains example queries
                         that should activate the intent.  Must end with
                         '.intent'
            handler:     function to register with intent
        """
        name = "{}:{}".format(self.skill_id, intent_file)
        resource_file = ResourceFile(self.resources.types.intent, intent_file)
        if resource_file.file_path is None:
            raise FileNotFoundError('Unable to find "{}"'.format(intent_file))
        self.intent_service.register_padatious_intent(
            name, str(resource_file.file_path)
        )
        if handler:
            # self.add_event(
            #     name,
            #     handler,
            #     "mycroft.skill.handler",
            # )
            self._add_intent_handler(name, handler)

    def register_entity_file(self, entity_file):
        """Register an Entity file with the intent service.

        An Entity file lists the exact values that an entity can hold.
        For example:
            ask.day.intent:
                Is it {weekend}?
            weekend.entity:
                Saturday
                Sunday

        Args:
            entity_file (string): name of file that contains examples of an
                                  entity.
        """
        entity = ResourceFile(self.resources.types.entity, entity_file)
        if entity.file_path is None:
            raise FileNotFoundError('Unable to find "{}"'.format(entity_file))

        name = "{}:{}".format(self.skill_id, entity_file)
        self.intent_service.register_padatious_entity(name, str(entity.file_path))

    def register_regex_intent(self, intent_file, handler):
        """Register a regular expression pattern with the intent service

        Args:
            intent_file: path to file with regex pattern that matches the entire
                         utterance
            handler:     function to register with intent
        """
        regex = ResourceFile(self.resources.types.regex, intent_file)
        if regex.file_path is None:
            raise FileNotFoundError('Unable to find "{}"'.format(intent_file))

        name = "{}:{}".format(self.skill_id, intent_file)
        self.intent_service.register_regex_intent(name, str(regex.file_path))
        if handler:
            # self.add_event(name, handler, "mycroft.skill.handler")
            self._add_intent_handler(name, handler)

    def handle_enable_intent(self, message):
        """Listener to enable a registered intent if it belongs to this skill."""
        intent_name = message.data["intent_name"]
        for (name, _) in self.intent_service:
            if name == intent_name:
                return self.enable_intent(intent_name)

    def handle_disable_intent(self, message):
        """Listener to disable a registered intent if it belongs to this skill."""
        intent_name = message.data["intent_name"]
        for (name, _) in self.intent_service:
            if name == intent_name:
                return self.disable_intent(intent_name)

    def disable_intent(self, intent_name):
        """Disable a registered intent if it belongs to this skill.

        Args:
            intent_name (string): name of the intent to be disabled

        Returns:
                bool: True if disabled, False if it wasn't registered
        """
        if intent_name in self.intent_service:
            LOG.debug("Disabling intent " + intent_name)
            name = "{}:{}".format(self.skill_id, intent_name)
            self.intent_service.detach_intent(name)
            return True
        else:
            LOG.error(
                "Could not disable "
                "{}, it hasn't been registered.".format(intent_name)
            )
            return False

    def enable_intent(self, intent_name):
        """(Re)Enable a registered intent if it belongs to this skill.

        Args:
            intent_name: name of the intent to be enabled

        Returns:
            bool: True if enabled, False if it wasn't registered
        """
        intent = self.intent_service.get_intent(intent_name)
        if intent:
            if ".intent" in intent_name:
                self.register_intent_file(intent_name, None)
            else:
                intent.name = intent_name
                self.register_intent(intent, None)
            LOG.debug("Enabling intent {}".format(intent_name))
            return True
        else:
            LOG.error(
                "Could not enable " "{}, it hasn't been registered.".format(intent_name)
            )
            return False

    def set_context(self, context, word="", origin=""):
        """Add context to intent service

        Args:
            context:    Keyword
            word:       word connected to keyword
            origin:     origin of context
        """
        if not isinstance(context, str):
            raise ValueError("Context should be a string")
        if not isinstance(word, str):
            raise ValueError("Word should be a string")

        context = self.alphanumeric_skill_id + context
        self.intent_service.set_adapt_context(context, word, origin)

    def handle_set_cross_context(self, message):
        """Add global context to intent service."""
        context = message.data.get("context")
        word = message.data.get("word")
        origin = message.data.get("origin")

        self.set_context(context, word, origin)

    def handle_remove_cross_context(self, message):
        """Remove global context from intent service."""
        context = message.data.get("context")
        self.remove_context(context)

    def set_cross_skill_context(self, context, word=""):
        """Tell all skills to add a context to intent service

        Args:
            context:    Keyword
            word:       word connected to keyword
        """
        self.bus.emit(
            Message(
                "mycroft.skill.set_cross_context",
                {"context": context, "word": word, "origin": self.skill_id},
            )
        )

    def remove_cross_skill_context(self, context):
        """Tell all skills to remove a keyword from the context manager."""
        if not isinstance(context, str):
            raise ValueError("context should be a string")
        self.bus.emit(
            Message("mycroft.skill.remove_cross_context", {"context": context})
        )

    def remove_context(self, context):
        """Remove a keyword from the context manager."""
        if not isinstance(context, str):
            raise ValueError("context should be a string")
        context = self.alphanumeric_skill_id + context
        self.intent_service.remove_adapt_context(context)

    def register_vocabulary(self, entity, entity_type):
        """Register a word to a keyword

        Args:
            entity:         word to register
            entity_type:    Intent handler entity to tie the word to
        """
        keyword_type = self.alphanumeric_skill_id + entity_type
        self.intent_service.register_adapt_keyword(keyword_type, entity)

    def register_regex(self, regex_str):
        """Register a new regex.
        Args:
            regex_str: Regex string
        """
        regex = munge_regex(regex_str, self.skill_id)
        re.compile(regex)  # validate regex
        self.intent_service.register_adapt_regex(regex)

    # def speak(
    #     self,
    #     utterance,
    #     expect_response=False,
    #     wait=True,
    #     meta=None,
    #     cache_key=None,
    #     cache_keep=False,
    #     response_skill_id=None,
    # ):
    #     """Speak a sentence.

    #     Args:
    #         utterance (str):        sentence mycroft should speak
    #         expect_response (bool): set to True if Mycroft should listen
    #                                 for a response immediately after
    #                                 speaking the utterance.
    #         wait (bool):            set to True to block while the text
    #                                 is being spoken.
    #         meta:                   Information of what built the sentence.
    #         cache_key (str):        key from cache_speech or cache_dialog
    #         cache_keep (bool):      True if cache_key can be reused
    #     """
    #     # Flush any previous wait_while_speaking()
    #     self._tts_speak_finished.set()
    #     self._tts_speak_finished.clear()
    #     self._tts_session_id = str(uuid4())

    #     # registers the skill as being active
    #     meta = meta or {}
    #     meta["skill"] = self.name
    #     meta["skill_id"] = self.skill_id
    #     self.enclosure.register(self.name)
    #     data = {
    #         "session_id": self._tts_session_id,
    #         "utterance": utterance,
    #         "expect_response": expect_response,
    #         "response_skill_id": response_skill_id,
    #         "meta": meta,
    #         "skill_id": self.skill_id,
    #         "cache_key": cache_key,
    #         "cache_keep": cache_keep,
    #         "activity_id": self._activity_id,
    #         "mycroft_session_id": self._mycroft_session_id,
    #     }
    #     m = Message("speak", data)
    #     self.bus.emit(m)

    #     if wait:
    #         self.wait_while_speaking()

    # def speak_dialog(
    #     self,
    #     key,
    #     data=None,
    #     expect_response=False,
    #     wait=True,
    #     cache_key=None,
    #     cache_keep=False,
    #     response_skill_id=None,
    # ):
    #     """Speak a random sentence from a dialog file.

    #     Args:
    #         key (str): dialog file key (e.g. "hello" to speak from the file
    #                                     "locale/en-us/hello.dialog")
    #         data (dict): information used to populate sentence
    #         expect_response (bool): set to True if Mycroft should listen
    #                                 for a response immediately after
    #                                 speaking the utterance.
    #         wait (bool):            set to True to block while the text
    #                                 is being spoken.
    #         cache_key (str):        key from cache_speech or cache_dialog
    #         cache_keep (bool):      True if cache_key can be reused
    #     """
    #     assert (
    #         self.dialog_renderer
    #     ), "dialog_render is None, does the locale/dialog folder exist?"
    #     data = data or {}
    #     self.speak(
    #         self.dialog_renderer.render(key, data),
    #         expect_response,
    #         wait,
    #         meta={"dialog": key, "data": data},
    #         cache_key=cache_key,
    #         cache_keep=cache_keep,
    #         response_skill_id=response_skill_id,
    #     )

    def acknowledge(self):
        """Acknowledge a successful request.

        This method plays a sound to acknowledge a request that does not
        require a verbal response. This is intended to provide simple feedback
        to the user that their request was handled successfully.
        """
        acknowledge = self.config_core.get("sounds").get("acknowledge")
        if acknowledge:
            audio_file = resolve_resource_file(acknowledge)

            if audio_file:
                LOG.warning("Could not find 'acknowledge' audio file!")
                return

            uri = f"file://{audio_file}"
            self.play_sound_uri(uri)

    def load_data_files(self):
        """Called by the skill loader to load intents, dialogs, etc."""
        self.init_dialog()
        self.load_vocab_files()
        self.load_regex_files()

    def init_dialog(self):
        # If "<skill>/dialog/<lang>" exists, load from there.  Otherwise
        # load dialog from "<skill>/locale/<lang>"
        dialog_dir = join(self.root_dir, "dialog", self.lang)
        if exists(dialog_dir):
            self.dialog_renderer = load_dialogs(dialog_dir)
        elif exists(join(self.root_dir, "locale", self.lang)):
            locale_path = join(self.root_dir, "locale", self.lang)
            self.dialog_renderer = load_dialogs(locale_path)
        else:
            LOG.debug("No dialog loaded")
        self.resources.dialog_renderer = self.dialog_renderer

    def load_vocab_files(self):
        """Load vocab files found under skill's root directory."""
        if self.resources.types.vocabulary.base_directory is None:
            self.log.info("Skill has no vocabulary")
        else:
            skill_vocabulary = self.resources.load_skill_vocabulary(
                self.alphanumeric_skill_id
            )
            # For each found intent register the default along with any aliases
            for vocab_type in skill_vocabulary:
                for line in skill_vocabulary[vocab_type]:
                    entity = line[0]
                    aliases = line[1:]
                    self.intent_service.register_adapt_keyword(
                        vocab_type, entity, aliases
                    )

    def load_regex_files(self):
        """Load regex files found under the skill directory."""
        if self.resources.types.regex.base_directory is not None:
            regexes = self.resources.load_skill_regex(self.alphanumeric_skill_id)
            for regex in regexes:
                self.intent_service.register_adapt_regex(regex)

    def __handle_stop(self, _):
        """Handler for the "mycroft.stop" signal. Runs the user defined
        `stop()` method.
        """
        msg = _
        if (
            msg.data.get("skill", "") == self.skill_id
            or msg.data.get("skill", "") == "*"
        ):
            LOG.debug("handle stop skill_id:%s" % (self.skill_id,))
        else:
            LOG.debug("stop ignored. %s, %s" % (self.skill_id, msg.data))
            return

        def __stop_timeout():
            # The self.stop() call took more than 100ms, assume it handled Stop
            self.bus.emit(
                Message("mycroft.stop.handled", {"skill_id": str(self.skill_id) + ":"})
            )

        timer = Timer(0.1, __stop_timeout)  # set timer for 100ms
        try:
            if self.stop():
                self.bus.emit(
                    Message("mycroft.stop.handled", {"by": "skill:" + self.skill_id})
                )
            timer.cancel()
        except Exception:
            timer.cancel()
            LOG.error("Failed to stop skill: {}".format(self.name), exc_info=True)

    def stop(self):
        """Optional method implemented by subclass."""
        pass

    def shutdown(self):
        """Optional shutdown proceedure implemented by subclass.

        This method is intended to be called during the skill process
        termination. The skill implementation must shutdown all processes and
        operations in execution.
        """
        pass

    def default_shutdown(self):
        """Parent function called internally to shut down everything.

        Shuts down known entities and calls skill specific shutdown method.
        """
        try:
            self.shutdown()
        except Exception as e:
            LOG.error(
                "Skill specific shutdown function encountered "
                "an error: {}".format(repr(e))
            )

        self.settings_change_callback = None

        # Store settings
        if self.settings != self._initial_settings and Path(self.root_dir).exists():
            save_settings(self.settings_write_path, self.settings)

        if self.settings_meta:
            self.settings_meta.stop()

        # Clear skill from gui
        self.gui.shutdown()

        # removing events
        self.event_scheduler.shutdown()
        self.events.clear()

        self.bus.emit(Message("detach_skill", {"skill_id": str(self.skill_id) + ":"}))
        try:
            self.stop()
        except Exception:
            LOG.error("Failed to stop skill: {}".format(self.name), exc_info=True)

    def schedule_event(self, handler, when, data=None, name=None, context=None):
        """Schedule a single-shot event.

        Args:
            handler:               method to be called
            when (datetime/int/float):   datetime (in system timezone) or
                                   number of seconds in the future when the
                                   handler should be called
            data (dict, optional): data to send when the handler is called
            name (str, optional):  reference name
                                   NOTE: This will not warn or replace a
                                   previously scheduled event of the same
                                   name.
            context (dict, optional): context (dict, optional): message
                                      context to send when the handler
                                      is called
        """
        context = {}
        return self.event_scheduler.schedule_event(
            handler, when, data, name, context=context
        )

    def schedule_repeating_event(
        self, handler, when, frequency, data=None, name=None, context=None
    ):
        """Schedule a repeating event.

        Args:
            handler:                method to be called
            when (datetime):        time (in system timezone) for first
                                    calling the handler, or None to
                                    initially trigger <frequency> seconds
                                    from now
            frequency (float/int):  time in seconds between calls
            data (dict, optional):  data to send when the handler is called
            name (str, optional):   reference name, must be unique
            context (dict, optional): context (dict, optional): message
                                      context to send when the handler
                                      is called
        """
        context = {}
        return self.event_scheduler.schedule_repeating_event(
            handler, when, frequency, data, name, context=context
        )

    def update_scheduled_event(self, name, data=None):
        """Change data of event.

        Args:
            name (str): reference name of event (from original scheduling)
            data (dict): event data
        """
        return self.event_scheduler.update_scheduled_event(name, data)

    def cancel_scheduled_event(self, name):
        """Cancel a pending event. The event will no longer be scheduled
        to be executed

        Args:
            name (str): reference name of event (from original scheduling)
        """
        return self.event_scheduler.cancel_scheduled_event(name)

    def get_scheduled_event_status(self, name):
        """Get scheduled event data and return the amount of time left

        Args:
            name (str): reference name of event (from original scheduling)

        Returns:
            int: the time left in seconds

        Raises:
            Exception: Raised if event is not found
        """
        return self.event_scheduler.get_scheduled_event_status(name)

    def cancel_all_repeating_events(self):
        """Cancel any repeating events started by the skill."""
        return self.event_scheduler.cancel_all_repeating_events()

    # def activity_started(self):
    #     """Indicate that a skill activity has started.

    #     This will flush the TTS cache and keep LED animations going.
    #     """
    #     self._activity_id = str(uuid4())
    #     self.bus.emit(
    #         Message(
    #             "skill.started",
    #             data={
    #                 "skill_id": self.skill_id,
    #                 "activity_id": self._activity_id,
    #                 "mycroft_session_id": self._mycroft_session_id,
    #             },
    #         )
    #     )
    #     LOG.info(
    #         "%s started (skill=%s, activity=%s)",
    #         self.name,
    #         self.skill_id,
    #         self._activity_id,
    #     )

    #     self.acknowledge()

    # def activity_ended(self):
    #     """Indicate that a skill activity has ended.

    #     This will stop LED animations.
    #     """
    #     self.bus.emit(
    #         Message(
    #             "skill.ended",
    #             data={
    #                 "skill_id": self.skill_id,
    #                 "activity_id": self._activity_id,
    #                 "mycroft_session_id": self._mycroft_session_id,
    #             },
    #         )
    #     )
    #     LOG.info(
    #         "%s ended (skill=%s, activity=%s)",
    #         self.name,
    #         self.skill_id,
    #         self._activity_id,
    #     )

    # @contextmanager
    # def activity(self):
    #     """Return a context manager that calls activity started/ended.

    #     Yields the activity id.
    #     """
    #     self.activity_started()
    #     try:
    #         yield self._activity_id
    #     finally:
    #         self.activity_ended()

    def play_sound_uri(self, uri: str):
        self.bus.emit(
            Message(
                "mycroft.audio.play-sound",
                data={"uri": uri, "mycroft_session_id": self._mycroft_session_id},
            )
        )

    # def wait_while_speaking(self, timeout=60):
    #     if self._tts_session_id:
    #         self._tts_speak_finished.wait(timeout=timeout)

    # def _handle_speaking_finished(self, message: Message):
    #     session_id = message.data.get("session_id")
    #     if session_id == self._tts_session_id:
    #         self._tts_session_id = None
    #         self._tts_speak_finished.set()

    # def stop_speaking(self):
    #     self.bus.emit(Message("mycroft.tts.stop"))

    # def _handle_skill_response(self, message: Message):
    #     """Catch responses intended for a specific skill"""
    #     skill_id = message.data.get("skill_id")
    #     if skill_id == self.skill_id:
    #         # Intended for this skill
    #         utterances = message.data.get("utterances")
    #         utterance = utterances[0] if utterances else None
    #         LOG.debug("Handling response in skill: %s", utterance)
    #         self._response_queue.put_nowait(utterance)
    #         self._bus.emit(message.response())

    # -------------------------------------------------------------------------

    def _build_actions(
        self,
        dialog: Optional[SessionDialogsType] = None,
        speak: Optional[str] = None,
        speak_wait: bool = True,
        gui: Optional[SessionGuisType] = None,
        gui_clear: str = "on_idle",
        message: Optional[Message] = None,
    ):
        actions = []

        if message is not None:
            actions.append(
                {
                    "type": "message",
                    "message_type": message.msg_type,
                    "data": {
                        # Automatically add session id
                        "mycroft_session_id": self._mycroft_session_id,
                        **message.data,
                    },
                }
            )

        guis = []
        if gui is not None:
            if isinstance(gui, (str, tuple)):
                # Single gui
                guis = [gui]
            else:
                guis = list(gui)

        dialogs = []
        if dialog is not None:
            if isinstance(dialog, (str, tuple)):
                # Single dialog
                dialogs = [dialog]
            else:
                dialogs = list(dialog)

        for maybe_dialog, maybe_gui in itertools.zip_longest(dialogs, guis):
            if maybe_gui is not None:
                if isinstance(maybe_gui, str):
                    gui_page, gui_data = maybe_gui, {}
                else:
                    gui_page, gui_data = maybe_gui

                actions.append(
                    {
                        "type": "show_page",
                        # "page": "file://" + self.find_resource(gui_page, "ui"),
                        "page": f"file:///home/pi/mycroft-dinkum/skills/{self.skill_id}/ui/{gui_page}",
                        "data": gui_data or {},
                        "override_idle": gui_clear == "on_idle",
                    }
                )

            if maybe_dialog is not None:
                if isinstance(maybe_dialog, str):
                    dialog_name, dialog_data = maybe_dialog, {}
                else:
                    dialog_name, dialog_data = maybe_dialog

                utterance = self.dialog_renderer.render(dialog_name, dialog_data)
                actions.append(
                    {
                        "type": "speak",
                        "utterance": utterance,
                        "dialog": dialog_name,
                        "wait": speak_wait,
                    }
                )

        if speak is not None:
            actions.append(
                {
                    "type": "speak",
                    "utterance": speak,
                    "wait": speak_wait,
                }
            )

        if gui_clear == "after_speak":
            actions.append({"type": "clear_display"})

        return actions

    def start_session(
        self,
        dialog: Optional[SessionDialogsType] = None,
        speak: Optional[str] = None,
        speak_wait: bool = True,
        gui: Optional[SessionGuisType] = None,
        gui_clear: str = "on_idle",
        expect_response: bool = False,
        message: Optional[Message] = None,
        continue_session: bool = False,
    ) -> Message:
        return Message(
            "mycroft.session.start",
            data={
                "mycroft_session_id": self._mycroft_session_id,
                "skill_id": self.skill_id,
                "actions": self._build_actions(
                    dialog=dialog,
                    speak=speak,
                    speak_wait=speak_wait,
                    gui=gui,
                    gui_clear=gui_clear,
                    message=message,
                ),
                "expect_response": expect_response,
                "continue_session": continue_session,
            },
        )

    def continue_session(
        self,
        dialog: Optional[SessionDialogsType] = None,
        speak: Optional[str] = None,
        speak_wait: bool = True,
        gui: Optional[SessionGuisType] = None,
        gui_clear: str = "on_idle",
        expect_response: bool = False,
        message: Optional[Message] = None,
    ) -> Message:
        return Message(
            "mycroft.session.continue",
            data={
                "mycroft_session_id": self._mycroft_session_id,
                "skill_id": self.skill_id,
                "actions": self._build_actions(
                    dialog=dialog,
                    speak=speak,
                    speak_wait=speak_wait,
                    gui=gui,
                    gui_clear=gui_clear,
                    message=message,
                ),
                "expect_response": expect_response,
            },
        )

    def end_session(
        self,
        dialog: Optional[SessionDialogsType] = None,
        speak: Optional[str] = None,
        speak_wait: bool = True,
        gui: Optional[SessionGuisType] = None,
        gui_clear: str = "on_idle",
        message: Optional[Message] = None,
    ) -> Message:
        return Message(
            "mycroft.session.end",
            data={
                "mycroft_session_id": self._mycroft_session_id,
                "skill_id": self.skill_id,
                "actions": self._build_actions(
                    dialog=dialog,
                    speak=speak,
                    speak_wait=speak_wait,
                    gui=gui,
                    gui_clear=gui_clear,
                    message=message,
                ),
            },
        )

    def abort_session(self) -> Message:
        message = self.end_session()
        message.data["aborted"] = True
        return message

    # def _handle_session_started(self, message: Message):
    #     self._mycroft_session_id = message.data.get("mycroft_session_id")

    # def _handle_session_ended(self, _message: Message):
    #     self._mycroft_session_id = None

    def raw_utterance(self, utterance: Optional[str]) -> Optional[Message]:
        return None

    def _handle_skill_response(self, message: Message):
        if (message.data.get("skill_id") == self.skill_id) and (
            message.data.get("mycroft_session_id") == self._mycroft_session_id
        ):
            utterances = message.data.get("utterances", [])
            utterance = utterances[0] if utterances else None
            result_message = None
            try:
                result_message = self.raw_utterance(utterance)
            except Exception:
                LOG.exception("Unexpected error in raw_utterance")

            if result_message is None:
                result_message = self.end_session()
            self.bus.emit(result_message)
