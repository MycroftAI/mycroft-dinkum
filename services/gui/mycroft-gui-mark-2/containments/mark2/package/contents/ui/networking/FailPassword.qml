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
import org.kde.kirigami 2.5 as Kirigami
import org.kde.plasma.networkmanagement 0.2 as PlasmaNM
import org.kde.lottie 1.0
import Mycroft.Private.Mark2SystemAccess 1.0

Rectangle {
    id: incorrectView
    color: "black"
    
    Timer {
        id: failedPassTimer
        running: true
        interval: 3000
        onTriggered: {
            networkingLoader.clear()
            Mark2SystemAccess.networkConfigurationVisible = false;
            Mark2SystemAccess.networkConfigurationVisible = true;
        }
    }
    
    ColumnLayout {
        anchors.fill: parent
        
        Kirigami.Heading {
            text: qsTr("Incorrect Password")
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: Kirigami.Units.gridUnit * 2
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        
        LottieAnimation {
            id: failAnimation
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: Kirigami.Units.gridUnit * 2
            source: Qt.resolvedUrl("animations/security.json")
            loops: 0
            fillMode: Image.PreserveAspectFit
            running: true
        }
    }
}
 
