# Copyright 2017, Mycroft AI Inc.
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
import hashlib

import os
import random
from adapt.intent import IntentBuilder
from glob import glob
from os.path import isfile, expanduser, isdir
from requests import HTTPError
from shutil import rmtree

from mycroft.api import DeviceApi
from mycroft.messagebus.message import Message
from mycroft import MycroftSkill, intent_handler

def on_error_speak_dialog(dialog_file):
    def decorator(function):
        def wrapper(self, message):
            try:
                try:
                    function(self, message)
                except TypeError:
                    function(self)
            except Exception:
                self.log.exception('In safe wrapped function')
                self.speak_dialog(dialog_file)
        return wrapper
    return decorator


class ConfigurationSkill(MycroftSkill):
    PRECISE_DEV_DIST_URL = "https://github.com/MycroftAI/precise-data/" \
                           "raw/dist/{arch}/latest"
    PRECISE_DEV_MODEL_URL = "https://raw.githubusercontent.com/MycroftAI/" \
                            "precise-data/models-dev/{wake_word}.tar.gz"

    def __init__(self):
        super().__init__("ConfigurationSkill")
        self.api = DeviceApi()
        self.config_hash = ''
        self.model_file = expanduser('~/.mycroft/precise/hey-mycroft.pb')
        self.settings["max_delay"] = 60

    def initialize(self):
        self.schedule_repeating_event(self.update_remote, None, 60,
                                      'UpdateRemote')

    @intent_handler(IntentBuilder('').require('Query').require('Name'))
    def handle_query_name(self, message):
        device = DeviceApi().get()
        self.speak_dialog("my.name.is", data={"name": device["name"]})

    @intent_handler("EnablePreciseDev.intent")
    @on_error_speak_dialog('must.update')
    def handle_use_precise_dev(self, message):
        from mycroft.configuration.config import (
            LocalConf, USER_CONFIG, Configuration
        )

        wake_word = Configuration.get()['listener']['wake_word']

        new_config = {
            'precise': {
                "dist_url": self.PRECISE_DEV_DIST_URL,
                "model_url": self.PRECISE_DEV_MODEL_URL
            },
            'hotwords': {wake_word: {'module': 'precise', 'sensitivity': 0.5}}
        }
        user_config = LocalConf(USER_CONFIG)
        user_config.merge(new_config)
        user_config.store()

        self.bus.emit(Message('configuration.updated'))
        self.speak_dialog('precise.devmode.enabled')

    @intent_handler("DisablePreciseDev.intent")
    @on_error_speak_dialog('must.update')
    def handle_disable_precise_dev(self, message):
        from mycroft.configuration.config import (
            LocalConf, USER_CONFIG
        )

        for item in glob(expanduser('~/.mycroft/precise/precise-engine*')):
            self.log.info('Removing: {}...'.format(item))
            if isdir(item):
                rmtree(item)
            else:
                os.remove(item)
        local_conf = LocalConf(USER_CONFIG)
        pconfig = local_conf.get('precise', {})
        if pconfig.get('dist_url') == self.PRECISE_DEV_DIST_URL:
            del pconfig['dist_url']
        if pconfig.get('model_url') == self.PRECISE_DEV_MODEL_URL:
            del pconfig['model_url']
        local_conf.store()

        self.bus.emit(Message('configuration.updated'))
        self.speak_dialog('precise.devmode.disabled')

    @intent_handler("WhereAreYou.intent")
    def handle_where_are_you(self, message):
        from mycroft.configuration.config import Configuration
        config = Configuration.get()
        data = {
            "city": config["location"]["city"]["name"],
            "state": config["location"]["city"]["state"]["name"],
            "country": config["location"]["city"]["state"]["country"]["name"]
        }

        self.speak_dialog("i.am.at", data)

    def get_listener(self):
        """Raises ImportError or KeyError if not supported"""
        from mycroft.configuration.config import Configuration
        wake_word = Configuration.get()['listener']['wake_word']
        ww_config = Configuration.get()['hotwords'].get(wake_word, {})
        return ww_config.get('module', 'pocketsphinx')

    @intent_handler(IntentBuilder('SetListenerIntent').
                    require('Set').
                    require('Listener').
                    require('ListenerType'))
    @on_error_speak_dialog('must.update')
    def handle_set_listener(self, message):
        from mycroft.configuration.config import (
            LocalConf, USER_CONFIG, Configuration
        )
        module = message.data['ListenerType'].replace(' ', '')
        module = module.replace('default', 'precise')
        name = module.replace('pocketsphinx', 'pocket sphinx')

        if self.get_listener() == module:
            self.speak_dialog('listener.same', data={'listener': name})
            return

        wake_word = Configuration.get()['listener']['wake_word']

        new_config = {
            'hotwords': {wake_word: {'module': module}}
        }
        user_config = LocalConf(USER_CONFIG)
        user_config.merge(new_config)
        user_config.store()

        self.bus.emit(Message('configuration.updated'))

        if module == 'precise':
            engine_folder = expanduser('~/.mycroft/precise/precise-engine')
            if not isdir(engine_folder):
                self.speak_dialog('download.started')
                return

        self.speak_dialog('set.listener', data={'listener': name})

    @intent_handler(IntentBuilder('UpdatePrecise').
                    require('Update').
                    require('Precise'))
    @on_error_speak_dialog('must.update')
    def handle_update_precise(self):
        if self.get_listener() != 'precise':
            self.speak_dialog('not.precise')

        if isfile(self.model_file):
            os.remove(self.model_file)
            new_conf = {'config': {'rand_val': random.random()}}
            self.bus.emit(Message('configuration.patch', new_conf))
            self.bus.emit(Message('configuration.updated'))
            self.speak_dialog('models.updated')
        else:
            self.speak_dialog('models.not.found')

    @intent_handler(IntentBuilder('WhatPreciseModel').
                    require('Query').
                    require('Precise').
                    require('Using'))
    @on_error_speak_dialog('must.update')
    def handle_what_precise_model(self):
        if self.get_listener() != 'precise':
            self.speak_dialog('not.precise')
        if isfile(self.model_file):
            with open(self.model_file, 'rb') as f:
                model_hash = hashlib.md5(f.read()).hexdigest()
            from humanhash import humanize
            model_name = humanize(model_hash, separator=' ')
            self.speak_dialog('model.is', {'name': model_name})

    @intent_handler(IntentBuilder('GetListenerIntent').
                    require('Query').
                    require('Listener'))
    @on_error_speak_dialog('must.update')
    def handle_get_listener(self):
        module = self.get_listener()
        name = module.replace('pocketsphinx', 'pocket sphinx')
        self.speak_dialog('get.listener', data={'listener': name})

    @intent_handler(IntentBuilder('UpdateConfigurationIntent').
                    require('Update').
                    require('Config'))
    def handle_update_intent(self, message):
        try:
            self.bus.emit(Message('mycroft.skills.settings.update'))
            if self.update():
                self.speak_dialog("config.updated")
            else:
                self.speak_dialog("config.no_change")
        except HTTPError as e:
            self.__api_error(e)

    def update_remote(self, message):
        """ Handler for scheduled remote configuration update.

        Updates configuration and handles exceptions.
        """
        try:
            if self.update():
                self.log.info('Remote configuration updated')
        except Exception as e:
            if isinstance(e, HTTPError) and e.response.status_code == 401:
                self.log.warn("Impossible to update configuration because "
                              "device isn't paired")
            else:
                self.log.warn("Failed to update settings, will retry later")

    def update(self):
        """ Update remote configuration.

        Reads remote configuration from the Mycroft backend and trigger
        an update event if a change has occured.
        """
        config = self.api.get_settings() or {}
        location = self.api.get_location()
        if location:
            config["location"] = location

        if self.config_hash != hash(str(config)):
            self.bus.emit(Message("configuration.updated", config))
            self.config_hash = hash(str(config))
            return True
        else:
            return False

    def __api_error(self, e):
        if e.response.status_code == 401:
            self.speak_dialog('config.not.paired.dialog')

    def get_times(self):
        return [self.get_utc_time() + self.settings["max_delay"]]

    def shutdown(self):
        self.cancel_scheduled_event('UpdateRemote')


def create_skill():
    return ConfigurationSkill()
