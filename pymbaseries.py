#!/usr/bin/env python3
"""
    Acquire NFRAMES images every DELTASEC seconds.
    Save them to OUTPUTFOLDER.
"""
import argparse
import os
import threading
import time
import warnings

import datetime as dt
import numpy as np
import pymba
from scipy import misc, optimize

PARSER = argparse.ArgumentParser( \
        description='Acquire a series of frames from an Allied Vision GigE camera.')
PARSER.add_argument('--nframes', '-n', metavar='num', type=int, nargs=1, required=True,
                    help='number of frames to collect (>=1)')
PARSER.add_argument('--dt', '-t', metavar='time', type=float, nargs=1, required=True,
                    help='time period between frames, '
                    'in case of exponential periods it\'s the first period')
PARSER.add_argument('--exptmax', '-e', metavar='time', type=float, nargs=1,
                    help='if set, will use exponentially increasing periods between shots, '
                    'dt_0 = dt (argument), dt_{n+1} = \\tau dt_n, where \\tau > 1, '
                    'up to total time exptmax since the first shot')
PARSER.add_argument('--output', '-o', metavar='path', type=str, nargs=1, required=True,
                    help='output folder')
PARSER.add_argument('--format', '-f', metavar='format', type=str, nargs=1, default=['png'],
                    help='output format')
PARSER.add_argument('--nohc', '-c', action='store_true', help='don\'t generate hi-contrast images')
PARSER.add_argument('--onlyhc', '-l', action='store_true', help='generate only hi-contrast images')
ARGS = PARSER.parse_args()

NFRAMES = ARGS.nframes[0]
DELTASEC = ARGS.dt[0]
OUTPUTFOLDER = ARGS.output[0]
HICONTRASTFOLDER = OUTPUTFOLDER + "/hicontrast"
if not ARGS.nohc:
    if not os.path.exists(HICONTRASTFOLDER):
        os.makedirs(HICONTRASTFOLDER)
else:
    if not os.path.exists(OUTPUTFOLDER):
        os.makedirs(OUTPUTFOLDER)

def saveimages(imgdata, opath=None, hcpath=None):
    """ Save a raw and an enchanted image, to be called in a separate thread """
    if opath is not None:
        misc.imsave(opath, imgdata)
    if hcpath is not None:
        mindata, maxdata = imgdata.min(), imgdata.max()
        misc.imsave(hcpath, (imgdata-mindata)/(maxdata-mindata))
    print('{}: saved shot(s) ({} threads)'.format(dt.datetime.utcnow(), \
            threading.active_count()))

with pymba.Vimba() as vimba:
    SYSTEM = vimba.getSystem()

    if SYSTEM.GeVTLIsPresent:
        SYSTEM.runFeatureCommand("GeVDiscoveryAllOnce")
        time.sleep(0.2)
    CAMERAIDS = vimba.getCameraIds()
    assert len(CAMERAIDS) > 0, "No cameras found!"
    CAMERA0 = vimba.getCamera(CAMERAIDS[0])
    CAMERA0.openCamera()
    CAMERA0.AcquisitionMode = 'SingleFrame'

    if ARGS.exptmax is None:
        TIMEDELTA = dt.timedelta(seconds=DELTASEC)
        ACQUISITIONTIMES = [dt.datetime.utcnow()+j*TIMEDELTA for j in range(NFRAMES)]
    else:
        BASE = 2 # semi-arbitrary, influences the algorithm's effective range
        TAUMAX = ARGS.exptmax[0] / DELTASEC
        FUNC = lambda x: BASE**(x*(NFRAMES-1)) - 1 - TAUMAX*(BASE**x - 1)

        XX = np.logspace(-8, 2, 100)
        I0 = None
        with warnings.catch_warnings():
            # Overflow is expected here
            warnings.simplefilter("ignore")
            YY = FUNC(XX)
            for i, v in enumerate(YY[:-1]*YY[1:]):
                if v < 0:
                    I0 = i
                    break
        A, B = XX[I0], XX[I0+1]

        TAU = BASE**optimize.brentq(FUNC, A, B)
        TIMEDELTALIST = [dt.timedelta(seconds=0)] \
                + [dt.timedelta(seconds=DELTASEC*TAU**i) for i in range(NFRAMES-1)]
        ACQUISITIONTIMES = dt.datetime.utcnow() + np.cumsum(TIMEDELTALIST)

    for i, t in enumerate(ACQUISITIONTIMES):
        frame0 = CAMERA0.getFrame()
        frame0.announceFrame()

        CAMERA0.startCapture()
        frame0.queueFrameCapture()
        CAMERA0.runFeatureCommand('AcquisitionStart')
        CAMERA0.runFeatureCommand('AcquisitionStop')
        frame0.waitFrameCapture()
        TIMESTAMP = dt.datetime.utcnow()

        imgData = np.ndarray(buffer=frame0.getBufferByteData(),
                             dtype=np.uint8,
                             shape=(frame0.height, frame0.width))

        outputpath, hicontrastpath = None, None
        if not ARGS.onlyhc:
            outputpath = '{}/{}.{}'.format(OUTPUTFOLDER, TIMESTAMP, ARGS.format[0])
        if not ARGS.nohc:
            hicontrastpath = '{}/{}.{}'.format(HICONTRASTFOLDER, TIMESTAMP, ARGS.format[0])
        threading.Thread(target=saveimages, args=[np.array(imgData), \
                   outputpath, hicontrastpath]).start()

        if i+1 < NFRAMES:
            naptime = (ACQUISITIONTIMES[i+1] - dt.datetime.utcnow()).total_seconds()
            #print(naptime)
            if naptime > 0:
                time.sleep(naptime)

        CAMERA0.endCapture()
        CAMERA0.revokeAllFrames()
