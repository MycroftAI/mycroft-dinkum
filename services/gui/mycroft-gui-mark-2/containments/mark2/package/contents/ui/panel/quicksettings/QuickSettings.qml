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

import QtQuick 2.1
import QtQuick.Layouts 1.1
import QtQuick.Window 2.2
import QtQuick.Controls 2.2 as Controls
import org.kde.plasma.core 2.0 as PlasmaCore
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.kirigami 2.5 as Kirigami

GridLayout {
    id: root

    signal delegateClicked

    property bool horizontal: true
    columns: horizontal ? 2 : 1
    rowSpacing: Kirigami.Units.largeSpacing
    columnSpacing: Kirigami.Units.largeSpacing

    RowLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignTop
        spacing: Kirigami.Units.largeSpacing
        BrightnessSlider {
            Layout.fillWidth: true
            Layout.preferredHeight: root.horizontal ? Window.window.height - buttonsLayout.spacing*2 : implicitHeight
        }
        VolumeSlider {
            Layout.fillWidth: true
            Layout.preferredHeight: root.horizontal ? Window.window.height - buttonsLayout.spacing*2 : implicitHeight
        }
    }

    ColumnLayout {
        id: buttonsLayout
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignTop
        Layout.minimumWidth: 0
        spacing: Kirigami.Units.largeSpacing

        readonly property int minimumDelegateSize: Kirigami.Units.iconSizes.medium  + Kirigami.Units.smallSpacing * 2
        readonly property int maximumDelegateSize: Kirigami.Units.iconSizes.large  + Kirigami.Units.largeSpacing * 2

        readonly property int dynamicDelegateSize: (Window.window.height - spacing * (visibleChildren.length + 1)) / visibleChildren.length

        readonly property int delegateSize: Math.min(maximumDelegateSize, Math.max(minimumDelegateSize, dynamicDelegateSize))

        HomeDelegate {}
        WirelessDelegate {
	    enabled: false
	}
        Delegate {
            visible: plasmoid.configuration.showRotationButton
            iconSource: "image-rotate-symbolic"
            text: "Rotate"
            onClicked: {
                if (plasmoid.configuration.rotation === "CW") {
                    plasmoid.configuration.rotation = "NORMAL";
                } else if (plasmoid.configuration.rotation === "NORMAL") {
                    plasmoid.configuration.rotation = "CCW";
                } else if (plasmoid.configuration.rotation === "CCW") {
                    plasmoid.configuration.rotation = "UD";
                } else {
                    //if (plasmoid.configuration.rotation === "UD") {
                    plasmoid.configuration.rotation = "CW";
                }
                print(plasmoid.configuration.rotation)
            }
        }
        MuteDelegate {
            visible: plasmoid.configuration.showMuteButton
        }
        AdditionalSettingsDelegate {}
        RebootDelegate {}
        ShutdownDelegate {}
    }
}
