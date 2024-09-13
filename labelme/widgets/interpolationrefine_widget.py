from qtpy import QtGui
from qtpy import QtWidgets
from qtpy.QtCore import Qt
from qtpy import QtCore

from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets
from qtpy.QtCore import Qt
from qtpy.QtGui import QPalette
from qtpy.QtWidgets import QStyle

import labelme.utils
from labelme.logger import logger

from .. import utils


class IterpolationRefineWidget(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(IterpolationRefineWidget, self).__init__(parent)

        self.button = QtWidgets.QPushButton("Edit")
        
        self.statusBar = QtWidgets.QStatusBar()
        self.statusBar.setStyleSheet("border :1px solid black;border-radius: 1px ;text-align: center; ")
        self.statusBar.showMessage('Name: None | ID: None') 
        
        self.checkBox = QtWidgets.QCheckBox()
        
        navigationLayout = QtWidgets.QHBoxLayout()
        navigationLayout.addWidget(self.statusBar)
        navigationLayout.addWidget(self.checkBox )
        navigationLayout.addWidget(self.button   )
        
        self.setLayout(navigationLayout)