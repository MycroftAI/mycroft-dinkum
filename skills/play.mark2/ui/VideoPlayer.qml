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

import QtMultimedia 5.12
import QtQuick.Layouts 1.4
import QtQuick 2.9
import QtQuick.Controls 2.12 as Controls
import org.kde.kirigami 2.10 as Kirigami
import QtQuick.Window 2.3
import QtGraphicalEffects 1.0
import Mycroft 1.0 as Mycroft
import "." as Local

Mycroft.Delegate {
    id: root

    readonly property var videoService: Mycroft.MediaService

    property var videoSource
    property var videoStatus
    property var videoRepeat
    property var videoThumb
    property var videoTitle
    property var videoAuthor
    property var playerMeta
    property var cpsMeta
    property bool busyIndicate: false

    //Player Button Control Actions
    property var nextAction: "mediaservice.gui.requested.next"
    property var previousAction: "mediaservice.gui.requested.previous"
    property var currentState: videoService.playbackState

    //Mediaplayer Related Properties To Be Set By Probe MediaPlayer
    property var playerDuration
    property var playerPosition

    fillWidth: true
    background: Rectangle {
        color: "black"
    }
    leftPadding: 0
    topPadding: 0
    rightPadding: 0
    bottomPadding: 0

    Keys.onDownPressed: {
        controlBarItem.opened = true
        controlBarItem.forceActiveFocus()
    }

    onFocusChanged: {
        video.forceActiveFocus();
    }

    onVideoSourceChanged: {
        root.play()
        delay(6000, function() {
            infomationBar.visible = false;
        })
    }

    function play(){
        videoService.playURL(videoSource)
    }

    function pause(){
        videoService.playerPause()
    }

    function stop(){
        videoService.playerStop()
    }

    function resume(){
        videoService.playerContinue()
    }

    function seek(val){
        videoService.playerSeek(val)
    }

    Connections {
        target: Window.window
        onVisibleChanged: {
            if(video.playbackState == MediaPlayer.PlayingState) {
                stop()
            }
        }
    }

    Connections {
        target: Mycroft.MediaService

        onDurationChanged: {
            playerDuration = dur
        }
        onPositionChanged: {
            playerPosition = pos
        }
        onPlayRequested: {
            videoSource = videoService.getTrack()
        }

        onStopRequested: {
            videoSource = ""
        }

        onMediaStatusChanged: {
            console.log(status)
        }

        onMetaUpdated: {
            console.log("Got Meta Update Signal Here")

            root.playerMeta = videoService.getPlayerMeta()
            root.videoTitle = root.playerMeta.Title ? root.playerMeta.Title : ""
            if(root.playerMeta.hasOwnProperty("Artist")) {
                root.videoAuthor = root.playerMeta.Artist
            } else if(root.playerMeta.hasOwnProperty("ContributingArtist")) {
                root.videoAuthor = root.playerMeta.ContributingArtist
            } else {
                root.videoAuthor = ""
            }
        }

        onMetaReceived: {
            root.cpsMeta = videoService.getCPSMeta()
            root.videoThumb = root.cpsMeta.thumbnail
        }
    }


    Timer {
        id: delaytimer
    }

    function delay(delayTime, cb) {
        delaytimer.interval = delayTime;
        delaytimer.repeat = false;
        delaytimer.triggered.connect(cb);
        delaytimer.start();
    }

    controlBar: Local.SeekControl {
        id: seekControl
        anchors {
            bottom: parent.bottom
        }
        title: videoTitle
        videoControl: root
        duration: root.playerDuration
        playPosition: root.playerPosition
        onSeekPositionChanged: seek(seekPosition);
        z: 1000
    }

    Item {
        id: videoRoot
        anchors.fill: parent

        Rectangle {
            id: infomationBar
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            visible: false
            color: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.6)
            implicitHeight: vidTitle.implicitHeight + Kirigami.Units.largeSpacing * 2
            z: 1001

            onVisibleChanged: {
                delay(15000, function() {
                    infomationBar.visible = false;
                })
            }

            Controls.Label {
                id: vidTitle
                visible: true
                maximumLineCount: 2
                wrapMode: Text.Wrap
                anchors.left: parent.left
                anchors.leftMargin: Kirigami.Units.largeSpacing
                anchors.verticalCenter: parent.verticalCenter
                text: videoTitle
                z: 100
            }
        }

        VideoOutput {
            id: video
            anchors.fill: parent
            source: videoService

            Keys.onReturnPressed: {
                video.playbackState == MediaPlayer.PlayingState ? video.pause() : video.play()
            }

            Keys.onDownPressed: {
                controlBarItem.opened = true
                controlBarItem.forceActiveFocus()
            }

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    controlBarItem.opened = !controlBarItem.opened
                }
            }
        }
    }
}

