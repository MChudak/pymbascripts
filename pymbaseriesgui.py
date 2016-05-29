#!/usr/bin/env python
"""
    A prototype GUI for the pymbaseries script.
"""
import sys
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtGui import QImage, QPixmap
# mainwindowui.py has to be generated from mainwindow.ui with pyuic5
from mainwindowui import Ui_MainWindow

def onresize(_):
    """ A slot called when the label is resized. """
    if UI.checkBox.checkState():
        immax = IMAGEDATA.max()
        immin = IMAGEDATA.min()
        imbytes = (255*(IMAGEDATA-immin)/(immax-immin)).astype(np.uint8)
    else:
        imbytes = IMAGEBYTES
    image = QImage(imbytes.flatten(), IMAGEBYTES.shape[1], IMAGEBYTES.shape[0],
                   QImage.Format_Grayscale8)
    UI.label.setPixmap(QPixmap.fromImage(image.scaled(UI.label.size(), Qt.KeepAspectRatio)))

APP = QApplication(sys.argv)
WINDOW = QMainWindow()
UI = Ui_MainWindow()
UI.setupUi(WINDOW)

UI.label.resizeEvent = onresize
UI.checkBox.stateChanged.connect(onresize)

# some fake 'photo' data to process
XX = np.arange(0, 300)
YY = np.arange(0, 200)
IMAGEDATA = np.array([[np.cos(x/25) + np.cos(y/25) for x in XX] for y in YY])
IMAGEBYTES = (100 + 56*(0.5+IMAGEDATA/4)).astype(np.uint8)

WINDOW.show()
sys.exit(APP.exec_())
