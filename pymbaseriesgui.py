#!/usr/bin/env python
"""
    A prototype GUI for the pymbaseries script.
"""
import argparse
import os
import sys
import threading
import time
import warnings
import datetime as dt
import numpy as np
import pymba
from scipy import misc, optimize
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog
from PyQt5.QtGui import QImage, QPixmap

# mainwindowui.py has to be generated from mainwindow.ui with pyuic5
QTCREATORUIFILE = 'mainwindow.ui'
PYQT5UIFILE = 'mainwindowui.py'
if os.stat(QTCREATORUIFILE).st_mtime > os.stat(PYQT5UIFILE).st_mtime:
    from PyQt5 import uic
    with open(QTCREATORUIFILE, 'r') as uifile, open(PYQT5UIFILE, 'w') as pyfile:
        uic.compileUi(uifile, pyfile)
        print("Updated the {} file.".format(PYQT5UIFILE))
from mainwindowui import Ui_MainWindow

PARSER = argparse.ArgumentParser( \
        description='Acquire a series of frames from an Allied Vision GigE camera.')
PARSER.add_argument('--nframes', '-n', metavar='num', type=int, nargs=1, default=[100],
                    help='number of frames to collect (>=1)')
PARSER.add_argument('--dt', '-t', metavar='time', type=float, nargs=1, default=[1.0],
                    help='time period between frames, '
                    'in case of exponential periods it\'s the first period')
PARSER.add_argument('--exptmax', '-e', metavar='time', type=float, nargs=1,
                    help='if set, will use exponentially increasing periods between shots, '
                    'dt_0 = dt (argument), dt_{n+1} = \\tau dt_n, where \\tau > 1, '
                    'up to total time exptmax since the first shot')
PARSER.add_argument('--output', '-o', metavar='path', type=str, nargs=1,
                    default=['~/OutputFolder/'], help='output folder')
PARSER.add_argument('--format', '-f', metavar='format', type=str, nargs=1, default=['png'],
                    help='output format')
PARSER.add_argument('--nohc', '-c', action='store_true', help='don\'t generate hi-contrast images')
PARSER.add_argument('--onlyhc', '-l', action='store_true', help='generate only hi-contrast images')
ARGS = PARSER.parse_args()

CAMERA0 = None
NFRAMES = ARGS.nframes[0]
DELTASEC = ARGS.dt[0]
if ARGS.exptmax is not None:
    EXPTMAX = ARGS.exptmax[0]
else:
    EXPTMAX = None
OUTPUTFOLDER = ARGS.output[0]
HICONTRASTFOLDER = OUTPUTFOLDER + "/hicontrast"

def drawimage(_=None, imbytes=None):
    """ A slot called when the label is resized. """
    if imbytes is None:
        if UI.checkBoxHCView.checkState():
            imgfloat = IMAGEBYTES.astype(np.double)
            immax = imgfloat.max()
            immin = imgfloat.min()
            imbytes = (255*(imgfloat-immin)/(immax-immin)).astype(np.uint8)
        else:
            imbytes = IMAGEBYTES
    image = QImage(imbytes.flatten(), imbytes.shape[1], imbytes.shape[0],
                   QImage.Format_Grayscale8)
    UI.label.setPixmap(QPixmap.fromImage(image.scaled(UI.label.size(), Qt.KeepAspectRatio)))

def outputdialog(_=None):
    """ Show a file dialog to choose the output folder. """
    global OUTPUTFOLDER, HICONTRASTFOLDER
    OUTPUTFOLDER = QFileDialog.getExistingDirectory()
    HICONTRASTFOLDER = OUTPUTFOLDER + "/hicontrast"
    UI.lineEditOutput.setText(OUTPUTFOLDER)

def spinboxchanged(_=None):
    """ If not using exp. delays update the total time spinbox. """
    global NFRAMES, DELTASEC, EXPTMAX
    NFRAMES = UI.spinBoxNFrames.value()
    DELTASEC = UI.doubleSpinBoxDT0.value()
    if UI.checkBoxExpT.checkState():
        EXPTMAX = UI.doubleSpinBoxTMax.value()
    else:
        EXPTMAX = None
        UI.doubleSpinBoxTMax.setValue(NFRAMES*DELTASEC)
    UI.labelExpTH.setText('That\'s {:.0f}h {:02.0f}m {:02.0f}s.'.format(
        EXPTMAX//3600, EXPTMAX%3600//60, EXPTMAX%60))

def saveimage(data, path):
    """ Save image to path """
    if not os.path.exists(path):
        os.makedirs(path)
    misc.imsave(path, data)

def saveimages(imgdata, opath=None, hcpath=None):
    """ Save a raw and an enchanted image, to be called in a separate thread """
    if opath is not None:
        saveimage(imgdata, opath)
    if hcpath is not None:
        mindata, maxdata = imgdata.min(), imgdata.max()
        saveimage((imgdata-mindata)/(maxdata-mindata), hcpath)
    print('{}: saved shot(s) ({} threads)'.format(dt.datetime.utcnow(), \
            threading.active_count()))

def acquirephoto(_=None):
    """ Save a series of photographs. """
    global IMAGEBYTES, CAMERA0
    with pymba.Vimba() as vimba:
        if CAMERA0 is None:
            system = vimba.getSystem()

            if system.GeVTLIsPresent:
                system.runFeatureCommand("GeVDiscoveryAllOnce")
                time.sleep(0.2)
            cameraids = vimba.getCameraIds()
            assert len(cameraids) > 0, "No cameras found!"
            CAMERA0 = vimba.getCamera(cameraids[0])
        CAMERA0.openCamera()
        CAMERA0.AcquisitionMode = 'SingleFrame'

        frame0 = CAMERA0.getFrame()
        frame0.announceFrame()
        CAMERA0.startCapture()
        frame0.queueFrameCapture()
        CAMERA0.runFeatureCommand('AcquisitionStart')
        CAMERA0.runFeatureCommand('AcquisitionStop')
        frame0.waitFrameCapture()

        IMAGEBYTES = np.ndarray(buffer=frame0.getBufferByteData(), \
                             dtype=np.uint8, \
                             shape=(frame0.height, frame0.width))
        drawimage(imbytes=IMAGEBYTES)
        UI.label.update()

        CAMERA0.endCapture()
        CAMERA0.revokeAllFrames()
        CAMERA0.closeCamera()

def saveimageseries(_=None):
    """ Save a series of photographs. """
    global IMAGEBYTES, CAMERA0
    with pymba.Vimba() as vimba:
        if CAMERA0 is None:
            system = vimba.getSystem()
            if system.GeVTLIsPresent:
                system.runFeatureCommand("GeVDiscoveryAllOnce")
                time.sleep(0.2)
            cameraids = vimba.getCameraIds()
            assert len(cameraids) > 0, "No cameras found!"
            CAMERA0 = vimba.getCamera(cameraids[0])
        CAMERA0.openCamera()
        CAMERA0.AcquisitionMode = 'SingleFrame'

        if EXPTMAX is False:
            timedelta = dt.timedelta(seconds=DELTASEC)
            acquisitiontimes = [dt.datetime.utcnow()+j*timedelta for j in range(NFRAMES)]
        else:
            base = 2 # semi-arbitrary, influences the algorithm's effective range
            taumax = EXPTMAX / DELTASEC
            func = lambda x: base**(x*(NFRAMES-1)) - 1 - taumax*(base**x - 1)

            testx = np.logspace(-8, 2, 100)
            testi = None
            with warnings.catch_warnings():
                # Overflow is expected here
                warnings.simplefilter("ignore")
                testy = func(testx)
                for i, product in enumerate(testy[:-1]*testy[1:]):
                    if product < 0:
                        testi = i
                        break
            taumin, taumax = testx[testi], testx[testi+1]

            tau = base**optimize.brentq(func, taumin, taumax)
            timedeltalist = [dt.timedelta(seconds=0)] \
                    + [dt.timedelta(seconds=DELTASEC*tau**i) for i in range(NFRAMES-1)]
            acquisitiontimes = dt.datetime.utcnow() + np.cumsum(timedeltalist)

        imageformat = UI.comboBoxFormat.currentText()
        outputfolder = UI.lineEditOutput.text()
        hicontrastfolder = outputfolder + "/hicontrast"
        if not UI.checkBoxUnaltered.checkState():
            outputfolder = None
        if not UI.checkBoxHCOut.checkState():
            hicontrastfolder = None

        for i in range(len(acquisitiontimes)):
            frame0 = CAMERA0.getFrame()
            frame0.announceFrame()

            CAMERA0.startCapture()
            frame0.queueFrameCapture()
            CAMERA0.runFeatureCommand('AcquisitionStart')
            CAMERA0.runFeatureCommand('AcquisitionStop')
            frame0.waitFrameCapture()
            timestamp = dt.datetime.utcnow()

            IMAGEBYTES = np.ndarray(buffer=frame0.getBufferByteData(), \
                                 dtype=np.uint8, \
                                 shape=(frame0.height, frame0.width))
            drawimage()
            UI.label.update()

            filename = '{}.{}'.format(timestamp, imageformat)
            threading.Thread(target=saveimages, args=[np.array(IMAGEBYTES), \
                       outputfolder, hicontrastfolder, filename]).start()

            if i+1 < NFRAMES:
                naptime = (acquisitiontimes[i+1] - dt.datetime.utcnow()).total_seconds()
                if naptime > 0:
                    time.sleep(naptime)

            CAMERA0.endCapture()
            CAMERA0.revokeAllFrames()

APP = QApplication(sys.argv)
WINDOW = QMainWindow()
UI = Ui_MainWindow()
UI.setupUi(WINDOW)

UI.label.resizeEvent = drawimage
UI.checkBoxExpT.stateChanged.connect(spinboxchanged)
UI.checkBoxHCView.stateChanged.connect(drawimage)
UI.doubleSpinBoxDT0.valueChanged.connect(spinboxchanged)
UI.doubleSpinBoxTMax.valueChanged.connect(spinboxchanged)
UI.pushButtonStart.clicked.connect(saveimageseries)
UI.spinBoxNFrames.valueChanged.connect(spinboxchanged)
UI.toolButtonChooseFolder.clicked.connect(outputdialog)

if NFRAMES is not None:
    UI.spinBoxNFrames.setValue(NFRAMES)
if DELTASEC is not None:
    UI.doubleSpinBoxDT0.setValue(DELTASEC)
if EXPTMAX is not None:
    UI.doubleSpinBoxTMax.setValue(EXPTMAX)

spinboxchanged()
acquirephoto()

# some fake 'photo' data to process
XX = np.arange(0, 300)
YY = np.arange(0, 200)
IMAGEDATA = np.array([[np.cos(x/25) + np.cos(y/25) for x in XX] for y in YY])
IMAGEBYTES = (100 + 32*(0.5+IMAGEDATA/4)).astype(np.uint8)

WINDOW.show()
sys.exit(APP.exec_())
