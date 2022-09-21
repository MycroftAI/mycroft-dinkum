/*
 * Copyright 2020 Aditya Mehra <Aix.m@outlook.com>
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

import QtQuick 2.9
import QtQuick.Layouts 1.3
import QtQuick.Controls 2.2
import QtGraphicalEffects 1.0
import org.kde.kirigami 2.9 as Kirigami
import Mycroft 1.0 as Mycroft

Rectangle {
    id: root
    property color borderColor: {
        if (isMuted) {
            return "#EB5757";

        } else {
            return "#40DBB0";
        }
    }

    property bool isAwake: false
    property bool isMuted: false

    border.color: borderColor
    border.width: Mycroft.Units.gridUnit
    color: "transparent"
    visible: isAwake || isMuted


    Connections {
        target: Mycroft.MycroftController
        onIntentRecevied: {
            switch(type){
            case "recognizer_loop:wakeword":
                root.isAwake = true;
                break
            case "mycroft.mic.listen":
                root.isAwake = true;
                break
            case "recognizer_loop:record_end":
                root.isAwake = false;
                break
            case "mycroft.speech.recognition.unknown":
                root.isAwake = false;
                break
            case "mycroft.mic.mute":
                root.isMuted = true;
                break
            case "mycroft.mic.unmute":
                root.isMuted = false;
                break
            }
        }
    }
}
