from qtpy import QtWidgets

class DeletionDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(DeletionDialog, self).__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Modification Options")

        self.start_frame = -1
        self.end_frame = -1
        self.interval = -1
        self.ID = -1
        self.label = -1

        self.start_frame_cell = QtWidgets.QLineEdit()
        self.end_frame_cell = QtWidgets.QLineEdit()
        self.interval_cell = QtWidgets.QLineEdit()
        self.ID_cell = QtWidgets.QLineEdit()
        self.label_cell = QtWidgets.QLineEdit()
        self.new_ID_cell = QtWidgets.QLineEdit()
        self.new_label_cell = QtWidgets.QLineEdit()

        self.row1 = QtWidgets.QHBoxLayout()
        self.row1.addWidget(QtWidgets.QLabel("Start Frame:"))
        self.row1.addStretch()
        self.row1.addWidget(self.start_frame_cell)

        self.row2 = QtWidgets.QHBoxLayout()
        self.row2.addWidget(QtWidgets.QLabel("End Frame:"))
        self.row2.addStretch()
        self.row2.addWidget(self.end_frame_cell)

        self.row4 = QtWidgets.QHBoxLayout()
        self.row4.addWidget(QtWidgets.QLabel("Object ID:"))
        self.row4.addStretch()
        self.row4.addWidget(self.ID_cell)

        self.row5 = QtWidgets.QHBoxLayout()
        self.row5.addWidget(QtWidgets.QLabel("Object Label"))
        self.row5.addStretch()
        self.row5.addWidget(self.label_cell)

        self.row6 = QtWidgets.QHBoxLayout()
        self.row6.addWidget(QtWidgets.QLabel("New ID:"))
        self.row6.addStretch()
        self.row6.addWidget(self.new_ID_cell)

        self.row7 = QtWidgets.QHBoxLayout()
        self.row7.addWidget(QtWidgets.QLabel("New Label"))
        self.row7.addStretch()
        self.row7.addWidget(self.new_label_cell)

        combobox = QtWidgets.QComboBox()
        combobox.addItems(["Remove Box", "Swap Label", "Swap ID"])
        row8 = QtWidgets.QHBoxLayout()
        row8.addWidget(QtWidgets.QLabel("Mode:"))
        row8.addStretch()
        row8.addWidget(combobox)

        self.button = QtWidgets.QPushButton("Finish")
        self.button.clicked.connect(self.get_info)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(self.row1)
        layout.addLayout(self.row2)
        layout.addLayout(self.row4)
        layout.addLayout(self.row5)
        layout.addLayout(self.row6)
        layout.addLayout(self.row7)
        layout.addLayout(row8)
        layout.addWidget(self.button)
        self.setLayout(layout)

    def get_info(self):
        self.start_frame = self.start_frame_cell.text()
        self.end_frame = self.end_frame_cell.text()
        self.ID = self.interval_cell.text()
        self.label = self.label_cell.text()

        self.accept()






