/*
 * Copyright 2018 by Aditya Mehra <aix.m@outlook.com>
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
import QtQuick 2.4
import QtQuick.Controls 2.0
import org.kde.kirigami 2.4 as Kirigami

import Mycroft 1.0 as Mycroft

/* Define a screen instructing user to a URL for pairing */
Mycroft.Delegate {
    id: root
    property var spacingUnit: 10
    property bool horizontalMode: root.width > root.height ? 1 : 0
    leftPadding: 0
    rightPadding: 0
    topPadding: 0
    bottomPadding: 0

    Rectangle {
        anchors.fill: parent
        color: "#000000"

        GridLayout {
            anchors.fill: parent
            columns: horizontalMode ? 2 : 1

            Image {
                id: img
                source: Qt.resolvedUrl("images/phone.svg")
                Layout.preferredWidth: horizontalMode ? parent.width / 2 : parent.width
                Layout.preferredHeight: horizontalMode ? parent.height * 0.9 : parent.height / 2
                Layout.alignment: Qt.AlignBottom
                Layout.bottomMargin: -Kirigami.Units.largeSpacing
                fillMode: Image.PreserveAspectFit
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true

                Kirigami.Heading {
                    id: firstLine
                    Layout.fillWidth: true
                    Layout.alignment: horizontalMode ? Qt.AlignLeft : Qt.AlignHCenter | Qt.AlignVCenter
                    Layout.leftMargin: horizontalMode ? spacingUnit : 0
                    horizontalAlignment: horizontalMode ? Text.AlignLeft : Text.AlignHCenter
                    verticalAlignment: horizontalMode ? Text.AlignVCenter : Text.AlignTop
                    wrapMode: Text.WordWrap
                    elide: Text.ElideRight
                    font.weight: Font.Bold
                    font.pixelSize: horizontalMode ? root.width * 0.050 : root.height * 0.065
                    text: "I need to be activated,"
                }
                Kirigami.Heading {
                    id: secondLine
                    Layout.fillWidth: true
                    Layout.alignment: horizontalMode ? Qt.AlignLeft : Qt.AlignHCenter | Qt.AlignVCenter
                    Layout.leftMargin: horizontalMode ? spacingUnit : 0
                    horizontalAlignment: horizontalMode ? Text.AlignLeft : Text.AlignHCenter
                    verticalAlignment: horizontalMode ? Text.AlignVCenter : Text.AlignTop
                    wrapMode: Text.WordWrap
                    elide: Text.ElideRight
                    font.weight: Font.Bold
                    font.pixelSize: horizontalMode ? root.width * 0.050 : root.height * 0.065
                    text: "pair me at"
                }
                Kirigami.Heading {
                    id: url
                    Layout.fillWidth: true
                    Layout.leftMargin: horizontalMode ? spacingUnit : 0
                    Layout.alignment: horizontalMode ? Qt.AlignLeft : Qt.AlignHCenter | Qt.AlignTop
                    horizontalAlignment: horizontalMode ? Text.AlignLeft : Text.AlignHCenter
                    verticalAlignment: horizontalMode ? Text.AlignVCenter : Text.AlignTop
                    wrapMode: Text.WordWrap
                    elide: Text.ElideRight
                    font.weight: Font.Bold
                    font.pixelSize: horizontalMode ? root.width * 0.035 : root.height * 0.05
                    color: "#22a7f0"
                    text: "mycroft.ai/pair"
                }
            }
        }
    }
}

