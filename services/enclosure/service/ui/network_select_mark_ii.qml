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

/* Define a screen instructing user to a URL for pairing */
Mycroft.Delegate {
    id: root
    leftPadding: 0
    rightPadding: 0
    topPadding: 0
    bottomPadding: 0
    property int gridUnit: Mycroft.Units.gridUnit

    Rectangle {
        id: networkSelectBackground
        anchors.fill: parent
        color: "#000000"

        // Image of mobile phone with wifi networks and MYCROFT access point.
        WifiImage {
            id: networkSelectImage
            anchors.left: parent.left
            anchors.leftMargin: gridUnit * 2
            anchors.top: parent.top
            anchors.topMargin: gridUnit * 2
            heightUnits: 28
            widthUnits: 21
            imageSource: "images/network-select.png"
        }

        Item {
            id: networkSelectText
            anchors.left: networkSelectImage.right
            anchors.leftMargin: gridUnit * 4
            anchors.top: parent.top
            anchors.topMargin: gridUnit * 5
            width: gridUnit * 21

            WifiLabel {
                id: firstLine
                text: "Choose the"
            }

            WifiLabel {
                id: secondLine
                anchors.top: firstLine.bottom
                text: "Wifi network"
            }

            WifiLabel {
                id: thirdLine
                anchors.top: secondLine.bottom
                text: "to connect"
            }

            WifiLabel {
                id: fourthLine
                anchors.top: thirdLine.bottom
                text: "your Mycroft"
            }

            WifiLabel {
                id: fifthLine
                anchors.top: fourthLine.bottom
                text: "device"
            }
        }
    }
}

