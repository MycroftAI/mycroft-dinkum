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

Mycroft.Delegate {
    id: root
    property var code: sessionData.code

    ColumnLayout {
        anchors.fill: parent
        
        Kirigami.Heading {
            id: hey
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignLeft
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            elide: Text.ElideRight
            font.bold: true
            font.weight: Font.Bold
            font.pixelSize: 70
            visible: !content.visible
            color: "#22a7f0"
            text: "Hey Mycroft"
        }
        Kirigami.Heading {
            id: example1
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignLeft
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            elide: Text.ElideRight
            font.bold: true
            font.weight: Font.Bold
            font.pixelSize: 55
            visible: !content.visible
            text: "What's the weather?"
        }
        Kirigami.Heading {
            id: example2
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignLeft
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            elide: Text.ElideRight
            font.bold: true
            font.weight: Font.Bold
            font.pixelSize: 55
            visible: !content.visible
            text: "Tell me about\nAbraham Lincoln"
        }
        Kirigami.Heading {
            id: example3
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignLeft
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            elide: Text.ElideRight
            font.bold: true
            font.weight: Font.Bold
            font.pixelSize: 55
            visible: !content.visible
            text: "Play the news"
        }
    }
}  
