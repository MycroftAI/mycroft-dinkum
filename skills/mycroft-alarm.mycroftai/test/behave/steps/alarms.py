import time

from behave import given, then

from mycroft.messagebus.message import Message
from mycroft.skills.api import SkillApi
from test.integrationtests.voight_kampff import emit_utterance


CANCEL_RESPONSES = (
    "cancelled-multiple",
    "cancelled-single",
    "cancelled-single-recurring",
    "no-active-alarms",
)


def connect_to_skill(bus):
    """Setup Skill API connection"""
    SkillApi.connect_bus(bus)
    return SkillApi.get("mycroft-alarm.mycroftai")


@given("an alarm is set for {alarm_time}")
def given_set_alarm(context, alarm_time):
    alarm_skill = connect_to_skill(context.bus)
    pre_alarm_creation = alarm_skill.get_number_of_active_alarms()
    print(pre_alarm_creation)
    alarm_skill._create_single_test_alarm("set an alarm for {}".format(alarm_time))
    post_alarm_creation = alarm_skill.get_number_of_active_alarms()
    print(post_alarm_creation)
    time.sleep(0.5)
    assert post_alarm_creation - pre_alarm_creation == 1


@given("no active alarms")
def reset_alarms(context):
    """Cancel all active timers to test how skill behaves when no timers are set."""
    alarm_skill = connect_to_skill(context.bus)
    alarm_skill._cancel_all_alarms()
    num_alarms = alarm_skill.get_number_of_active_alarms()
    assert num_alarms == 0


@given("an alarm is expired and beeping")
def given_expired_alarm(context):
    emit_utterance(context.bus, "set an alarm in 10 seconds")
    time.sleep(12)


@then('"mycroft-alarm" should stop beeping')
def then_stop_beeping(context):
    time.sleep(2)
    response = context.bus.wait_for_response(Message("skill.alarm.query-expired"))
    if response and response.data.get("expired_alarms"):
        assert not response.data["expired_alarms"]
