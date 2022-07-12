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

import QtQuick 2.4
import QtQuick.Controls 2.2
import QtQuick.Layouts 1.4
import org.kde.kirigami 2.4 as Kirigami
import QtGraphicalEffects 1.0
import Mycroft 1.0 as Mycroft

Mycroft.CardDelegate {
    id: root
    cardBackgroundOverlayColor: "black"

    // The Wolfram Alpha logo is positioned in the upper left corner of the card
    Image {
        id: wolframAlphaLogo
        anchors.top: parent.top
        anchors.topMargin: gridUnit
        anchors.left: parent.left
        anchors.leftMargin: gridUnit
        fillMode: Image.PreserveAspectFit
        height: gridUnit * 3
        source: "wolfy_mark.svg"
        width: gridUnit * 3
    }


    // Show the article's title in the center of the card or scroll it horzontally
    // if it is longer than the width of the card.
    Marquee {
        id: articleTitle
        anchors.top: parent.top
        anchors.left: wikiLogo.right
        anchors.leftMargin: gridUnit * 2
        color: "#FFFFFF"
        font.pixelSize: 47
        font.styleName: "Bold"
        height: gridUnit * 5
        text: sessionData.title
        width: gridUnit * 36
    }

    Img {
        width: parent.width
        height: parent.height - Mycroft.Units.gridUnit * 6
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        imgSrc: sessionData.imgLink
    }
}
