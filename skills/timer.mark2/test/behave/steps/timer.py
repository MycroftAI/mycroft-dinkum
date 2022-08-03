from typing import List

from behave import given, then

SKILL_ID = "timer.mark2"
CANCEL_RESPONSES = (
    "no-active-timer",
    "cancel-all",
    "cancelled-single-timer",
    "cancelled-timer-named",
    "cancelled-timer-named-ordinal",
)


@given("an active {duration} timer")
def start_single_timer(context, duration):
    """Clear any active timers and start a single timer for a specified duration."""
    _cancel_all_timers(context)
    _start_a_timer(
        context, utterance="set a timer for " + duration, response=["started-timer"]
    )


@given("an active timer named {name}")
def start_single_named_timer(context, name):
    """Clear any active timers and start a single named timer for 90 minutes."""
    _cancel_all_timers(context)
    _start_a_timer(
        context,
        utterance="set a timer for 90 minutes named " + name,
        response=["started-timer-named"],
    )


@given("an active timer for {duration} named {name}")
def start_single_named_dialog_timer(context, duration, name):
    """Clear any active timers and start a single named timer for specified duration."""
    _cancel_all_timers(context)
    _start_a_timer(
        context,
        utterance=f"set a timer for {duration} named {name}",
        response=["started-timer-named"],
    )


@given("multiple active timers")
def start_multiple_timers(context):
    """Clear any active timers and start multiple timers by duration."""
    _cancel_all_timers(context)
    for row in context.table:
        _start_a_timer(
            context,
            utterance="set a timer for " + row["duration"],
            response=["started-timer", "started-timer-named"],
        )


def _start_a_timer(context, utterance: str, response: List[str]):
    """Helper function to start a timer.

    If one of the expected responses is not spoken, cause the step to error out.
    """
    context.client.say_utterance(utterance)
    context.client.match_dialogs_or_fail(response)


@given("no active timers")
@then("timers are stopped")
def reset_timers(context):
    """Cancel all active timers to test how skill behaves when no timers are set."""
    _cancel_all_timers(context)


@given("an expired timer")
def let_timer_expire(context):
    """Start a short timer and let it expire to test expiration logic."""
    _cancel_all_timers(context)
    _start_a_timer(context, "set a 3 second timer", ["started-timer"])
    context.client.match_dialogs_or_fail(["timer-expired"], skill_id=SKILL_ID)


def _cancel_all_timers(context):
    """Cancel all active timers.

    If one of the expected responses is not spoken, cause the step to error out.
    """
    context.client.say_utterance("cancel all timers")
    context.client.match_dialogs_or_fail(CANCEL_RESPONSES, skill_id=SKILL_ID)


@then("the expired timer should stop beeping")
def then_stop_beeping(context):
    context.client.wait_for_message(f"{SKILL_ID}.expired.clear")
