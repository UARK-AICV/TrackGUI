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

"""
class NavigationWidget(QtWidgets.QDialogButtonBox):
    def __init__(self, parent=None):
        super(NavigationWidget, self).__init__(parent)
        self.setOrientation(Qt.Horizontal)
        self.button1 = QtWidgets.QPushButton("Next Image (D)")
        # self.button1.clicked.connect(self.next)
        self.addButton(self.button1, QtWidgets.QDialogButtonBox.ActionRole)
        self.button2 = QtWidgets.QPushButton("Previous Image (A)")
        # self.button2.clicked.connect(self.prev)
        self.addButton(self.button2, QtWidgets.QDialogButtonBox.ActionRole)
        self.button3 = QtWidgets.QPushButton("OK")
        # self.button3.clicked.connect(self.okay)
        self.addButton(self.button3, QtWidgets.QDialogButtonBox.ActionRole)

        self.statusBar = QtWidgets.QStatusBar()
        self.statusBar.showMessage('Ready')
        

        # buttonLayout = QtWidgets.QHBoxLayout()
        # buttonLayout.addWidget(self.button1)
        # buttonLayout.addWidget(self.button2)
        # buttonLayout.addWidget(self.button3)
        # self.setLayout(buttonLayout)

    #     self.option_value = 0

    # def next(self):
    #     self.option_value = 1
    #     print("1")
    #     self.accept()
    
    # def prev(self):
    #     self.option_value = 2
    #     print("2")
    #     self.accept()
    
    # def okay(self):
    #     self.option_value = 3
    #     print("3")
    #     self.accept()
"""

class NavigationWidget(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(NavigationWidget, self).__init__(parent)

        self.button_box = QtWidgets.QDialogButtonBox()
        self.button_box.setOrientation(Qt.Horizontal)
        self.button1 = QtWidgets.QPushButton("FINISH")
        self.button_box.addButton(self.button1, QtWidgets.QDialogButtonBox.ActionRole)
        self.button2 = QtWidgets.QPushButton("Next Image (D)")
        self.button_box.addButton(self.button2, QtWidgets.QDialogButtonBox.ActionRole)
        self.button3 = QtWidgets.QPushButton("Previous Image (A)")
        self.button_box.addButton(self.button3, QtWidgets.QDialogButtonBox.ActionRole)
        
        self.statusBar = QtWidgets.QStatusBar()
        self.statusBar.setStyleSheet("border :1px solid black;border-radius: 1px ;text-align: center; ")
        self.statusBar.showMessage('Status: Not Ready | Mode: None') 

        navigationLayout = QtWidgets.QVBoxLayout()
        navigationLayout.addWidget(self.button_box)
        navigationLayout.addWidget(self.statusBar)
        self.setLayout(navigationLayout)