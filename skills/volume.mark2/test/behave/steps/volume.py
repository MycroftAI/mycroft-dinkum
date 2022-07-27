from test.integrationtests.voight_kampff import emit_utterance, then_wait
from time import sleep

from behave import given, then
from mycroft.messagebus import Message
from mycroft.skills.api import SkillApi

DEFAULT_DELAY = 1.0


def connect_to_skill(bus):
    """Setup Skill API connection"""
    SkillApi.connect_bus(bus)
    return SkillApi.get("mycroft-volume.mycroftai")


def check_volume_is(level, bus):
    """Check that the system volume is currently the expected value.

    Args:
        level: volume in range 0.0 - 1.0

    Returns:
        if volume is set correctly, current volume as float
    """
    response = bus.wait_for_response(Message("mycroft.volume.get"))
    if response:
        if response.data.get("muted"):
            return 0.0 == level, 0.0
        elif response.data.get("percent"):
            actual_volume = response.data["percent"]
            return actual_volume == level, actual_volume
    return None, None


@given("Mycroft audio is muted")
def given_muted(context):
    skill = connect_to_skill(context.bus)
    skill._mute_volume()
    sleep(DEFAULT_DELAY)
    is_volume_correct, actual_volume = check_volume_is(0.0, context.bus)
    assert is_volume_correct, f"Volume is not muted. Current volume is: {actual_volume}"


@given("the volume is set to {level}")
def given_volume_is_specific_level(context, level):
    skill = connect_to_skill(context.bus)
    skill._set_volume(int(level) * 10)  # eg 50
    context.volume = int(level) / 10  # eg 0.5

    is_volume_correct, actual_volume = check_volume_is(context.volume, context.bus)
    assert (
        is_volume_correct
    ), f"Volume is not {level}. Current volume is: {actual_volume}"


@then('"mycroft-volume" should decrease the volume')
def then_decrease(context):
    sleep(DEFAULT_DELAY)
    expected_volume = context.volume - 0.1
    volume_decreased, actual_volume = check_volume_is(expected_volume, context.bus)
    assert (
        volume_decreased
    ), f"Volume did not decrease. Current volume is: {actual_volume}"


@then('"mycroft-volume" should increase the volume')
def then_increase(context):
    sleep(DEFAULT_DELAY)
    expected_volume = context.volume + 0.1
    volume_increased, actual_volume = check_volume_is(expected_volume, context.bus)
    assert (
        volume_increased
    ), f"Volume did not increase. Current volume is: {actual_volume}"


@then('the volume should be "{level}"')
def then_check_volume(context, level):
    sleep(DEFAULT_DELAY)
    expected_volume = int(level) / 10  # eg 0.5
    is_volume_correct, actual_volume = check_volume_is(expected_volume, context.bus)
    assert (
        is_volume_correct
    ), f"Volume is not {expected_volume}. Current volume is: {actual_volume}"
