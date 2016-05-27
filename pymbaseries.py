#!/usr/bin/env python3
"""
    Acquire NFRAMES images every TIMEDELTAS seconds.
    Save them to OUTPUTFOLDER.
"""
import os
import sys
import time
import threading

import datetime as dt
import numpy as np
import pymba
from scipy import misc

NFRAMES = int(sys.argv[1])
TIMEDELTAS = float(sys.argv[2])
OUTPUTFOLDER = sys.argv[3]
HICONTRASTFOLDER = OUTPUTFOLDER + "/hicontrast"
if not os.path.exists(HICONTRASTFOLDER):
    os.makedirs(HICONTRASTFOLDER)

def saveimages(imgdata, outputpath, hicontrastpath):
    """ Save a raw and an enchanted image, to be called in a separate thread """
    misc.imsave(outputpath, imgdata)
    mindata, maxdata = imgdata.min(), imgdata.max()
    misc.imsave(hicontrastpath, (imgdata-mindata)/(maxdata-mindata))
    print('{}: saved {} ({} threads)'.format(dt.datetime.utcnow(), outputpath, threading.active_count()))

with pymba.Vimba() as vimba:
    SYSTEM = vimba.getSystem()

    if SYSTEM.GeVTLIsPresent:
        SYSTEM.runFeatureCommand("GeVDiscoveryAllOnce")
        time.sleep(0.2)
    CAMERAIDS = vimba.getCameraIds()
    CAMERA0 = vimba.getCamera(CAMERAIDS[0])
    CAMERA0.openCamera()
    CAMERA0.AcquisitionMode = 'SingleFrame'

    UTCNOW = dt.datetime.utcnow()
    TIMEDELTA = dt.timedelta(seconds=TIMEDELTAS)
    ACQUISITIONTIMES = [UTCNOW+j*TIMEDELTA for j in range(NFRAMES)]

    for i, t in enumerate(ACQUISITIONTIMES):
        frame0 = CAMERA0.getFrame()
        frame0.announceFrame()

        CAMERA0.startCapture()
        frame0.queueFrameCapture()
        CAMERA0.runFeatureCommand('AcquisitionStart')
        CAMERA0.runFeatureCommand('AcquisitionStop')
        frame0.waitFrameCapture()

        imgData = np.ndarray(buffer=frame0.getBufferByteData(),
                             dtype=np.uint8,
                             shape=(frame0.height, frame0.width))

        threading.Thread(target=saveimages, args=[np.array(imgData), \
                   '{}/{}.png'.format(OUTPUTFOLDER, t), \
                   '{}/{}.png'.format(HICONTRASTFOLDER, t)]).start()

        if i+1 < NFRAMES:
            naptime = (ACQUISITIONTIMES[i+1] - dt.datetime.utcnow()).total_seconds()
            #print(naptime)
            if naptime > 0:
                time.sleep(naptime)

        CAMERA0.endCapture()
        CAMERA0.revokeAllFrames()
