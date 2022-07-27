import QtQuick.Layouts 1.4
import QtQuick 2.4
import QtQuick.Controls 2.0
import org.kde.kirigami 2.4 as Kirigami
import org.kde.plasma.components 3.0 as PlasmaComponents3

import Mycroft 1.0 as Mycroft
import org.kde.lottie 1.0

Item {
    id: "thinking"

    LottieAnimation {
        id: thinkingAnimation
        anchors.centerIn: parent
        height: Math.min(parent.width, parent.height)
        source: Qt.resolvedUrl("thinking.json")
        loops: Animation.Infinite
        fillMode: Image.PreserveAspectFit
        running: true
    }
}
