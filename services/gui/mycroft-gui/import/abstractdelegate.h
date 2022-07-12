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

#pragma once

#include <QQuickItem>
#include <QQmlParserStatus>
#include <QQmlPropertyMap>
#include <QPointer>

#include "sessiondatamap.h"
#include "abstractskillview.h"

class MycroftController;

class DelegateLoader : public QObject {
    Q_OBJECT
public:
    DelegateLoader(AbstractSkillView *parent);
    ~DelegateLoader();

    void init(const QString skillId, const QUrl &url);
    AbstractDelegate *delegate();

    void setFocus(bool focus);

    QUrl translationsUrl() const;

Q_SIGNALS:
    void delegateCreated();

private:
    void createObject();

    QString m_skillId;
    QUrl m_delegateUrl;
    bool m_focus = false;
    QQmlComponent *m_component = nullptr;
    AbstractSkillView *m_view;
    QPointer <AbstractDelegate> m_delegate;
};

class AbstractDelegate: public QQuickItem
{
    Q_OBJECT
    Q_INTERFACES(QQmlParserStatus)

    /**
     * The skill data sent by the server.
     */
    Q_PROPERTY(SessionDataMap *sessionData READ sessionData CONSTANT)

    /**
     * When true the delegate will always take the full screen width. (default false)
     */
    Q_PROPERTY(bool fillWidth MEMBER m_fillWidth NOTIFY fillWidthChanged)

    /**
     * The idle time after Mycroft stopped talking  before the delegate wants to return to the resting face expressed in milliseconds.
     * The view may or may not follow this.
     * By default, it's 5 seconsa
     */
    Q_PROPERTY(int timeout MEMBER m_timeout NOTIFY timeoutChanged)

    /**
     * Source file for a skill-wide background (independent to the background item): it can be either an image or a QML file. 
     * The view may or may not decide to display it, if different delegates of the same skill have different skillBackgrounds, it will fade between them when the current delegate changes.
     * Both relative paths and remote urls are supported
     */
    Q_PROPERTY(QString skillBackgroundSource MEMBER m_backgroundSource NOTIFY skillBackgroundSourceChanged)

    /**
     * Color to be used as an overlay for the skill-wide background.
     * If you are using skillBackgroundSource as well, consider using a semi transparent color.
     * By default is completely transparent on this implementation and Delegate has a slightly translucent black or white depending on the color scheme
     */
    Q_PROPERTY(QColor skillBackgroundColorOverlay MEMBER m_skillBackgroundColorOverlay NOTIFY skillBackgroundColorOverlayChanged)

    Q_PROPERTY(QQuickItem *contentItem READ contentItem WRITE setContentItem NOTIFY contentItemChanged)
    Q_PROPERTY(bool contentItemAutoHeight MEMBER m_contentItemAutoHeight NOTIFY contentItemAutoHeightChanged)
    Q_PROPERTY(bool contentItemAutoWidth MEMBER m_contentItemAutoWidth NOTIFY contentItemAutoWidthChanged)
    Q_PROPERTY(QQuickItem *background READ background WRITE setBackground NOTIFY backgroundChanged)

    /**
     * Padding adds a space between each edge of the content item and the background item, effectively controlling the size of the content item.
     */
    Q_PROPERTY(int leftPadding READ leftPadding WRITE setLeftPadding NOTIFY leftPaddingChanged)
    Q_PROPERTY(int rightPadding READ rightPadding WRITE setRightPadding NOTIFY rightPaddingChanged)
    Q_PROPERTY(int topPadding READ topPadding WRITE setTopPadding NOTIFY topPaddingChanged)
    Q_PROPERTY(int bottomPadding READ bottomPadding WRITE setBottomPadding NOTIFY bottomPaddingChanged)

    /**
     * Inset adds a space between the delagate edges and the background, adding an extra empty padding around the delegate
     */
    Q_PROPERTY(int leftInset READ leftInset WRITE setLeftInset NOTIFY leftInsetChanged)
    Q_PROPERTY(int rightInset READ rightInset WRITE setRightInset NOTIFY rightInsetChanged)
    Q_PROPERTY(int topInset READ topInset WRITE setTopInset NOTIFY topInsetChanged)
    Q_PROPERTY(int bottomInset READ bottomInset WRITE setBottomInset NOTIFY bottomInsetChanged)

    /**
     * The size of the contents: the size of this item minux the padding
     */
    Q_PROPERTY(int contentWidth READ contentWidth NOTIFY contentWidthChanged)
    Q_PROPERTY(int contentHeight READ contentHeight NOTIFY contentHeightChanged)

    Q_PROPERTY(QQmlListProperty<QObject> contentData READ contentData FINAL)
   // Q_CLASSINFO("DeferredPropertyNames", "background,contentItem")
    Q_CLASSINFO("DefaultProperty", "contentData")

public:
    AbstractDelegate(QQuickItem *parent = nullptr);
    ~AbstractDelegate();

    QQmlListProperty<QObject> contentData();

/*
 * QML properties setters and getters
 */
    QQuickItem *contentItem() const;
    void setContentItem(QQuickItem *item);

    QQuickItem *background() const;
    void setBackground(QQuickItem *item);

    /**
     * The only way the skill UI has to access the data sent by the server
     */
    SessionDataMap *sessionData() const;

    // Setters and getters for the padding
    int leftPadding() const;
    void setLeftPadding(int padding);

    int topPadding() const;
    void setTopPadding(int padding);

    int rightPadding() const;
    void setRightPadding(int padding);

    int bottomPadding() const;
    void setBottomPadding(int padding);

    // Setters and getters for the inset
    int leftInset() const;
    void setLeftInset(int inset);

    int topInset() const;
    void setTopInset(int inset);

    int rightInset() const;
    void setRightInset(int inset);

    int bottomInset() const;
    void setBottomInset(int inset);

    int contentWidth() const;
    int contentHeight() const;

/*
 * @internal All the following API is meant to be used only by AbstractSkillView during initialization, *NOT* QML from where is not accessible at all.
 */

    /**
     * The sessiondata is writable only by AbstractskillView internally, not from QML
     */
    void setSessionData(SessionDataMap *data);

    void setSkillView(AbstractSkillView *view);
    AbstractSkillView *skillView() const;

    /**
     * @internal Url of the qml file that generated this instance
     */
    void setQmlUrl(const QUrl &url);
    QUrl qmlUrl() const;

    /**
     * @internal skill id this delegate belongs to
     */
    void setSkillId(const QString &skillId);

public Q_SLOTS:
    /**
     * Trigger an event either for this skill or a system one
     * Is not possible to trigger events belonging to different skills
     */
    void triggerGuiEvent(const QString &eventName, const QVariantMap &parameters);
    QString skillId() const;

protected:
    void geometryChanged(const QRectF &newGeometry, const QRectF &oldGeometry) override;
    protected:
    //void classBegin() override;
    void componentComplete() override;
    bool childMouseEventFilter(QQuickItem *item, QEvent *event) override;
    void mousePressEvent(QMouseEvent *event) override;
    void keyReleaseEvent(QKeyEvent *event) override;
    void focusInEvent(QFocusEvent *event) override;

Q_SIGNALS:
    /**
     * Emitted when the server triggered an event.
     * It is guaranteed the event will be either a system event or an event belonging to our skill, but never to another skill.
     * The Skill writer can access this by implementing the following code on the root element of the delegate:
     * @code
     *  onGuiEvent: {
     *      switch (eventName) {
     *      case "myevent1":
     *       ....
     *      }
     *  }
     * @endcode
     * @param eventName the unique name for the event
     * @param data the data for this event in JSon form
     */
    void guiEvent(const QString &eventName, const QVariantMap &data);

    //QML property notifiers
    void skillBackgroundSourceChanged();
    void skillBackgroundColorOverlayChanged();
    void backgroundChanged();
    void contentItemChanged();
    void contentItemAutoWidthChanged();
    void contentItemAutoHeightChanged();
    void timeoutChanged();
    void fillWidthChanged();
    void leftPaddingChanged();
    void rightPaddingChanged();
    void topPaddingChanged();
    void bottomPaddingChanged();
    void leftInsetChanged();
    void rightInsetChanged();
    void topInsetChanged();
    void bottomInsetChanged();
    void contentWidthChanged();
    void contentHeightChanged();

private:
    void syncChildItemsGeometry(const QSizeF &size);
    //internal accessorts for the contentData QProperty
    static void contentData_append(QQmlListProperty<QObject> *prop, QObject *object);
    static int contentData_count(QQmlListProperty<QObject> *prop);
    static QObject *contentData_at(QQmlListProperty<QObject> *prop, int index);
    static void contentData_clear(QQmlListProperty<QObject> *prop);

    QPointer<QQuickItem> m_contentItem;
    QPointer<QQuickItem> m_backgroundItem;

    //Internal implementation detail: this is used to reparent all items to contentItem
    QList<QObject *> m_contentData;


    //The main data from the Mycroft server
    QPointer<SessionDataMap> m_data;
    QPointer<AbstractSkillView> m_skillView;

    QUrl m_qmlUrl;
    QString m_skillId;

    QString m_backgroundSource;
    QColor m_skillBackgroundColorOverlay = Qt::transparent;
    int m_timeout = 5000; //Completely arbitrary 5 seconds of timeout
    bool m_fillWidth = false;

    /**
     * Padding adds a space between each edge of the content item and the background item, effectively controlling the size of the content item.
     */
    int m_leftPadding = 0;
    int m_rightPadding = 0;
    int m_topPadding = 0;
    int m_bottomPadding = 0;

    int m_leftInset = 0;
    int m_rightInset = 0;
    int m_topInset = 0;
    int m_bottomInset = 0;

    bool m_contentItemAutoWidth = true;
    bool m_contentItemAutoHeight = true;
    friend class ServerTest;
};

