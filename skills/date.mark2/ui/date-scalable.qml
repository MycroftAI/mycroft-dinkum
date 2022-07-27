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

/*  Scalable date skill screen for the devices using the Mycroft GUI framework.

This screen defined in this file is for platforms with a screen, except for the Mark II.
It leverages some of the defined best practices for Mark II screen design but deviates
from it slightly in an attempt to make the screen look good on multiple screen sizes.
*/
import QtQuick.Layouts 1.4
import QtQuick 2.4
import QtQuick.Controls 2.0
import org.kde.kirigami 2.4 as Kirigami
import Mycroft 1.0 as Mycroft
import QtGraphicalEffects 1.0

Mycroft.CardDelegate {
    id: dateRoot
    topInset: Mycroft.Units.gridUnit / 2
    bottomInset: Mycroft.Units.gridUnit / 2

    ColumnLayout {
        id: grid
        anchors.fill: parent
        spacing: 0

        /* Put the day of the week at the top of the screen */
        Item { 
            Layout.alignment: Qt.AlignHCenter | Qt.AlignTop
            Layout.fillWidth: true
            Layout.preferredHeight: parent.height / 6
            
            Label {
                id: weekday
                anchors.centerIn: parent
                font.pixelSize: parent.height
                wrapMode: Text.WordWrap
                renderType: Text.NativeRendering
                font.family: "Noto Sans Display"
                font.styleName: "Black"
                font.capitalization: Font.AllUppercase
                text: sessionData.weekdayString
                color: "white"
            }
        }

        /* Add some spacing between the day of week and the calendar graphic */
        Item {
            Layout.preferredHeight: Mycroft.Units.gridUnit / 2
        }
        
        /* Calendar graphic */
        Item {
            Layout.alignment: Qt.AlignHCenter | Qt.AlignTop
            Layout.preferredWidth: Mycroft.Units.gridUnit * 25.5
            Layout.preferredHeight: Mycroft.Units.gridUnit * 19.25
            
            /* Use Rectangles Instead of Graphics For Proper Scaling of Graphics Items*/
            Rectangle {
                id: outterRectangle
                anchors.fill: parent
                radius: 30
                Item {
                    id: date
                    anchors.fill: parent
                    anchors.topMargin: Mycroft.Units.gridUnit * 5.5
                    
                    /* The day of the month goes in the calendar graphic under the month */
                    Label {
                        anchors.centerIn: parent
                        font.pixelSize: parent.height
                        wrapMode: Text.WordWrap
                        font.family: "Noto Sans Display"
                        font.styleName: "Bold"
                        text: sessionData.dayString
                        color: "#2C3E50"
                    }
                }
            }
            
            
            Item {
                anchors.fill: outterRectangle
                layer.enabled: true
                layer.effect: OpacityMask {
                    maskSource: outterRectangle
                }            
                Rectangle {
                    id: innerRectangle
                    width: Mycroft.Units.gridUnit * 25.5
                    height: Mycroft.Units.gridUnit * 5.5
                    clip: true
                    color: "#22A7F0"
                    
                    /*  The top part of the calendar graphic containing the month */
                    Label {
                        id: month
                        anchors.centerIn: parent
                        font.pixelSize: parent.height * 0.65
                        wrapMode: Text.WordWrap
                        font.family: "Noto Sans Display"
                        font.styleName: "Bold"
                        text: sessionData.monthString
                        color: "white"
                    }
                }
            }
        }
    }
}
