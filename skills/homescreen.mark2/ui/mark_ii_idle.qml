// Copyright 2021 Mycroft AI Inc.
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
Defines the idle screen for the Mark II.
*/
import QtQuick 2.12
import QtQuick.Controls 2.0
import QtGraphicalEffects 1.0
import Mycroft 1.0 as Mycroft

Mycroft.Delegate {
    id: homeScreenRoot
    leftPadding: 0
    rightPadding: 0
    bottomPadding: 0
    topPadding: 0
    property int gridUnit: Mycroft.Units.gridUnit

    Image {
        id: homeScreenWallpaper
        anchors.fill: parent
        source: Qt.resolvedUrl(sessionData.wallpaperPath)
    }

    Item {
        x: gridUnit * 2
        y: gridUnit * 2
        height: gridUnit * 26
        width: gridUnit * 46

        // Icon representing the current weather conditionsre, freshed every fifteen minutes.
        HomeScreenImage {
            id: homeScreenWeatherCondition
            anchors.left: parent.left
            anchors.leftMargin: gridUnit * 18
            anchors.top: parent.top
            heightUnits: 3
            imageSource: sessionData.homeScreenWeatherCondition
            width: gridUnit * 3
        }

        // The current temperature, refreshed every fifteen minutes.
        HomeScreenLabel {
            id: homeScreenTemperature
            anchors.top: parent.top
            anchors.left: homeScreenWeatherCondition.right
            anchors.leftMargin: gridUnit
            fontSize: 59
            fontStyle: "Regular"
            heightUnits: 3
            text: sessionData.homeScreenTemperature ? sessionData.homeScreenTemperature + "°" : ""
            width: gridUnit * 6
        }

        // Alarm icon that is displayed when there are future alarms set on the device.
        HomeScreenImage {
            id: homeScreenActiveAlarm
            anchors.right: parent.right
            anchors.top: parent.top
            heightUnits: 3
            imageSource: "icons/alarm.svg"
            visible: sessionData.showAlarmIcon
            width: gridUnit * 3
        }

        // The date and time of the most recent Mark II build
        HomeScreenLabel {
            id: homeScreenBuildDateTime
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.leftMargin: gridUnit
            fontSize: 22
            fontStyle: "Regular"
            heightUnits: 3
            text: sessionData.mycroftContainerBuildDate
            width: gridUnit * 10
        }

        // The date and time of the most recent skill update.  Only displayed for developers.
        HomeScreenLabel {
            id: homeScreenSkillDateTime
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.leftMargin: gridUnit * 30
            fontSize: 22
            fontStyle: "Regular"
            heightUnits: 3
            text: sessionData.skillDateTime ? "Skills: " + sessionData.skillDateTime : ""
            width: gridUnit * 10
        }

        // Current time of day
        HomeScreenLabel {
            id: homeScreenTime
            anchors.top: parent.top
            anchors.topMargin: gridUnit * 6
            fontSize: 200
            fontStyle: "Bold"
            heightUnits: 10
            text: sessionData.homeScreenTime.replace(":", "꞉")
            width: parent.width
        }

        // Current date
        HomeScreenLabel {
            id: homeScreenDate
            anchors.top: homeScreenTime.bottom
            anchors.topMargin: gridUnit * 3
            fontSize: 59
            fontStyle: "Regular"
            heightUnits: 3
            text: sessionData.homeScreenDate
            width: parent.width
        }


        Item {
            id: hardwareStatusIcons
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.leftMargin: gridUnit * 12
            anchors.horizontalCenter: parent.horizontalCenter
            height: gridUnit * 3
            width: gridUnit * 21

            // Muted microphone icon that is displayed when the microphone is off.
            HomeScreenImage {
                id: homeScreenMicMuted
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                heightUnits: 3
                imageSource: "icons/mic-mute.svg"
                visible: sessionData.isMuted
            }
        }

        // Mycroft Logo
        HomeScreenImage {
            id: homeScreenMycroftLogo
            anchors.bottom: parent.bottom
            anchors.right: parent.right
            heightUnits: 3
            imageSource: "icons/mycroft-logo.png"
            widthUnits: 3
        }
    }
}
