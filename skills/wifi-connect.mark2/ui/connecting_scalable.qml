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

/* Define a screen instructing user to wait while connection is attempted */
Mycroft.Delegate {
    id: root
    leftPadding: 0
    rightPadding: 0
    topPadding: 0
    bottomPadding: 0
    property int gridUnit: Mycroft.Units.gridUnit

    Rectangle {
        id: connectingBackground
        anchors.fill: parent
        color: "#000000"

        // Text instructing the user to select the MYCROFT access point
        Item {
            id: firstLine
            anchors.top: parent.top
            anchors.topMargin: gridUnit * 8
            height: gridUnit * 3
            width: parent.width

            Label {
                id: firstLineText
                anchors.baseline: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                font.pixelSize: 47
                font.styleName: "Bold"
                text: "Attempting to"
            }
        }

        Item {
            id: secondLine
            anchors.top: firstLine.bottom
            anchors.topMargin: gridUnit
            height: gridUnit * 3
            width: parent.width

            Label {
                id: secondLineText
                anchors.baseline: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                font.pixelSize: 47
                font.styleName: "Bold"
                text: "connect to Wi-Fi"
            }
        }

        ProgressBar {
            id: connectionProgress
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: secondLine.bottom
            anchors.topMargin: gridUnit * 4
            height: gridUnit
            indeterminate: true
            width: gridUnit * 24

            background: Rectangle {
                anchors.fill: connectionProgress
                radius: 8
            }

        }
    }
}
