/*
 * Copyright 2019 Marco Martin <mart@kde.org>
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

import QtQuick 2.5
import QtQuick.Window 2.2
import org.kde.lottie 1.0

Rectangle {
    id: root
    color: "black"

    property int stage

    onStageChanged: {
        if (stage == 2) {
            introAnimation.playing = true;
        }
    }

    Item {
        id: content
        anchors.fill: parent
        TextMetrics {
            id: units
            text: "M"
            property int gridUnit: boundingRect.height
            property int largeSpacing: units.gridUnit
            property int smallSpacing: Math.max(2, gridUnit/4)
        }

        AnimatedImage {
            id: introAnimation
            anchors.fill: parent

            source: Qt.resolvedUrl("boot.gif")

            fillMode: Image.PreserveAspectFit
            visible: true
        }

        //LottieAnimation {
        //    id: introAnimation
        //    anchors.centerIn: parent
        //    width: Math.min(parent.width, parent.height)
        //    height: width

        //    source: Qt.resolvedUrl("thinking.json")

        //    loops: Animation.Infinite
        //    fillMode: Image.PreserveAspectFit
        //    visible: true
        //    running: true
        //}
    }
}
