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
import shutil
import wave
from glob import glob
from os import chdir
from os.path import dirname, isfile, join
from tempfile import mkdtemp, mkstemp
from threading import Event, Thread
from zipfile import ZIP_DEFLATED, ZipFile

import mycroft
import pyaudio
import requests
from mycroft import MycroftSkill, intent_handler
from mycroft.api import DeviceApi


class AudioRecorder:
    def __init__(self, **params):
        params.setdefault("format", pyaudio.paInt16)
        params.setdefault("channels", 1)
        params.setdefault("rate", 16000)
        params.setdefault("frames_per_buffer", 1024)
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(input=True, **params)
        self.params = params
        self.frames = []

    def update(self):
        self.frames.append(self.stream.read(self.params["frames_per_buffer"]))

    def stop(self):
        if not self.stream.is_stopped():
            self.stream.stop_stream()
            self.stream.close()
            self.audio.terminate()

    def save(self, filename):
        self.stop()
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(self.params["channels"])
            wf.setsampwidth(self.audio.get_sample_size(self.params["format"]))
            wf.setframerate(self.params["rate"])
            wf.writeframes(b"".join(self.frames))


class ThreadedRecorder(Thread, AudioRecorder):
    def __init__(self, daemon=False, **params):
        Thread.__init__(self, daemon=daemon)
        AudioRecorder.__init__(self, **params)
        self.stop_event = Event()
        self.start()

    def run(self):
        while not self.stop_event.is_set():
            self.update()

    def stop(self):
        if self.is_alive():
            self.stop_event.set()
            self.join()
            AudioRecorder.stop(self)


class SupportSkill(MycroftSkill):
    # TODO: Will need to read from config under KDE, etc.
    log_locations = [
        "/opt/mycroft/*.json",
        "/var/log/mycroft/*.log",
        "/etc/mycroft/*.conf",
        join(dirname(dirname(mycroft.__file__)), "scripts", "logs", "*.log"),
    ]
    log_types = ["audio", "bus", "enclosure", "skills", "update", "voice"]

    def get_log_files(self):
        log_files = sum([glob(pattern) for pattern in self.log_locations], [])
        for i in self.log_locations:
            for log_type in self.log_types:
                fn = i.replace("*", log_type)
                if fn in log_files:
                    continue
                if isfile(fn):
                    log_files.append(fn)
        return log_files

    def create_debug_package(self, extra_files=None):
        fd, name = mkstemp(suffix=".zip")
        tmp_folder = mkdtemp()
        zip_files = []
        for file in self.get_log_files() + (extra_files or []):
            tar_name = file.strip("/").replace("/", ".")
            tmp_file = join(tmp_folder, tar_name)
            shutil.copy(file, tmp_file)
            zip_files.append(tar_name)

        chdir(tmp_folder)
        try:
            with ZipFile(name, "w", ZIP_DEFLATED) as zf:
                for fn in zip_files:
                    zf.write(fn)
        except OSError as e:
            self.log.warning("Failed to create debug package: {}".format(e))
            return None
        return name

    def upload_file(self, filename):
        with open(filename, "rb") as f:
            r = requests.post("https://0x0.st", files={"file": f})
        if r.status_code != 200:
            self.log.warning("Failed to post logs: {}".format(r.text))
            return ""
        return r.text.strip()

    def get_device_name(self):
        try:
            return DeviceApi().get()["name"]
        except Exception:
            self.log.exception("API Error")
            return ":error:"

    def upload_debug_package(self, extra_files=None):
        package_fn = self.create_debug_package(extra_files)
        if not package_fn:
            return None
        url = self.upload_file(package_fn)
        if not url:
            return None
        return url

    # "Create a support ticket"
    @intent_handler("contact.support.intent")
    def troubleshoot(self):
        # Get a problem description from the user
        user_words = self.get_response("confirm.support", num_retries=0)

        yes_words = self.translate_list("yes")

        # TODO: .strip() shouldn't be needed, translate_list should remove
        #       the '\r' I'm seeing.  Remove after bugfix.
        if not user_words or not any(i.strip() in user_words for i in yes_words):
            self.speak_dialog("cancelled")
            return

        sr = self.config_core["listener"]["sample_rate"]
        recorder = ThreadedRecorder(rate=sr)
        description = self.get_response("ask.description", num_retries=0)
        recorder.stop()

        if description is None:
            self.speak_dialog("cancelled")
            return

        fd, audio_file = mkstemp(suffix=".wav")
        recorder.save(audio_file)

        self.speak_dialog("one.moment")

        # Log so that the message will appear in the package of logs sent
        self.log.debug("Troubleshooting Package Description: " + str(description))

        # Upload the logs to the web
        url = self.upload_debug_package([audio_file])
        if not url:
            self.speak_dialog("upload.failed")
            return  # Something failed creating package. More info in logs

        # Create the troubleshooting email and send to user
        data = {
            "url": url,
            "device_name": self.get_device_name(),
            "description": description,
        }
        email = "\n".join(self.translate_template("support.email", data))
        title = self.translate("support.title")
        self.send_email(title, email)
        self.speak_dialog("complete")


def create_skill():
    return SupportSkill()
