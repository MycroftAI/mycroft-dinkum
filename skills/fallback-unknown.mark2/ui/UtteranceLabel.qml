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

/*
Abstract component for alphanunumeric values.

The Mark II card design requires the ability to have a text field's baseline sit on one
of the 16 pixel grid lines.  The benefit of this approach is consistent alignment of
text fields that disregards the extra space that can be included around the text for
ascenders and descenders.

To implement this idea, a bounding box is defined around a label for alignment purposes.
The baseline of the text sits on the bottom of the bounding box and the value is
centered within the box.

This code is specific to the Mark II device.  It uses a grid of 16x16 pixel
squares for alignment of items.
*/
import QtQuick 2.4
import QtQuick.Layouts 1.1
import QtQuick.Controls 2.3
import QtGraphicalEffects 1.0
import Mycroft 1.0 as Mycroft

Item {
    property int gridUnit: Mycroft.Units.gridUnit
    property alias text: utteranceLabel.text
    property color textColor: "#FFFFFF"
    property string hotwordAudio
    property string sttAudio

    height: utteranceLabel.height
    width: parent.width
    anchors.left: parent.left
    anchors.top: parent.top

    Button {
        id: playHotwordAudio
        text: "Wake"
        anchors.verticalCenter: utteranceLabel.verticalCenter
        visible: hotwordAudio
        onClicked: triggerGuiEvent("play", { "uri": hotwordAudio })
    }

    Button {
        id: playSttAudio
        text: "STT"
        anchors.left: playHotwordAudio.right
        anchors.leftMargin: gridUnit
        anchors.verticalCenter: utteranceLabel.verticalCenter
        visible: sttAudio
        onClicked: triggerGuiEvent("play", { "uri": sttAudio })
    }

    Label {
        id: utteranceLabel
        anchors.left: playSttAudio.visible ? playSttAudio.right : parent.left
        anchors.leftMargin: gridUnit
        color: textColor
        font.pixelSize: 32
        font.styleName: "Bold"
    }
}
