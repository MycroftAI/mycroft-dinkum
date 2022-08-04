// Copyright 2022 by Mycroft AI
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

/* Simple music player for the Mark II without any touch screen buttons */
import QtQuick 2.12
import Mycroft 1.0 as Mycroft


Mycroft.CardDelegate {
    id: root

    // Track lengths, durations and positions are always expressed in milliseconds
    // Position is always in milleseconds and relative to track length
    // If track length = 530000, position values range from 0 to 530000
    property var media: sessionData.media
    property var playerState: sessionData.status
    property real playerPosition: sessionData.playerPosition
    property bool isStreaming: media.streaming
    property bool streamTimerPaused: false

    Item {
        id: cardContents
        anchors.fill: parent

        Item {
            id: imageContainer
            anchors.left: parent.left
            anchors.top : parent.top
            anchors.topMargin: gridUnit * 1
            height: gridUnit * 15
            width: parent.width

            Image {
                id: trackImage
                anchors.horizontalCenter: parent.horizontalCenter
                height: parent.height
                width: gridUnit * 27
                source: media.image
                fillMode: Image.PreserveAspectCrop
                z: 100
            }
        }

        // Show the name of the track in the center of the card or scroll it horzontally
        // if it is longer than the width of the card.
        Marquee {
            id: trackName
            anchors.bottom: artistName.top
            anchors.left: parent.left
            anchors.leftMargin: gridUnit * 10
            color: "#FFFFFF"
            font.pixelSize: 35
            font.styleName: "Normal"
            height: gridUnit * 3
            text: media.song
            width: gridUnit * 26
        }

        // Show the name of the artist in the center of the card or scroll it horzontally
        // if it is longer than the width of the card.
        Marquee {
            id: artistName
            anchors.bottom: trackProgressBackground.top
            anchors.left: parent.left
            anchors.leftMargin: gridUnit * 10
            color: "#FFFFFF"
            font.pixelSize: 47
            font.styleName: "Bold"
            height: gridUnit * 4
            text: media.artist
            width: gridUnit * 26
        }

        MusicDuration {
            id: trackElapsedDuration
            anchors.bottom: trackProgressBackground.top
            anchors.left: parent.left
            anchors.leftMargin: gridUnit * 2
            mediaLength: media.length
            duration: playerPosition
        }

        MusicDuration {
            id: trackTotalDuration
            alignRight: true
            anchors.bottom: trackProgressBackground.top
            anchors.left: parent.right
            anchors.leftMargin: gridUnit * -9
            mediaLength: media.length
            duration: media.length
            textWidth: gridUnit * 7
        }

        Rectangle {
            id: trackProgressBackground
            anchors.bottom: parent.bottom
            color: "#22A7F0"
            height: gridUnit * 2
            radius: 16
            visible: media.length !== -1 ? 1 : 0
            width: parent.width

            Rectangle {
                id: trackProgressForeground
                anchors.bottom: parent.bottom
                height: gridUnit * 2
                radius: 16
                visible: media.length !== -1 ? 1 : 0
                color: "#FFFFFF"
                width: 200
            }

            NumberAnimation {
                id: elapsedTimeAnimation
                duration: media.length
                from: 16
                running: true
                property: "width"
                target: trackProgressForeground
                to: gridUnit * 46
            }
        }
    }
}
