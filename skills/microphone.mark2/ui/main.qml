import QtQuick.Layouts 1.4
import QtQuick 2.4
import QtQuick.Controls 2.0
import org.kde.kirigami 2.5 as Kirigami
import Mycroft 1.0 as Mycroft

Mycroft.Delegate {
    id: root
    property int gridUnit: Mycroft.Units.gridUnit
    property int barWidth: gridUnit * 5

    RowLayout {
        anchors.fill: parent
        anchors.topMargin: gridUnit
        anchors.leftMargin: gridUnit

        Item {
            id: vad
            width: barWidth
            height: width * 2

            Rectangle {
                id: vadRect
                color: sessionData.is_speech ? "blue" : "white"
                width: parent.width
                height: parent.height
            }

            Rectangle {
                width: parent.width
                height: (1.0 - sessionData.vad_probability) * parent.height
                color: "black"
            }

            Label {
                anchors.top: vadRect.bottom
                anchors.topMargin: gridUnit
                anchors.horizontalCenter: parent.horizontalCenter
                text: "VAD"
            }
        }

        Item {
            id: hotword
            // anchors.left: vad.right
            anchors.leftMargin: gridUnit * 2
            width: barWidth
            height: width * 2

            Rectangle {
                id: hotwordRect
                width: parent.width
                height: parent.height
                color: "green"
            }

            Rectangle {
                width: parent.width
                height: (1.0 - sessionData.hotword_probability) * parent.height
                color: "black"
            }

            Label {
                anchors.top: hotwordRect.bottom
                anchors.topMargin: gridUnit
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Hotword"
            }
        }

        Item {
            id: energy
            // anchors.left: hotword.right
            anchors.leftMargin: gridUnit * 2
            width: barWidth
            height: width * 2

            Rectangle {
                id: energyRect
                width: parent.width
                height: parent.height
                color: "red"
            }

            Rectangle {
                width: parent.width
                height: (1.0 - sessionData.energy_norm) * parent.height
                color: "black"
            }

            Label {
                anchors.top: energyRect.bottom
                anchors.topMargin: gridUnit
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Energy"
            }
        }
    }

    RowLayout {
        anchors.left: parent.left
        anchors.right: parent.right

        Label {
            text: "[" + sessionData.state + "]"
        }

        Label {
            text: sessionData.utterance
        }

        Label {
            text: "Gain: " + sessionData.gain
        }
    }

    Kirigami.Separator {
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
                triggerGuiEvent("mycroft.microphone.settings.close", {})
            }
        }
    }
}
