from qtpy import QtWidgets

class InterpolationRefineInfo_Dialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(InterpolationRefineInfo_Dialog, self).__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Association Options")
        self.name = "None"
        self.ID = "None"
        
        self.name_cell = QtWidgets.QLineEdit()
        self.id_cell = QtWidgets.QLineEdit()
        
        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(QtWidgets.QLabel("Name:"))
        row1.addStretch()
        row1.addWidget(self.name_cell)

        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(QtWidgets.QLabel("ID:"))
        row2.addStretch()
        row2.addWidget(self.id_cell)
        
        self.button = QtWidgets.QPushButton("Finish")
        self.button.clicked.connect(self.get_info)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addWidget(self.button)
        self.setLayout(layout)
        
    def get_info(self):
        self.name = self.name_cell.text()
        self.id = self.id_cell.text()

        self.accept()


