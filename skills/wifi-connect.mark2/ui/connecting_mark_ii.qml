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

        // Text instructing the user to wait while the wifi connection is attempted
        WifiLabel {
            id: textFirstLine
            anchors.top: parent.top
            anchors.topMargin: gridUnit * 8
            center: true
            height: gridUnit * 3
            text: "Attempting to"
            width: parent.width
        }

        WifiLabel {
            id: textSecondLine
            anchors.top: textFirstLine.bottom
            anchors.topMargin: gridUnit
            center: true
            height: gridUnit * 3
            text: "connect to Wi-Fi"
            width: parent.width
        }

        // Indeterminate progress bar to show work is being done in the background.
        ProgressBar {
            id: connectionProgress
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: textSecondLine.bottom
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
