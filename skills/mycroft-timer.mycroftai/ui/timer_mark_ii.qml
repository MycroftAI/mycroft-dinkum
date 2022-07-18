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
    id: timerScreen

    MycroftTimer {
        id: timerOne
        backgroundColor: "#22A7F0"
        timerInfo: sessionData.activeTimers.timers[0]
        timerCount: sessionData.activeTimerCount
        visible: sessionData.activeTimerCount > 0
    }

    MycroftTimer {
        id: timerTwo
        anchors.left: timerOne.right
        anchors.leftMargin: gridUnit * 2
        backgroundColor: "#40DBB0"
        timerInfo: sessionData.activeTimers.timers[1]
        timerCount: sessionData.activeTimerCount
        visible: sessionData.activeTimerCount > 1
    }

    MycroftTimer {
        id: timerThree
        anchors.top: timerOne.bottom
        anchors.topMargin: gridUnit * 2
        backgroundColor: "#BDC3C7"
        timerInfo: sessionData.activeTimers.timers[2]
        timerCount: sessionData.activeTimerCount
        visible: sessionData.activeTimerCount > 2
    }

    MycroftTimer {
        id: timerFour
        anchors.top: timerTwo.bottom
        anchors.topMargin: gridUnit * 2
        anchors.left: timerThree.right
        anchors.leftMargin: gridUnit * 2
        backgroundColor: "#4DE0FF"
        timerInfo: sessionData.activeTimers.timers[3]
        timerCount: sessionData.activeTimerCount
        visible: sessionData.activeTimerCount > 3
    }
}
