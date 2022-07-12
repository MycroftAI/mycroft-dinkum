/*
 * Copyright 2021 by Aditya Mehra <aix.m@outlook.com>
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

import QtQuick 2.9
import Mycroft 1.0 as Mycroft
import org.kde.plasma.private.volume 0.1 as PA

SliderControl {
    id: root
    iconSource: "audio-volume-high"
    visible: false
    property var refSlidingPanel

    slider.from: 0
    slider.to: 1
    slider.stepSize: 0.1

    onRefSlidingPanelChanged: {
        if(refSlidingPanel > 0.5) {
            visible = false
            feedbackTimer.stop()
        }
    }

    onChangeValueChanged: {
        Mycroft.MycroftController.sendRequest("mycroft.volume.set", {"percent": changeValue});
        feedbackAudioTimer.running = true;
        feedbackTimer.restart()
    }

    Connections {
        target: Mycroft.MycroftController

        onIntentRecevied:{
            if (type == "hardware.volume") {
                root.parent.color = Qt.rgba(0, 0, 0, 0.5)
                root.visible = true
                root.value = data.volume;
                feedbackTimer.restart()
            }
        }
    }

    Timer {
        id: feedbackTimer
        interval: 5000

        onTriggered: {
	    root.parent.color = Qt.rgba(0, 0, 0, 0)
            root.visible = false
        }
    }

    PA.SinkModel {
        id: paSinkModel
    }

    PA.VolumeFeedback {
        id: feedbackAudio
    }

    Timer {
        id: feedbackAudioTimer
        interval: 250
        onTriggered: feedbackAudio.play(paSinkModel.preferredSink.index);
    }
}
