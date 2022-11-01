# Copyright 2022 Mycroft AI Inc.
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
from mycroft.service import DinkumService
from mycroft.util.log import configure_mycroft_logger
from .namespace import NamespaceManager

configure_mycroft_logger("gui")

class GuiService(DinkumService):
    """
    Service for communicating with Mycroft GUI.

    The Mycroft GUI exists as a pre-compiled "mark2" KDE Plasma theme.
    The code lives here:
      * https://github.com/mycroftAI/mycroft-gui
      * https://github.com/MycroftAI/mycroft-gui-mark-2

    The GUI application runs automatically with Plasma, and connects to the
    Mycroft messagebus (default port: 8181). Mycroft response by creating a
    *second* messagebus (default port: 18181) and telling the GUI to connect to
    that. After the initial exchange, messages are passed over the GUI
    messagebus.

    The GUI can show QML pages in a "namespace" and update "session" data values
    within that namespace. These session data values are accessed as variables
    inside the QML page.  Namespaces usually correspond to skills, but in this
    service they are of the form "{skill_id}.{page_name}". So each page in each
    skill gets its own namespace and session data.

    For the initial Mark II release, only one namespace is active at any time.
    This corresponds to position 0 of the magic namespace
    "mycroft.system.active_skills". Showing a page always replaces this item.

    Input messages:
    * mycroft.gui.connected
      * From GUI, indicates successful connection to Mycroft messagebus
      * Mycroft sends mycroft.gui.port message with port of GUI messagebus
        * See gui_websocket in mycroft.conf
      * Fields:
        * gui_id - unique ID of GUI
    * gui.page.show
      * Replaces the current GUI screen with a new page
      * Fields:
        * namespace - "{skill_id}.{page_name}"
        * page - list of URIs for QML files to display
        * data - key/value pairs of data for QML page
    * gui.status.request
      * Requests the connection status of the GUI
    * gui.value.set

    Output messages:
    * mycroft.gui.port (from GUI)
      * Tells the GUI the port of the GUI websocket messagebus
    * gui.status.request.response
      * Response to gui.status.request

    GUI bus messages:
    * mycroft.session.list.insert
    * mycroft.session.list.remove
    * mycroft.session.set
    * mycroft.gui.list.insert

    Service messages:
    * gui.service.connected
    * gui.service.connected.response
    * gui.initialize.started
    * gui.initialize.ended

    """

    def __init__(self):
        super().__init__(service_id="gui")

    def start(self):
        self.namespace_manager = NamespaceManager(self.bus)

    def stop(self):
        pass


def main():
    """Service entry point"""
    GuiService().main()


if __name__ == "__main__":
    main()
