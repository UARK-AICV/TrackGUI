from qtpy import QtWidgets

class TrackDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(TrackDialog, self).__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Association Options")
        
        self.button1 = QtWidgets.QPushButton("Track from Scratch")
        self.button1.clicked.connect(self.option1)
        self.button2 = QtWidgets.QPushButton("Track w/ Current Annotation")
        self.button2.clicked.connect(self.option2)
        
        self.end_frame = QtWidgets.QLineEdit()
        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(QtWidgets.QLabel("End Frame:"))
        row1.addStretch()
        row1.addWidget(self.end_frame)

        combobox = QtWidgets.QComboBox()
        combobox.addItems(["SORT", "Byte-SORT", "OC-SORT"])
        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(QtWidgets.QLabel("Methods:"))
        row2.addStretch()
        row2.addWidget(combobox)

        buttonLayout = QtWidgets.QVBoxLayout()
        buttonLayout.addWidget(self.button1)
        buttonLayout.addWidget(self.button2)
        buttonLayout.addLayout(row1)
        buttonLayout.addLayout(row2)
        self.setLayout(buttonLayout)

        self.option_value = 0

    def option1(self):
        self.option_value = 1
        self.accept()
    
    def option2(self):
        self.option_value = 2
        self.accept()



