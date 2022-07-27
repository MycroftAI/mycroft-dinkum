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
        color: "#EB5757"

        // Image of a check mark indicating success.
        WifiImage {
            id: wifiFailureImage
            anchors.left: parent.left
            anchors.leftMargin: gridUnit * 15
            anchors.top: parent.top
            anchors.topMargin: gridUnit * 2
            heightUnits: 20
            imageSource: "images/failure.svg"
            widthUnits: 20
        }


        WifiLabel {
            id: textFirstLine
            anchors.top: wifiFailureImage.bottom
            center: true
            height: gridUnit * 3
            text: "Connection failed"
            width: parent.width
        }

        WifiLabel {
            id: textSecondLine
            anchors.top: textFirstLine.bottom
            center: true
            height: gridUnit * 3
            text: "Wi-Fi setup is restarting"
            width: parent.width
        }
    }
}
