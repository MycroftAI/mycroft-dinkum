/*
 * Copyright (c) 2016 Daniel Holanda Noronha. All rights reserved.
 *
 * This work is licensed under the terms of the MIT license.
 * For a copy, see <https://opensource.org/licenses/MIT>.
 *
 */

#ifndef FFTCALC_H
#define FFTCALC_H

#include <QThread>
#include <QWaitCondition>
#include <QMutex>
#include <QVector>
#include <QDebug>
#include <QTimer>
#include <QObject>
#include "fft.h"

#define SPECSIZE 512

class BufferProcessor: public QObject{
    Q_OBJECT
    QVector<double> array;
    QVector<double> window;
    QVector<double> spectrum;
    QVector<double> logscale;
    QTimer *timer;
    bool compressed;
    bool running;
    int numberOfChunks;
    int interval;
    int pass;
    CArray complexFrame;

public slots:
    void processBuffer(QVector<double> _array, int duration);
signals:
    void calculatedSpectrum(QVector<double> spectrum);
    void allDone(void);
protected slots:
    void run();
public:
    explicit BufferProcessor(QObject *parent=0);
    ~BufferProcessor();
    void calc(QVector<double> &_array, int duration);
};
class FFTCalc : public QObject{
    Q_OBJECT
private:
    bool isBusy;
    BufferProcessor processor;
    QThread processorThread;

public:
    explicit FFTCalc(QObject *parent = 0);
    ~FFTCalc();
    void calc(QVector<double> &_array, int duration);
public slots:
    void setSpectrum(QVector<double> spectrum);
    void freeCalc();
signals:
    void calculatedSpectrum(QVector<double> spectrum);
};

#endif // FFTCALC_H
