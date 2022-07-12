/*
 * Copyright 2018 by Marco Martin <mart@kde.org>
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
import QtQuick 2.9
import QtQuick.Controls 2.2 as Controls
import org.kde.kirigami 2.4 as Kirigami 

Rectangle {
    id: root

    width: Kirigami.Units.gridUnit * 15
    height: Kirigami.Units.gridUnit * 24

    color: "black"
    state: "idle"

    Kirigami.Theme.colorSet: Kirigami.Theme.Complementary

    property bool wideMode: width > Kirigami.Units.gridUnit * 30

    property int hours: 6
    property string time: "6:59"

    Timer {
        id: ringTimer
        interval: 3000
        running: true
        onTriggered: {
            time = "7:00"
            root.state = "ringing"
        }
    }


    ColumnLayout {
        id: timeLayout
        anchors {
            centerIn: wideMode ? undefined : parent
            left: wideMode ? parent.left : undefined
            top: wideMode ? parent.top : undefined
            margins: Kirigami.Units.gridUnit * 5
        }
        spacing: 0

        Behavior on opacity {
            OpacityAnimator {
                duration: Kirigami.Units.longDuration
                easing.type: Easing.InOutCubic
            }
        }

        Kirigami.Heading {//HACK ON SIZE
            font.pointSize: 50
            text: time
            Layout.preferredHeight: Kirigami.Units.gridUnit * 3
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight
            Kirigami.Icon {
                id: alarmIconPlaceHolder
                Layout.fillHeight: true
                Layout.preferredWidth: height*0.8
                opacity: 0.5

                source: "alarm-symbolic"
            }
            Controls.Label {
                font.pointSize: 20
                Layout.preferredHeight: paintedHeight
                Layout.alignment: Qt.AlignRight
                verticalAlignment: Text.AlignTop
                text: "AM"
                color: root.state == "ringing" ? Kirigami.Theme.textColor : Kirigami.Theme.highlightColor
                Behavior on color {
                    ColorAnimation {
                        duration: Kirigami.Units.longDuration*3
                        easing.type: Easing.InOutCubic
                    }
                }
            }
        }
    }

    Rectangle {
        id: mainRect
        anchors {
            fill: parent
            margins: wideMode ? Kirigami.Units.gridUnit : 0
        }
        radius: Kirigami.Units.gridUnit
        color: "#fffadb"
        clip: true

        Behavior on opacity {
            OpacityAnimator {
                duration: Kirigami.Units.longDuration*5
                easing.type: Easing.InOutCubic
            }
        }

        Rectangle {
            id: alarmRectangle
            anchors.centerIn: parent
            opacity: 0
            scale: 0
            width: Math.round (Math.max(parent.width, parent.height) * 0.8)
            height: width
            radius: root.width
            color: "gold"
            Behavior on scale {
                SpringAnimation {
                    velocity: 20
                    spring: 5
                    mass: 1
                    damping: 0.08
                }
            }
            Behavior on opacity {
                OpacityAnimator {
                    duration: Kirigami.Units.longDuration
                    easing.type: Easing.InOutCubic
                }
            }


            Kirigami.Heading {
                anchors.horizontalCenter: parent.horizontalCenter
                y: parent.height/4
                text: time + "am"
                //Layout.alignment: Qt.AlignBottom
                verticalAlignment: Text.AlignBottom
                font.pointSize: 40
                font.capitalization: Font.SmallCaps
            }

            Kirigami.Icon {
                id: alarmIcon
                anchors {
                    horizontalCenter: parent.horizontalCenter
                    bottom: parent.bottom
                    bottomMargin: parent.height/4
                }

                smooth: true
                width: Kirigami.Units.iconSizes.huge
                height: width
                source: "alarm-symbolic"
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: {
            root.state = "idle"
            ringTimer.restart();
        }
    }

    states: [
        State {
            name: "idle"
            PropertyChanges {
                target: timeLayout
                opacity: 1
            }
            PropertyChanges {
                target: mainRect
                opacity: 0
            }
            PropertyChanges {
                target: alarmRectangle
                scale: 0
                opacity: 0
            }
        },
        State {
            name: "ringing"
            PropertyChanges {
                target: timeLayout
                opacity: 0
            }
            PropertyChanges {
                target: mainRect
                opacity: 1
            }
            PropertyChanges {
                target: alarmRectangle
                scale: 1
                opacity: 1
            }
        }
    ]
}
