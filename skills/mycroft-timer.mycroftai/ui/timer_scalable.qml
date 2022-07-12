import QtQuick.Layouts 1.4
import QtQuick 2.4
import QtQuick.Controls 2.0
import QtGraphicalEffects 1.0
import QtQml.Models 2.12
import org.kde.kirigami 2.9 as Kirigami
import Mycroft 1.0 as Mycroft

Mycroft.CardDelegate {
    id: timerFrame
    leftPadding: 0
    rightPadding: 0
    topPadding: 0
    bottomPadding: 0

    property bool horizontalMode: timerFrame.width > timerFrame.height ? 1 : 0

    Component {
        id: timerDelegate
        Item {
            width: view.cellWidth
            height: view.cellHeight

            Rectangle {
                id: timerBackground
                width: view.cellWidth - Kirigami.Units.gridUnit
                height: view.cellHeight - Kirigami.Units.gridUnit
                anchors.centerIn: parent
                color: modelData.backgroundColor
                radius: 20

                /* Name of the timer */
                Label {
                    id: timerName
                    anchors.horizontalCenter: timerBackground.horizontalCenter
                    anchors.top: timerBackground.top
                    anchors.topMargin: Kirigami.Units.largeSpacing
                    color: "#2C3E50"
                    horizontalAlignment: Text.AlignHCenter
                    width: timerBackground.width - (Kirigami.Units.largeSpacing + Kirigami.Units.smallSpacing)
                    height: parent.height * 0.35
                    font.pixelSize: parent.width * 0.15
                    font.weight: Font.Bold
                    maximumLineCount: 2
                    wrapMode: Text.WrapAnywhere
                    elide: Text.ElideRight
                    text: modelData.timerName
                }

                /* Time remaining on the timer */
                Label {
                    id: timeRemaining
                    anchors.horizontalCenter: timerBackground.horizontalCenter
                    anchors.top: timerName.bottom
                    horizontalAlignment: Text.AlignHCenter
                    width: timerBackground.width - Kirigami.Units.largeSpacing
                    font.pixelSize: parent.width * 0.20
                    font.weight: Font.Bold
                    text: modelData.timeDelta

                    /* Flash the time delta when the timer expires for a visual cue */
                    SequentialAnimation on opacity {
                        id: expireAnimation
                        running: modelData.expired
                        loops: Animation.Infinite
                        PropertyAnimation {
                            from: 1;
                            to: 0;
                            duration: 500
                        }
                        PropertyAnimation {
                            from: 0;
                            to: 1;
                            duration: 500
                        }
                    }
                }

                Rectangle {
                    id: progressBar
                    height: gridUnit * 2
                    radius: timerBackground.radius
                    anchors.bottom: parent.bottom
                    color: "#FD9E66"
                    width: parent.width * modelData.percentRemaining
                }
            }
        }
    }

    GridView {
        id: view
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width - Kirigami.Units.gridUnit * 2
        height: parent.height
        model: sessionData.activeTimers.timers
        delegate: timerDelegate
        cellWidth: horizontalMode && count > 1 ? width / 2 : width
        cellHeight: {
            if (horizontalMode && count >= 3) {
                return view.height / 2
            } else if (horizontalMode && count <= 2) {
                return view.height
            } else if (!horizontalMode && count > 1) {
                if (count > 4) {
                    return view.height / 4
                } else {
                    return view.height / count
                }
            } else if (!horizontalMode && count == 1) {
                return view.height
            }
        }
    }
}
