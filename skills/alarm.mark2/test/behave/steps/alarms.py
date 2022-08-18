from typing import List

from behave import given, then

SKILL_ID = "alarm.mark2"
CANCEL_RESPONSES = (
    "cancelled-multiple",
    "cancelled-single",
    "cancelled-single-recurring",
    "no-active-alarms",
)


@given("an alarm is set for {alarm_time}")
def given_set_alarm(context, alarm_time):
    _start_an_alarm(
        context,
        f"set an alarm for {alarm_time}",
        ["alarm-scheduled", "alarm-scheduled-recurring"],
    )


@given("no active alarms")
@then("alarms are stopped")
def reset_alarms(context):
    _cancel_all_alarms(context)


@given("an alarm is expired and beeping")
def given_expired_alarm(context):
    _start_an_alarm(context, "set an alarm in 3 seconds", ["alarm-scheduled"])
    message = context.client.wait_for_message(f"{SKILL_ID}.alarms.expired")
    assert message is not None, "Did not receive alarm.expired message"


@then('"alarm.mark2" should stop beeping')
def then_stop_beeping(context):
    message = context.client.wait_for_message(f"{SKILL_ID}.expired.cleared")
    assert message is not None, "Did not receive expired.cleared message"


def _start_an_alarm(context, utterance: str, response: List[str]):
    """Helper function to start a alarm.

    If one of the expected responses is not spoken, cause the step to error out.
    """
    context.client.say_utterance(utterance)
    context.client.match_dialogs_or_fail(response)


def _cancel_all_alarms(context):
    """Cancel all active alarms.

    If one of the expected responses is not spoken, cause the step to error out.
    """
    context.client.say_utterance("cancel all alarms")
    context.client.match_dialogs_or_fail(CANCEL_RESPONSES, skill_id=SKILL_ID)
