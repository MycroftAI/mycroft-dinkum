/*
 * Copyright 2018 by Marco Martin <mart@kde.org>
 * Copyright 2018 David Edmundson <davidedmundson@kde.org>
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

SliderBase {
    iconSource: "audio-volume-high"

    slider.from: PA.PulseAudio.MinimalVolume
    slider.to: PA.PulseAudio.MaximalVolume

    slider.value: paSinkModel.preferredSink ? paSinkModel.preferredSink.volume : PA.PulseAudio.MinimalVolume
    slider.onMoved: {
        paSinkModel.preferredSink.volume = slider.value
        feedbackTimer.running = true;
    }

    PA.SinkModel {
        id: paSinkModel
    }
    PA.VolumeFeedback {
        id: feedback
    }

    Timer {
        id: feedbackTimer
        interval: 250
        onTriggered: feedback.play(paSinkModel.preferredSink.index);
    }
}
