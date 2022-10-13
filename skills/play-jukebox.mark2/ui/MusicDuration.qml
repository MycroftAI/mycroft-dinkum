// Copyright 2022, Mycroft AI Inc.
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

/* Abstraction for expressing track duration */
import QtQuick 2.4

Item {
    property alias textWidth: musicText.width
    property bool alignRight: false
    property int duration
    property real mediaLength
    property int oneMinute: 60000
    property int oneSecond: 1000

    // Convert a duration expressed in milliseconds to a MM:SS format
    function formatTime(duration) {
        if (typeof(duration) !== "number") {
            return "";
        }
        var minutes = Math.floor(duration / oneMinute);
        var seconds = ((duration % oneMinute) / oneSecond).toFixed(0);
        return minutes + ":" + (seconds < 10 ? '0' : '') + seconds;
    }

    anchors.bottomMargin: gridUnit
    height: gridUnit * 2
    visible: mediaLength !== -1 ? 1 : 0

    Text {
        id: musicText
        anchors.baseline: parent.bottom
        color: "#FFFFFF"
        font.pixelSize: 35
        font.styleName: "Normal"
        horizontalAlignment: alignRight ? Text.AlignRight : Text.AlignLeft
        text: formatTime(duration)
    }
}
