/*
 * Copyright 2018 by Marco Martin <mart@kde.org>
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

#include "mark2systemaccess.h"

#include <QDebug>
#include <QProcess>

#include <kworkspace5/kdisplaymanager.h>

Mark2SystemAccess::Mark2SystemAccess(QObject *parent)
    : QObject(parent)
{
}

Mark2SystemAccess::~Mark2SystemAccess()
{
}

Mark2SystemAccess *Mark2SystemAccess::instance()
{
    static Mark2SystemAccess* s_self = nullptr;
    if (!s_self) {
        s_self = new Mark2SystemAccess;
    }
    return s_self;
}

void Mark2SystemAccess::executeCommand(const QString &command)
{
    qWarning()<<"Executing"<<command;
    QProcess::startDetached(command);
}

void Mark2SystemAccess::requestShutdown()
{
    KWorkSpace::requestShutDown(KWorkSpace::ShutdownConfirmDefault, KWorkSpace::ShutdownTypeHalt);
}

void Mark2SystemAccess::requestReboot()
{
    KWorkSpace::requestShutDown(KWorkSpace::ShutdownConfirmDefault, KWorkSpace::ShutdownTypeReboot);
}

#include "mark2systemaccess.moc"
