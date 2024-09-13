from qtpy import QtWidgets
from qtpy.QtCore import Qt

class InterpolationDialog(QtWidgets.QDialog):
    def __init__(self, min_val, max_val, parent=None):
        super(InterpolationDialog, self).__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Interpolation Options")

        self.start_frame = -1
        self.end_frame = -1
        self.interval = -1
        self.ID = -1
        self.label = -1

        self.start_value = 0
        self.end_value = 0

        self.start_frame_cell = QtWidgets.QLineEdit()
        self.end_frame_cell = QtWidgets.QLineEdit()
        self.interval_cell = QtWidgets.QLineEdit()
        self.ID_cell = QtWidgets.QLineEdit()
        self.label_cell = QtWidgets.QLineEdit()

        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(QtWidgets.QLabel("Start Frame:"))
        row1.addStretch()
        row1.addWidget(self.start_frame_cell)

        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(QtWidgets.QLabel("End Frame:"))
        row2.addStretch()
        row2.addWidget(self.end_frame_cell)

        row3 = QtWidgets.QHBoxLayout()
        row3.addWidget(QtWidgets.QLabel("Interval/FPS:"))
        row3.addStretch()
        row3.addWidget(self.interval_cell)

        row4 = QtWidgets.QHBoxLayout()
        row4.addWidget(QtWidgets.QLabel("Object ID:"))
        row4.addStretch()
        row4.addWidget(self.ID_cell)

        row5 = QtWidgets.QHBoxLayout()
        row5.addWidget(QtWidgets.QLabel("Object Label"))
        row5.addStretch()
        row5.addWidget(self.label_cell)

        # startsliderLayout = QtWidgets.QHBoxLayout()
        # self.start_slider = QtWidgets.QSlider(Qt.Horizontal)
        # self.start_slider.setPageStep(1)
        # self.start_slider.setRange(min_val, max_val)
        # self.start_slider.setValue(min_val)
        # self.start_slider.valueChanged.connect(self.onNewValue)
        # self.start_label = QtWidgets.QLabel(str(min_val), self)
        # startsliderLayout.addWidget(QtWidgets.QLabel("Start Frame:"))
        # startsliderLayout.addWidget(self.start_slider)
        # startsliderLayout.addWidget(self.start_label)

        # endsliderLayout = QtWidgets.QHBoxLayout()
        # self.end_slider = QtWidgets.QSlider(Qt.Horizontal)
        # self.end_slider.setPageStep(1)
        # self.end_slider.setRange(min_val, max_val)
        # self.end_slider.setValue(max_val)
        # self.end_slider.valueChanged.connect(self.onNewValue)
        # self.end_label = QtWidgets.QLabel(str(max_val), self)
        # endsliderLayout.addWidget(QtWidgets.QLabel("End Frame:"))
        # endsliderLayout.addWidget(self.end_slider)
        # endsliderLayout.addWidget(self.end_label)


        # self.formLayout = QtWidgets.QFormLayout()
        # self.formLayout.addRow(self.tr("Start Frame:"), self.slider_start_frame)
        # self.formLayout.addRow(self.tr("End Frame:"), self.slider_end_frame)

        self.button = QtWidgets.QPushButton("Finish")
        self.button.clicked.connect(self.get_info)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addLayout(row3)
        layout.addLayout(row4)
        layout.addLayout(row5)
        # layout.addLayout(startsliderLayout,stretch=3)
        # layout.addLayout(endsliderLayout,stretch=3)
        layout.addWidget(self.button)
        self.setLayout(layout)

    def get_info(self):
        self.start_frame = self.start_frame_cell.text()
        self.end_frame = self.end_frame_cell.text()
        self.interval = self.interval_cell.text()
        self.ID = self.interval_cell.text()
        self.label = self.label_cell.text()

        self.accept()
    
    # def onNewValue(self):
    #     start_value = self.start_slider.value() 
    #     end_value = self.end_slider.value()
    #     self.start_label.setText(str(start_value))
    #     self.end_label.setText(str(end_value))






