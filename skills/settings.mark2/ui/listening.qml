import QtQuick.Layouts 1.4
import QtQuick 2.4
import QtQuick.Controls 2.0
import org.kde.kirigami 2.4 as Kirigami

import Mycroft 1.0 as Mycroft

Item {
    id: root

    property var volume: sessionData.volume

    function getOpacity(volume) {
        if (volume < 2)
            return 0.7;
        else if (volume < 5)
            return 0.8;
        else if (volume < 8)
            return 0.9;
        else
            return 1.0;
    }

    function getLength(volume, pos) {
        var val = (volume * 2) * pos;
        if (val < 0)
            val = 0;
        else if (val > 15)
            val = 15;
        return 36 + 36 * val;
    }


    RowLayout {
        id: frame1
        anchors.centerIn: parent
        //Spacing is faked by items black space
        spacing: 0
        // Dynamic sizing of 4/6 of the screen size
        width: Math.min(root.width, root.height)/6 * 4
        height: width
        visible: true

        VolumeBar {
            strength: 0.5
        }
        VolumeBar {
            strength: 0.75
        }
        VolumeBar {
            strength: 1
        }
        VolumeBar {
            strength: 0.75
        }
        VolumeBar {
            strength: 0.5
        }
    }
}
