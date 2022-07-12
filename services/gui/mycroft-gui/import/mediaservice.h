/*
 * Copyright 2021 by Aditya Mehra <aix.m@outlook.com>
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

#ifndef MEDIASERVICE_H
#define MEDIASERVICE_H

#include <QObject>
#include <QAudioProbe>
#include <QVector>
#include <QMediaPlayer>
#include <QAbstractVideoSurface>
#include <QJsonDocument>
#include "thirdparty/fftcalc.h"
#include "mycroftcontroller.h"

class MediaService : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QVector<double> spectrum READ spectrum NOTIFY spectrumChanged)
    Q_PROPERTY(QMediaPlayer::State playbackState READ playbackState NOTIFY playbackStateChanged)
    Q_PROPERTY(QAbstractVideoSurface* videoSurface READ videoSurface WRITE setVidSurface NOTIFY signalVideoSurfaceChanged)

public:
    explicit MediaService(QObject *parent = Q_NULLPTR);

    QMediaPlayer::State playerState() const {return m_playerState;}
    QVector<double> spectrum() const {return m_spectrum;}
    QAbstractVideoSurface *videoSurface() const;
    void setVidSurface(QAbstractVideoSurface *videoSurface);
    QMediaPlayer::State getPlaybackState();

public Q_SLOTS:
    void setupProbeSource();
    void processBuffer(QAudioBuffer buffer);
    void playURL(const QString &filename);
    void playerStop();
    void playerPause();
    void playerContinue();
    void playerRestart();
    void playerNext();
    void playerPrevious();
    void playerShuffle();
    void playerRepeat();
    void playerSeek(qint64 seekvalue);
    QMediaPlayer::State playbackState() const;
    void setPlaybackState(QMediaPlayer::State playbackState);
    QString getTrack();
    QVariantMap getPlayerMeta();
    QVariantMap getCPSMeta();
    bool getRepeat();

signals:
    void signalVideoSurfaceChanged();

Q_SIGNALS:
    void playbackStateChanged(QMediaPlayer::State pbstate);
    void mediaStatusChanged(QMediaPlayer::MediaStatus status);
    void durationChanged(qint64 dur);
    void positionChanged(qint64 pos);
    void playRequested();
    void pauseRequested();
    void stopRequested();
    void repeatRequested();
    void resumeRequested();
    void shuffleRequested();
    void metaReceived();
    void metaUpdated();

private:
    MycroftController *m_controller;
    QAbstractVideoSurface *mVideoSurface;
    void onMainSocketIntentReceived(const QString &type, const QVariantMap &data);
    void onMediaStatusChanged(QMediaPlayer::MediaStatus status);

    QVector<double> sample;
    QVector<double> m_spectrum;
    QMediaPlayer::State m_playerState;
    double levelLeft, levelRight;
    FFTCalc *calculator;
    QMediaPlayer *m_player;
    QString m_track;
    QString m_artist;
    QString m_album;
    QString m_title;
    QString m_thumbnail;
    bool m_repeat;
    QVariantMap m_emptyData;
    QVariantMap m_metadataList;
    QVariantMap m_playerStateSync;
    QVariantMap m_currentMediaStatus;

signals:
    int levels(double left, double right);
    void spectrumChanged();
};

#endif // MEDIASERVICE_H
