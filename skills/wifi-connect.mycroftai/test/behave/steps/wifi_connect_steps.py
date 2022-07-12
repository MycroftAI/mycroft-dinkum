from behave import  when

from mycroft.messagebus import Message


@when('no network is detected')
def emit_message(context):
    context.bus.emit(Message('hardware.network-not-detected'))
