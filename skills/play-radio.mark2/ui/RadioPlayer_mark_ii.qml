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
    readonly property var audioService: Mycroft.MediaService
    property var media_image: sessionData.media_image
    property var media_station: sessionData.media_station
    property var media_genre: sessionData.media_genre
    property var media_skill: sessionData.media_skill
    property var media_info: sessionData.media_current_station_info

    // Vars with state info.
    property var playerState: sessionData.media_status

    readonly property var mediaService: Mycroft.MediaService

    /* Image {
        id: trackImage
        anchors.top: parent.top
        anchors.topMargin: gridUnit * 2
        anchors.left: parent.left
        anchors.rightMargin: gridUnit * 2
        source: sessionData.media_image
        fillMode: Image.PreserveAspectFit
        height: gridUnit * 18
        width: gridUnit * 18
        z: 100
    } */

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
                height: Mycroft.Units.gridUnit * 15 - bottomArea.height
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

                    Controls.Button {
                        id: prevGenreButton
                        anchors.right: genre.left
                        anchors.top: skillNameLogo.bottom
                        anchors.topMargin: Mycroft.Units.gridUnit * 1
                        width: Mycroft.Units.gridUnit * 3
                        height: Mycroft.Units.gridUnit * 3

                        onClicked: {
                            triggerGuiEvent("gui.prev_genre", {})
                        }

                        background: Rectangle {
                            id: prevGenreBox
                            color: "transparent"
                            Image {
                                id: prevGenreIcon
                                visible: true
                                enabled: true
                                anchors.fill: parent
                                source: "images/prev_genre.svg"
                                // fillMode: Image.PreserveAspectFit
                                // z: 100
                            }
                        }
                    }
                    
                    Marquee {
                        id: genre
                        anchors.top: skillNameLogo.bottom
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.topMargin: Mycroft.Units.gridUnit * 1
                        font.pixelSize: 47
                        // font.styleName: "SemiBold"
                        font.capitalization: Font.Capitalize
                        // heightUnits: 4
                        // widthUnits: 15
                        // leftPadding: Mycroft.Units.gridUnit * 1
                        // rightPadding: Mycroft.Units.gridUnit * 1
                        text: media_genre
                        // maxTextLength: 13
                        color: "white"
			width: gridUnit * 15
			height: gridUnit * 4
                    }

                    Controls.Button {
                        id: nextGenreButton
                        anchors.left: genre.right
                        anchors.top: skillNameLogo.bottom
                        anchors.topMargin: Mycroft.Units.gridUnit * 1
                        width: Mycroft.Units.gridUnit * 3
                        height: Mycroft.Units.gridUnit * 3

                        onClicked: {
                            triggerGuiEvent("gui.prev_genre", {})
                        }

                        background: Rectangle {
                            id: nextGenreBox
                            color: "transparent"
                            Image {
                                id: nextGenreIcon
                                visible: true
                                enabled: true
                                anchors.fill: parent
                                source: "images/next_genre_flipped.svg"
                                // fillMode: Image.PreserveAspectFit
                                // z: 100
                            }
                        }
                    }

                    Marquee {
                        id: station
                        anchors.top: genre.bottom
                        anchors.topMargin: Mycroft.Units.gridUnit * 1
			anchors.horizontalCenter: genre.horizontalCenter
                        font.pixelSize: 24
                        font.capitalization: Font.AllUppercase
                        // font.styleName: "SemiBold"
                        // heightUnits: 4
                        text: media_info + ": " + media_station
                        // maxTextLength: 15
                        color: "white"
			width: gridUnit * 20
			height: gridUnit * 4
                    }
                }

                Item {
                    id: transportControls
                    anchors.top: skillNameLine.bottom
                    // anchors.centerIn: parent
                    // anchors.topMargin: Mycroft.Units.gridUnit * 1
                    // anchors.horizontalCenter: parent.horizontalCenter
                    // anchors.verticalCenter: parent.verticalCenter
                    width: parent.width
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: Mycroft.Units.gridUnit * 5

                    Rectangle {
                        
                    }

                    Controls.Button {
                        id: prevStationButton
                        anchors.right: stopButton.left
                        anchors.top: parent.top
                        // anchors.topMargin: Mycroft.Units.gridUnit * 1
                        anchors.leftMargin: Mycroft.Units.gridUnit * 4
                        anchors.rightMargin: Mycroft.Units.gridUnit * 4
                        width: Mycroft.Units.gridUnit * 3
                        height: Mycroft.Units.gridUnit * 3

                        onClicked: {
                            triggerGuiEvent("gui.prev_station", {})
                        }

                        background: Rectangle {
                            id: prevStationBox
                            
                            color: "transparent"
                            Image {
                                id: prevStationIcon
                                visible: true
                                enabled: true
                                anchors.fill: parent
                                source: "images/prev_station.svg"
                                // fillMode: Image.PreserveAspectFit
                                // z: 100
                            }
                        }
                    }
                    
                    Controls.Button {
                        id: stopButton
                        // anchors.right: nextStationBox.left
                        anchors.top: parent.top
                        anchors.horizontalCenter: parent.horizontalCenter
                        // anchors.verticalCenter: parent.verticalCenter
                        // anchors.centerIn: parent
                        // anchors.topMargin: Mycroft.Units.gridUnit * 1
                        anchors.leftMargin: Mycroft.Units.gridUnit * 4
                        anchors.rightMargin: Mycroft.Units.gridUnit * 4
                        width: Mycroft.Units.gridUnit * 3
                        height: Mycroft.Units.gridUnit * 3

                        onClicked: {
                            triggerGuiEvent("gui.stop_radio", {})
                        }

                        background: Rectangle {
                            id: stopBox
                            color: "transparent"
                            Image {
                                id: stopIcon
                                visible: true
                                enabled: true
                                anchors.fill: parent
                                source: "images/stop.svg"
                                // fillMode: Image.PreserveAspectFit
                                // z: 100
                            }
                        }
                    }

                    Controls.Button {
                        id: nextStationButton
                        anchors.left: stopButton.right
                        anchors.top: parent.top
                        // anchors.topMargin: Mycroft.Units.gridUnit * 1
                        anchors.leftMargin: Mycroft.Units.gridUnit * 4
                        anchors.rightMargin: Mycroft.Units.gridUnit * 4
                        width: Mycroft.Units.gridUnit * 3
                        height: Mycroft.Units.gridUnit * 3

                        onClicked: {
                            triggerGuiEvent("gui.next_station", {})
                        }

                        background: Rectangle {
                            id: nextStationBox
                            color: "transparent"
                            Image {
                                id: nextStationIcon
                                visible: true
                                enabled: true
                                anchors.fill: parent
                                source: "images/next_station.svg"
                                // paintedWidth: 20px
                                // fillMode: Image.PreserveAspectFit
                                // z: 100
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            id: bottomArea
            width: parent.width
            anchors.bottom: parent.bottom
            height: Mycroft.Units.gridUnit * 2
            color: "#22A7F0"
            radius: Mycroft.Units.gridUnit

            Title {
                id: streamingText
                font.pixelSize: 24
                font.capitalization: Font.AllUppercase
                font.styleName: "Bold"
                text: "STREAMING"
                maxTextLength: 15
                color: "white"
            }
        }
    }
}
