import time

from behave import then
from mycroft.messagebus import Message


@then("dialog is stopped")
def dialog_is_stopped(context):
    time.sleep(3)
    context.bus.emit(Message("mycroft.audio.speech.stop", data={}, context={}))
    time.sleep(1)
