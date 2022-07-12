import QtQuick.Layouts 1.4
import QtQuick 2.4
import QtQuick.Controls 2.0
import org.kde.kirigami 2.4 as Kirigami

import Mycroft 1.0 as Mycroft

Item {
    id: root

    Mycroft.AutoFitLabel {
        font.weight: Font.Bold
        Layout.fillWidth: true
        Layout.preferredHeight: proportionalGridUnit * 40
        rightPadding: -font.pixelSize * 0.1
        font.family: "Noto Sans"
        font.pixelSize: 50
        color: "#22a7f0"
        text: "Loading..."
    }

    BusyIndicator {
        anchors.centerIn: parent
        width: root.contentWidth / 2
        height: root.contentWidth / 2
        running: true
    }
}
