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

import QtQuick.Layouts 1.4
import QtQuick 2.4
import QtQuick.Controls 2.0
import org.kde.kirigami 2.5 as Kirigami
import Mycroft 1.0 as Mycroft

Mycroft.ProportionalDelegate {
    id: root
    property int gridUnit: Mycroft.Units.gridUnit

    UtteranceLabel {
        id: utterance1
        text: sessionData.utterance1
        hotwordAudio: sessionData.utterance1_hotword_audio
        sttAudio: sessionData.utterance1_stt_audio
    }

    UtteranceLabel {
        id: utterance2
        anchors.topMargin: gridUnit * 6
        Layout.row: 2
        text: sessionData.utterance2
        hotwordAudio: sessionData.utterance2_hotword_audio
        sttAudio: sessionData.utterance2_stt_audio
    }

    UtteranceLabel {
        id: utterance3
        anchors.topMargin: gridUnit * 12
        text: sessionData.utterance3
        hotwordAudio: sessionData.utterance3_hotword_audio
        sttAudio: sessionData.utterance3_stt_audio
    }

    UtteranceLabel {
        id: utterance4
        anchors.topMargin: gridUnit * 18
        text: sessionData.utterance4
        hotwordAudio: sessionData.utterance4_hotword_audio
        sttAudio: sessionData.utterance4_stt_audio
    }

    Button {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        text: "Back"
        onClicked: {
            triggerGuiEvent("close", {})
        }
    }
}
