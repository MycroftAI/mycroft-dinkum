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
import time
from test.integrationtests.voight_kampff import (
    emit_utterance,
    mycroft_responses,
    then_wait,
)

from behave import given, then
from mycroft.messagebus import Message
from mycroft.skills.audioservice import AudioService


def wait_for_service_message(context, message_type):
    """Common method for detecting audio play, stop, or pause messages"""
    msg_type = "mycroft.audio.service.{}".format(message_type)

    def check_for_msg(message):
        return (message.msg_type == msg_type, "")

    passed, debug = then_wait(msg_type, check_for_msg, context)

    if not passed:
        debug += mycroft_responses(context)
    if not debug:
        if message_type == "play":
            message_type = "start"
        debug = "Mycroft didn't {} playback".format(message_type)

    assert passed, debug


@given("news is playing")
def given_news_playing(context):
    emit_utterance(context.bus, "what is the news")
    wait_for_service_message(context, "play")
    time.sleep(3)
    context.bus.clear_messages()


@given("nothing is playing")
def given_nothing_playing(context):
    # TODO simplify this when the Common Play service is updated
    # First sleep to give any previous calls to play enough time to start
    time.sleep(2)
    context.bus.emit(Message("mycroft.stop"))
    context.audio_service = AudioService(context.bus)
    time.sleep(3)
    for i in range(5):
        if context.audio_service.is_playing:
            context.audio_service.stop()
            time.sleep(1)
        else:
            break
    assert not context.audio_service.is_playing
    context.bus.clear_messages()


@then('"mycroft-news" should stop playing')
def then_playback_stop(context):
    # Note - currently only checking for mycroft.stop being emitted.
    # We do not check that the audioservice has actually stopped playing.
    expected_msg_type = "mycroft.stop"

    def check_for_msg(message):
        return (message.msg_type == expected_msg_type, "")

    passed, debug = then_wait(expected_msg_type, check_for_msg, context)

    if not passed:
        debug += mycroft_responses(context)
    if not debug:
        debug = "Mycroft didn't stop playback"

    assert passed, debug
    context.bus.clear_messages()


@then('"mycroft-news" should pause playing')
def then_playback_pause(context):
    wait_for_service_message(context, "pause")


@then('"{station}" should play')
def then_station_playback_started(context, station):
    wait_for_service_message(context, "play")
    context.audio_service = AudioService(context.bus)
    for i in range(5):
        if context.audio_service.is_playing:
            break
        else:
            time.sleep(1)
    assert context.audio_service.is_playing
    track_info = context.audio_service.track_info()
    # If track info isn't supported by audio backend artist will be blank
    if track_info.get("artist"):
        assert track_info["artist"] in ["", station]
    elif track_info.get("artists"):
        # The VLC backend does not currently report 'artist'
        assert track_info["artists"] == [None]
