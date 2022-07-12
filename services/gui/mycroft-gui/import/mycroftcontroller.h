/*
 * Copyright 2018 by Marco Martin <mart@kde.org>
 * Copyright 2018 David Edmundson <davidedmundson@kde.org>
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

#pragma once

#include <QObject>
#include <QWebSocket>
#include <QPointer>
#include <QQuickItem>

#ifdef Q_OS_ANDROID
#include <QTextToSpeech>
#include <QQueue>
#endif

#include <QTimer>

class GlobalSettings;
class QQmlPropertyMap;
class ActiveSkillsModel;
class AbstractSkillView;

class MycroftController : public QObject
{
    Q_OBJECT
    Q_PROPERTY(Status status READ status NOTIFY socketStatusChanged)
    //FIXME: make those two enums?
    Q_PROPERTY(bool speaking READ isSpeaking NOTIFY isSpeakingChanged)
    Q_PROPERTY(bool listening READ isListening NOTIFY isListeningChanged)

    Q_PROPERTY(QString currentSkill READ currentSkill NOTIFY currentSkillChanged)
    Q_PROPERTY(QString currentIntent READ currentIntent NOTIFY currentIntentChanged)

    Q_PROPERTY(bool serverReady READ serverReady NOTIFY serverReadyChanged)

    Q_ENUMS(Status)
public:
    enum Status {
        Connecting,
        Open,
        Closing,
        Closed,
        Error
    };
    static MycroftController* instance();

    bool isSpeaking() const;
    bool isListening() const;
    bool serverReady() const;
    Status status() const;
    QString currentSkill() const;
    QString currentIntent() const;

    //Public API NOT to be used with QML
    void registerView(AbstractSkillView *view);

Q_SIGNALS:
    //socket stuff
    void socketStatusChanged();
    void closed();

    //mycroft
    void isSpeakingChanged();
    void isListeningChanged();
    void stopped();
    void notUnderstood();
    void currentSkillChanged();
    void currentIntentChanged();
    void serverReadyChanged();
    void speechRequestedChanged(bool expectingResponse);

    //signal with nearly all data
    //TODO: remove?
    void intentRecevied(const QString &type, const QVariantMap &data);

    //type utterances, type is the current skill
    //TODO: remove?
    void fallbackTextRecieved(const QString &skill, const QVariantMap &data);

    void utteranceManagedBySkill(const QString &skill);
    void skillTimeoutReceived(const QString &skillidleid);

public Q_SLOTS:
    void start();
    void disconnectSocket();
    void reconnect();
    void sendRequest(const QString &type, const QVariantMap &data, const QVariantMap &context = QVariantMap({}));
    void sendBinary(const QString &type, const QJsonObject &data, const QVariantMap &context = QVariantMap({}));
    void sendText(const QString &message);
    void startPTTClient();

private:
    explicit MycroftController(QObject *parent = nullptr);
    void onMainSocketMessageReceived(const QString &message);

    QWebSocket m_mainWebSocket;

    QTimer m_reconnectTimer;
    QTimer m_reannounceGuiTimer;

    GlobalSettings *m_appSettingObj;

    //TODO: remove
    QString m_currentSkill;
    QString m_currentIntent;

    QHash<QString, AbstractSkillView *> m_views;

    QHash<QString, QQmlPropertyMap*> m_skillData;

#ifdef Q_OS_ANDROID
    QTextToSpeech *m_speech;
    bool m_isExpectingSpeechResponse = false;
    QQueue<QString> ttsqueue;
#endif
    
    bool m_isSpeaking = false;
    bool m_isListening = false;
    bool m_mycroftLaunched = false;
    bool m_serverReady = false;
};

