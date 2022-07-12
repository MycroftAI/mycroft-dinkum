/*
 * Copyright 2018 by Marco Martin <mart@kde.org>
 * Copyright 2018 David Edmundson <davidedmundson@kde.org>
 * Copyright 2018 Aditya Mehra <aix.m@outlook.com>
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 */

#include "mycroftplugin.h"

#include "mycroftcontroller.h"
#include "globalsettings.h"
#include "filereader.h"
#include "abstractdelegate.h"
#include "abstractskillview.h"
#include "activeskillsmodel.h"
#include "delegatesmodel.h"
#include "sessiondatamap.h"
#include "audiorec.h"
#include "mediaservice.h"

#include <QQmlEngine>
#include <QQmlContext>
#include <QQuickItem>

static QObject *fileReaderSingletonProvider(QQmlEngine *engine, QJSEngine *scriptEngine)
{
    Q_UNUSED(engine)
    Q_UNUSED(scriptEngine)

    return new FileReader;
}

static QObject *globalSettingsSingletonProvider(QQmlEngine *engine, QJSEngine *scriptEngine)
{
    Q_UNUSED(engine)
    Q_UNUSED(scriptEngine)

    return new GlobalSettings;
}

static QObject *mycroftControllerSingletonProvider(QQmlEngine *engine, QJSEngine *scriptEngine)
{
    Q_UNUSED(scriptEngine);

    //singleton managed internally, qml should never delete it
    engine->setObjectOwnership(MycroftController::instance(), QQmlEngine::CppOwnership);
    return MycroftController::instance();
}

static QObject *audioRecSingletonProvider(QQmlEngine *engine, QJSEngine *scriptEngine)
{
    Q_UNUSED(engine)
    Q_UNUSED(scriptEngine)

    return new AudioRec;
}

static QObject *mediaServiceSingletonProvider(QQmlEngine *engine, QJSEngine *scriptEngine)
{
    Q_UNUSED(engine)
    Q_UNUSED(scriptEngine)

    return new MediaService;
}

void MycroftPlugin::registerTypes(const char *uri)
{
    Q_ASSERT(QLatin1String(uri) == QLatin1String("Mycroft"));

    qmlRegisterSingletonType<MycroftController>(uri, 1, 0, "MycroftController", mycroftControllerSingletonProvider);
    qmlRegisterSingletonType<GlobalSettings>(uri, 1, 0, "GlobalSettings", globalSettingsSingletonProvider);
    qmlRegisterSingletonType<FileReader>(uri, 1, 0, "FileReader", fileReaderSingletonProvider);
    qmlRegisterSingletonType<AudioRec>(uri, 1, 0, "AudioRec", audioRecSingletonProvider);
    qmlRegisterSingletonType<MediaService>(uri, 1, 0, "MediaService", mediaServiceSingletonProvider);
    qmlRegisterSingletonType(QUrl(QStringLiteral("qrc:/qml/Units.qml")), uri, 1, 0, "Units");
    qmlRegisterSingletonType(QUrl(QStringLiteral("qrc:/qml/SoundEffects.qml")), uri, 1, 0, "SoundEffects");
    qmlRegisterType<AbstractSkillView>(uri, 1, 0, "AbstractSkillView");
    qmlRegisterType<AbstractDelegate>(uri, 1, 0, "AbstractDelegate");
    qmlRegisterType(QUrl(QStringLiteral("qrc:/qml/AudioPlayer.qml")), uri, 1, 0, "AudioPlayer");
    qmlRegisterType(QUrl(QStringLiteral("qrc:/qml/AutoFitLabel.qml")), uri, 1, 0, "AutoFitLabel");
    qmlRegisterType(QUrl(QStringLiteral("qrc:/qml/Delegate.qml")), uri, 1, 0, "Delegate");
    qmlRegisterType(QUrl(QStringLiteral("qrc:/qml/PaginatedText.qml")), uri, 1, 0, "PaginatedText");
    qmlRegisterType(QUrl(QStringLiteral("qrc:/qml/ProportionalDelegate.qml")), uri, 1, 0, "ProportionalDelegate");
    qmlRegisterType(QUrl(QStringLiteral("qrc:/qml/ScrollableDelegate.qml")), uri, 1, 0, "ScrollableDelegate");
    qmlRegisterType(QUrl(QStringLiteral("qrc:/qml/SkillView.qml")), uri, 1, 0, "SkillView");
    qmlRegisterType(QUrl(QStringLiteral("qrc:/qml/SlideShow.qml")), uri, 1, 0, "SlideShow");
    qmlRegisterType(QUrl(QStringLiteral("qrc:/qml/SlidingImage.qml")), uri, 1, 0, "SlidingImage");
    qmlRegisterType(QUrl(QStringLiteral("qrc:/qml/StatusIndicator.qml")), uri, 1, 0, "StatusIndicator");
    qmlRegisterType(QUrl(QStringLiteral("qrc:/qml/VideoPlayer.qml")), uri, 1, 0, "VideoPlayer");
    qmlRegisterType(QUrl(QStringLiteral("qrc:/qml/BoxLayout.qml")), uri, 1, 0, "BoxLayout");
    qmlRegisterType(QUrl(QStringLiteral("qrc:/qml/CardDelegate.qml")), uri, 1, 0, "CardDelegate");
    qmlRegisterType(QUrl(QStringLiteral("qrc:/qml/BusyIndicator.qml")), uri, 1, 0, "BusyIndicator");

    qmlRegisterUncreatableType<ActiveSkillsModel>(uri, 1, 0, "ActiveSkillsModel", QStringLiteral("You cannot instantiate items of type ActiveSkillsModel"));
    qmlRegisterUncreatableType<DelegatesModel>(uri, 1, 0, "DelegatesModel", QStringLiteral("You cannot instantiate items of type DelegatesModel"));
    qmlRegisterUncreatableType<SessionDataMap>(uri, 1, 0, "SessionDataMap", QStringLiteral("You cannot instantiate items of type SessionDataMap"));

    //use this only when all qml files are registered by the plugin
   // qmlProtectModule(uri, 1);
}

#include "moc_mycroftplugin.cpp"

