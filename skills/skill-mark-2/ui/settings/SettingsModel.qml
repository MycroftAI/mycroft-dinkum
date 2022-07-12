import QtQuick.Layouts 1.4
import QtQuick 2.4
import QtQuick.Controls 2.0
import org.kde.kirigami 2.5 as Kirigami
import Mycroft 1.0 as Mycroft

ListModel {
    id: settingsListModel
    
    ListElement {
        settingIcon: "go-home"
        settingName: "Homescreen"
        settingEvent: "mycroft.device.settings.homescreen"
        settingCall: "show homescreen settings"
    }
    // ListElement {
    //     settingIcon: "circular-arrow-shape"
    //     settingName: "Factory Reset"
    //     settingEvent: "mycroft.device.settings.reset"
    //     settingCall: ""
    // }
    // ListElement {
    //     settingIcon: "download"
    //     settingName: "Update Device"
    //     settingEvent: "mycroft.device.settings.update"
    //     settingCall: ""
    // }
    ListElement {
        settingIcon: "question"
        settingName: "About"
        settingEvent: "mycroft.device.settings.about"
        settingCall: "show about page"
    }
}
