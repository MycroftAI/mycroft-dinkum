import QtQuick 2.12
import QtQuick.Controls 2.5
import QtQuick.Layouts 1.3
import Mycroft 1.0 as Mycroft
import org.kde.kirigami 2.11 as Kirigami
import QtGraphicalEffects 1.0

Mycroft.CardDelegate {
    id: root
    property bool alarmExpired: sessionData.alarmExpired
    property color alarmColor: alarmExpired ? "#FFFFFF" : "#22A7F0"
    cardBackgroundOverlayColor: "black"
    
    Rectangle {
        id: leftRect
        anchors.top: parent.top
        anchors.topMargin: Mycroft.Units.gridUnit - 2
        anchors.right: centerRect.left
        anchors.rightMargin: Math.round(-centerRect.width * 0.340)
        color: alarmColor
        radius: width
        width: parent.width / 6
        height: width
        layer.enabled: true
        layer.effect: OpacityMask {
            maskSource: centerRect
        }
    }

    Rectangle {
        id: rightRect
        anchors.top: parent.top
        anchors.topMargin: Mycroft.Units.gridUnit - 2
        anchors.left: centerRect.right
        anchors.leftMargin: Math.round(-centerRect.width * 0.340)
        color: alarmColor
        radius: width
        width: parent.width / 6
        height: width
        layer.enabled: true
        layer.effect: OpacityMask {
            maskSource: centerRect
        }
    }

    Rectangle {
        id: rightBottomRect
        anchors.top: centerRect.bottom
        anchors.topMargin: -centerRect.height * 0.30
        anchors.left: centerRect.right
        anchors.leftMargin: -centerRect.width * 0.20
        color: alarmColor
        radius: 30
        rotation: -48
        z: 2
        width: centerRect.width * 0.16
        height: centerRect.height * 0.28
    }

    Rectangle {
        id: leftBottomRect
        anchors.top: centerRect.bottom
        anchors.topMargin: -centerRect.height * 0.30
        anchors.right: centerRect.left
        anchors.rightMargin: -centerRect.width * 0.20
        color: alarmColor
        radius: 30
        rotation: 48
        z: 2
        width: centerRect.width * 0.16
        height: centerRect.height * 0.28
    }

    Rectangle {
        id: centerRect
        anchors.top: parent.top
        anchors.topMargin: Mycroft.Units.gridUnit + 5
        anchors.horizontalCenter: parent.horizontalCenter
        color: "black"
        radius: width
        width: Math.min(Math.round(parent.width / 2.480), 800)
        height: width

        Rectangle {
            id: centerRectInner
            anchors.centerIn: parent
            color: alarmColor
            radius: width
            width: Math.round(parent.width / 1.1180)
            height: width
            z: 5

            Item {
                anchors.fill: parent

                Label {
                    id: timeI
                    anchors.centerIn: parent
                    font.weight: Font.ExtraBold
                    font.pixelSize: timeI.text.length > 4 ? parent.width * 0.35 : parent.width * 0.40
                    color: sessionData.alarmExpired ? "black" : "white"
                    font.family: "Noto Sans Display"
                    font.styleName: "bold"
                    font.letterSpacing: 2
                    text: sessionData.alarmTime.split(" ")[0]
                    z: 100

                    SequentialAnimation on opacity {
                        id: expireAnimation
                        running: alarmExpired
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

                Label {
                    id: ampm
                    anchors.top: timeI.baseline
                    anchors.topMargin: 15
                    anchors.horizontalCenter: parent.horizontalCenter
                    font.weight: Font.Bold
                    font.family: "Noto Sans Display"
                    font.styleName: "bold"
                    font.pixelSize: parent.height * 0.175
                    font.letterSpacing: 2
                    color: sessionData.alarmExpired ? "black" : "white"
                    text: sessionData.alarmTime.split(" ")[1]
                    z: 100

                    SequentialAnimation on opacity {
                        id: expireAnimation2
                        running: alarmExpired
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
            }
        }
    }

    Rectangle {
        id: alarmLabelBox
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Mycroft.Units.gridUnit * 2 - 5
        width: centerRect.width
        color: "transparent"
        height: alarmLabel.contentHeight

        Label {
            id: alarmLabel
            color: "white"
            width: parent.width
            font.bold: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.weight: Font.Bold
            font.family: "Noto Sans Display"
            font.styleName: "SemiBold"
            font.pixelSize: parent.width * 0.12
            font.letterSpacing: 2
            text: sessionData.alarmName
        }
    }
}
