// Copyright 2021, Mycroft AI Inc.
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
Abstract component for displaying images.

This component is intended to cleanly display images of any size within a bounding box.
If the image source is not defined or the image is still loading, a loading spinner is
shown.
*/

import QtQuick 2.4
import QtQuick.Controls 2.2
import QtQuick.Layouts 1.4
import org.kde.kirigami 2.4 as Kirigami
import QtGraphicalEffects 1.0
import Mycroft 1.0 as Mycroft

Item {
    id: imgOuterContainer
    property alias imgSrc: img.source

    Item {
        id: imgInnerContainer
        width: parent.width
        height: parent.height
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom

        Image {
            id: img
            anchors.fill: parent
            opacity: 0
            fillMode: Image.PreserveAspectFit

            asynchronous: true
            onStatusChanged: {
                if (status == Image.Ready) {
                    opacity = 1
                }
            }
        }
    }

    Mycroft.BusyIndicator {
        anchors.centerIn: parent
        running: img.status === Image.Loading || img.source == "" ? 1 : 0
        visible: running
    }
}
