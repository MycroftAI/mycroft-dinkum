/*
 * Copyright 2020 Aditya Mehra <Aix.m@outlook.com>
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

import QtQuick 2.9
import QtQuick.Layouts 1.3
import QtQuick.Controls 2.2
import QtGraphicalEffects 1.0
import org.kde.kirigami 2.9 as Kirigami
import Mycroft 1.0 as Mycroft

Rectangle {
    id: rootAnimator
    property Gradient borderGradient: borderGradient
    property int borderWidth: Mycroft.Units.gridUnit
    property bool horizontalMode: parent.width > parent.height ? 1 : 0
    property color primaryBorderColor: {
        if (isMuted) {
            return "#EB5757";

        } else {
            return "#22A7F0";
        }
    }
    readonly property color secondaryBorderColor: Qt.rgba(1, 1, 1, 0.7)

    property bool isAwake: false
    property bool isMuted: false

    color: "transparent"
    visible: isAwake || isMuted


    Connections {
        target: Mycroft.MycroftController
        onIntentRecevied: {
            switch(type){
            case "recognizer_loop:wakeword":
                rootAnimator.isAwake = true;
                break
            case "mycroft.mic.listen":
                rootAnimator.isAwake = true;
                break
            case "recognizer_loop:record_end":
                rootAnimator.isAwake = false;
                break
            case "mycroft.speech.recognition.unknown":
                rootAnimator.isAwake = false;
                break
            case "mycroft.mic.mute":
                rootAnimator.isMuted = true;
                break
            case "mycroft.mic.unmute":
                rootAnimator.isMuted = false;
                break
            }
        }
    }

    Loader {
        id: loader
        width: parent.width
        height: parent.height
        anchors.centerIn: parent
        active: borderGradient
        sourceComponent: border
    }

    Gradient {
        id: borderGradient
        GradientStop {
            position: 0.000
            SequentialAnimation on color {
                loops: Animation.Infinite
                running: rootAnimator.visible
                ColorAnimation { from: rootAnimator.primaryBorderColor; to: rootAnimator.secondaryBorderColor;  duration: 1000 }
                ColorAnimation { from: rootAnimator.secondaryBorderColor; to: rootAnimator.primaryBorderColor;  duration: 1000 }
            }
        }
        GradientStop {
            position: 0.256
            color: Qt.rgba(0, 1, 1, 1)
            SequentialAnimation on color {
                loops: Animation.Infinite
                running: rootAnimator.visible
                ColorAnimation { from: rootAnimator.secondaryBorderColor; to: rootAnimator.primaryBorderColor;  duration: 1000 }
                ColorAnimation { from: rootAnimator.primaryBorderColor; to: rootAnimator.secondaryBorderColor;  duration: 1000 }
            }
        }
        GradientStop {
            position: 0.500
            SequentialAnimation on color {
                loops: Animation.Infinite
                running: rootAnimator.visible
                ColorAnimation { from: rootAnimator.primaryBorderColor; to: rootAnimator.secondaryBorderColor;  duration: 1000 }
                ColorAnimation { from: rootAnimator.secondaryBorderColor; to: rootAnimator.primaryBorderColor;  duration: 1000 }
            }
        }
        GradientStop {
            position: 0.756
            SequentialAnimation on color {
                loops: Animation.Infinite
                running: rootAnimator.visible
                ColorAnimation { from: rootAnimator.secondaryBorderColor; to: rootAnimator.primaryBorderColor;  duration: 1000 }
                ColorAnimation { from: rootAnimator.primaryBorderColor; to: rootAnimator.secondaryBorderColor;  duration: 1000 }
            }
        }
        GradientStop {
            position: 1.000
            SequentialAnimation on color {
                loops: Animation.Infinite
                running: rootAnimator.visible
                ColorAnimation { from: rootAnimator.primaryBorderColor; to: rootAnimator.secondaryBorderColor;  duration: 1000 }
                ColorAnimation { from: rootAnimator.secondaryBorderColor; to: rootAnimator.primaryBorderColor;  duration: 1000 }
            }
        }
    }

    Component {
        id: border
        Item {
            ConicalGradient {
                id: borderFill
                anchors.fill: parent
                gradient: borderGradient
                visible: false
            }

            FastBlur {
                anchors.fill: parent
                source: parent
                radius: 32
            }

            Rectangle {
                id: mask
                radius: rootAnimator.radius
                border.width: rootAnimator.borderWidth
                anchors.fill: parent
                color: 'transparent'
                visible: false
            }

            OpacityMask {
                id: opM
                anchors.fill: parent
                source: borderFill
                maskSource: mask
            }
        }
    }
}
