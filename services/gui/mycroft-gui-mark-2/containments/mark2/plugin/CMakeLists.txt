#include_directories("${CMAKE_CURRENT_BINARY_DIR}")

add_definitions(-DTRANSLATION_DOMAIN=\"mark2systemaccessplugin\")

set(mark2systemaccessplugin_SRCS
    mark2systemaccessplugin.cpp
    mark2systemaccess.cpp
)

add_library(mark2systemaccessplugin SHARED ${mark2systemaccessplugin_SRCS})

target_link_libraries(mark2systemaccessplugin
                      Qt5::Gui
                      Qt5::Qml
                      KF5::I18n
                      PW::KWorkspace)

install(TARGETS mark2systemaccessplugin DESTINATION ${QML_INSTALL_DIR}/Mycroft/Private/Mark2SystemAccess)

install(FILES qmldir DESTINATION ${QML_INSTALL_DIR}/Mycroft/Private/Mark2SystemAccess)

