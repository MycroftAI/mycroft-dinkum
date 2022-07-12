/*
 * Copyright 2019 by Marco Martin <mart@kde.org>
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


class Mark2SystemAccess : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool networkConfigurationVisible MEMBER m_networkConfigurationVisible NOTIFY networkConfigurationVisibleChanged)
    Q_PROPERTY(qreal fakeBrightness MEMBER m_fakeBrightness NOTIFY fakeBrightnessChanged)

public:
    Mark2SystemAccess(QObject *parent=0);
    ~Mark2SystemAccess();

    static Mark2SystemAccess *instance();

public Q_SLOTS:
    void executeCommand(const QString &command);

    void requestShutdown();
    void requestReboot();

Q_SIGNALS:
    void networkConfigurationVisibleChanged();
    void fakeBrightnessChanged();

private:
    bool m_networkConfigurationVisible = false;
    qreal m_fakeBrightness = 0.0;
};

