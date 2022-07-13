import time
from test.integrationtests.voight_kampff import then_wait

from behave import then
from mycroft.messagebus import Message


@then("dialog is stopped")
def dialog_is_stopped(context):
    def check_dialog_tts_stop(message):
        who = message.data.get("by", "")
        return (who == "TTS", "")

    context.bus.emit(Message("mycroft.audio.speech.stop", data={}, context={}))
    status, debug = then_wait("mycroft.stop.handled", check_dialog_tts_stop, context, 5)
    return status, debug


@then("there will be a short delay")
def short_sleep(context):
    time.sleep(1)
