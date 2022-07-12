// Copyright 2021 Mycroft AI Inc.
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
Defines a scalable idle screen for use on different screen sizes.
*/
import QtQuick.Layouts 1.4
import QtQuick 2.12
import QtQuick.Controls 2.0
import org.kde.kirigami 2.4 as Kirigami
import QtGraphicalEffects 1.0
import Mycroft 1.0 as Mycroft

Mycroft.CardDelegate {
    id: idleRoot
    skillBackgroundColorOverlay: "transparent"
    cardBackgroundOverlayColor: "transparent"
    cardRadius: 0
    skillBackgroundSource: Qt.resolvedUrl(sessionData.wallpaperPath)
    property bool horizontalMode: idleRoot.width > idleRoot.height ? 1 : 0
    property real dropSpread: 0.3
    property real dropRadius: 8
    property real dropSample: 8
    property color dropColor: Qt.rgba(0.2, 0.2, 0.2, 0.60)

    Item {
        anchors.fill: parent

        RowLayout {
            id: weatherItemBox
            anchors.top: parent.top
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.round(parent.width * 0.1969)
            height: Math.round(parent.height * 0.2150)
            spacing: Mycroft.Units.gridUnit

            Kirigami.Icon {
                id: weatherItemIcon
                source: sessionData.homeScreenWeatherCondition
                Layout.preferredWidth: Mycroft.Units.gridUnit * 3
                Layout.preferredHeight: Mycroft.Units.gridUnit * 3
                layer.enabled: true
                layer.effect: DropShadow {
                    spread: idleRoot.dropSpread
                    radius: idleRoot.dropRadius
                    color:  idleRoot.dropColor
                }
            }

            Text {
                id: weatherItem
                text: sessionData.homeScreenTemperature + "°"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.alignment: Qt.AlignRight | Qt.AlignTop
                fontSizeMode: Text.Fit;
                minimumPixelSize: 50;
                font.pixelSize: parent.height;
                verticalAlignment: Text.AlignVCenter
                horizontalAlignment: Text.AlignHCenter
                color: "white"
                layer.enabled: true
                layer.effect: DropShadow {
                    spread: idleRoot.dropSpread
                    radius: idleRoot.dropRadius
                    color:  idleRoot.dropColor
                }
            }
        }

        Item {
            id: timeItemBox
            anchors.top: parent.top
            anchors.topMargin: Math.round(parent.height * 0.10)
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.round(parent.width * 0.70)
            height: Math.round(parent.height * 0.6565)

            Text {
                id: timeItem
                anchors.fill: parent
                text: sessionData.homeScreenTime.replace(":", "꞉")
                fontSizeMode: Text.Fit;
                font.bold: true;
                minimumPixelSize: 50;
                font.pixelSize: parent.height;
                verticalAlignment: Text.AlignVCenter
                horizontalAlignment: Text.AlignHCenter
                color: "white"
                layer.enabled: true
                layer.effect: DropShadow {
                    spread: idleRoot.dropSpread
                    radius: idleRoot.dropRadius
                    color:  idleRoot.dropColor
                }
            }
        }

        Item {
            id: dateItemBox
            anchors.top: timeItemBox.bottom
            anchors.topMargin: -Math.round(height * 0.40)
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.round(parent.width * 0.6065)
            height: Math.round(parent.height * 0.1950)

            Text {
                id: dateItem
                anchors.fill: parent
                text: sessionData.homeScreenDate
                fontSizeMode: Text.Fit;
                minimumPixelSize: 50;
                font.pixelSize: parent.height;
                verticalAlignment: Text.AlignVCenter
                horizontalAlignment: Text.AlignHCenter
                color: "white"
                layer.enabled: true
                layer.effect: DropShadow {
                    spread: idleRoot.dropSpread
                    radius: idleRoot.dropRadius
                    color:  idleRoot.dropColor
                }
            }
        }

        RowLayout {
            id: bottomItemBox
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.round(parent.width * 0.1630)
            height: Mycroft.Units.gridUnit * 2
            spacing: Mycroft.Units.gridUnit * 2.75

            Kirigami.Icon {
                id: micItemIcon
                source: Qt.resolvedUrl("icons/mic-mute.svg")
                Layout.preferredWidth: Mycroft.Units.gridUnit * 2
                Layout.preferredHeight: Mycroft.Units.gridUnit * 2
                color: "white"
                visible: false
                layer.enabled: true
                layer.effect: DropShadow {
                    spread: idleRoot.dropSpread
                    radius: idleRoot.dropRadius
                    color:  idleRoot.dropColor
                }
            }

            Kirigami.Icon {
                id: camItemIcon
                source: Qt.resolvedUrl("icons/cam.svg")
                width: Mycroft.Units.gridUnit * 3
                height: Mycroft.Units.gridUnit * 3
                color: "white"
                visible: false
                layer.enabled: true
                layer.effect: DropShadow {
                    spread: idleRoot.dropSpread
                    radius: idleRoot.dropRadius
                    color:  idleRoot.dropColor
                }
            }
        }

        Kirigami.Icon {
            id: widgetLeftTop
            anchors.left: parent.left
            anchors.top: parent.top
            source: Qt.resolvedUrl("icons/mic.svg")
            width: Mycroft.Units.gridUnit * 3
            height: Mycroft.Units.gridUnit * 3
            color: "white"
            visible: false
            layer.enabled: true
            layer.effect: DropShadow {
                spread: idleRoot.dropSpread
                radius: idleRoot.dropRadius
                color:  idleRoot.dropColor
            }
        }

        Kirigami.Icon {
            id: widgetLeftBottom
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            source: Qt.resolvedUrl("icons/mic.svg")
            width: Mycroft.Units.gridUnit * 3
            height: Mycroft.Units.gridUnit * 3
            color: "white"
            visible: false
            layer.enabled: true
            layer.effect: DropShadow {
                spread: idleRoot.dropSpread
                radius: idleRoot.dropRadius
                color:  idleRoot.dropColor
            }
        }

        Kirigami.Icon {
            id: widgetRightTop
            anchors.right: parent.right
            anchors.top: parent.top
            source: Qt.resolvedUrl("icons/mic.svg")
            width: Mycroft.Units.gridUnit * 3
            height: Mycroft.Units.gridUnit * 3
            color: "white"
            visible: false
            layer.enabled: true
            layer.effect: DropShadow {
                spread: idleRoot.dropSpread
                radius: idleRoot.dropRadius
                color:  idleRoot.dropColor
            }
        }
    }
    
    Label {
        id: buildDate
        visible: sessionData.buildDateTime === "" ? 0 : 1
        enabled: sessionData.buildDateTime === "" ? 0 : 1
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.bottomMargin: -Mycroft.Units.gridUnit * 2
        font.pixelSize: 22
        wrapMode: Text.WordWrap
        text: "BI " + sessionData.buildDateTime
        color: "white"
        layer.enabled: true
        layer.effect: DropShadow {
            spread: idleRoot.dropSpread
            radius: idleRoot.dropRadius
            color:  idleRoot.dropColor
        }
    }
}
