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
import os
import re
import time
from subprocess import CalledProcessError, check_output

from adapt.intent import IntentBuilder
from ifaddr import get_adapters
from mycroft.skills import GuiClear, MycroftSkill, intent_handler


def speakable_name(iface_name: str):
    match = re.match(r"^(wlan|eth)([0-9]+)$", iface_name)
    if match:
        iface_type, iface_num = match.group(1), match.group(2)
        if iface_type == "wlan":
            # wireless 0
            return f"wireless {iface_num}"

        return f"wired {iface_num}"

    return iface_name


def get_ifaces(ignore_list=None):
    """Build a dict with device names and their associated ip address.

    Arguments:
        ignore_list(list): list of devices to ignore. Defaults to "lo"

    Returns:
        (dict) with device names as keys and ip addresses as value.
    """
    ignore_list = ignore_list or ["lo", "lxcbr0"]
    res = {}
    for iface in get_adapters():
        # ignore "lo" (the local loopback)
        if iface.ips and iface.name not in ignore_list:
            for addr in iface.ips:
                if addr.is_IPv4:
                    res[iface.nice_name] = addr.ip
                    break
    return res


def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return False


class IPSkill(MycroftSkill):
    def __init__(self):
        super(IPSkill, self).__init__(name="IPSkill")

    def initialize(self):
        # Only register the SSID intent if iwlist is installed on the system
        if which("iwlist"):
            self.register_intent_file("what.ssid.intent", self.handle_SSID_query)

    @intent_handler(IntentBuilder("IPIntent").require("query").require("IP"))
    def handle_query_IP(self, _):
        dialog = None
        gui = None

        addr = get_ifaces()
        dot = self.dialog_renderer.render("dot")

        if len(addr) == 0:
            dialog = "no network connection"
        elif len(addr) == 1:
            iface, ip = addr.popitem()
            gui = self.gui_show(ip)
            ip_spoken = ip.replace(".", " " + dot + " ")
            dialog = (
                "my address is",
                {"ip": ip_spoken},
            )
        else:
            dialog = []
            gui = []
            for iface, ip in addr.items():
                gui.append(self.gui_show(ip))
                ip_spoken = ip.replace(".", " " + dot + " ")
                dialog.append(
                    (
                        "my address on X is Y",
                        {"interface": speakable_name(iface), "ip": ip_spoken},
                    )
                )

        return self.end_session(dialog=dialog, gui=gui, gui_clear=GuiClear.ON_IDLE)

    def handle_SSID_query(self, _):
        dialog = None
        speak = None
        addr = get_ifaces()
        ssid = None
        if len(addr) == 0:
            dialog = "no network connection"
        else:
            try:
                scanoutput = check_output(["iwlist", "wlan0", "scan"])

                for line in scanoutput.split():
                    line = line.decode("utf-8")
                    if line[:5] == "ESSID":
                        ssid = line.split('"')[1]
            except CalledProcessError:
                # Computer has no wlan0
                pass
            finally:
                if ssid:
                    speak = ssid
                else:
                    dialog = "ethernet.connection"

        return self.end_session(dialog=dialog, speak=speak, gui_clear=GuiClear.ON_IDLE)

    @intent_handler(
        IntentBuilder("")
        .require("query")
        .require("IP")
        .require("last")
        .require("digits")
    )
    def handle_query_last_part_IP(self, _):
        dialog = None
        gui = None

        ip = None
        addr = get_ifaces()
        if len(addr) == 0:
            dialog = "no network connection"
        else:
            if "wlan0" in addr:
                # Wifi is probably the one we're looking for
                ip = addr["wlan0"]
            elif "eth0" in addr:
                # If there's no wifi report the eth0
                ip = addr["eth0"]
            elif len(addr) == 1:
                # If none of the above matches and there's only one device
                ip = list(addr.values())[0]

            if ip:
                gui = self.gui_show(ip)
                dialog = self.speak_last_digits(ip)
            else:
                # Ok now I don't know, I'll just report them all
                dialog, gui = self.speak_multiple_last_digits(addr)

        return self.end_session(dialog=dialog, gui=gui, gui_clear=GuiClear.ON_IDLE)

    def gui_show(self, ip):
        return ("ip-address.qml", {"ip": ip})

    def speak_last_digits(self, ip):
        ip_end = ip.split(".")[-1]
        return ("last digits", {"digits": ip_end})

    def speak_multiple_last_digits(self, addr):
        dialog = []
        for key in addr:
            ip_end = addr[key].split(".")[-1]
            dialog.append(("last digits device", {"device": key, "digits": ip_end}))

        gui = self.gui_show(addr)
        return dialog, gui


def create_skill():
    return IPSkill()
