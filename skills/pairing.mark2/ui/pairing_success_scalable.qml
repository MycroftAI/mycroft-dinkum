/*
 * Copyright 2021 Mycroft AI Inc.
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

Mycroft.ProportionalDelegate {
    id: root
    skillBackgroundColorOverlay: "#40DBB0"

    ColumnLayout {
        id: grid
        anchors.centerIn: parent

        Image {
            id: statusIcon
            visible: true
            enabled: true
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: proportionalGridUnit * 50
            Layout.preferredHeight: proportionalGridUnit * 50
            source: Qt.resolvedUrl("images/success.svg")
        }

        /* Add some spacing between icon and text */
        Item {
            height: Kirigami.Units.largeSpacing
        }

        Label {
            id: statusLabel
            Layout.alignment: Qt.AlignHCenter
            font.pixelSize: 65
            wrapMode: Text.WordWrap
            renderType: Text.NativeRendering
            font.styleName: "Black"
            font.capitalization: Font.AllUppercase
            text: "Paired"
            color: "white"
        }
    }
}
