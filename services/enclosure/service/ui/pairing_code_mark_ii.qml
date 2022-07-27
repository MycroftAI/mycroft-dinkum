/*
 * Copyright 2018 by Aditya Mehra <aix.m@outlook.com>
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
import QtQuick 2.4
import QtQuick.Controls 2.0
import QtQuick.Layouts 1.4

import Mycroft 1.0 as Mycroft

/* Define a screen requesting that a user create an account before pairing. */
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
        color: "#22a7f0"

        PairingLabel {
            id: pairingCode
            anchors.top: parent.top
            anchors.topMargin: gridUnit * 11
            fontSize: 118
            fontStyle: "Black"
            heightUnits: 6
            text: sessionData.pairingCode
        }

        PairingLabel {
            id: pairingUrl
            anchors.top: pairingCode.bottom
            anchors.topMargin: gridUnit * 3
            fontSize: 47
            fontStyle: "Bold"
            heightUnits: 3
            text: "mycroft.ai/pair"
            textColor: "#2C3E50"
        }
    }
}
