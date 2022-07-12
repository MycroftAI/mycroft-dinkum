/*
 *   Copyright 2018 by Marco Martin <mart@kde.org>
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

#include "abstractdelegate.h"
#include "mycroftcontroller.h"

#include <QQmlEngine>
#include <QQmlContext>


DelegateLoader::DelegateLoader(AbstractSkillView *parent)
    : QObject(parent),
      m_view(parent)
{}

DelegateLoader::~DelegateLoader()
{
    if (m_delegate) {
        m_delegate->deleteLater();
    }
}

void DelegateLoader::init(const QString skillId, const QUrl &delegateUrl)
{
    if (!m_skillId.isEmpty()) {
        qWarning() << "Init already called";
    }

    m_skillId = skillId;
    m_delegateUrl = delegateUrl;
    QQmlEngine *engine = qmlEngine(m_view);
    //This class should be *ALWAYS* created from QML
    Q_ASSERT(engine);

    m_component = new QQmlComponent(engine, delegateUrl, m_view);

    switch(m_component->status()) {
    case QQmlComponent::Error:
        qWarning() << "ERROR Loading QML file" << delegateUrl;
        for (auto err : m_component->errors()) {
            qWarning() << err.toString();
        }
        break;
    case QQmlComponent::Ready:
        createObject();
        break;
    case QQmlComponent::Loading:
        connect(m_component, &QQmlComponent::statusChanged, this, &DelegateLoader::createObject);
        break;
    default:
        break;
    }
}

QUrl DelegateLoader::translationsUrl() const
{
    QUrl url(m_delegateUrl);
    url.setPath(m_delegateUrl.path().mid(0, m_delegateUrl.path().indexOf(QStringLiteral("/ui/")) + 4) + QStringLiteral("translations"));

    return url;
}

void DelegateLoader::createObject()
{
    QQmlContext *context = QQmlEngine::contextForObject(m_view);
    //This class should be *ALWAYS* created from QML
    Q_ASSERT(context);

    QObject *guiObject = m_component->beginCreate(context);
    m_delegate = qobject_cast<AbstractDelegate *>(guiObject);
    if (m_component->isError()) {
        qWarning() << "ERROR Loading QML file" << m_delegateUrl;
        for (auto err : m_component->errors()) {
            qWarning() << err.toString();
        }
        return;
    }

    if (!m_delegate) {
        qWarning()<<"ERROR: QML gui" << guiObject << "not a Mycroft.AbstractDelegate instance";
        guiObject->deleteLater();
        return;
    }

    connect(m_delegate, &QObject::destroyed, this, &QObject::deleteLater);

    m_delegate->setSkillId(m_skillId);
    m_delegate->setQmlUrl(m_delegateUrl);
    m_delegate->setSkillView(m_view);
    m_delegate->setSessionData(m_view->sessionDataForSkill(m_skillId));
    m_component->completeCreate();

    emit delegateCreated();

    if (m_focus) {
        m_delegate->forceActiveFocus((Qt::FocusReason)AbstractSkillView::ServerEventFocusReason);
    }
};

AbstractDelegate *DelegateLoader::delegate()
{
    return m_delegate;
}

void DelegateLoader::setFocus(bool focus)
{
    m_focus = focus;

    if (m_delegate && focus) {
        m_delegate->forceActiveFocus((Qt::FocusReason)AbstractSkillView::ServerEventFocusReason);
    } else if (m_delegate) {
        m_delegate->setFocus(false);
    }
}

//////////////////////////////////////////

AbstractDelegate::AbstractDelegate(QQuickItem *parent)
    : QQuickItem(parent)
{
    setFiltersChildMouseEvents(true);
    setFlags(QQuickItem::ItemIsFocusScope);
    setAcceptedMouseButtons(Qt::LeftButton);
}

AbstractDelegate::~AbstractDelegate()
{
}

void AbstractDelegate::triggerGuiEvent(const QString &eventName, const QVariantMap &parameters)
{
    if (!m_skillView) {
        qWarning() << "No SkillView, this should never happen: orphan delegate?";
        return;
    }

    if (eventName.startsWith(QStringLiteral("system."))) {
        m_skillView->triggerEvent(QStringLiteral("system"), eventName, parameters);
    } else {
        m_skillView->triggerEvent(m_skillId, eventName, parameters);
    }
}

void AbstractDelegate::syncChildItemsGeometry(const QSizeF &size)
{
    if (m_contentItem) {
        m_contentItem->setX(m_leftPadding + m_leftInset);
        m_contentItem->setY(m_topPadding + m_topInset);
        if (m_contentItemAutoWidth && m_contentItemAutoHeight) {
            m_contentItem->setSize(QSizeF(size.width() - m_leftPadding - m_rightPadding - m_leftInset - m_rightInset,
                size.height() - m_topPadding - m_bottomPadding - m_topInset - m_bottomInset));
        } else if (m_contentItemAutoWidth) {
            m_contentItem->setWidth(size.width() - m_leftPadding - m_rightPadding - m_leftInset - m_rightInset);
        } else if (m_contentItemAutoHeight) {
            m_contentItem->setHeight(size.height() - m_topPadding - m_bottomPadding - m_topInset - m_bottomInset);
        }
    }

    if (m_backgroundItem) {
        m_backgroundItem->setX(m_leftInset);
        m_backgroundItem->setY(m_topInset);
        m_backgroundItem->setSize(size - QSizeF(m_leftInset + m_rightInset, m_topInset + m_bottomInset));
    }

}

void AbstractDelegate::contentData_append(QQmlListProperty<QObject> *prop, QObject *object)
{
    AbstractDelegate *delegate = static_cast<AbstractDelegate *>(prop->object);
    if (!delegate) {
        return;
    }

//    QQuickItem *item = qobject_cast<QQuickItem *>(object);
    delegate->m_contentData.append(object);
}

int AbstractDelegate::contentData_count(QQmlListProperty<QObject> *prop)
{
    AbstractDelegate *delegate = static_cast<AbstractDelegate *>(prop->object);
    if (!delegate) {
        return 0;
    }

    return delegate->m_contentData.count();
}

QObject *AbstractDelegate::contentData_at(QQmlListProperty<QObject> *prop, int index)
{
    AbstractDelegate *delegate = static_cast<AbstractDelegate *>(prop->object);
    if (!delegate) {
        return nullptr;
    }

    if (index < 0 || index >= delegate->m_contentData.count()) {
        return nullptr;
    }
    return delegate->m_contentData.value(index);
}

void AbstractDelegate::contentData_clear(QQmlListProperty<QObject> *prop)
{
    AbstractDelegate *delegate = static_cast<AbstractDelegate *>(prop->object);
    if (!delegate) {
        return;
    }

    return delegate->m_contentData.clear();
}

QQmlListProperty<QObject> AbstractDelegate::contentData()
{
    return QQmlListProperty<QObject>(this, nullptr,
                                     contentData_append,
                                     contentData_count,
                                     contentData_at,
                                     contentData_clear);
}

void AbstractDelegate::geometryChanged(const QRectF &newGeometry, const QRectF &oldGeometry)
{
    syncChildItemsGeometry(newGeometry.size());
    QQuickItem::geometryChanged(newGeometry, oldGeometry);
    emit contentWidthChanged();
    emit contentHeightChanged();
}

void AbstractDelegate::componentComplete()
{
    if (!m_contentItem) {
        //qWarning()<<"Creting default contentItem";
        m_contentItem = new QQuickItem(this);
    }

    QQuickItem *item;
    for (auto *o : m_contentData) {
        item = qobject_cast<QQuickItem *>(o);
        if (item) {
            item->setParentItem(m_contentItem);
        } else {
            o->setParent(this);
        }
    }
    QQuickItem::componentComplete();
}

bool AbstractDelegate::childMouseEventFilter(QQuickItem *item, QEvent *event)
{
    if (event->type() == QEvent::MouseButtonPress) {
        forceActiveFocus(Qt::MouseFocusReason);
        triggerGuiEvent(QStringLiteral("system.gui.user.interaction"), QVariantMap({{QStringLiteral("skillId"), m_skillId}}));
    }
    return QQuickItem::childMouseEventFilter(item, event);
}

void AbstractDelegate::mousePressEvent(QMouseEvent *event)
{
    forceActiveFocus(Qt::MouseFocusReason);
    triggerGuiEvent(QStringLiteral("system.gui.user.interaction"), QVariantMap({{QStringLiteral("skillId"), m_skillId}}));
}

void AbstractDelegate::keyReleaseEvent(QKeyEvent *event)
{
    triggerGuiEvent(QStringLiteral("system.gui.user.interaction"), QVariantMap({{QStringLiteral("skillId"), m_skillId}}));
}

void AbstractDelegate::focusInEvent(QFocusEvent *event)
{
    //if the focus came from the server, don't ask the server again
    if (event->reason() == (Qt::FocusReason)AbstractSkillView::ServerEventFocusReason) {
        return;
    }

    if (!parentItem()) {
        return;
    }

    QQmlContext *context = QQmlEngine::contextForObject(parentItem());

    if (!context) {
        return;
    }

    int index = context->contextProperty(QStringLiteral("index")).toInt();
    if (index >= 0) {
        triggerGuiEvent(QStringLiteral("page_gained_focus"), QVariantMap({{QStringLiteral("number"), index}, {QStringLiteral("skillId"), m_skillId}}));
    }
}

QQuickItem *AbstractDelegate::contentItem() const
{
    return m_contentItem;
}

void AbstractDelegate::setContentItem(QQuickItem *item)
{
    if (m_contentItem == item) {
        return;
    }

    m_contentItem = item;
    item->setParentItem(this);
    m_contentItem->setX(m_leftPadding + m_leftInset);
    m_contentItem->setY(m_topPadding + m_topInset);

    if (m_contentItemAutoWidth && m_contentItemAutoHeight) {
        m_contentItem->setSize(QSizeF(width() - m_leftPadding - m_rightPadding - m_leftInset - m_rightInset,
            height() - m_topPadding - m_bottomPadding - m_topInset - m_bottomInset));
    } else if (m_contentItemAutoWidth) {
        m_contentItem->setWidth(width() - m_leftPadding - m_rightPadding - m_leftInset - m_rightInset);
    } else if (m_contentItemAutoHeight) {
        m_contentItem->setHeight(height() - m_topPadding - m_bottomPadding- m_topInset - m_bottomInset);
    }

    emit contentItemChanged();
}

QQuickItem *AbstractDelegate::background() const
{
    return m_backgroundItem;
}

void AbstractDelegate::setBackground(QQuickItem *item)
{
    if (m_backgroundItem == item) {
        return;
    }

    m_backgroundItem = item;
    m_backgroundItem->setParentItem(this);
    m_backgroundItem->setX(0);
    m_backgroundItem->setY(0);
    m_backgroundItem->setSize(size());

    emit backgroundChanged();
}

int AbstractDelegate::leftPadding() const
{
    return m_leftPadding;
}

void AbstractDelegate::setLeftPadding(int padding)
{
    if (m_leftPadding == padding) {
        return;
    }

    m_leftPadding = padding;
    syncChildItemsGeometry(size());
    emit leftPaddingChanged();
    emit contentWidthChanged();
}


int AbstractDelegate::topPadding() const
{
    return m_topPadding;
}

void AbstractDelegate::setTopPadding(int padding)
{
    if (m_topPadding == padding) {
        return;
    }

    m_topPadding = padding;
    syncChildItemsGeometry(size());
    emit topPaddingChanged();
    emit contentHeightChanged();
}


int AbstractDelegate::rightPadding() const
{
    return m_rightPadding;
}

void AbstractDelegate::setRightPadding(int padding)
{
    if (m_rightPadding == padding) {
        return;
    }

    m_rightPadding = padding;
    syncChildItemsGeometry(size());
    emit rightPaddingChanged();
    emit contentWidthChanged();
}


int AbstractDelegate::bottomPadding() const
{
    return m_bottomPadding;
}

void AbstractDelegate::setBottomPadding(int padding)
{
    if (m_bottomPadding == padding) {
        return;
    }

    m_bottomPadding = padding;
    syncChildItemsGeometry(size());
    emit bottomPaddingChanged();
    emit contentHeightChanged();
}


int AbstractDelegate::leftInset() const
{
    return m_leftInset;
}

void AbstractDelegate::setLeftInset(int inset)
{
    if (m_leftInset == inset) {
        return;
    }

    m_leftInset = inset;
    syncChildItemsGeometry(size());
    emit leftInsetChanged();
    emit contentWidthChanged();
}


int AbstractDelegate::topInset() const
{
    return m_topInset;
}

void AbstractDelegate::setTopInset(int inset)
{
    if (m_topInset == inset) {
        return;
    }

    m_topInset = inset;
    syncChildItemsGeometry(size());
    emit topInsetChanged();
    emit contentHeightChanged();
}


int AbstractDelegate::rightInset() const
{
    return m_rightInset;
}

void AbstractDelegate::setRightInset(int inset)
{
    if (m_rightInset == inset) {
        return;
    }

    m_rightInset = inset;
    syncChildItemsGeometry(size());
    emit rightInsetChanged();
    emit contentWidthChanged();
}


int AbstractDelegate::bottomInset() const
{
    return m_bottomInset;
}

void AbstractDelegate::setBottomInset(int inset)
{
    if (m_bottomInset == inset) {
        return;
    }

    m_bottomInset = inset;
    syncChildItemsGeometry(size());
    emit bottomInsetChanged();
    emit contentHeightChanged();
}


int AbstractDelegate::contentWidth() const
{
    return width() - m_leftPadding - m_rightPadding - m_leftInset - m_rightInset;
}

int AbstractDelegate::contentHeight() const
{
    return height() - m_topPadding - m_bottomPadding - m_topInset - m_bottomInset;
}



void AbstractDelegate::setSkillView(AbstractSkillView *view)
{
    //possible to call only once, by the skillview, setting itself upon instantiation
    Q_ASSERT(!m_skillView);
    m_skillView = view;
}

AbstractSkillView *AbstractDelegate::skillView() const
{
    return m_skillView;
}

void AbstractDelegate::setSessionData(SessionDataMap *data)
{
    //possible to call only once, by the skillview upon instantiation
    Q_ASSERT(!m_data);
    m_data = data;
}

SessionDataMap *AbstractDelegate::sessionData() const
{
    return m_data;
}

void AbstractDelegate::setQmlUrl(const QUrl &url)
{
    //possible to call only once, by the skillview upon instantiation
    Q_ASSERT(m_qmlUrl.isEmpty());
    m_qmlUrl = url;
}

QUrl AbstractDelegate::qmlUrl() const
{
    return m_qmlUrl;
}

void AbstractDelegate::setSkillId(const QString &skillId)
{
    //possible to call only once, by the skillview upon instantiation
    Q_ASSERT(m_skillId.isEmpty());
    m_skillId = skillId;
}

QString AbstractDelegate::skillId() const
{
    return m_skillId;
}

#include "moc_abstractdelegate.cpp"
