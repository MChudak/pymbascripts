#!/usr/bin/env python
import sys
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtGui import QImage, QPixmap
# mainwindowui.py has to be generated from mainwindow.ui with pyuic5
from mainwindowui import Ui_MainWindow

def onResize(event):
    if ui.checkBox.checkState():
        immax = imagedata.max()
        immin = imagedata.min()
        imbytes = (255*(imagedata-immin)/(immax-immin)).astype(np.uint8)
    else:
        imbytes = imagebytes
    image = QImage(imbytes.flatten(), imagebytes.shape[1], imagebytes.shape[0], QImage.Format_Grayscale8)    
    ui.label.setPixmap(QPixmap.fromImage(image.scaled(ui.label.size(), Qt.KeepAspectRatio)))

app = QApplication(sys.argv)
window = QMainWindow()
ui = Ui_MainWindow()
ui.setupUi(window)

ui.label.resizeEvent = onResize
ui.checkBox.stateChanged.connect(onResize)

# some fake 'photo' data to process
xx = np.arange(0, 300)
yy = np.arange(0, 200)
imagedata = np.array([[np.cos(x/25) + np.cos(y/25) for x in xx] for y in yy])
imagebytes = (100 + 56*(0.5+imagedata/4)).astype(np.uint8)

window.show()
try:
    sys.exit(app.exec_())
except:
    pass
