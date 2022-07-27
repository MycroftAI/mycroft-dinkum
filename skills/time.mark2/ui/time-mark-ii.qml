// Copyright 2021, Mycroft AI Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//    http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

import QtQuick 2.4
import QtQuick.Controls 2.0
import Mycroft 1.0 as Mycroft

Mycroft.CardDelegate {
    id: timeScreen

    TimeLabel {
        id: location
        heightUnits: 4
        fontSize: 47
        fontStyle: "Medium"
        text: sessionData.location
    }

    Item {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: gridUnit * 6
        width: {
            if (sessionData.hour.length === 1) {
                return gridUnit * 35
            } else {
                return gridUnit * 45
            }
        }

        TimeLabel {
            id: hour
            heightUnits: 14
            widthUnits: sessionData.hour.length * 10
            fontSize: 300
            fontStyle: "Bold"
            text: sessionData.hour
        }

        TimeLabel {
            id: minute
            anchors.left: hour.right
            anchors.leftMargin: gridUnit * 5
            textColor: "#22A7F0"
            heightUnits: 14
            widthUnits: 20
            fontSize: 300
            fontStyle: "Bold"
            text: sessionData.minute
        }
    }
}
