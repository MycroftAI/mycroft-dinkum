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
import logging
import sys
import time
from threading import Thread

import sdnotify
from mycroft.configuration import Configuration
from mycroft_bus_client import Message, MessageBusClient

from .voice_loop import (
    load_hotword_module,
    load_stt_module,
    load_vad_detector,
    voice_loop,
)

SERVICE_ID = "voice"
LOG = logging.getLogger(SERVICE_ID)
NOTIFIER = sdnotify.SystemdNotifier()
WATCHDOG_DELAY = 0.5


def main():
    """Service entry point"""
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[
            logging.FileHandler(f"/var/log/mycroft/{SERVICE_ID}.log", mode="a"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    LOG.info("Starting service...")

    try:
        bus = _connect_to_bus()
        config = Configuration.get()
        hotword = load_hotword_module(config)
        vad = load_vad_detector()
        stt = load_stt_module(config, bus)

        # Start watchdog thread
        Thread(target=_watchdog, daemon=True).start()

        # Inform systemd that we successfully started
        NOTIFIER.notify("READY=1")
        bus.emit(Message(f"{SERVICE_ID}.initialize.ended"))

        try:
            voice_loop(config=config, bus=bus, hotword=hotword, vad=vad, stt=stt)
        except KeyboardInterrupt:
            pass
        finally:
            bus.close()

        LOG.info("Service is shutting down...")
    except Exception:
        LOG.exception("Service failed to start")


def _connect_to_bus() -> MessageBusClient:
    bus = MessageBusClient()
    bus.run_in_thread()
    bus.connected_event.wait()
    bus.emit(Message(f"{SERVICE_ID}.initialize.started"))
    LOG.info("Connected to Mycroft Core message bus")

    return bus


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
