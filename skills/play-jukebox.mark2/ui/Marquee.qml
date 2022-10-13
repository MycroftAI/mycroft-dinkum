// Copyright 2022, Mycroft AI Inc.
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
Implementaion of a text marquee.

The text passed to this delegate will scroll horizontally if the text is 
wider than the field it is contained within.  The text will be centered in the
field and not scroll if it fits inside the field.

The scrolling implementation puts copies of the text value side by side.  As one
scrolls of the screen to the left, the other scrolls onto the screen on the right.
Animation stops when the second text field reaches where the first text field started.
There is a pause of four seconds between animations.

This code is specific to the Mark II device.  It uses a grid of 16x16 pixel
squares for alignment of items.
*/
import QtQuick 2.4

Item {
    id: marqueeText
    property font font
    property color color
    property string text
    property bool scroll: timerTextMetrics.width > width

    clip: true

    // Provides width of text value to control whether or not scrolling is necessary
    TextMetrics {
        id: timerTextMetrics
        text: marqueeText.text
        font: marqueeText.font
    }

    // This is the first copy of the text value that shows up on the screen when
    // before animation begins.
    Item {
        id: timerTextOneItem
        height: parent.height - gridUnit
        width: parent.width
        Text {
            id: timerTextOne
            anchors.baseline: parent.bottom
            anchors.horizontalCenter: scroll ? undefined : parent.horizontalCenter
            color: marqueeText.color
            font: marqueeText.font
            maximumLineCount: 1;
            text: marqueeText.text
        }
    }

    // This is the second copy of the text value that scrolls into view as the first
    // text value scrolls out of view.  It is an empty string if there is no scrolling.
    Item {
        height: parent.height - gridUnit
        Text {
            id: timerTextTwo
            anchors.baseline: parent.bottom
            color: marqueeText.color
            font: marqueeText.font
            maximumLineCount: 1;
            text: scroll ? marqueeText.text : ""
            x: timerTextOne.contentWidth
        }
    }

    // Only animate if the text doesn't fit.  Pause for four seconds before starting 
    // the animation.  Then scroll both text values until the second reaches the same
    // position the first started in.
    SequentialAnimation {
        id: marqueeAnimator
        loops: Animation.Infinite
        running: scroll
        PauseAnimation {
            duration: 4000
        }
        ParallelAnimation {
            NumberAnimation {
                id: timerTextOneAnimation
                target: timerTextOne
                property: "x"
                from: 0
                to: -(timerTextOne.width + gridUnit * 6);
                duration: Math.round((timerTextOne.width + marqueeText.width) * 1000. / 128);
            }
            NumberAnimation {
                id: timerTextTwoAnimation
                target: timerTextTwo
                property: "x"
                from: timerTextOne.width + gridUnit * 6
                to: 0;
                duration: Math.round((timerTextOne.width + marqueeText.width) * 1000. / 128);

            }
        }
    }
}
