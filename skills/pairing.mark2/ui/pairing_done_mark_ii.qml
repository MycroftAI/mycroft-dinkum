/*
 * Copyright 2021 Mycroft AI Inc.
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
import QtQuick.Layouts 1.4
import QtQuick 2.4
import QtQuick.Controls 2.0

import Mycroft 1.0 as Mycroft

/* Define a screen indicating that pairing was successful. */
Mycroft.Delegate {
    id: root
    leftPadding: 0
    rightPadding: 0
    bottomPadding: 0
    topPadding: 0
    property int gridUnit: Mycroft.Units.gridUnit

    Rectangle {
        id: background
        anchors.fill: parent
        color: "#000000"

        PairingLabel {
            id: pairingWakeWord
            anchors.top: parent.top
            anchors.topMargin: gridUnit * 3
            fontSize: 82
            fontStyle: "Bold"
            heightUnits: 4
            text: "Hey Mycroft"
            textColor: "#22a7f0"
        }

        PairingLabel {
            id: pairingExample1
            anchors.top: pairingWakeWord.bottom
            anchors.topMargin: gridUnit * 3
            fontSize: 35
            fontStyle: "Bold"
            heightUnits: 2
            text: "What's the weather?"
        }

        PairingLabel {
            id: pairingExample2
            anchors.top: pairingExample1.bottom
            anchors.topMargin: gridUnit * 3
            fontSize: 35
            fontStyle: "Bold"
            heightUnits: 2
            text: "Tell me about"
        }

        PairingLabel {
            id: pairingExample3
            anchors.top: pairingExample2.bottom
            anchors.topMargin: gridUnit * 2
            fontSize: 35
            fontStyle: "Bold"
            heightUnits: 2
            text: "Abraham Lincoln"
        }

        PairingLabel {
            id: pairingExample4
            anchors.top: pairingExample3.bottom
            anchors.topMargin: gridUnit * 3
            fontSize: 35
            fontStyle: "Bold"
            heightUnits: 2
            text: "Play the news"
        }
    }
}
