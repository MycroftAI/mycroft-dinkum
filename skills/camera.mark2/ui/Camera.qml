import QtQuick 2.12
import QtQuick.Controls 2.12
import QtMultimedia 5.12
import org.kde.kirigami 2.11 as Kirigami
import Mycroft 1.0 as Mycroft
import "." as Local

Mycroft.Delegate {
    id: root
    property bool selfieMode: sessionData.singleshot_mode
    property var savePath: sessionData.save_path
    property int defaultSeconds: 5
    property int seconds: defaultSeconds
    property bool imageProcess: false
    leftPadding: 0
    rightPadding: 0
    topPadding: 0
    bottomPadding: 0
    
    onSavePathChanged: {
        console.log(savePath)
    }
    
    onSelfieModeChanged: {
        if(!selfieMode) {
            selfieTimer.stop()
            controlBarItem.opened = true
        } else {
            imageProcess = true
            seconds = defaultSeconds
            selfieTimer.running = true
            controlBarItem.opened = false
        }
    }
    
    controlBar: Local.ControlBar {
        id: cameraControls
        cameraControl: camera
        viewArea: viewOutputArea
        savePath: sessionData.save_path
        anchors.bottom: parent.bottom
    }

    Timer {
        id: selfieTimer
        interval: 1000
        repeat: true
        onTriggered: {
            root.seconds--
            if (root.seconds == 0) {
                running = false;
                imageProcess = false;
                root.seconds = root.defaultSeconds
                cameraShootSound.play()

                // Workaround Gstreamer & 4.19 kernel V4l2 module failing to capture image
                // Use After Fix: camera.imageCapture.captureToLocation(savePath);
                camera.imageCapture.capture() // Emit only for signal activation
                var filepath = savePath + "/image-" +  Qt.formatDateTime(new Date(), "hhmmss-ddMMyy") + ".png"
                viewOutputArea.grabToImage(function(result) {
                    result.saveToFile(filepath);
                });

                shootFeedback.start()
            }
        }
    }

    Timer {
        id: previewDisapperTimer
        interval: 5000
        onTriggered: {
            photoPreview.source = ""
        }
    }

    Item {
        anchors.fill: parent
        
        SoundEffect {
            id: cameraShootSound
            source: "sounds/clicking.wav"
        }

        Camera {
            id: camera

            imageProcessing.whiteBalanceMode: CameraImageProcessing.WhiteBalanceFlash
            captureMode: Camera.CaptureStillImage
            viewfinder.resolution: "1280x720"
            exposure {
                exposureCompensation: 1.0
                exposureMode: Camera.ExposurePortrait
            }
            digitalZoom: zoomSlider.value

            flash.mode: Camera.FlashRedEyeReduction

            imageCapture {
                id: capImage
                onImageCaptured: {
                    photoPreview.source = preview
                    photoPreviewPopUpViewer.source = preview
                    previewDisapperTimer.start()
                    triggerGuiEvent("CameraSkill.ViewPortStatus", {"status": "imagetaken"})
                }
            }

            onCameraStatusChanged: {
                if(Camera.ActiveStatus && selfieMode){
                    selfieTimer.running = true
                    imageProcess = true
                }
                if(selfieMode) {
                    triggerGuiEvent("CameraSkill.ViewPortStatus", {"status": "singleshot"})
                } else {
                    triggerGuiEvent("CameraSkill.ViewPortStatus", {"status": "generic"})
                }
            }
        }

        VideoOutput {
            id: viewOutputArea
            source: camera
            anchors.fill: parent
            focus : visible

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    if(selfieMode){
                        triggerGuiEvent("CameraSkill.ViewPortStatus", {"status": "generic"})
                    }
                    controlBarItem.opened = !controlBarItem.opened
                }
            }
        }

        Kirigami.Heading {
            text: seconds
            anchors.centerIn: parent
            color: "white"
            font.bold: true
            font.pixelSize: parent.height / 2
            visible: root.imageProcess && selfieMode ? 1 : 0
        }

        Rectangle {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.rightMargin: Kirigami.Units.largeSpacing * 2
            anchors.topMargin: Kirigami.Units.largeSpacing * 2
            width: parent.width * 0.15
            height: parent.width * 0.2
            color: "#000"
            border.width: Kirigami.Units.smallSpacing / 2
            border.color: Kirigami.Theme.linkColor
            visible: photoPreview.status == Image.Ready ? 1 : 0
            Image {
                anchors.fill: parent
                anchors.margins: Kirigami.Units.largeSpacing
                fillMode: Image.PreserveAspectFit
                id: photoPreview

                MouseArea{
                    anchors.fill: parent
                    onClicked: {
                        previewPopUp.open()
                    }
                }
            }
        }

        Slider {
            id: zoomSlider
            orientation: "Vertical"
            anchors.left: parent.left
            anchors.leftMargin: Kirigami.Units.largeSpacing * 2
            height: parent.height / 2
            anchors.verticalCenter: parent.verticalCenter
            from: 1
            to: camera.maximumDigitalZoom
            stepSize:camera.maximumDigitalZoom / 10
            value: 1
            visible: controlBarItem.opened
        }

        Rectangle {
            id: shootFeedback
            anchors.fill: parent
            color: "black"
            visible: opacity != 0.0
            opacity: 0.0

            function start() {
                shootFeedback.opacity = 1.0;
                shootFeedbackAnimation.restart();
            }

            OpacityAnimator {
                id: shootFeedbackAnimation
                target: shootFeedback
                from: 1.0
                to: 0.0
                duration: 500
            }
        }
    }

    Popup {
        id: previewPopUp
        width: parent.width / 2
        height:  parent.height / 2
        x: (parent.width - width) / 2
        y: (parent.height - height) / 2
        dim: true
        modal: true

        background: Rectangle {
            color: "#000"
        }

        contentItem: Image {
            id: photoPreviewPopUpViewer
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            fillMode: Image.PreserveAspectFit

            RoundButton {
                id: closeButtonPreview
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                width: Kirigami.Units.iconSizes.huge
                height: Kirigami.Units.iconSizes.huge
                
                background: Rectangle {
                    radius: 200
                    color: "#1a1a1a"
                    border.width: 1.25
                    border.color: "white"
                }
                
                contentItem: Item {
                    Image {
                        width: parent.width - Kirigami.Units.largeSpacing
                        height: width
                        anchors.centerIn: parent
                        source: "images/close.svg"
                    }
                }

                onClicked: {
                    previewPopUp.close()
                }
            }
        }
    }
}

