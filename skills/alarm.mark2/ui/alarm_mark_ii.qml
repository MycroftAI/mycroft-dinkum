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
    id: alarmScreen

    MycroftAlarm {
        id: alarmOne
        backgroundColor: "#22A7F0"
        alarmInfo: sessionData.activeAlarms.alarms[0]
        alarmCount: sessionData.activeAlarmCount
    }

    MycroftAlarm {
        id: alarmTwo
        anchors.left: alarmOne.right
        anchors.leftMargin: gridUnit * 2
        backgroundColor: "#40DBB0"
        alarmInfo: sessionData.activeAlarms.alarms[1]
        alarmCount: sessionData.activeAlarmCount
    }

    MycroftAlarm {
        id: alarmThree
        anchors.top: alarmOne.bottom
        anchors.topMargin: gridUnit * 2
        backgroundColor: "#BDC3C7"
        alarmInfo: sessionData.activeAlarms.alarms[2]
        alarmCount: sessionData.activeAlarmCount
    }

    MycroftAlarm {
        id: alarmFour
        anchors.top: alarmTwo.bottom
        anchors.topMargin: gridUnit * 2
        anchors.left: alarmThree.right
        anchors.leftMargin: gridUnit * 2
        backgroundColor: "#4DE0FF"
        alarmInfo: sessionData.activeAlarms.alarms[3]
        alarmCount: sessionData.activeAlarmCount
    }
}
