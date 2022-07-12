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

import QtQuick 2.6
import QtQuick.Layouts 1.1
import QtQuick.Controls 2.2 as Controls
import QtQuick.Templates 2.2 as T
import org.kde.kirigami 2.5 as Kirigami
import QtGraphicalEffects 1.0
import QtQuick.Window 2.10
import Mycroft 1.0 as Mycroft

Controls.Control {
    id: root

    property alias iconSource: iconSlider.source
    property real value
    property real changeValue
    property alias slider: slider

    leftPadding: Mycroft.Units.gridUnit * 0.4
    rightPadding: Mycroft.Units.gridUnit * 0.4
    topPadding: Mycroft.Units.gridUnit * 0.4
    bottomPadding: Mycroft.Units.gridUnit * 0.4

    onValueChanged: {
        slider.value = value
    }

    contentItem: MouseArea {
        preventStealing: true

        Item {
            id: iconHolderArea
            anchors.left: parent.left
            width: parent.width * 0.10
            height: parent.height

            Kirigami.Icon {
                id: iconSlider
                anchors.fill: parent
                anchors.margins: Mycroft.Units.gridUnit * 0.4
                color: "black"
                layer.enabled: true
                layer.effect: DropShadow {
                    anchors.fill: parent
                    anchors.margins: Mycroft.Units.gridUnit * 0.4
                    radius: 8
                    samples: 16
                    verticalOffset: 0
                    horizontalOffset: 0
                    spread: 0.5
                    color: "#ffffff"
                }
            }
        }

        Rectangle {
            id: rowButtonsArea
            anchors.left: iconHolderArea.right
            anchors.right: labelValHolderArea.left
            height: parent.height
            color: "transparent"

            T.Slider {
                id: slider
                anchors.fill: parent

                onMoved: {
                   changeValue = slider.value
                }

                handle: Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    x: slider.visualPosition * (slider.width - width)
                    color: "#FD9E66"
                    radius: 15
                    implicitWidth: 30
                    implicitHeight: 80
                }

                background: Rectangle {
                    x: slider.leftPadding
                    y: (slider.height - height) / 2
                    width: slider.availableWidth
                    height: 30
                    radius: width
                    color: "#BDC3C7"

                    Rectangle {
                        width: slider.visualPosition * parent.width
                        height: parent.height
                        color: "#22A7F0"
                        radius: 100
                    }
                }
            }
        }

        Rectangle {
            id: labelValHolderArea
            color: "transparent"
            anchors.right: parent.right
            width: parent.width * 0.10
            height: parent.height

            Controls.Label {
                id: labelval
                anchors.fill: parent
                fontSizeMode: Text.Fit
                minimumPixelSize: 3
                font.pixelSize: 32
                verticalAlignment: Text.AlignVCenter
                horizontalAlignment: Text.AlignHCenter
                color: "black"
                text: Math.round(slider.value * 10)
                layer.enabled: true
                layer.effect: DropShadow {
                    radius: 8
                    samples: 16
                    verticalOffset: 0
                    horizontalOffset: 0
                    spread: 0.1
                    width: parent.width
                    height: parent.height
                    color: "#ffffff"
                }
            }
        }
    }

    background: Rectangle {
        radius: Kirigami.Units.largeSpacing
        color: "#ffffff"
        layer.enabled: true
        layer.effect: DropShadow {
            anchors.fill: parent
            radius: 40
            samples: 32
            horizontalOffset: 0
            verticalOffset: 0
            spread: 0
            color: "#000000"
        }
    }
}
