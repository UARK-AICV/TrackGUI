import re

from qtpy import QT_VERSION
from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets

import labelme.utils
from labelme.logger import logger

QT5 = QT_VERSION[0] == "5"


# TODO(unknown):
# - Calculate optimal position so as not to go out of screen area.


class IDQLineEdit(QtWidgets.QLineEdit):
    def setListWidget(self, list_widget):
        self.list_widget = list_widget

    def keyPressEvent(self, e):
        if e.key() in [QtCore.Qt.Key_Up, QtCore.Qt.Key_Down]:
            self.list_widget.keyPressEvent(e)
        else:
            super(IDQLineEdit, self).keyPressEvent(e)


class IDDialog(QtWidgets.QDialog):
    def __init__(
        self,
        text="Enter object id",
        parent=None,
        ids=None,
        sort_ids=True,
        show_text_field=True,
        completion="startswith",
        fit_to_content=None
    ):
        if fit_to_content is None:
            fit_to_content = {"row": False, "column": True}
        self._fit_to_content = fit_to_content

        super(IDDialog, self).__init__(parent)
        self.edit = IDQLineEdit()
        self.edit.setPlaceholderText(text)
        self.edit.setValidator(labelme.utils.labelValidator())
        self.edit.editingFinished.connect(self.postProcess)

        self.edit_track_id = QtWidgets.QLineEdit()
        self.edit_track_id.setPlaceholderText("Track ID")
        self.edit_track_id.setValidator(
            QtGui.QRegExpValidator(QtCore.QRegExp(r"\d*"), None)
        )
        layout = QtWidgets.QVBoxLayout()
        if show_text_field:
            layout_edit = QtWidgets.QHBoxLayout()
            layout_edit.addWidget(self.edit, 6)
            layout_edit.addWidget(self.edit_track_id, 2)
            layout.addLayout(layout_edit)
        # buttons
        self.buttonBox = bb = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        bb.button(bb.Ok).setIcon(labelme.utils.newIcon("done"))
        bb.button(bb.Cancel).setIcon(labelme.utils.newIcon("undo"))
        bb.accepted.connect(self.validate)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)
        # ID_list
        self.IDList = QtWidgets.QListWidget()
        if self._fit_to_content["row"]:
            self.IDList.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        if self._fit_to_content["column"]:
            self.IDList.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._sort_labels = sort_ids
        if ids:
            self.IDList.addItems(ids)
        if self._sort_labels:
            self.IDList.sortItems()
        else:
            self.IDList.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.IDList.currentItemChanged.connect(self.IDSelected)
        self.IDList.itemDoubleClicked.connect(self.IDDoubleClicked)
        self.IDList.setFixedHeight(150)
        self.edit.setListWidget(self.IDList)
        layout.addWidget(self.IDList)
        self.setLayout(layout)
        # completion
        # completer = QtWidgets.QCompleter()
        # if not QT5 and completion != "startswith":
        #     logger.warn(
        #         "completion other than 'startswith' is only "
        #         "supported with Qt5. Using 'startswith'"
        #     )
        #     completion = "startswith"
        # if completion == "startswith":
        #     completer.setCompletionMode(QtWidgets.QCompleter.InlineCompletion)
        #     # Default settings.
        #     # completer.setFilterMode(QtCore.Qt.MatchStartsWith)
        # elif completion == "contains":
        #     completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        #     completer.setFilterMode(QtCore.Qt.MatchContains)
        # else:
        #     raise ValueError("Unsupported completion: {}".format(completion))
        # completer.setModel(self.IDList.model())
        completer = QtWidgets.QCompleter(self.IDList.model(), self)
        completer.activated.connect(self.popUp)
        self.edit.setCompleter(completer)

    def addIDHistory(self, id):
        if self.IDList.findItems(id,QtCore.Qt.MatchExactly):
            return
        self.IDList.addItem(id)
        if self._sort_labels:
            self.IDList.sortItems()

    def IDSelected(self, item):
        self.edit.setText(item.text())

    def validate(self):
        text = self.edit.text()
        if hasattr(text, "strip"):
            text = text.strip()
        else:
            text = text.trimmed()
        if text:
            self.accept()

    def IDDoubleClicked(self,item):
        self.validate()

    def postProcess(self):
        text = self.edit.text()
        if hasattr(text, "strip"):
            text = text.strip()
        else:
            text = text.trimmed()
        self.edit.setText(text)

    def popUp(self, text=None, move=True):
        if self._fit_to_content["row"]:
            self.IDList.setMinimumHeight(
                self.IDList.sizeHintForRow(0) * self.IDList.count() + 2
            )
        if self._fit_to_content["column"]:
            self.IDList.setMinimumWidth(self.IDList.sizeHintForColumn(0) + 2)
        # if text is None, the previous label in self.edit is kept
        if text is None:
            text = self.edit.text()
        self.edit.setText(text)
        self.edit.setSelection(0, len(text))

        items = self.IDList.findItems(text, QtCore.Qt.MatchFixedString)
        if items:
            if len(items) != 1:
                logger.warning("ID list has duplicate '{}'".format(text))
            self.IDList.setCurrentItem(items[0])
            row = self.IDList.row(items[0])
            self.edit.completer().setCurrentRow(row)
        
        self.edit.setFocus(QtCore.Qt.PopupFocusReason)
        if move:
            self.move(QtGui.QCursor.pos())
        if self.exec_():
            return (
                self.edit.text()
            )
        else:
            return None
