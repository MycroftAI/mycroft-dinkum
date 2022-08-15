/*
* Copyright 2021 by Aditya Mehra <aix.m@outlook.com>
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

/*
This file defines the 'card' shown when the Radio skill is playing.

There may also be an 'AudioPlayer_scalable.qml' file. Only this file, 
not the scalable version, should be used. The only exception to that is
if you are intending to use this on a device other than the official 
Mycroft enclosure. However, be aware that the scalable version may be 
out of date.
*/

import QtQuick 2.12
import QtQuick.Controls 2.12 as Controls
import QtQuick.Layouts 1.3
import Mycroft 1.0 as Mycroft

Mycroft.CardDelegate {
    id: root
    fillWidth: true
    cardRadius: Mycroft.Units.gridUnit

    // Vars with station info.
    property var media_image: sessionData.media_image
    property var media_station: sessionData.media_station
    property var media_genre: sessionData.media_genre
    property var media_skill: sessionData.media_skill

    // Vars with state info.
    property var playerState: sessionData.media_status

    Rectangle {
        anchors.fill: parent
        radius: Mycroft.Units.gridUnit
        color: "#1B2837"

        Item {
            id: topArea
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: bottomArea.top
            anchors.topMargin: Mycroft.Units.gridUnit * 2
            anchors.leftMargin: Mycroft.Units.gridUnit * 2
            anchors.rightMargin: Mycroft.Units.gridUnit * 2

            Rectangle {
                id: imageContainer
                width: Mycroft.Units.gridUnit * 18
                height: Mycroft.Units.gridUnit * 18
                anchors.top: parent.top // remove this on scalable
                color: "#1B2837"
                radius: Mycroft.Units.gridUnit

                Image {
                    id: trackImage
                    visible: true
                    enabled: true
                    anchors.fill: parent
                    anchors.leftMargin: Mycroft.Units.gridUnit / 2
                    anchors.topMargin: Mycroft.Units.gridUnit / 2
                    anchors.rightMargin: Mycroft.Units.gridUnit / 2
                    anchors.bottomMargin: Mycroft.Units.gridUnit / 2
                    source: media_image
                    fillMode: Image.PreserveAspectFit
                    z: 100
                }
            }

            Rectangle {
                id: mediaControlsContainer
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.left: imageContainer.right
                // anchors.topMargin: provided by root container
                // anchors.rightMargin: provided by root container
                anchors.bottomMargin: Mycroft.Units.gridUnit * 2
                anchors.leftMargin: Mycroft.Units.gridUnit * 2
                width: Mycroft.Units.gridUnit * 24
                height: Mycroft.Units.gridUnit * 22 - bottomArea.height
                color: "transparent"

                Item {
                    id: skillNameLine
                    anchors.top: parent.top
                    // anchors.horizontalCenter: parent.horizontalCenter
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width
                    // height: Mycroft.Units.gridUnit * 5

                    Image {
                        id: skillNameLogo
                        anchors.top: parent.top
                        anchors.horizontalCenter: parent.horizontalCenter
                        source: "images/radio_skill_logo.svg"
                    }

                    Title {
                        id: genre
                        anchors.top: skillNameLogo.bottom
                        anchors.topMargin: Mycroft.Units.gridUnit * 1
                        font.pixelSize: 47
                        // font.styleName: "SemiBold"
                        font.capitalization: Font.Capitalize
                        // heightUnits: 4
                        text: media_genre
                        maxTextLength: 13
                    }

                    Title {
                        id: station
                        anchors.top: genre.bottom
                        // anchors.topMargin: Mycroft.Units.gridUnit * 1
                        font.pixelSize: 24
                        font.capitalization: Font.AllUppercase
                        // font.styleName: "SemiBold"
                        // heightUnits: 4
                        text: media_station
                        maxTextLength: 15
                    }
                }
            }
        }

        Rectangle {
            id: bottomArea
            width: parent.width
            anchors.bottom: parent.bottom
            height: Mycroft.Units.gridUnit * 5
            color: "transparent"

            RowLayout {
                anchors.left: parent.left
                anchors.right: parent.right
                visible: media.length !== -1 ? 1 : 0
                enabled: media.length !== -1 ? 1 : 0
                
                Controls.Label {
                    Layout.alignment: Qt.AlignLeft
                    Layout.leftMargin: Mycroft.Units.gridUnit * 2
                    font.pixelSize: Mycroft.Units.gridUnit * 2
                    font.bold: true
                    horizontalAlignment: Text.AlignLeft
                    verticalAlignment: Text.AlignVCenter
                    text: formatTime(playerPosition)
                    // color: theme.fgColor
                }

                Controls.Label {
                    Layout.alignment: Qt.AlignRight
                    Layout.rightMargin: Mycroft.Units.gridUnit * 2
                    font.pixelSize: Mycroft.Units.gridUnit * 2
                    font.bold: true
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                    text: formatTime(playerDuration)
                    // color: theme.fgColor
                }
            }
        }
    }
}
