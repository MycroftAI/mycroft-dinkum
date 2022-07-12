/*
 * Copyright (c) 2016 Daniel Holanda Noronha. All rights reserved.
 *
 * This work is licensed under the terms of the MIT license.
 * For a copy, see <https://opensource.org/licenses/MIT>.
 *
 */

#include "fftcalc.h"

#undef CLAMP
#define CLAMP(a,min,max) ((a) < (min) ? (min) : (a) > (max) ? (max) : (a))

FFTCalc::FFTCalc(QObject *parent)
    :QObject(parent){

    processor.moveToThread(&processorThread);

    qRegisterMetaType< QVector<double> >("QVector<double>");
    connect(&processor, SIGNAL(calculatedSpectrum(QVector<double>)), SLOT(setSpectrum(QVector<double>)));
    connect(&processor, SIGNAL(allDone()),SLOT(freeCalc()));
    processorThread.start(QThread::LowestPriority);
    isBusy = false;
}

FFTCalc::~FFTCalc(){
    processorThread.quit();
    processorThread.wait(10000);
}

void FFTCalc::calc(QVector<double> &_array, int duration){
    QMetaObject::invokeMethod(&processor, "processBuffer",
                              Qt::QueuedConnection, Q_ARG(QVector<double>, _array), Q_ARG(int, duration));
}

void FFTCalc::setSpectrum(QVector<double> spectrum){
    emit calculatedSpectrum(spectrum);
}

void FFTCalc::freeCalc()
{
    isBusy = false;
}

BufferProcessor::BufferProcessor(QObject *parent){
    Q_UNUSED(parent);
    timer = new QTimer(this);
    connect(timer,SIGNAL(timeout()),this,SLOT(run()));
    window.resize(SPECSIZE);
    complexFrame.resize(SPECSIZE);
    spectrum.resize(SPECSIZE/2);
    logscale.resize(SPECSIZE/2+1);
    compressed = true;
    for(int i=0; i<SPECSIZE;i++){
        window[i] = 0.5 * (1 - cos((2*PI*i)/(SPECSIZE)));
    }
    for(int i=0; i<=SPECSIZE/2; i++){
        logscale[i] = powf (SPECSIZE/2, (float) 2*i / SPECSIZE) - 0.5f;
    }
    running = false;
    timer->start(100);
}

BufferProcessor::~BufferProcessor(){
    timer->stop();

}

void BufferProcessor::processBuffer(QVector<double> _array, int duration){
    if(array.size() != _array.size()){
        numberOfChunks = _array.size()/SPECSIZE;
        array.resize(_array.size());
    }
    interval = duration/numberOfChunks;
    if(interval < 1)
        interval = 1;
    array = _array;
    pass = 0;
    timer->start(interval);
}

void BufferProcessor::run(){
    unsigned long bufferSize;
    qreal amplitude;
    if(pass == numberOfChunks){
        emit allDone();
        return;
    }
    bufferSize = array.size();
    if(bufferSize < SPECSIZE){
        return;
    }
    for(uint i=0; i<SPECSIZE; i++){
        complexFrame[i] = Complex(window[i]*array[i+pass*SPECSIZE],0);
    }
    fft(complexFrame);
    for(uint i=0; i<SPECSIZE/2;i++){
        qreal SpectrumAnalyserMultiplier = 1e-2;
        amplitude = SpectrumAnalyserMultiplier*std::abs(complexFrame[i]);
        amplitude = qMax(qreal(0.0), amplitude);
        amplitude = qMin(qreal(1.0), amplitude);
        complexFrame[i] = amplitude;
    }

    if(compressed){
        for (int i = 0; i <SPECSIZE/2; i ++){
            int a = ceilf (logscale[i]);
            int b = floorf (logscale[i+1]);
            float sum = 0;

            if (b < a)
                sum += complexFrame[b].real()*(logscale[i+1]-logscale[i]);
            else{
                if (a > 0)
                    sum += complexFrame[a-1].real()*(a-logscale[i]);
                for (; a < b; a++)
                    sum += complexFrame[a].real();
                if (b < SPECSIZE/2)
                    sum += complexFrame[b].real()*(logscale[i+1] - b);
            }

            sum *= (float) SPECSIZE/24;
            float val = 20*log10f (sum);
            val = 1 + val / 40;
            spectrum[i] = CLAMP (val, 0, 1);
        }
    }
    else{
        for(int i=0; i<SPECSIZE/2; i++){
            spectrum[i] = CLAMP(complexFrame[i].real()*100,0,1);
        }
    }
    emit calculatedSpectrum(spectrum);
    pass++;
}
