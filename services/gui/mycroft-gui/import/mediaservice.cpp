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

#include "mediaservice.h"
#include <QAudioProbe>
#include <QMediaObject>
#include <QMediaPlayer>
#include <QAudioDecoder>
#include <QAudioDeviceInfo>
#include <QAudioInput>
#include <QAudioRecorder>

MediaService::MediaService(QObject *parent)
    : QObject(parent),
      m_controller(MycroftController::instance()),
      mVideoSurface(nullptr)
{
    if (m_controller->status() == MycroftController::Open){
        connect(m_controller, &MycroftController::intentRecevied, this,
                &MediaService::onMainSocketIntentReceived);
    }

    calculator = new FFTCalc(this);
    m_player = new QMediaPlayer;
    connect(calculator, &FFTCalc::calculatedSpectrum, this, [this](QVector<double> spectrum) {
        int size = 20;
        m_spectrum.resize(size);
        int j = 0;
        for (int i = 0; i < spectrum.size(); i += spectrum.size()/(size - 1)) {
            m_spectrum[j] = spectrum[i];
            ++j;
        }
        emit spectrumChanged();
    });

    connect(m_player, &QMediaPlayer::mediaStatusChanged, this, &MediaService::onMediaStatusChanged);
    setupProbeSource();
}

void MediaService::setupProbeSource()
{
    QAudioProbe *probe = new QAudioProbe;
    probe->setSource(m_player);
    connect(probe, SIGNAL(audioBufferProbed(QAudioBuffer)), this, SLOT(processBuffer(QAudioBuffer)));
    return;
}

QAbstractVideoSurface *MediaService::videoSurface() const
{
    return mVideoSurface;
}

void MediaService::setVidSurface(QAbstractVideoSurface *videoSurface)
{
    if(videoSurface != mVideoSurface)
    {
        mVideoSurface = videoSurface;
        m_player->setVideoOutput(mVideoSurface);

        emit signalVideoSurfaceChanged();
    }
}

void MediaService::processBuffer(QAudioBuffer buffer)
{
    qreal peakValue;
    int duration;

    if(buffer.frameCount() < 512)
        return;

    levelLeft = levelRight = 0;

    if(buffer.format().channelCount() != 2)
        return;

    sample.resize(buffer.frameCount());
    if(buffer.format().sampleType() == QAudioFormat::SignedInt){
        QAudioBuffer::S16S *data = buffer.data<QAudioBuffer::S16S>();
        if (buffer.format().sampleSize() == 32)
            peakValue=INT_MAX;
        else if (buffer.format().sampleSize() == 16)
            peakValue=SHRT_MAX;
        else
            peakValue=CHAR_MAX;

        for(int i=0; i<buffer.frameCount(); i++){
            sample[i] = data[i].left/peakValue;
            levelLeft+= abs(data[i].left)/peakValue;
            levelRight+= abs(data[i].right)/peakValue;
        }
    }

    else if(buffer.format().sampleType() == QAudioFormat::UnSignedInt){
        QAudioBuffer::S16U *data = buffer.data<QAudioBuffer::S16U>();
        if (buffer.format().sampleSize() == 32)
            peakValue=UINT_MAX;
        else if (buffer.format().sampleSize() == 16)
            peakValue=USHRT_MAX;
        else
            peakValue=UCHAR_MAX;
        for(int i=0; i<buffer.frameCount(); i++){
            sample[i] = data[i].left/peakValue;
            levelLeft+= abs(data[i].left)/peakValue;
            levelRight+= abs(data[i].right)/peakValue;
        }
    }

    else if(buffer.format().sampleType() == QAudioFormat::Float){
        QAudioBuffer::S32F *data = buffer.data<QAudioBuffer::S32F>();
        peakValue = 1.00003;
        for(int i=0; i<buffer.frameCount(); i++){
            sample[i] = data[i].left/peakValue;
            if(sample[i] != sample[i]){
                sample[i] = 0;
            }
            else{
                levelLeft+= abs(data[i].left)/peakValue;
                levelRight+= abs(data[i].right)/peakValue;
            }
        }
    }
    duration = buffer.format().durationForBytes(buffer.frameCount())/1000;
    calculator->calc(sample, duration);
    emit levels(levelLeft/buffer.frameCount(), levelRight/buffer.frameCount());
}

void MediaService::playURL(const QString &filename)
{
    m_player->setMedia(QUrl(filename));
    m_player->play();
    setPlaybackState(QMediaPlayer::PlayingState);
    connect(m_player, &QMediaPlayer::durationChanged, this, [&](qint64 dur) {
        emit durationChanged(dur);
    });
    connect(m_player, &QMediaPlayer::positionChanged, this, [&](qint64 pos) {
        emit positionChanged(pos);
    });
}

void MediaService::playerStop()
{
    m_player->stop();
    setPlaybackState(QMediaPlayer::StoppedState);
}

void MediaService::playerPause()
{
    m_player->pause();
    setPlaybackState(QMediaPlayer::PausedState);
}

void MediaService::playerContinue()
{
    m_player->play();
    setPlaybackState(QMediaPlayer::PlayingState);
}

void MediaService::playerRestart()
{
    m_player->stop();
    playURL(m_track);
}

void MediaService::playerNext()
{
    m_controller->sendRequest(QStringLiteral("gui.player.media.service.get.next"), m_emptyData);
}

void MediaService::playerPrevious()
{
    m_controller->sendRequest(QStringLiteral("gui.player.media.service.get.previous"), m_emptyData);
}

void MediaService::playerRepeat()
{
    m_controller->sendRequest(QStringLiteral("gui.player.media.service.get.repeat"), m_emptyData);
}

void MediaService::playerShuffle()
{
    m_controller->sendRequest(QStringLiteral("gui.player.media.service.get.shuffle"), m_emptyData);
}

QMediaPlayer::State MediaService::getPlaybackState()
{
    return m_playerState;
}

void MediaService::setPlaybackState(QMediaPlayer::State playbackState)
{
    m_playerState = playbackState;
    emit playbackStateChanged(playbackState);

    m_playerStateSync.clear();
    m_playerStateSync.insert(QStringLiteral("state"), playbackState);
    m_controller->sendRequest(QStringLiteral("gui.player.media.service.sync.status"), m_playerStateSync);
}

void MediaService::playerSeek(qint64 seekvalue)
{
    m_player->setPosition(seekvalue);
}

QString MediaService::getTrack()
{
    return m_track;
}

QVariantMap MediaService::getPlayerMeta()
{
    return m_metadataList;
}

QVariantMap MediaService::getCPSMeta()
{
    QVariantMap cpsMap;

    if(!m_artist.isEmpty()){
        cpsMap.insert(QStringLiteral("artist"), m_artist);
    };
    if(!m_title.isEmpty()){
        cpsMap.insert(QStringLiteral("title"), m_title);
    };
    if(!m_album.isEmpty()){
        cpsMap.insert(QStringLiteral("album"), m_album);
    };
    if(!m_thumbnail.isEmpty()){
        cpsMap.insert(QStringLiteral("thumbnail"), m_thumbnail);
    };
    return cpsMap;
}

bool MediaService::getRepeat()
{
    return m_repeat;
}

QMediaPlayer::State MediaService::playbackState() const
{
    return m_player->state();
}

void MediaService::onMediaStatusChanged(QMediaPlayer::MediaStatus status)
{
    emit mediaStatusChanged(status);

    m_currentMediaStatus.clear();
    m_currentMediaStatus.insert(QStringLiteral("status"), status);
    m_controller->sendRequest(QStringLiteral("gui.player.media.service.current.media.status"), m_currentMediaStatus);

    if (status == QMediaPlayer::LoadedMedia || status == QMediaPlayer::BufferedMedia)
    {
        QStringList metadataAvailableList = m_player->availableMetaData();
        int availableListSize = metadataAvailableList.size();
        QString availableMetaKey;
        QVariant availableMetaVal;

        m_metadataList.clear();
        for (int idx = 0; idx < availableListSize; idx++)
        {
            availableMetaKey = metadataAvailableList.at(idx);
            availableMetaVal = m_player->metaData(availableMetaKey);
            m_metadataList.insert(availableMetaKey, availableMetaVal);

            if(availableMetaKey == QStringLiteral("Title")){
                m_title = m_player->metaData(availableMetaKey).toString();
            }
            if(availableMetaKey == QStringLiteral("Artist")){
                m_artist = m_player->metaData(availableMetaKey).toString();
            }
        }

        emit metaUpdated();
        m_controller->sendRequest(QStringLiteral("gui.player.media.service.get.meta"), m_metadataList);
    }
}

void MediaService::onMainSocketIntentReceived(const QString &type, const QVariantMap &data)
{

    if(type == QStringLiteral("gui.player.media.service.play")) {
        m_track = data[QStringLiteral("track")].toString();
        m_repeat = data[QStringLiteral("repeat")].toBool();

        emit playRequested();
    }

    if(type == QStringLiteral("gui.player.media.service.pause")) {
        playerPause();
        emit pauseRequested();
    }

    if(type == QStringLiteral("gui.player.media.service.stop")) {
        playerStop();
        emit stopRequested();
    }

    if(type == QStringLiteral("gui.player.media.service.resume")) {
        playerContinue();
        emit resumeRequested();
    }

    if(type == QStringLiteral("gui.player.media.service.set.meta")) {
        QString metaVal;

        if(data.contains(QStringLiteral("artist"))){
            metaVal = data[QStringLiteral("artist")].toString();
            if(!metaVal.isEmpty()){
                m_artist = metaVal;
            }
        }

        if(data.contains(QStringLiteral("album"))){
            metaVal = data[QStringLiteral("album")].toString();
            if(!metaVal.isEmpty()){
                m_album = metaVal;
            }
        }

        if(data.contains(QStringLiteral("title"))){
            metaVal = data[QStringLiteral("title")].toString();
            if(!metaVal.isEmpty()){
                m_title = metaVal;
            }
        }

        if(data.contains(QStringLiteral("track"))){
            metaVal = data[QStringLiteral("track")].toString();
            if(!metaVal.isEmpty()){
                m_title = metaVal;
            }
        }

        if(data.contains(QStringLiteral("image"))){
            metaVal = data[QStringLiteral("image")].toString();
            if(!metaVal.isEmpty()){
                m_thumbnail = metaVal;
            }
        }

        emit metaReceived();
    }
}
