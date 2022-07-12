/*
 *  Copyright 2019 Marco Martin <mart@kde.org>
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
import QtQuick.Layouts 1.1
import QtQuick.Controls 2.0 as Controls

import org.kde.plasma.plasmoid 2.0
import org.kde.plasma.core 2.0 as PlasmaCore

import org.kde.kirigami 2.5 as Kirigami

import org.kde.plasma.private.volume 0.1 as PA

import "panel" as Panel
import "osd" as Osd

import Mycroft 1.0 as Mycroft
import Mycroft.Private.Mark2SystemAccess 1.0

Item {
    id: root
    width: 480
    height: 640

//BEGIN properties
    property Item toolBox
    readonly property bool smallScreenMode: Math.min(width, height) < Kirigami.Units.gridUnit * 18

//END properties

//BEGIN slots
    Component.onCompleted: {
        Mycroft.MycroftController.start();
    }

    Timer {
        interval: 10000
        running: Mycroft.MycroftController.status != Mycroft.MycroftController.Open
        onTriggered: {
            print("Trying to connect to Mycroft");
            Mycroft.MycroftController.start();
        }
    }
    
    Connections {
        target: Mycroft.MycroftController
        
        onIntentRecevied: {
            if (type == "mycroft.display.screenshot.get") {
                var filepath = "/tmp/" + "screen-" +  Qt.formatDateTime(new Date(), "hhmmss-ddMMyy") + ".png"
                mainParent.grabToImage(function(result) {
                    result.saveToFile(filepath);
                });
                Mycroft.MycroftController.sendRequest("mycroft.display.screenshot.result", {"result": filepath});
            }
        }
    }

    
//END slots

    Rectangle {
        anchors.fill: parent
        z: mainParent.z + 1
        // Avoid hiding everything completely
        color: Qt.rgba(0, 0, 0, (1 - plasmoid.configuration.fakeBrightness) * 0.8)
    }

    Item {
        id: mainParent

        rotation: {
            switch (plasmoid.configuration.rotation) {
            case "CW":
                return 90;
            case "CCW":
                return -90;
            case "UD":
                return 180;
            case "NORMAL":
            default:
                return 0;
            }
        }
        anchors.centerIn: parent
        width: rotation == 0 || rotation == 180 ? parent.width : parent.height
        height: rotation == 0 || rotation == 180 ? parent.height : parent.width


//BEGIN VirtualKeyboard
        VirtualKeyboardLoader {
            id: virtualKeyboard
            z: 1000
        }
//END VirtualKeyboard

        Image {
            id: splash
            property var skillGrabResult

            anchors.fill: parent

            source: Qt.resolvedUrl("splash.png")

            fillMode: Image.PreserveAspectFit
            visible: !skillView.currentItem
        }

        // HACK: Take a screenshot of the current skill two times a second, and
        // set it as the background image to avoid showing something else during
        // skill transitions.
        Timer {
            id: skillImageTimer
            interval: 500
            running: true
            repeat: true
            onTriggered: {
                if(skillView.currentItem){
                    skillView.currentItem.grabToImage(function(result) {
                           splash.skillGrabResult = result;
                           splash.source = result.url;
                       });
                }
            }
        }

        //Controls.BusyIndicator {
        //    anchors.centerIn: parent
        //    running: visible
        //    visible: !skillView.currentItem
        //}

        Rectangle {
            anchors.fill: parent
            visible: panel.position < 0.05
            enabled: panel.position < 0.05
            color: Qt.rgba(0, 0, 0, 0)
            z: 10

            Osd.VolumeOSD {
                id: volumeOSD
                height: Mycroft.Units.gridUnit * 6
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: Mycroft.Units.gridUnit * 3
                anchors.rightMargin: Mycroft.Units.gridUnit * 3
                anchors.verticalCenter: parent.verticalCenter
                refSlidingPanel: panel.position
            }
        }

        Mycroft.SkillView {
            id: skillView
            anchors.fill: parent
            Kirigami.Theme.colorSet: Kirigami.Theme.Complementary

            bottomPadding: virtualKeyboard.state == "visible" ? virtualKeyboard.height : 0

            ListenerAnimation {
                id: listenerAnimator
                anchors.fill: parent
            }
        }

        Controls.Button {
            anchors.centerIn: parent
            text: "start"
            visible: Mycroft.MycroftController.status == Mycroft.MycroftController.Closed
            onClicked: Mycroft.MycroftController.start();
        }

        Rectangle {
            id: networkingArea
            anchors.fill: parent

            visible: Mark2SystemAccess.networkConfigurationVisible

            Kirigami.Theme.inherit: false
            Kirigami.Theme.colorSet: Kirigami.Theme.Complementary
            color: Kirigami.Theme.backgroundColor

            PlasmaCore.ColorScope {
                anchors {
                    fill: parent
                    bottomMargin: virtualKeyboard.state == "visible" ? virtualKeyboard.height : 0
                }
                colorGroup: PlasmaCore.Theme.ComplementaryColorGroup

                NetworkingLoader {
                    id: networkingLoader
                    anchors.fill: parent
                }
            }
        }

        Item {
            anchors {
                left: parent.left
                right: parent.right
                top: parent.top
            }
            height: Kirigami.Units.gridUnit
            clip: panel.position <= 0
            Panel.SlidingPanel {
                id: panel
                width: mainParent.width
                height: mainParent.height
            }
        }
    }
}
