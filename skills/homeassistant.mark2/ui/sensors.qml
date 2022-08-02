import QtQuick 2.4
import QtQuick.Controls 2.2
import QtQuick.Layouts 1.4
import org.kde.kirigami 2.4 as Kirigami

import Mycroft 1.0 as Mycroft

Mycroft.CardDelegate {
    id: homeAssistantRoot
    skillBackgroundColorOverlay: "transparent"
    cardBackgroundOverlayColor: "transparent"
    skillBackgroundSource: Qt.resolvedUrl("wallpapers/home-assistant-default.png")

    property bool hasSensorDescription: sessionData.sensorDescription.length > 0 ? true : false

    contentItem: ColumnLayout {
        Label {
            id: sensorName
            Layout.fillWidth: true
            font.pixelSize: 25
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
            font.weight: Font.Bold
            text: sessionData.sensorName
        }

        Mycroft.AutoFitLabel {
            id: sensorValue
            Layout.fillWidth: true
            Layout.fillHeight: true
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
            font.weight: Font.Bold
            text: sessionData.sensorValue
        }

        Label {
            id: sensorDescription
            Layout.fillWidth: true
            font.pixelSize: 50
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
            visible: hasSensorDescription
            enabled: hasSensorDescription
            font.weight: Font.Bold
            text: sessionData.sensorDescription
        }
    }
}
