PROJECT(mycroft-gui-mark-2)

# Set minimum CMake version (required for CMake 3.0 or later)
cmake_minimum_required(VERSION 2.8.12)
 
set(QT_MIN_VERSION "5.11.0")
set(KF5_MIN_VERSION "5.50.0")
 
# Use Extra CMake Modules (ECM) for common functionality.
# See http://api.kde.org/ecm/manual/ecm.7.html
# and http://api.kde.org/ecm/manual/ecm-kde-modules.7.html
IF(POLICY CMP0063)
    CMAKE_POLICY(SET CMP0063 NEW)
ENDIF(POLICY CMP0063)

find_package(ECM 1.6.0 REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} ${ECM_MODULE_PATH} ${ECM_KDE_MODULE_DIR})

include(KDEInstallDirs)
set(CMAKE_AUTOMOC ON)


find_package(Qt5 ${QT_MIN_VERSION} CONFIG REQUIRED COMPONENTS
    Quick
    Core
    Qml
)

find_package(LibKWorkspace 5.14.90 CONFIG REQUIRED)

find_package(KF5 ${KF5_MIN_VERSION} REQUIRED COMPONENTS I18n Plasma Package)

add_definitions(-DQT_DISABLE_DEPRECATED_BEFORE=0)

#add_definitions(-Wno-deprecated)

add_definitions(-DQT_NO_URL_CAST_FROM_STRING -DQT_USE_QSTRINGBUILDER -DQT_NO_CAST_TO_ASCII -DQT_NO_CAST_FROM_ASCII)


install(FILES MycroftMark2.colors
        DESTINATION ${DATA_INSTALL_DIR}/color-schemes/)
plasma_install_package(lookandfeel org.mycroft.mark2 look-and-feel lookandfeel)
add_subdirectory(containments)
add_subdirectory(icons)


