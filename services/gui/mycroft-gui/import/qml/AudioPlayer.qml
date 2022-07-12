/*
 * Copyright 2019 by Aditya Mehra <aix.m@outlook.com>
 * Copyright 2019 by Marco Martin <mart@kde.org>
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
import QtQuick.Controls 2.2 as Controls
import QtQuick.Layouts 1.3
import QtMultimedia 5.9
import org.kde.kirigami 2.5 as Kirigami
import Mycroft 1.0 as Mycroft


Item {
    id: root

    property alias source: player.source
    property string status: "stop"
    property int switchWidth: Kirigami.Units.gridUnit * 22
    property alias thumbnail: albumimg.source
    property alias title: songtitle.text
    property bool progressBar: true
    property bool thumbnailVisible: true
    property bool titleVisible: true
    property var nextAction
    property var previousAction
    property alias currentState: player.status
    readonly property bool horizontal: width > switchWidth

    onEnabledChanged: syncStatusTimer.restart()
    onSourceChanged: syncStatusTimer.restart()
    Component.onCompleted: syncStatusTimer.restart()

    // Sometimes can't be restarted reliably immediately, put it in a timer
    onActiveFocusChanged: {
        if(activeFocus){
            playButton.forceActiveFocus();
        }
    }

    function msToTime(duration) {
        var seconds = parseInt((duration/1000)%60);
        var minutes = parseInt((duration/(1000*60))%60);

        minutes = (minutes < 10) ? "0" + minutes : minutes;
        seconds = (seconds < 10) ? "0" + seconds : seconds;

        return minutes + ":" + seconds;
    }
    
    Timer {
        id: syncStatusTimer
        interval: 0
        onTriggered: {
            if (enabled && status == "play") {
                player.play();
            } else if (status == "stop") {
                player.stop();
            } else {
                player.pause();
            }
        }
    }
    MediaPlayer {
        id: player
        autoPlay: false
        readonly property string currentStatus: root.enabled ? root.status : "pause"

        onCurrentStatusChanged: {
            switch(currentStatus){
            case "stop":
                player.stop();
                break;
            case "pause":
                player.pause()
                break;
            case "play":
                player.play()
                break;
            }
        }
    }


    GridLayout {
        anchors {
            top: root.horizontal ? undefined : parent.top
            left: parent.left
            right: parent.right
            bottom: parent.bottom
        }
        columns: root.horizontal ? 2 : 1
        height: implicitHeight

        Image {
            id: albumimg
            fillMode: Image.PreserveAspectCrop
            visible: root.thumbnailVisible ? 1 : 0
            enabled: root.thumbnailVisible ? 1 : 0
            Layout.preferredWidth: root.horizontal ? Kirigami.Units.gridUnit * 10 : Kirigami.Units.gridUnit * 5
            Layout.preferredHeight: root.horizontal ? Kirigami.Units.gridUnit * 10 : Kirigami.Units.gridUnit * 5
            Layout.alignment: Qt.AlignHCenter
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Kirigami.Units.largeSpacing

            Kirigami.Heading {
                id: songtitle
                text: title
                level: root.horizontal ? 1 : 3
                Layout.fillWidth: true
                elide: Text.ElideRight
                font.capitalization: Font.Capitalize
                visible: root.titleVisible ? 1 : 0
                enabled: root.titleVisible ? 1 : 0
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.alignment: root.horizontal ? Qt.AlignLeft : Qt.AlignHCenter
                spacing: Kirigami.Units.largeSpacing

                Controls.RoundButton {
                    id: previousButton
                    Layout.minimumWidth: Kirigami.Units.iconSizes.smallMedium
                    Layout.minimumHeight: width
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.maximumWidth: Kirigami.Units.gridUnit * 3
                    Layout.maximumHeight: width
                    focus: false
                    icon.name: "media-seek-backward"
                    KeyNavigation.right: playButton
                    KeyNavigation.down: seekableslider
                    onClicked: {
                        triggerGuiEvent(previousAction, {})
                    }
                    
                    background: Rectangle {
                        Kirigami.Theme.colorSet: Kirigami.Theme.Button
                        radius: width
                        color: previousButton.activeFocus ? Kirigami.Theme.highlightColor : Kirigami.Theme.backgroundColor
                    }
                    
                    Keys.onReturnPressed: {
                        clicked()
                    }
                }

                Controls.RoundButton {
                    id: playButton
                    Layout.minimumWidth: Kirigami.Units.iconSizes.medium
                    Layout.minimumHeight: width
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.maximumWidth: Kirigami.Units.gridUnit * 4
                    Layout.maximumHeight: width
                    focus: false
                    icon.name: player.playbackState === MediaPlayer.PlayingState ? "media-playback-pause" : "media-playback-start"
                    KeyNavigation.left: previousButton
                    KeyNavigation.right: nextButton
                    KeyNavigation.down: seekableslider
                    onClicked: {
                        player.playbackState === MediaPlayer.PlayingState ? player.pause() : player.play()
                    }
                    
                    background: Rectangle {
                        Kirigami.Theme.colorSet: Kirigami.Theme.Button
                        radius: width
                        color: playButton.activeFocus ? Kirigami.Theme.highlightColor : Kirigami.Theme.backgroundColor
                    }
                    
                    Keys.onReturnPressed: {
                        clicked()
                    }
                }

                Controls.RoundButton {
                    id: nextButton
                    Layout.minimumWidth: Kirigami.Units.iconSizes.smallMedium
                    Layout.minimumHeight: width
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.maximumWidth: Kirigami.Units.gridUnit * 3
                    Layout.maximumHeight: width
                    focus: false
                    icon.name: "media-seek-forward"
                    KeyNavigation.left: playButton
                    KeyNavigation.down: seekableslider
                    onClicked: {
                        triggerGuiEvent(nextAction, {})
                    }
                    
                    background: Rectangle {
                        Kirigami.Theme.colorSet: Kirigami.Theme.Button
                        radius: width
                        color: nextButton.activeFocus ? Kirigami.Theme.highlightColor : Kirigami.Theme.backgroundColor
                    }
                    
                    Keys.onReturnPressed: {
                        clicked()
                    }
                }
            }

            RowLayout {
                spacing: Kirigami.Units.smallSpacing
                Layout.fillWidth: true
                visible: root.progressBar ? 1 : 0
                enabled: root.progressBar ? 1 : 0

                Controls.Slider {
                    id: seekableslider
                    to: player.duration
                    Layout.fillWidth: true
                    property bool sync: false

                    onValueChanged: {
                        if (!sync)
                            player.seek(value)
                    }

                    Connections {
                        target: player
                        onPositionChanged: {
                            seekableslider.sync = true
                            seekableslider.value = player.position
                            seekableslider.sync = false
                        }
                    }
                    
                    Keys.onLeftPressed: {
                        var l = 0
                        l = seekableslider.position - 0.05
                        seekableslider.value = seekableslider.valueAt(l);                        
                    }
                    
                    Keys.onRightPressed: {
                        var l = 0
                        l = seekableslider.position + 0.05
                        seekableslider.value = seekableslider.valueAt(l);
                    }
                }

                Controls.Label {
                    id: positionLabel
                    text: msToTime(player.position) + " / " + msToTime(player.duration)
                }
            }
        }
    }
}
 
