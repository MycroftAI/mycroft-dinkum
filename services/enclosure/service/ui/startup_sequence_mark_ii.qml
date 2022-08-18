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

Mycroft.Delegate {
    id: root
    leftPadding: 0
    rightPadding: 0
    topPadding: 0
    bottomPadding: 0
    property int gridUnit: Mycroft.Units.gridUnit

    property int step: sessionData.step

    Rectangle {
        id: connectingBackground
        anchors.fill: parent
        color: "#000000"

        StartupSequenceStep {
            id: connectingToInternet1
            anchors.top: parent.top
            anchors.topMargin: gridUnit * 3
            anchors.leftMargin: gridUnit * 4
            anchors.left: parent.left
            text: "Connect to Internet"
            height: gridUnit * 5
            success: step > 1
            showSpinner: step == 1
        }

        StartupSequenceStep {
            id: syncingClock2
            anchors.top: connectingToInternet1.top
            anchors.topMargin: gridUnit * 6
            anchors.left: connectingToInternet1.left
            text: "Synchronize clock"
            height: gridUnit * 5
            success: step > 2
            showSpinner: step == 2
        }

        StartupSequenceStep {
            id: connectingToServer3
            anchors.top: syncingClock2.top
            anchors.topMargin: gridUnit * 6
            anchors.left: connectingToInternet1.left
            text: "Pair with mycroft.ai"
            height: gridUnit * 5
            success: step > 3
            showSpinner: step == 3
        }

        StartupSequenceStep {
            id: downloadingSettings4
            anchors.top: connectingToServer3.top
            anchors.topMargin: gridUnit * 6
            anchors.left: connectingToInternet1.left
            text: "Download settings"
            height: gridUnit * 5
            success: step > 4
            showSpinner: step == 4
        }

    }
}
