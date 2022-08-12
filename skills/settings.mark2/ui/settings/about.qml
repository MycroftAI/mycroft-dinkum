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
Display information about the current system including version of core.
*/

import QtQuick.Layouts 1.4
import QtQuick 2.4
import QtQuick.Controls 2.0
import org.kde.kirigami 2.5 as Kirigami
import org.kde.plasma.core 2.0 as PlasmaCore
import Mycroft 1.0 as Mycroft

Item {
    id: aboutSettingsView
    anchors.fill: parent

    Item {
        id: topArea
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: Kirigami.Units.gridUnit * 2

        Kirigami.Heading {
            id: aboutSettingPageTextHeading
            level: 1
            wrapMode: Text.WordWrap
            anchors.centerIn: parent
            font.bold: true
            text: "About"
            color: Kirigami.Theme.linkColor
        }
    }

    Flickable {
        anchors.top: topArea.bottom
        anchors.topMargin: Mycroft.Units.largeSpacing
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: areaSep.top
        anchors.bottomMargin: Mycroft.Units.largeSpacing
        clip: true
        contentHeight: contentColumnLayout.implicitHeight

        ColumnLayout {
            id: contentColumnLayout
            anchors.fill: parent
            anchors.leftMargin: Mycroft.Units.gridUnit * 10
            anchors.rightMargin: Mycroft.Units.gridUnit * 10
            spacing: Kirigami.Units.smallSpacing

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.largeSpacing
            }

            // Kirigami.Heading {
            //     id: versionsHeading
            //     level: 2
            //     Layout.alignment: Qt.AlignHCenter
            //     text: "Mycroft-core"
            // }

            // Item {
            //     Layout.fillWidth: true
            //     Layout.preferredHeight: Kirigami.Units.smallSpacing
            // }

            // Label {
            //     id: mycroftCoreVersionLabel
            //     Layout.alignment: Qt.AlignHCenter
            //     text: "Version: " + sessionData.mycroftCoreVersion
            // }

            // Label {
            //     id: mycroftCoreCommitLabel
            //     Layout.alignment: Qt.AlignHCenter
            //     text: "Commit: " + sessionData.mycroftCoreCommit
            // }

            // Item {
            //     Layout.fillWidth: true
            //     Layout.preferredHeight: Kirigami.Units.largeSpacing
            // }

            // Kirigami.Separator {
            //     Layout.fillWidth: true
            // }

            // Item {
            //     Layout.fillWidth: true
            //     Layout.preferredHeight: Kirigami.Units.largeSpacing
            // }

            // Kirigami.Heading {
            //     id: updateDateHeading
            //     level: 2
            //     Layout.alignment: Qt.AlignHCenter
            //     text: "Last updated"
            // }

            // Item {
            //     Layout.fillWidth: true
            //     Layout.preferredHeight: Kirigami.Units.smallSpacing
            // }

            // Label {
            //     id: mycroftContainerBuildDateLabel
            //     Layout.alignment: Qt.AlignHCenter
            //     text: "Mycroft Container: " + sessionData.mycroftContainerBuildDate
            // }

            // Label {
            //     id: mycroftSkillsUpdateDateLabel
            //     Layout.alignment: Qt.AlignHCenter
            //     text: "Mycroft Skills: " + sessionData.mycroftSkillsUpdateDate
            // }

            // Item {
            //     Layout.fillWidth: true
            //     Layout.preferredHeight: Kirigami.Units.largeSpacing
            // }

            // Kirigami.Separator {
            //     Layout.fillWidth: true
            // }

            // Item {
            //     Layout.fillWidth: true
            //     Layout.preferredHeight: Kirigami.Units.largeSpacing
            // }

            Kirigami.Heading {
                id: deviceIdHeading
                level: 2
                Layout.alignment: Qt.AlignHCenter
                text: "Device Identification"
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.smallSpacing
            }

            Label {
                id: deviceNameLabel
                Layout.alignment: Qt.AlignHCenter
                text: "Name: " + sessionData.deviceName
            }

            // Label {
            //     id: mycroftUUIDLabel
            //     Layout.alignment: Qt.AlignHCenter
            //     text: "UUID: " + sessionData.mycroftUUID
            // }

            Label {
                id: pantacorDeviceIdLabel
                Layout.alignment: Qt.AlignHCenter
                text: "Pantacor ID: " + sessionData.pantacorDeviceId
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.largeSpacing * 2
            }

            Kirigami.Heading {
                id: networkAddressesHeading
                level: 2
                Layout.alignment: Qt.AlignHCenter
                text: "Network Addresses"
            }

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.smallSpacing
            }

            Label {
                id: networkAddressesLabel
                Layout.alignment: Qt.AlignHCenter
                text: sessionData.networkAddresses
            }

        }
    }

    Kirigami.Separator {
        id: areaSep
        anchors.bottom: bottomArea.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 1
    }

    Item {
        id: bottomArea
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Kirigami.Units.largeSpacing * 1.15
        height: backIcon.implicitHeight + Kirigami.Units.largeSpacing * 1.15

        RowLayout {
            anchors.fill: parent
            
            Kirigami.Icon {
                id: backIcon
                isMask: true
                source: Qt.resolvedUrl("./go-previous.svg")
                Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                Layout.preferredWidth: Kirigami.Units.iconSizes.medium
            }
            
            Kirigami.Heading {
                level: 2
                wrapMode: Text.WordWrap
                font.bold: true
                text: "Back"
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 2
            }
        }
        
        MouseArea {
            anchors.fill: parent
            onClicked: {
                triggerGuiEvent("mycroft.device.settings.close", {})
            }
        }
    }
} 
 
