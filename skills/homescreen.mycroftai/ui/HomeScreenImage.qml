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
Abstract component for SVGs.

This code is specific to the Mark II device.  It uses a grid of 16x16 pixel
squares for alignment of items.  The image is wrapped in a bounding box for
alignment purposes.
*/
import QtQuick 2.4
import QtQuick.Layouts 1.1
import QtQuick.Controls 2.3
import QtGraphicalEffects 1.0

Item {
    property alias imageSource: homeScreenImage.source
    property int heightUnits
    property int widthUnits

    height: gridUnit * heightUnits
    width: widthUnits ? widthUnits * 3 : parent.width

        Image {
            id: homeScreenImage
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            fillMode: Image.PreserveAspectFit
            height: gridUnit * heightUnits
            layer.effect: DropShadow {
                spread: 0.3
                radius: 8
                color:  Qt.rgba(0.2, 0.2, 0.2, 0.60)
            }
            layer.enabled: true
        }
}
