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
""" Message bus service for mycroft-core

The message bus facilitates inter-process communication between mycroft-core
processes. It implements a websocket server so can also be used by external
systems to integrate with the Mycroft system.
"""
import logging
import sys
import time
from threading import Thread

import sdnotify
import tornado.options
from tornado import ioloop, web

from .event_handler import MessageBusEventHandler
from .load_config import load_message_bus_config

LOG = logging.getLogger("messagebus")
NOTIFIER = sdnotify.SystemdNotifier()
WATCHDOG_DELAY = 0.5


def main():
    """Service entry point"""
    logging.basicConfig(level=logging.DEBUG)
    LOG.info("Starting message bus service...")

    try:

        # Disable all tornado logging so mycroft loglevel isn't overridden
        tornado.options.parse_command_line(sys.argv + ["--logging=None"])

        config = load_message_bus_config()
        routes = [(config.route, MessageBusEventHandler)]
        application = web.Application(routes, debug=True)
        application.listen(config.port, config.host)

        # Start watchdog thread
        Thread(target=_watchdog, daemon=True).start()

        # Inform systemd that we successfully started
        NOTIFIER.notify("READY=1")

        try:
            ioloop.IOLoop.instance().start()
        except KeyboardInterrupt:
            pass

        LOG.info("Message bus is shutting down...")
    except Exception:
        LOG.exception("Message bus failed to start")


def _watchdog():
    try:
        while True:
            # Prevent systemd from restarting service
            NOTIFIER.notify("WATCHDOG=1")
            time.sleep(WATCHDOG_DELAY)
    except Exception:
        LOG.exception("Unexpected error in watchdog thread")


if __name__ == "__main__":
    main()
