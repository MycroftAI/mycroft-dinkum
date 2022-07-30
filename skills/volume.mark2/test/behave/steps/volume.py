from behave import given, then
from mycroft.messagebus import Message


@given("Mycroft audio is muted")
def given_muted(context):
    context.client.bus.emit(Message("mycroft.volume.mute"))
    message = context.client.wait_for_message("hardware.volume")
    assert message is not None, "No response to setting volume"


@given("the volume is set to {level}")
def given_volume_is_specific_level(context, level):
    level = int(level)
    percent = _level_to_percent(level)
    context.client.bus.emit(Message("mycroft.volume.set", data={"percent": percent}))

    # Block until volume has been updated
    message = context.client.wait_for_message("hardware.volume")
    assert message is not None, "No response to setting volume"
    actual_percent = message.data.get("volume")
    assert (
        percent == actual_percent
    ), f"Expected percent set to {percent}, got {actual_percent}"


@then('the volume should be "{level}"')
def then_check_volume(context, level):
    level = int(level)

    # Block until volume has been updated
    message = context.client.wait_for_message("hardware.volume")

    response = context.client.bus.wait_for_response(Message("mycroft.volume.get"))
    assert response is not None, "No response for volume"

    actual_percent = response.data.get("percent")
    assert actual_percent is not None, "No volume in message"

    actual_level = _percent_to_level(actual_percent)
    assert actual_level == level, f"Expected level {level}, got {actual_level}"


def _level_to_percent(level: int) -> float:
    level = max(0, min(10, level))
    return level / 10.0


def _percent_to_level(percent: float) -> int:
    percent = max(0.0, min(1.0, percent))
    return int(percent * 10.0)
