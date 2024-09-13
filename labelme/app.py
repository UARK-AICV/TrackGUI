# -*- coding: utf-8 -*-

import functools
import html
import math
import os
import os.path as osp
import re
import webbrowser

import imgviz
import natsort
from qtpy import QtCore
from qtpy import QtGui
from qtpy import QtWidgets
from qtpy.QtCore import Qt

from labelme import PY2
from labelme import __appname__
from labelme.ai import MODELS
from labelme.config import get_config
from labelme.label_file import LabelFile
from labelme.label_file import LabelFileError
from labelme.logger import logger
from labelme.shape import Shape
from labelme.widgets import BrightnessContrastDialog
from labelme.widgets import Canvas
from labelme.widgets import FileDialogPreview
from labelme.widgets import LabelDialog
from labelme.widgets import IDDialog
from labelme.widgets import LabelListWidget
from labelme.widgets import LabelListWidgetItem
from labelme.widgets import IDListWidget
from labelme.widgets import IDListWidgetItem
from labelme.widgets import NavigationWidget
from labelme.widgets import TrackDialog
from labelme.widgets import InterpolationDialog
from labelme.widgets import IterpolationRefineWidget
from labelme.widgets import InterpolationRefineInfo_Dialog
from labelme.widgets import DeletionDialog
from labelme.widgets import ToolBar
from labelme.widgets import UniqueLabelQListWidget
from labelme.widgets import ZoomWidget

from . import utils

import numpy as np
import json
from labelme.track_algo import SORT_main
from labelme.track_algo import KalmanBoxTracker
from scipy.optimize import linear_sum_assignment

# FIXME
# - [medium] Set max zoom value to something big enough for FitWidth/Window

# TODO(unknown):
# - Zoom is too "steppy".


LABEL_COLORMAP = imgviz.label_colormap()


class MainWindow(QtWidgets.QMainWindow):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = 0, 1, 2

    def __init__(
        self,
        config=None,
        filename=None,
        output=None,
        output_file=None,
        output_dir=None,
    ):
        if output is not None:
            logger.warning("argument output is deprecated, use output_file instead")
            if output_file is None:
                output_file = output

        # see labelme/config/default_config.yaml for valid configuration
        if config is None:
            config = get_config()
        self._config = config

        self._config["auto_save"] = True
        self._config["store_data"] = False

        # set default shape colors
        Shape.line_color = QtGui.QColor(*self._config["shape"]["line_color"])
        Shape.fill_color = QtGui.QColor(*self._config["shape"]["fill_color"])
        Shape.select_line_color = QtGui.QColor(
            *self._config["shape"]["select_line_color"]
        )
        Shape.select_fill_color = QtGui.QColor(
            *self._config["shape"]["select_fill_color"]
        )
        Shape.vertex_fill_color = QtGui.QColor(
            *self._config["shape"]["vertex_fill_color"]
        )
        Shape.hvertex_fill_color = QtGui.QColor(
            *self._config["shape"]["hvertex_fill_color"]
        )

        # Set point size from config file
        Shape.point_size = self._config["shape"]["point_size"]

        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        # Whether we need to save or not.
        self.dirty = False

        self._noSelectionSlot = False

        self._copied_shapes = None

        # Main widgets and related state.
        self.labelDialog = LabelDialog(
            parent=self,
            labels=self._config["labels"],
            sort_labels=self._config["sort_labels"],
            show_text_field=self._config["show_label_text_field"],
            completion=self._config["label_completion"],
            fit_to_content=self._config["fit_to_content"],
            flags=self._config["label_flags"],
        )

        self.IDDialog = IDDialog(
            parent=self,
            ids=self._config["labels"],
            sort_ids=self._config["sort_labels"],
            show_text_field=self._config["show_label_text_field"],
            completion=self._config["label_completion"],
            fit_to_content=self._config["fit_to_content"]
        )

        self.labelList = LabelListWidget()
        self.lastOpenDir = None

        self.flag_dock = self.flag_widget = None
        self.flag_dock = QtWidgets.QDockWidget(self.tr("Flags"), self)
        self.flag_dock.setObjectName("Flags")
        self.flag_widget = QtWidgets.QListWidget()
        if config["flags"]:
            self.loadFlags({k: False for k in config["flags"]})
        self.flag_dock.setWidget(self.flag_widget)
        self.flag_widget.itemChanged.connect(self.setDirty)

        self.mode = "None"
        self.list_length = ""
        self.start_INP0 = 0
        self.end_INP0 = 0
        self.interval_INPO = 0
        self.ID_INPO = ""
        self.label_INPO = ""
        self.INTERPOLATION_list = []
        self.INTERPOLATION_filename = None
        self.navigation_list = NavigationWidget()
        self.navigation_list.button1.clicked.connect(self.OKAY)
        self.navigation_list.button2.clicked.connect(self.openNextImg)
        self.navigation_list.button3.clicked.connect(self.openPrevImg)
        self.navigation_dock = QtWidgets.QDockWidget(self.tr("Navigation"), self)
        self.navigation_dock.setObjectName("Navigation")
        self.navigation_dock.setWidget(self.navigation_list)
        
        self.interpolationrefine_list = IterpolationRefineWidget()
        self.interpolationrefine_list.button.clicked.connect(self.editIR_info)
        self.interpolationrefine_dock = QtWidgets.QDockWidget(self.tr("Interpolation Refinement"), self)
        self.interpolationrefine_dock.setObjectName("Interpolation Refinement")
        self.interpolationrefine_dock.setWidget(self.interpolationrefine_list)
        self.ir_name = "None"
        self.ir_id = "None"
        self.ir_old_shapes = []
        self.ir_old_shape = "None"
        self.ir_mod_shape = "None"
        self.ir_activated = False
        # self.interpolationrefine_list.checkBox.isChecked()

        self.labelList.itemSelectionChanged.connect(self.labelSelectionChanged)
        self.labelList.itemDoubleClicked.connect(self.editLabel)
        self.labelList.itemChanged.connect(self.labelItemChanged)
        self.labelList.itemDropped.connect(self.labelOrderChanged)
        self.shape_dock = QtWidgets.QDockWidget(self.tr("Polygon Labels"), self)
        self.shape_dock.setObjectName("Labels")
        self.shape_dock.setWidget(self.labelList)

        self.IDList = IDListWidget()
        self.IDList.itemSelectionChanged.connect(self.IDSelectionChanged)
        self.IDList.itemDoubleClicked.connect(self.editID)
        self.IDList.itemChanged.connect(self.IDItemChanged)
        self.IDList.itemDropped.connect(self.IDOrderChanged)
        self.shape_dock = QtWidgets.QDockWidget(self.tr("Polygon IDs"), self)
        self.shape_dock.setObjectName("IDs")
        self.shape_dock.setWidget(self.IDList)

        self.uniqLabelList = UniqueLabelQListWidget()
        self.uniqLabelList.setToolTip(
            self.tr(
                "Select label to start annotating for it. " "Press 'Esc' to deselect."
            )
        )
        if self._config["labels"]:
            for label in self._config["labels"]:
                item = self.uniqLabelList.createItemFromLabel(label)
                self.uniqLabelList.addItem(item)
                rgb = self._get_rgb_by_label(label)
                self.uniqLabelList.setItemLabel(item, label, rgb)
        self.label_dock = QtWidgets.QDockWidget(self.tr("Label List"), self)
        self.label_dock.setObjectName("Label List")
        self.label_dock.setWidget(self.uniqLabelList)

        self.fileSearch = QtWidgets.QLineEdit()
        self.fileSearch.setPlaceholderText(self.tr("Search Filename"))
        self.fileSearch.textChanged.connect(self.fileSearchChanged)
        self.fileListWidget = QtWidgets.QListWidget()
        self.fileListWidget.itemSelectionChanged.connect(self.fileSelectionChanged)
        fileListLayout = QtWidgets.QVBoxLayout()
        fileListLayout.setContentsMargins(0, 0, 0, 0)
        fileListLayout.setSpacing(0)
        fileListLayout.addWidget(self.fileSearch)
        fileListLayout.addWidget(self.fileListWidget)
        self.file_dock = QtWidgets.QDockWidget(self.tr("File List"), self)
        self.file_dock.setObjectName("Files")
        fileListWidget = QtWidgets.QWidget()
        fileListWidget.setLayout(fileListLayout)
        self.file_dock.setWidget(fileListWidget)

        self.zoomWidget = ZoomWidget()
        self.setAcceptDrops(True)

        self.canvas = self.labelList.canvas = Canvas(
            epsilon=self._config["epsilon"],
            double_click=self._config["canvas"]["double_click"],
            num_backups=self._config["canvas"]["num_backups"],
            crosshair=self._config["canvas"]["crosshair"],
        )
        self.canvas.zoomRequest.connect(self.zoomRequest)

        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidget(self.canvas)
        scrollArea.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scrollArea.verticalScrollBar(),
            Qt.Horizontal: scrollArea.horizontalScrollBar(),
        }
        self.canvas.scrollRequest.connect(self.scrollRequest)

        self.canvas.newShape.connect(self.newShape)
        self.canvas.shapeMoved.connect(self.setDirty)
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)

        self.setCentralWidget(scrollArea)

        features = QtWidgets.QDockWidget.DockWidgetFeatures()
        for dock in ["flag_dock", "label_dock", "shape_dock", "file_dock"]:
            if self._config[dock]["closable"]:
                features = features | QtWidgets.QDockWidget.DockWidgetClosable
            if self._config[dock]["floatable"]:
                features = features | QtWidgets.QDockWidget.DockWidgetFloatable
            if self._config[dock]["movable"]:
                features = features | QtWidgets.QDockWidget.DockWidgetMovable
            getattr(self, dock).setFeatures(features)
            if self._config[dock]["show"] is False:
                getattr(self, dock).setVisible(False)

        
        self.addDockWidget(Qt.RightDockWidgetArea, self.navigation_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.interpolationrefine_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.flag_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.label_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.shape_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.file_dock)

        # Actions
        action = functools.partial(utils.newAction, self)
        shortcuts = self._config["shortcuts"]
        quit = action(
            self.tr("&Quit"),
            self.close,
            shortcuts["quit"],
            "quit",
            self.tr("Quit application"),
        )
        open_ = action(
            self.tr("&Open\n"),
            self.openFile,
            shortcuts["open"],
            "open",
            self.tr("Open image or label file"),
        )
        opendir = action(
            self.tr("Open Dir"),
            self.openDirDialog,
            shortcuts["open_dir"],
            "open",
            self.tr("Open Dir"),
        )
        openNextImg = action(
            self.tr("&Next Image"),
            self.openNextImg,
            shortcuts["open_next"],
            "next",
            self.tr("Open next (hold Ctl+Shift to copy labels)"),
            enabled=False,
        )
        openPrevImg = action(
            self.tr("&Prev Image"),
            self.openPrevImg,
            shortcuts["open_prev"],
            "prev",
            self.tr("Open prev (hold Ctl+Shift to copy labels)"),
            enabled=False,
        )
        save = action(
            self.tr("&Save\n"),
            self.saveFile,
            shortcuts["save"],
            "save",
            self.tr("Save labels to file"),
            enabled=False,
        )
        saveAs = action(
            self.tr("&Save As"),
            self.saveFileAs,
            shortcuts["save_as"],
            "save-as",
            self.tr("Save labels to a different file"),
            enabled=False,
        )

        deleteFile = action(
            self.tr("&Delete File"),
            self.deleteFile,
            shortcuts["delete_file"],
            "delete",
            self.tr("Delete current label file"),
            enabled=False,
        )

        changeOutputDir = action(
            self.tr("&Change Output Dir"),
            slot=self.changeOutputDirDialog,
            shortcut=shortcuts["save_to"],
            icon="open",
            tip=self.tr("Change where annotations are loaded/saved"),
        )

        saveAuto = action(
            text=self.tr("Save &Automatically"),
            slot=lambda x: self.actions.saveAuto.setChecked(x),
            icon="save",
            tip=self.tr("Save automatically"),
            checkable=True,
            enabled=True,
        )
        saveAuto.setChecked(self._config["auto_save"])

        saveWithImageData = action(
            text="Save With Image Data",
            slot=self.enableSaveImageWithData,
            tip="Save image data in label file",
            checkable=True,
            checked=self._config["store_data"],
        )

        close = action(
            "&Close",
            self.closeFile,
            shortcuts["close"],
            "close",
            "Close current file",
        )

        toggle_keep_prev_mode = action(
            self.tr("Keep Previous Annotation"),
            self.toggleKeepPrevMode,
            shortcuts["toggle_keep_prev_mode"],
            None,
            self.tr('Toggle "keep pevious annotation" mode'),
            checkable=True,
        )
        toggle_keep_prev_mode.setChecked(self._config["keep_prev"])

        createMode = action(
            self.tr("Create Polygons"),
            lambda: self.toggleDrawMode(False, createMode="polygon"),
            shortcuts["create_polygon"],
            "objects",
            self.tr("Start drawing polygons"),
            enabled=False,
        )
        createRectangleMode = action(
            self.tr("Create Rectangle"),
            lambda: self.toggleDrawMode(False, createMode="rectangle"),
            shortcuts["create_rectangle"],
            "objects",
            self.tr("Start drawing rectangles"),
            enabled=False,
        )
        createCircleMode = action(
            self.tr("Create Circle"),
            lambda: self.toggleDrawMode(False, createMode="circle"),
            shortcuts["create_circle"],
            "objects",
            self.tr("Start drawing circles"),
            enabled=False,
        )
        createLineMode = action(
            self.tr("Create Line"),
            lambda: self.toggleDrawMode(False, createMode="line"),
            shortcuts["create_line"],
            "objects",
            self.tr("Start drawing lines"),
            enabled=False,
        )
        createPointMode = action(
            self.tr("Create Point"),
            lambda: self.toggleDrawMode(False, createMode="point"),
            shortcuts["create_point"],
            "objects",
            self.tr("Start drawing points"),
            enabled=False,
        )
        createLineStripMode = action(
            self.tr("Create LineStrip"),
            lambda: self.toggleDrawMode(False, createMode="linestrip"),
            shortcuts["create_linestrip"],
            "objects",
            self.tr("Start drawing linestrip. Ctrl+LeftClick ends creation."),
            enabled=False,
        )
        createAiPolygonMode = action(
            self.tr("Create AI-Polygon"),
            lambda: self.toggleDrawMode(False, createMode="ai_polygon"),
            None,
            "objects",
            self.tr("Start drawing ai_polygon. Ctrl+LeftClick ends creation."),
            enabled=False,
        )
        createAiPolygonMode.changed.connect(
            lambda: self.canvas.initializeAiModel(
                name=self._selectAiModelComboBox.currentText()
            )
            if self.canvas.createMode == "ai_polygon"
            else None
        )
        createAiMaskMode = action(
            self.tr("Create AI-Mask"),
            lambda: self.toggleDrawMode(False, createMode="ai_mask"),
            None,
            "objects",
            self.tr("Start drawing ai_mask. Ctrl+LeftClick ends creation."),
            enabled=False,
        )
        createAiMaskMode.changed.connect(
            lambda: self.canvas.initializeAiModel(
                name=self._selectAiModelComboBox.currentText()
            )
            if self.canvas.createMode == "ai_mask"
            else None
        )
        editMode = action(
            self.tr("Edit Polygons"),
            self.setEditMode,
            shortcuts["edit_polygon"],
            "edit",
            self.tr("Move and edit the selected polygons"),
            enabled=False,
        )

        delete = action(
            self.tr("Delete Polygons"),
            self.deleteSelectedShape,
            shortcuts["delete_polygon"],
            "cancel",
            self.tr("Delete the selected polygons"),
            enabled=False,
        )
        duplicate = action(
            self.tr("Duplicate Polygons"),
            self.duplicateSelectedShape,
            shortcuts["duplicate_polygon"],
            "copy",
            self.tr("Create a duplicate of the selected polygons"),
            enabled=False,
        )
        copy = action(
            self.tr("Copy Polygons"),
            self.copySelectedShape,
            shortcuts["copy_polygon"],
            "copy_clipboard",
            self.tr("Copy selected polygons to clipboard"),
            enabled=False,
        )
        paste = action(
            self.tr("Paste Polygons"),
            self.pasteSelectedShape,
            shortcuts["paste_polygon"],
            "paste",
            self.tr("Paste copied polygons"),
            enabled=False,
        )
        undoLastPoint = action(
            self.tr("Undo last point"),
            self.canvas.undoLastPoint,
            shortcuts["undo_last_point"],
            "undo",
            self.tr("Undo last drawn point"),
            enabled=False,
        )
        removePoint = action(
            text="Remove Selected Point",
            slot=self.removeSelectedPoint,
            shortcut=shortcuts["remove_selected_point"],
            icon="edit",
            tip="Remove selected point from polygon",
            enabled=False,
        )

        undo = action(
            self.tr("Undo\n"),
            self.undoShapeEdit,
            shortcuts["undo"],
            "undo",
            self.tr("Undo last add and edit of shape"),
            enabled=False,
        )

        hideAll = action(
            self.tr("&Hide\nPolygons"),
            functools.partial(self.togglePolygons, False),
            shortcuts["hide_all_polygons"],
            icon="eye",
            tip=self.tr("Hide all polygons"),
            enabled=False,
        )
        showAll = action(
            self.tr("&Show\nPolygons"),
            functools.partial(self.togglePolygons, True),
            shortcuts["show_all_polygons"],
            icon="eye",
            tip=self.tr("Show all polygons"),
            enabled=False,
        )
        toggleAll = action(
            self.tr("&Toggle\nPolygons"),
            functools.partial(self.togglePolygons, None),
            shortcuts["toggle_all_polygons"],
            icon="eye",
            tip=self.tr("Toggle all polygons"),
            enabled=False,
        )

        help = action(
            self.tr("&Tutorial"),
            self.tutorial,
            icon="help",
            tip=self.tr("Show tutorial page"),
        )

        zoom = QtWidgets.QWidgetAction(self)
        zoomBoxLayout = QtWidgets.QVBoxLayout()
        zoomLabel = QtWidgets.QLabel("Zoom")
        zoomLabel.setAlignment(Qt.AlignCenter)
        zoomBoxLayout.addWidget(zoomLabel)
        zoomBoxLayout.addWidget(self.zoomWidget)
        zoom.setDefaultWidget(QtWidgets.QWidget())
        zoom.defaultWidget().setLayout(zoomBoxLayout)
        self.zoomWidget.setWhatsThis(
            str(
                self.tr(
                    "Zoom in or out of the image. Also accessible with "
                    "{} and {} from the canvas."
                )
            ).format(
                utils.fmtShortcut(
                    "{},{}".format(shortcuts["zoom_in"], shortcuts["zoom_out"])
                ),
                utils.fmtShortcut(self.tr("Ctrl+Wheel")),
            )
        )
        self.zoomWidget.setEnabled(False)

        zoomIn = action(
            self.tr("Zoom &In"),
            functools.partial(self.addZoom, 1.1),
            shortcuts["zoom_in"],
            "zoom-in",
            self.tr("Increase zoom level"),
            enabled=False,
        )
        zoomOut = action(
            self.tr("&Zoom Out"),
            functools.partial(self.addZoom, 0.9),
            shortcuts["zoom_out"],
            "zoom-out",
            self.tr("Decrease zoom level"),
            enabled=False,
        )
        zoomOrg = action(
            self.tr("&Original size"),
            functools.partial(self.setZoom, 100),
            shortcuts["zoom_to_original"],
            "zoom",
            self.tr("Zoom to original size"),
            enabled=False,
        )
        keepPrevScale = action(
            self.tr("&Keep Previous Scale"),
            self.enableKeepPrevScale,
            tip=self.tr("Keep previous zoom scale"),
            checkable=True,
            checked=self._config["keep_prev_scale"],
            enabled=True,
        )
        fitWindow = action(
            self.tr("&Fit Window"),
            self.setFitWindow,
            shortcuts["fit_window"],
            "fit-window",
            self.tr("Zoom follows window size"),
            checkable=True,
            enabled=False,
        )
        fitWidth = action(
            self.tr("Fit &Width"),
            self.setFitWidth,
            shortcuts["fit_width"],
            "fit-width",
            self.tr("Zoom follows window width"),
            checkable=True,
            enabled=False,
        )
        brightnessContrast = action(
            "&Brightness Contrast",
            self.brightnessContrast,
            None,
            "color",
            "Adjust brightness and contrast",
            enabled=False,
        )
        # Group zoom controls into a list for easier toggling.
        zoomActions = (
            self.zoomWidget,
            zoomIn,
            zoomOut,
            zoomOrg,
            fitWindow,
            fitWidth,
        )
        self.zoomMode = self.FIT_WINDOW
        fitWindow.setChecked(Qt.Checked)
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        edit = action(
            self.tr("&Edit Label"),
            self.editLabel,
            shortcuts["edit_label"],
            "edit",
            self.tr("Modify the label of the selected polygon"),
            enabled=False,
        )

        edit_ID = action(
            self.tr("&Edit ID"),
            self.editID,
            shortcuts["edit_id"],
            "edit",
            self.tr("Modify the ID of the selected polygon"),
            enabled=False
        )

        call_sort = action(
            self.tr("&ID Association"),
            self.SORT,
            None,
            "edit",
            self.tr("ID Association"),
            enabled=False,
        )

        call_interpolation = action(
            self.tr("&Box/ID Interpolation"),
            self.INTERPOLATION,
            None,
            "edit",
            self.tr("Box/ID Interpolation"),
            enabled=False,
        )

        call_deletion = action(
            self.tr("&Box/ID Modification"),
            self.DELETION,
            None,
            "edit",
            self.tr("Box/ID Modification"),
            enabled=False,
        )

        fill_drawing = action(
            self.tr("Fill Drawing Polygon"),
            self.canvas.setFillDrawing,
            None,
            "color",
            self.tr("Fill polygon while drawing"),
            checkable=True,
            enabled=True,
        )
        if self._config["canvas"]["fill_drawing"]:
            fill_drawing.trigger()

        # Lavel list context menu.
        labelMenu = QtWidgets.QMenu()
        utils.addActions(labelMenu, (edit, delete))
        self.labelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.labelList.customContextMenuRequested.connect(self.popLabelListMenu)

        IDMenu = QtWidgets.QMenu()
        utils.addActions(IDMenu, (edit_ID, delete))
        self.IDList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.IDList.customContextMenuRequested.connect(self.popIDListMenu)

        # Store actions for further handling.
        self.actions = utils.struct(
            saveAuto=saveAuto,
            saveWithImageData=saveWithImageData,
            changeOutputDir=changeOutputDir,
            save=save,
            saveAs=saveAs,
            open=open_,
            close=close,
            deleteFile=deleteFile,
            toggleKeepPrevMode=toggle_keep_prev_mode,
            delete=delete,
            edit=edit,
            edit_id=edit_ID,
            SORT=call_sort,
            INPO=call_interpolation,
            DELE=call_deletion,
            duplicate=duplicate,
            copy=copy,
            paste=paste,
            undoLastPoint=undoLastPoint,
            undo=undo,
            removePoint=removePoint,
            createMode=createMode,
            editMode=editMode,
            createRectangleMode=createRectangleMode,
            createCircleMode=createCircleMode,
            createLineMode=createLineMode,
            createPointMode=createPointMode,
            createLineStripMode=createLineStripMode,
            createAiPolygonMode=createAiPolygonMode,
            createAiMaskMode=createAiMaskMode,
            zoom=zoom,
            zoomIn=zoomIn,
            zoomOut=zoomOut,
            zoomOrg=zoomOrg,
            keepPrevScale=keepPrevScale,
            fitWindow=fitWindow,
            fitWidth=fitWidth,
            brightnessContrast=brightnessContrast,
            zoomActions=zoomActions,
            openNextImg=openNextImg,
            openPrevImg=openPrevImg,
            fileMenuActions=(open_, opendir, save, saveAs, close, quit),
            tool=(),
            # XXX: need to add some actions here to activate the shortcut
            editMenu=(
                edit,
                edit_ID,
                duplicate,
                copy,
                paste,
                delete,
                None,
                undo,
                undoLastPoint,
                None,
                removePoint,
                None,
                toggle_keep_prev_mode,
            ),
            # menu shown at right click
            menu=(
                createMode,
                createRectangleMode,
                createCircleMode,
                createLineMode,
                createPointMode,
                createLineStripMode,
                createAiPolygonMode,
                createAiMaskMode,
                editMode,
                edit,
                edit_ID,
                duplicate,
                copy,
                paste,
                delete,
                undo,
                undoLastPoint,
                removePoint,
            ),
            onLoadActive=(
                close,
                createMode,
                createRectangleMode,
                createCircleMode,
                createLineMode,
                createPointMode,
                createLineStripMode,
                createAiPolygonMode,
                createAiMaskMode,
                editMode,
                brightnessContrast,
            ),
            onShapesPresent=(saveAs, hideAll, showAll, toggleAll),
        )

        self.canvas.vertexSelected.connect(self.actions.removePoint.setEnabled)

        self.menus = utils.struct(
            file=self.menu(self.tr("&File")),
            edit=self.menu(self.tr("&Edit")),
            track=self.menu(self.tr("&Track")),
            view=self.menu(self.tr("&View")),
            help=self.menu(self.tr("&Help")),
            recentFiles=QtWidgets.QMenu(self.tr("Open &Recent")),
            labelList=labelMenu,
            IDList=IDMenu
        )

        utils.addActions(
            self.menus.file,
            (
                open_,
                openNextImg,
                openPrevImg,
                opendir,
                self.menus.recentFiles,
                save,
                saveAs,
                saveAuto,
                changeOutputDir,
                saveWithImageData,
                close,
                deleteFile,
                None,
                quit,
            ),
        )
        utils.addActions(self.menus.help, (help,))
        utils.addActions(
            self.menus.view,
            (
                self.flag_dock.toggleViewAction(),
                self.label_dock.toggleViewAction(),
                self.shape_dock.toggleViewAction(),
                self.file_dock.toggleViewAction(),
                None,
                fill_drawing,
                None,
                hideAll,
                showAll,
                toggleAll,
                None,
                zoomIn,
                zoomOut,
                zoomOrg,
                keepPrevScale,
                None,
                fitWindow,
                fitWidth,
                None,
                brightnessContrast,
            ),
        )
        utils.addActions(
            self.menus.track,
            (call_interpolation,call_sort,call_deletion),
        )

        self.menus.file.aboutToShow.connect(self.updateFileMenu)

        # Custom context menu for the canvas widget:
        utils.addActions(self.canvas.menus[0], self.actions.menu)
        # utils.addActions(self.canvas.editID)
        utils.addActions(
            self.canvas.menus[1],
            (
                action("&Copy here", self.copyShape),
                action("&Move here", self.moveShape),
            ),
        )

        selectAiModel = QtWidgets.QWidgetAction(self)
        selectAiModel.setDefaultWidget(QtWidgets.QWidget())
        selectAiModel.defaultWidget().setLayout(QtWidgets.QVBoxLayout())
        #
        selectAiModelLabel = QtWidgets.QLabel(self.tr("AI Model"))
        selectAiModelLabel.setAlignment(QtCore.Qt.AlignCenter)
        selectAiModel.defaultWidget().layout().addWidget(selectAiModelLabel)
        #
        self._selectAiModelComboBox = QtWidgets.QComboBox()
        selectAiModel.defaultWidget().layout().addWidget(self._selectAiModelComboBox)
        model_names = [model.name for model in MODELS]
        self._selectAiModelComboBox.addItems(model_names)
        if self._config["ai"]["default"] in model_names:
            model_index = model_names.index(self._config["ai"]["default"])
        else:
            logger.warning(
                "Default AI model is not found: %r",
                self._config["ai"]["default"],
            )
            model_index = 0
        self._selectAiModelComboBox.setCurrentIndex(model_index)
        self._selectAiModelComboBox.currentIndexChanged.connect(
            lambda: self.canvas.initializeAiModel(
                name=self._selectAiModelComboBox.currentText()
            )
            if self.canvas.createMode in ["ai_polygon", "ai_mask"]
            else None
        )

        self.tools = self.toolbar("Tools")
        self.actions.tool = (
            open_,
            opendir,
            openPrevImg,
            openNextImg,
            save,
            deleteFile,
            None,
            createMode,
            editMode,
            duplicate,
            delete,
            undo,
            brightnessContrast,
            None,
            fitWindow,
            zoom,
            None,
            selectAiModel,
        )

        self.statusBar().showMessage(str(self.tr("%s started.")) % __appname__)
        self.statusBar().show()

        if output_file is not None and self._config["auto_save"]:
            logger.warn(
                "If `auto_save` argument is True, `output_file` argument "
                "is ignored and output filename is automatically "
                "set as IMAGE_BASENAME.json."
            )
        self.output_file = output_file
        self.output_dir = output_dir

        # Application state.
        self.image = QtGui.QImage()
        self.imagePath = None
        self.recentFiles = []
        self.maxRecent = 7
        self.otherData = None
        self.zoom_level = 100
        self.fit_window = False
        self.zoom_values = {}  # key=filename, value=(zoom_mode, zoom_value)
        self.brightnessContrast_values = {}
        self.scroll_values = {
            Qt.Horizontal: {},
            Qt.Vertical: {},
        }  # key=filename, value=scroll_value

        if filename is not None and osp.isdir(filename):
            self.importDirImages(filename, load=False)
        else:
            self.filename = filename

        if config["file_search"]:
            self.fileSearch.setText(config["file_search"])
            self.fileSearchChanged()

        # XXX: Could be completely declarative.
        # Restore application settings.
        self.settings = QtCore.QSettings("labelme", "labelme")
        self.recentFiles = self.settings.value("recentFiles", []) or []
        size = self.settings.value("window/size", QtCore.QSize(600, 500))
        position = self.settings.value("window/position", QtCore.QPoint(0, 0))
        state = self.settings.value("window/state", QtCore.QByteArray())
        self.resize(size)
        self.move(position)
        # or simply:
        # self.restoreGeometry(settings['window/geometry']
        self.restoreState(state)

        # Populate the File menu dynamically.
        self.updateFileMenu()
        # Since loading the file may take some time,
        # make sure it runs in the background.
        if self.filename is not None:
            self.queueEvent(functools.partial(self.loadFile, self.filename))

        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)

        self.populateModeActions()

        # self.firstStart = True
        # if self.firstStart:
        #    QWhatsThis.enterWhatsThisMode()

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            utils.addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName("%sToolBar" % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            utils.addActions(toolbar, actions)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        return toolbar

    # Support Functions

    def noShapes(self):
        return not len(self.labelList)

    def populateModeActions(self):
        tool, menu = self.actions.tool, self.actions.menu
        self.tools.clear()
        utils.addActions(self.tools, tool)
        self.canvas.menus[0].clear()
        utils.addActions(self.canvas.menus[0], menu)
        self.menus.edit.clear()
        actions = (
            self.actions.createMode,
            self.actions.createRectangleMode,
            self.actions.createCircleMode,
            self.actions.createLineMode,
            self.actions.createPointMode,
            self.actions.createLineStripMode,
            self.actions.createAiPolygonMode,
            self.actions.createAiMaskMode,
            self.actions.editMode,
        )
        utils.addActions(self.menus.edit, actions + self.actions.editMenu)

    def setDirty(self):
        # Even if we autosave the file, we keep the ability to undo
        self.actions.undo.setEnabled(self.canvas.isShapeRestorable)
        if self._config["auto_save"] or self.actions.saveAuto.isChecked():
            label_file = osp.splitext(self.imagePath)[0] + ".json"
            if self.output_dir:
                label_file_without_path = osp.basename(label_file)
                label_file = osp.join(self.output_dir, label_file_without_path)
            self.saveLabels(label_file)
            return
        self.dirty = True
        self.actions.save.setEnabled(True)
        title = __appname__
        if self.filename is not None:
            title = "{} - {}*".format(title, self.filename)
        self.setWindowTitle(title)

    def setClean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.createMode.setEnabled(True)
        self.actions.createRectangleMode.setEnabled(True)
        self.actions.createCircleMode.setEnabled(True)
        self.actions.createLineMode.setEnabled(True)
        self.actions.createPointMode.setEnabled(True)
        self.actions.createLineStripMode.setEnabled(True)
        self.actions.createAiPolygonMode.setEnabled(True)
        self.actions.createAiMaskMode.setEnabled(True)
        self.actions.SORT.setEnabled(True)
        self.actions.INPO.setEnabled(True)
        self.actions.DELE.setEnabled(True)
        title = __appname__
        if self.filename is not None:
            title = "{} - {}".format(title, self.filename)
        self.setWindowTitle(title)

        if self.hasLabelFile():
            self.actions.deleteFile.setEnabled(True)
        else:
            self.actions.deleteFile.setEnabled(False)

    def toggleActions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)

    def queueEvent(self, function):
        QtCore.QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.labelList.clear()
        self.IDList.clear()
        self.filename = None
        self.imagePath = None
        self.imageData = None
        self.labelFile = None
        self.otherData = None
        self.canvas.resetState()

    def currentItem(self):
        items_l = self.labelList.selectedItems()
        items_i = self.IDList.selectedItems()
        if items_l:
            return items_l[0], items_i[0]
        return None, None

    def addRecentFile(self, filename):
        if filename in self.recentFiles:
            self.recentFiles.remove(filename)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filename)

    # Callbacks

    def undoShapeEdit(self):
        self.canvas.restoreShape()
        self.labelList.clear()
        self.IDList.clear()
        self.loadShapes(self.canvas.shapes)
        self.actions.undo.setEnabled(self.canvas.isShapeRestorable)

    def tutorial(self):
        url = "https://github.com/wkentaro/labelme/tree/main/examples/tutorial"  # NOQA
        webbrowser.open(url)

    def toggleDrawingSensitive(self, drawing=True):
        """Toggle drawing sensitive.

        In the middle of drawing, toggling between modes should be disabled.
        """
        self.actions.editMode.setEnabled(not drawing)
        self.actions.undoLastPoint.setEnabled(drawing)
        self.actions.undo.setEnabled(not drawing)
        self.actions.delete.setEnabled(not drawing)

    def toggleDrawMode(self, edit=True, createMode="polygon"):
        draw_actions = {
            "polygon": self.actions.createMode,
            "rectangle": self.actions.createRectangleMode,
            "circle": self.actions.createCircleMode,
            "point": self.actions.createPointMode,
            "line": self.actions.createLineMode,
            "linestrip": self.actions.createLineStripMode,
            "ai_polygon": self.actions.createAiPolygonMode,
            "ai_mask": self.actions.createAiMaskMode,
        }

        self.canvas.setEditing(edit)
        self.canvas.createMode = createMode
        if edit:
            for draw_action in draw_actions.values():
                draw_action.setEnabled(True)
        else:
            for draw_mode, draw_action in draw_actions.items():
                draw_action.setEnabled(createMode != draw_mode)
        self.actions.editMode.setEnabled(not edit)

    def setEditMode(self):
        self.toggleDrawMode(True)

    def updateFileMenu(self):
        current = self.filename

        def exists(filename):
            return osp.exists(str(filename))

        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f != current and exists(f)]
        for i, f in enumerate(files):
            icon = utils.newIcon("labels")
            action = QtWidgets.QAction(
                icon, "&%d %s" % (i + 1, QtCore.QFileInfo(f).fileName()), self
            )
            action.triggered.connect(functools.partial(self.loadRecent, f))
            menu.addAction(action)

    def popLabelListMenu(self, point):
        self.menus.labelList.exec_(self.labelList.mapToGlobal(point))

    def popIDListMenu(self, point):
        self.menus.IDList.exec_(self.IDList.mapToGlobal(point))

    def validateLabel(self, label):
        # no validation
        if self._config["validate_label"] is None:
            return True

        for i in range(self.uniqLabelList.count()):
            label_i = self.uniqLabelList.item(i).data(Qt.UserRole)
            if self._config["validate_label"] in ["exact"]:
                if label_i == label:
                    return True
        return False

    def editIR_info(self, item=None):
        dialog = InterpolationRefineInfo_Dialog(
            parent=self,
        )
        dialog.exec_()
        
        self.ir_name = dialog.name
        self.ir_id = dialog.id
        
        self.interpolationrefine_list.statusBar.showMessage(f'Name: {self.ir_name} | ID: {self.ir_id}')
        
        
    def SORT(self, item=None):
        def convert(box):
            w = abs(box[1][0] - box[0][0])
            h = abs(box[1][1] - box[0][1])
            return [box[0][0],box[0][1],w,h]

        dialog = TrackDialog(
            parent=self,
        )
        dialog.exec_()

        # 3 modes
        # + start by using the current frame's track annotation
        # + start from scratch without track annotation
        track_option = dialog.option_value
        
        # print frame shortage here
        # ...

        if track_option != 0:   
            # get the index of current item
            items = self.fileListWidget.selectedItems()
            item = items[0]
            currIndex = self.imageList.index(str(item.text()))

            # get label list .json
            if track_option == 1:   # start from beginning
                labelList = [osp.splitext(img_p)[0] + ".json" for img_p in self.imageList]
            else:
                labelList = [osp.splitext(img_p)[0] + ".json" for img_p in self.imageList][currIndex:]
            
            # convert label to Track Evaluation
            lines = []
            frame_id = 1
            for jdx, json_path in enumerate(labelList):
                if jdx == 0:    # first frame 
                    bboxes = [ [[self.IDList[idx].shape().points[0].x(),\
                                self.IDList[idx].shape().points[0].y()],\
                                [self.IDList[idx].shape().points[1].x(),\
                                self.IDList[idx].shape().points[1].y()]]       for idx in range(len(self.IDList))]
                    bboxes_xywh = [convert(bboxes[i]) for i in range(len(bboxes))]
                    
                    if track_option == 2: # start with current annotation
                        track_ids = [self.IDList[idx].text() for idx in range(len(self.IDList))]
                        int_track_ids = [int(self.IDList[idx].text()) for idx in range(len(self.IDList))]
                        
                        if '-1' in track_ids:
                            self.errorMessage(
                                "Track IDs",
                                "You must label all objects' IDs.",
                            )
                            return
                        for l in range(len(bboxes_xywh)):
                            lines.append([frame_id,int(track_ids[l]),bboxes_xywh[l][0],bboxes_xywh[l][1],bboxes_xywh[l][2],bboxes_xywh[l][3],1,-1,-1,-1])
                    else:   # start with NO annotation
                        for l in range(len(bboxes_xywh)):
                            lines.append([frame_id,-1,bboxes_xywh[l][0],bboxes_xywh[l][1],bboxes_xywh[l][2],bboxes_xywh[l][3],1,-1,-1,-1])
                else:       # next frames # all ids are -1
                    with open(json_path) as file:
                        data = json.load(file)

                    bboxes = [data['shapes'][i]['points'] for i in range(len(data['shapes']))]
                    # need boxes in x,y,w,h
                    bboxes_xywh = [convert(bboxes[i]) for i in range(len(bboxes))]

                    # frame_id, track_id, x_top_left, y_top_left, width, height,1,-1,-1,-1
                    for l in range(len(bboxes_xywh)):
                        lines.append([frame_id,-1,bboxes_xywh[l][0],bboxes_xywh[l][1],bboxes_xywh[l][2],bboxes_xywh[l][3],1,-1,-1,-1])
                frame_id += 1
            seq_dets = np.array(lines).astype(float)
            
            mot_tracker = SORT_main(max_age=10,min_hits=0,iou_threshold=0.3)
            mot_tracker.trackers = []
            KalmanBoxTracker.count = 0
            track_results = []
            if track_option == 2:
                for idx in range(len(seq_dets[seq_dets[:, 0]==1])):
                    dets = seq_dets[seq_dets[:, 0]==1,2:7][idx:idx+1]   # original setting: x,y,w,h top left width height
                    det_id = seq_dets[seq_dets[:, 0]==1,1][idx]
                    dets[:, 2:4] += dets[:, 0:2] #convert to [x1,y1,w,h] to [x1,y1,x2,y2]
                    KalmanBoxTracker.count = max(int_track_ids)+1
                    KalmanBoxTracker.id = 0
                    mot_tracker.trackers.append(KalmanBoxTracker(dets[0],id=det_id))
            
            for frame in range(int(seq_dets[:,0].max())):
                frame += 1 #detection and frame numbers begin at 1
                dets = seq_dets[seq_dets[:, 0]==frame, 2:7]   # original setting: x,y,w,h top left width height
                dets[:, 2:4] += dets[:, 0:2] #convert to [x1,y1,w,h] to [x1,y1,x2,y2]
                trackers = mot_tracker.update(dets)

                for d in trackers:
                    track_results.append([frame,d[4],d[0],d[1],d[2]-d[0],d[3]-d[1]])
            track_results = np.array(track_results).astype(int)

            lf = LabelFile()
            flags = {}
            # Edit frame Shape and save
            for jdx, json_path in enumerate(labelList):
                loaded_label = LabelFile(json_path)
                loaded_shape = loaded_label.shapes
                frame = jdx+1
                track_ids = track_results[track_results[:, 0]==frame,1]
                track_xy = track_results[track_results[:, 0]==frame,2:4]
                shape_xy = [loaded_shape[idx]['points'][0] for idx in range(len(loaded_shape))]

                hungarian_matrix = []
                for adx in range(len(shape_xy)):
                    row = []
                    for bdx in range(len(track_xy)):
                        row.append( np.sum(np.abs(shape_xy[adx]-track_xy[bdx])) )
                    hungarian_matrix.append(row)
                shape_m,track_m = linear_sum_assignment(np.array(hungarian_matrix))

                for idx in range(len(shape_xy)):
                    loaded_shape[idx]['track_id'] = str(track_ids[track_m[idx]])
                
                imagePath = osp.splitext(json_path)[0] + ".jpg"            
                lf.save(
                    filename=json_path,
                    shapes=loaded_shape,
                    imagePath=imagePath,
                    imageData=None,
                    imageHeight=self.image.height(),
                    imageWidth=self.image.width(),
                    flags=flags,
                )
                
            # repaint the current frame
            self.informationMessage(
                                "Track IDs",
                                "ID Association is completed",
                            )
            self.loadFile(self.filename)

    def INTERPOLATION(self, item=None):
        dialog = InterpolationDialog(
            min_val=0,max_val=len(self.imageList),parent=self
        )
        dialog.exec_()
        # import ipdb; ipdb.set_trace()
        if (dialog.start_frame_cell.text() == '' or 
            dialog.end_frame_cell.text() == '' or 
            dialog.interval_cell.text() == '' or 
            dialog.ID_cell.text() == '' or 
            dialog.label_cell.text() == ''):

            self.errorMessage(
                                "Box Interpolation",
                                "You must fill all the values in the form.",
                            )
            
            return

        self.start_INP0 = start_frame = int(dialog.start_frame_cell.text().replace(" ", ""))
        self.end_INP0 = end_frame = int(dialog.end_frame_cell.text().replace(" ", ""))
        self.interval_INPO = interval = int(dialog.interval_cell.text().replace(" ", ""))
        self.ID_INPO = ID = dialog.ID_cell.text().replace(" ", "")
        self.label_INPO = label = dialog.label_cell.text().replace(" ", "")

        if end_frame - start_frame <=0:
            self.errorMessage(
                                "Box Interpolation",
                                "Start frame is higher than End frame.",
                            )
            
            return
        elif interval == 0 or interval > (end_frame-start_frame):
            self.errorMessage(
                                "Box Interpolation",
                                "Input Interval is bigger than Start-End frame gap (or is 0).",
                            )
            
            return
        elif end_frame > len(self.imageList):
            self.errorMessage(
                                "Box Interpolation",
                                "Input End frame is out of the video length.",
                            )
            
            return
       
        img_indices = np.linspace(start_frame-1,end_frame-1,num=int((end_frame-start_frame+1)/interval),dtype=int)

        self.mode = "TRACK INTERPOLATION"
        self.INTERPOLATION_list = np.array(self.imageList)[img_indices].tolist()
        self.INTERPOLATION_filename = self.INTERPOLATION_list[0]
        self.filename = self.INTERPOLATION_filename
        self.loadFile(self.filename)
    
    def OKAY(self, item=None):
        def convert(box):
            return [box[0][0],box[0][1],box[1][0],box[1][1]]
        
        def cvt_xyxy2xywh(old_bboxes):
            new_bboxes = np.zeros(old_bboxes.shape)
            new_bboxes[:,0] = (old_bboxes[:,0]+old_bboxes[:,2])/2
            new_bboxes[:,1] = (old_bboxes[:,1]+old_bboxes[:,3])/2
            new_bboxes[:,2] = old_bboxes[:,2] - old_bboxes[:,0]
            new_bboxes[:,3] = old_bboxes[:,3] - old_bboxes[:,1]
            return new_bboxes

        def cvt_xywh2xyxy(old_bboxes):
            new_bboxes = np.zeros(old_bboxes.shape)
            dw = old_bboxes[:,2]/2
            dh = old_bboxes[:,3]/2
            new_bboxes[:,0] = old_bboxes[:,0] - dw
            new_bboxes[:,1] = old_bboxes[:,1] - dh
            new_bboxes[:,2] = old_bboxes[:,0] + dw
            new_bboxes[:,3] = old_bboxes[:,1] + dh
            return new_bboxes
        
        from sklearn.gaussian_process import GaussianProcessRegressor
        from sklearn.gaussian_process.kernels import RationalQuadratic 
        
        if self.mode == "None" or self.mode == "NORMAL":
            return
        elif self.mode == "TRACK INTERPOLATION":
            self.INTERPOLATION_filename = self.INTERPOLATION_list[0]
            self.filename = self.INTERPOLATION_filename
            self.loadFile(self.filename)

            # print(self.start_INP0, self.end_INP0, self.ID_INPO, self.label_INPO)

            labelList = [osp.splitext(img_p)[0] + ".json" for img_p in self.INTERPOLATION_list]
            interpolatedList = self.imageList[self.start_INP0-1:self.end_INP0]
            interpolatedList = [osp.splitext(img_p)[0] + ".json" for img_p in interpolatedList]
            img_indices = np.linspace(self.start_INP0-1,self.end_INP0-1,num=int((self.end_INP0-self.start_INP0+1)/self.interval_INPO),dtype=int)

            ref_bxoxes = []
            for jdx, json_path in enumerate(labelList):
                with open(json_path) as file:
                    data = json.load(file)

                
                bboxes = [data['shapes'][i]['points'] for i in range(len(data['shapes']))]
                labels = [data['shapes'][i]['label'] for i in range(len(data['shapes']))]
                track_ids = [data['shapes'][i]['track_id'] for i in range(len(data['shapes']))]
                # need boxes in x,y,w,h
                bboxes_xyxy = [convert(bboxes[i]) for i in range(len(bboxes))]
                picked_item = np.intersect1d(np.argwhere(np.array(track_ids)==self.ID_INPO),
                                             np.argwhere(np.array(labels)==self.label_INPO))[0]
                ref_bxoxes.append(bboxes_xyxy[picked_item])

            xyxy_bboxes = np.array(ref_bxoxes).astype(int)
            xywh_bboxes = cvt_xyxy2xywh(xyxy_bboxes)

            interpolated_data = []
            for jdx in range(4):
                kernel = RationalQuadratic() 
                gpr = GaussianProcessRegressor(kernel=kernel,random_state=0).fit(img_indices.reshape(-1,1), xywh_bboxes[:,jdx])
                interpolated_data.append(gpr.predict(np.arange(self.start_INP0-1,self.end_INP0).reshape(-1,1), return_std=False))

            interpolated_data = np.stack(interpolated_data,axis=1)
            cvt_interpolated_data = cvt_xywh2xyxy(interpolated_data).astype(int)

            lf = LabelFile()
            # Edit frame Shape and save
            for jdx, json_path in enumerate(interpolatedList):
                if json_path in labelList:
                    continue
                if os.path.isfile(json_path):
                    loaded_label = LabelFile(json_path)
                    loaded_shape = loaded_label.shapes
                    newshape = {
                        'label':self.label_INPO,
                        'points':[[int(cvt_interpolated_data[jdx][0]),int(cvt_interpolated_data[jdx][1])],[int(cvt_interpolated_data[jdx][2]),int(cvt_interpolated_data[jdx][3])]],
                        'shape_type':'rectangle',
                        'flags':{},
                        'description':'',
                        'group_id': None, 
                        'track_id': self.ID_INPO, 
                        'mask': None
                    }
                    loaded_shape.append(newshape)
                    
                    imagePath = osp.splitext(json_path)[0] + ".jpg"
                    # import ipdb; ipdb.set_trace()          
                    lf.save(
                        filename=json_path,
                        shapes=loaded_shape,
                        imagePath=imagePath,
                        imageData=None,
                        imageHeight=self.image.height(),
                        imageWidth=self.image.width(),
                        otherData={},
                        flags={},
                    )
                else:
                    loaded_shape = []
                    newshape = {
                        'label':self.label_INPO,
                        'points':[[int(cvt_interpolated_data[jdx][0]),int(cvt_interpolated_data[jdx][1])],[int(cvt_interpolated_data[jdx][2]),int(cvt_interpolated_data[jdx][3])]],
                        'shape_type':'rectangle',
                        'flags':{},
                        'description':'',
                        'group_id': None, 
                        'track_id': self.ID_INPO, 
                        'mask': None
                    }
                    loaded_shape.append(newshape)
                    imagePath = osp.splitext(json_path)[0] + ".jpg"
                    lf.save(
                        filename=json_path,
                        shapes=loaded_shape,
                        imagePath=imagePath,
                        imageData=None,
                        imageHeight=self.image.height(),
                        imageWidth=self.image.width(),
                        otherData={},
                        flags={},
                    )
            
            filenames = self.scanAllImages(self.lastOpenDir)
            
            for filename in filenames:
                label_file = osp.splitext(filename)[0] + ".json"
                label_index = self.imageList.index(filename)
                item = self.fileListWidget.item(label_index)
                if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(label_file):
                    item.setCheckState(Qt.Checked)            

            # repaint the current frame
            self.mode = "NORMAL"
            self.INTERPOLATION_filename = self.INTERPOLATION_list[0]
            self.filename = self.INTERPOLATION_filename
            # load the start file
            getIndex = self.imageList.index(self.INTERPOLATION_filename) + 1
            self.navigation_list.statusBar.showMessage(f'Status: {getIndex}/{len(self.imageList)} | Mode: {self.mode}')
            self.loadFile(self.filename)

            self.informationMessage(
                                "Box Interpolation",
                                f"Track {self.label_INPO}-{self.ID_INPO} from frame {self.start_INP0} to {self.end_INP0} Interpolation is completed",
                            )
    
    def DELETION(self, item=None):
        dialog = DeletionDialog(
            parent=self,
        )
        dialog.exec_()

        if (dialog.start_frame_cell.text() == '' or 
            dialog.end_frame_cell.text() == '' or 
            dialog.ID_cell.text() == '' or 
            dialog.label_cell.text() == ''):
            return

        start_frame = int(dialog.start_frame_cell.text().replace(" ", ""))
        end_frame = int(dialog.end_frame_cell.text().replace(" ", ""))
        ID = dialog.ID_cell.text().replace(" ", "")
        label = dialog.label_cell.text().replace(" ", "")

        if end_frame - start_frame <=0:
            self.errorMessage(
                                "Track Deletion",
                                "Start frame is higher than End frame.",
                            )
            
            return
        
        labelList = [osp.splitext(img_p)[0] + ".json" for img_p in self.imageList]
        deletionList = labelList[start_frame-1:end_frame]

        lf = LabelFile()
        # Edit frame Shape and save
        for jdx, json_path in enumerate(deletionList):
            loaded_label = LabelFile(json_path)
            loaded_shape = loaded_label.shapes
            new_shape = []
            for kdx in range(len(loaded_shape)):
                if loaded_shape[kdx]['label'] == label and loaded_shape[kdx]['track_id'] ==ID:
                    continue
                else:
                    new_shape.append(loaded_shape[kdx])
            
            imagePath = osp.splitext(json_path)[0] + ".jpg"
                     
            lf.save(
                filename=json_path,
                shapes=new_shape,
                imagePath=imagePath,
                imageData=None,
                imageHeight=self.image.height(),
                imageWidth=self.image.width(),
                flags={},
            )
        
        
        self.filename = self.imageList[start_frame]
        # load the start file
        getIndex = self.imageList.index(self.filename) + 1
        self.navigation_list.statusBar.showMessage(f'Status: {getIndex}/{len(self.imageList)} | Mode: {self.mode}')
        self.loadFile(self.filename)

        self.informationMessage(
                                "Track Deletion",
                                f"Track {label}-{ID} from frame {start_frame} to {end_frame} is deleted",
                            )


    def editID(self, item=None):
        if item and not isinstance(item, IDListWidgetItem):
            raise TypeError("item must be IDListWidgetItem type")

        if not self.canvas.editing():
            return
        if not item:
            _,item = self.currentItem()
        if item is None:
            return
        shape = item.shape()
        if shape is None:
            return
        id = self.IDDialog.popUp(
            text=shape.track_id
        )
        if id is None:
            return
        if not self.validateLabel(id):
            self.errorMessage(
                self.tr("Invalid ID"),
                self.tr("Invalid ID '{}' with validation type '{}'").format(
                    id, self._config["validate_label"]
                ),
            )
            return
        shape.track_id = id

        item.setText(shape.track_id)
        self._update_shape_color(shape)
        self.setDirty()
        unique_name = shape.label + '_' + str(shape.track_id)
        if self.uniqLabelList.findItemByLabel(unique_name) is None:
            item = self.uniqLabelList.createItemFromLabel(unique_name)
            self.uniqLabelList.addItem(item)
            rgb = self._get_rgb_by_label(unique_name)
            self.uniqLabelList.setItemLabel(item, unique_name, rgb)

    def editLabel(self, item=None):
        if item and not isinstance(item, LabelListWidgetItem):
            raise TypeError("item must be LabelListWidgetItem type")
        if not self.canvas.editing():
            return
        if not item:
            item,_ = self.currentItem()
        if item is None:
            return
        shape = item.shape()
        if shape is None:
            return
        text, flags, group_id, description = self.labelDialog.popUp(
            text=shape.label,
            flags=shape.flags,
            group_id=shape.group_id,
            description=shape.description,
        )
        if text is None:
            return
        if not self.validateLabel(text):
            self.errorMessage(
                self.tr("Invalid label"),
                self.tr("Invalid label '{}' with validation type '{}'").format(
                    text, self._config["validate_label"]
                ),
            )
            return
        shape.label = text
        shape.flags = flags
        shape.group_id = group_id
        shape.description = description

        self._update_shape_color(shape)
        if shape.group_id is None:
            item.setText(
                '{} <font color="#{:02x}{:02x}{:02x}">●</font>'.format(
                    html.escape(shape.label), *shape.fill_color.getRgb()[:3]
                )
            )
        else:
            item.setText("{} ({})".format(shape.label, shape.group_id))
        self.setDirty()
        unique_name = shape.label + '_' + str(shape.track_id)
        if self.uniqLabelList.findItemByLabel(unique_name) is None:
            item = self.uniqLabelList.createItemFromLabel(unique_name)
            self.uniqLabelList.addItem(item)
            rgb = self._get_rgb_by_label(unique_name)
            self.uniqLabelList.setItemLabel(item, unique_name, rgb)

    def fileSearchChanged(self):
        self.importDirImages(
            self.lastOpenDir,
            pattern=self.fileSearch.text(),
            load=False,
        )

    def fileSelectionChanged(self):
        items = self.fileListWidget.selectedItems()
        if not items:
            return
        item = items[0]

        if not self.mayContinue():
            return
        
        if self.mode == "None":
            self.mode = "NORMAL"
        
        if self.mode == "TRACK INTERPOLATION":
            currIndex = self.imageList.index(str(item.text()))
            if currIndex < len(self.imageList):
                filename = self.imageList[currIndex]
            
            if filename in self.INTERPOLATION_list:
                getIndex = self.imageList.index(filename) + 1
                interpolationIndex = self.INTERPOLATION_list.index(self.filename) + 1
                self.navigation_list.statusBar.showMessage(f'Status: {getIndex}/{len(self.imageList)} | Mode: {self.mode} - ({interpolationIndex}/{len(self.INTERPOLATION_list)})')

                self.loadFile(filename)
            else:
                self.errorMessage(
                                "Box Interpolation",
                                "You cannot select out-of-list frame. Use Previous (A) and Next (D) buttons to move between the selected frames",
                            )
                return

        else:
            currIndex = self.imageList.index(str(item.text()))
            if currIndex < len(self.imageList):
                filename = self.imageList[currIndex]
                if filename:
                    self.loadFile(filename)

            getIndex = self.imageList.index(self.filename) + 1
            self.navigation_list.statusBar.showMessage(f'Status: {getIndex}/{len(self.imageList)} | Mode: {self.mode}')

    # React to canvas signals.
    def shapeSelectionChanged(self, selected_shapes):
        self._noSelectionSlot = True
        for shape in self.canvas.selectedShapes:
            shape.selected = False
        self.labelList.clearSelection()
        self.IDList.clearSelection()
        self.canvas.selectedShapes = selected_shapes
        for shape in self.canvas.selectedShapes:
            shape.selected = True
            item = self.labelList.findItemByShape(shape)
            self.labelList.selectItem(item)
            self.labelList.scrollToItem(item)
            id_item = self.IDList.findItemByShape(shape)
            self.IDList.selectItem(id_item)
            self.IDList.scrollToItem(id_item)
        self._noSelectionSlot = False
        n_selected = len(selected_shapes)
        self.actions.delete.setEnabled(n_selected)
        self.actions.duplicate.setEnabled(n_selected)
        self.actions.copy.setEnabled(n_selected)
        self.actions.edit.setEnabled(n_selected == 1)
        self.actions.edit_id.setEnabled(n_selected == 1)

    def addLabel(self, shape):
        if shape.group_id is None:
            text = shape.label
        else:
            text = "{} ({})".format(shape.label, shape.group_id)
        label_list_item = LabelListWidgetItem(text, shape)
        self.labelList.addItem(label_list_item)
        id_list_item = IDListWidgetItem(str(shape.track_id),shape)
        self.IDList.addItem(id_list_item)
        unique_name = shape.label + '_' + str(shape.track_id)
        if self.uniqLabelList.findItemByLabel(unique_name) is None:
            item = self.uniqLabelList.createItemFromLabel(unique_name)
            self.uniqLabelList.addItem(item)
            rgb = self._get_rgb_by_label(unique_name)
            self.uniqLabelList.setItemLabel(item, unique_name, rgb)
        self.labelDialog.addLabelHistory(shape.label)
        self.IDDialog.addIDHistory(str(shape.track_id))
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)
        self._update_shape_color(shape)
        label_list_item.setText(
            '{} <font color="#{:02x}{:02x}{:02x}">●</font>'.format(
                html.escape(text), *shape.fill_color.getRgb()[:3]
            )
        )

    def _update_shape_color(self, shape):
        unique_name = shape.label + '_' + str(shape.track_id)
        r, g, b = self._get_rgb_by_label(unique_name)
        shape.line_color = QtGui.QColor(r, g, b)
        shape.vertex_fill_color = QtGui.QColor(r, g, b)
        shape.hvertex_fill_color = QtGui.QColor(255, 255, 255)
        shape.fill_color = QtGui.QColor(r, g, b, 128)
        shape.select_line_color = QtGui.QColor(255, 255, 255)
        shape.select_fill_color = QtGui.QColor(r, g, b, 155)

    def _get_rgb_by_label(self, label):
        if self._config["shape_color"] == "auto":
            item = self.uniqLabelList.findItemByLabel(label)
            if item is None:
                item = self.uniqLabelList.createItemFromLabel(label)
                self.uniqLabelList.addItem(item)
                rgb = self._get_rgb_by_label(label)
                self.uniqLabelList.setItemLabel(item, label, rgb)
            label_id = self.uniqLabelList.indexFromItem(item).row() + 1
            label_id += self._config["shift_auto_shape_color"]
            return LABEL_COLORMAP[label_id % len(LABEL_COLORMAP)]
        elif (
            self._config["shape_color"] == "manual"
            and self._config["label_colors"]
            # and label in self._config["label_colors"]
        ):
            # return self._config["label_colors"][label]
            if label.split('_')[-1] == 'None':
                return [224, 224,   0]
            else:
                return self._config["label_colors"][int(label.split('_')[-1])][int(label.split('_')[-1])]
        elif self._config["default_shape_color"]:
            return self._config["default_shape_color"]
        return (0, 255, 0)

    def remLabels(self, shapes):
        for shape in shapes:
            item = self.labelList.findItemByShape(shape)
            self.labelList.removeItem(item)

    def loadShapes(self, shapes, replace=True):
        self._noSelectionSlot = True
        for shape in shapes:
            self.addLabel(shape)
        self.labelList.clearSelection()
        self.IDList.clearSelection()
        self._noSelectionSlot = False
        self.canvas.loadShapes(shapes, replace=replace)

    def loadLabels(self, shapes):
        s = []
        for shape in shapes:
            label = shape["label"]
            points = shape["points"]
            shape_type = shape["shape_type"]
            flags = shape["flags"]
            description = shape.get("description", "")
            group_id = shape["group_id"]
            track_id = shape["track_id"]

            if not points:
                # skip point-empty shape
                continue
            
            if self.ir_activated == True and label == self.ir_name and track_id == self.ir_id:
                deltas = [
                    [self.ir_mod_shape[0][0] - self.ir_old_shape[0][0], self.ir_mod_shape[0][1] - self.ir_old_shape[0][1]],
                    [self.ir_mod_shape[1][0] - self.ir_old_shape[1][0], self.ir_mod_shape[1][1] - self.ir_old_shape[1][1]],
                ]
                
                points = [
                    [shape['points'][0][0] + deltas[0][0] ,shape['points'][0][1] + deltas[0][1]], 
                    [shape['points'][1][0] + deltas[1][0] ,shape['points'][1][1] + deltas[1][1]]
                ] 
                # self.ir_mod_shape
                # self.ir_old_shape
                # load_shape 
                # import ipdb ;ipdb.set_trace()

            shape = Shape(
                label=label,
                shape_type=shape_type,
                group_id=group_id,
                track_id=track_id,
                description=description,
                mask=shape["mask"],
            )
            for x, y in points:
                shape.addPoint(QtCore.QPointF(x, y))
            shape.close()

            default_flags = {}
            if self._config["label_flags"]:
                for pattern, keys in self._config["label_flags"].items():
                    if re.match(pattern, label):
                        for key in keys:
                            default_flags[key] = False
            shape.flags = default_flags
            shape.flags.update(flags)

            s.append(shape)
        self.loadShapes(s)

    def loadFlags(self, flags):
        self.flag_widget.clear()
        for key, flag in flags.items():
            item = QtWidgets.QListWidgetItem(key)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if flag else Qt.Unchecked)
            self.flag_widget.addItem(item)

    def saveLabels(self, filename):
        lf = LabelFile()

        def format_shape(s):
            data = s.other_data.copy()
            data.update(
                dict(
                    label=s.label.encode("utf-8") if PY2 else s.label,
                    points=[(p.x(), p.y()) for p in s.points],
                    group_id=s.group_id,
                    track_id=s.track_id,
                    description=s.description,
                    shape_type=s.shape_type,
                    flags=s.flags,
                    mask=None if s.mask is None else utils.img_arr_to_b64(s.mask),
                )
            )
            return data
        
        shapes = [format_shape(item.shape()) for item in self.labelList]
        flags = {}
        for i in range(self.flag_widget.count()):
            item = self.flag_widget.item(i)
            key = item.text()
            flag = item.checkState() == Qt.Checked
            flags[key] = flag
        try:
            imagePath = osp.relpath(self.imagePath, osp.dirname(filename))
            # imageData = self.imageData if self._config["store_data"] else None
            imageData = None
            if osp.dirname(filename) and not osp.exists(osp.dirname(filename)):
                os.makedirs(osp.dirname(filename))
            lf.save(
                filename=filename,
                shapes=shapes,
                imagePath=imagePath,
                imageData=imageData,
                imageHeight=self.image.height(),
                imageWidth=self.image.width(),
                flags=flags,
            )
            self.labelFile = lf
            items = self.fileListWidget.findItems(self.imagePath, Qt.MatchExactly)
            if len(items) > 0:
                if len(items) != 1:
                    raise RuntimeError("There are duplicate files.")
                items[0].setCheckState(Qt.Checked)
            # disable allows next and previous image to proceed
            # self.filename = filename
            return True
        except LabelFileError as e:
            self.errorMessage(
                self.tr("Error saving label data"), self.tr("<b>%s</b>") % e
            )
            return False

    def duplicateSelectedShape(self):
        added_shapes = self.canvas.duplicateSelectedShapes()
        for shape in added_shapes:
            self.addLabel(shape)
        self.setDirty()

    def pasteSelectedShape(self):
        self.loadShapes(self._copied_shapes, replace=False)
        self.setDirty()

    def copySelectedShape(self):
        self._copied_shapes = [s.copy() for s in self.canvas.selectedShapes]
        self.actions.paste.setEnabled(len(self._copied_shapes) > 0)

    def labelSelectionChanged(self):
        if self._noSelectionSlot:
            return
        if self.canvas.editing():
            selected_shapes = []
            for item in self.labelList.selectedItems():
                selected_shapes.append(item.shape())
            if selected_shapes:
                self.canvas.selectShapes(selected_shapes)
            else:
                self.canvas.deSelectShape()

    def IDSelectionChanged(self):
        if self._noSelectionSlot:
            return
        if self.canvas.editing():
            selected_shapes = []
            for item in self.IDList.selectedItems():
                selected_shapes.append(item.shape())
            if selected_shapes:
                self.canvas.selectShapes(selected_shapes)
            else:
                self.canvas.deSelectShape()

    def labelItemChanged(self, item):
        shape = item.shape()
        self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)
    
    def IDItemChanged(self, item):
        shape = item.shape()
        self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)

    def labelOrderChanged(self):
        self.setDirty()
        self.canvas.loadShapes([item.shape() for item in self.labelList])
    
    def IDOrderChanged(self):
        self.setDirty()
        self.canvas.loadShapes([item.shape() for item in self.IDList])

    # Callback functions:

    def newShape(self):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        items = self.uniqLabelList.selectedItems()
        text_label = None
        text_id = None
        if items:
            text_label = items[0].data(Qt.UserRole)
        flags = {}
        group_id = None
        description = ""
        if self._config["display_label_popup"] or not text_label:
            previous_text_label = self.labelDialog.edit.text()
            previous_text_id = self.IDDialog.edit.text()
            if self.mode == "NORMAL":
                text_label, flags, group_id, description = self.labelDialog.popUp(text_label)
                text_id = self.IDDialog.popUp(text_id)
            else:
                text_label = self.label_INPO
                flags = {}
                group_id = None 
                description = ''
                text_id = self.ID_INPO
            if not text_label:
                self.labelDialog.edit.setText(previous_text_label)
            if not text_id:
                self.IDDialog.edit.setText(previous_text_id)

        if text_label and not self.validateLabel(text_label):
            self.errorMessage(
                self.tr("Invalid label"),
                self.tr("Invalid label '{}' with validation type '{}'").format(
                    text_label, self._config["validate_label"]
                ),
            )
            text_label = ""
        if text_label:
            self.labelList.clearSelection()
            self.IDList.clearSelection()
            shape = self.canvas.setLastLabel(text_label, flags)
            shape.group_id = group_id
            shape.track_id = text_id
            shape.description = description
            self.addLabel(shape)
            self.actions.editMode.setEnabled(True)
            self.actions.undoLastPoint.setEnabled(False)
            self.actions.undo.setEnabled(True)
            self.setDirty()
        else:
            self.canvas.undoLastLine()
            self.canvas.shapesBackups.pop()

    def scrollRequest(self, delta, orientation):
        units = -delta * 0.1  # natural scroll
        bar = self.scrollBars[orientation]
        value = bar.value() + bar.singleStep() * units
        self.setScroll(orientation, value)

    def setScroll(self, orientation, value):
        self.scrollBars[orientation].setValue(int(value))
        self.scroll_values[orientation][self.filename] = value

    def setZoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(value)
        self.zoom_values[self.filename] = (self.zoomMode, value)

    def addZoom(self, increment=1.1):
        zoom_value = self.zoomWidget.value() * increment
        if increment > 1:
            zoom_value = math.ceil(zoom_value)
        else:
            zoom_value = math.floor(zoom_value)
        self.setZoom(zoom_value)

    def zoomRequest(self, delta, pos):
        canvas_width_old = self.canvas.width()
        units = 1.1
        if delta < 0:
            units = 0.9
        self.addZoom(units)

        canvas_width_new = self.canvas.width()
        if canvas_width_old != canvas_width_new:
            canvas_scale_factor = canvas_width_new / canvas_width_old

            x_shift = round(pos.x() * canvas_scale_factor) - pos.x()
            y_shift = round(pos.y() * canvas_scale_factor) - pos.y()

            self.setScroll(
                Qt.Horizontal,
                self.scrollBars[Qt.Horizontal].value() + x_shift,
            )
            self.setScroll(
                Qt.Vertical,
                self.scrollBars[Qt.Vertical].value() + y_shift,
            )

    def setFitWindow(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def enableKeepPrevScale(self, enabled):
        self._config["keep_prev_scale"] = enabled
        self.actions.keepPrevScale.setChecked(enabled)

    def onNewBrightnessContrast(self, qimage):
        self.canvas.loadPixmap(QtGui.QPixmap.fromImage(qimage), clear_shapes=False)

    def brightnessContrast(self, value):
        dialog = BrightnessContrastDialog(
            utils.img_data_to_pil(self.imageData),
            self.onNewBrightnessContrast,
            parent=self,
        )
        brightness, contrast = self.brightnessContrast_values.get(
            self.filename, (None, None)
        )
        if brightness is not None:
            dialog.slider_brightness.setValue(brightness)
        if contrast is not None:
            dialog.slider_contrast.setValue(contrast)
        dialog.exec_()

        brightness = dialog.slider_brightness.value()
        contrast = dialog.slider_contrast.value()
        self.brightnessContrast_values[self.filename] = (brightness, contrast)

    def togglePolygons(self, value):
        flag = value
        for item in self.labelList:
            if value is None:
                flag = item.checkState() == Qt.Unchecked
            item.setCheckState(Qt.Checked if flag else Qt.Unchecked)

    def loadFile(self, filename=None):
        """Load the specified file, or the last opened file if None."""
        # changing fileListWidget loads file
        if filename in self.imageList and (
            self.fileListWidget.currentRow() != self.imageList.index(filename)
        ):
            self.fileListWidget.setCurrentRow(self.imageList.index(filename))
            self.fileListWidget.repaint()
            return
        
        self.resetState()
        self.canvas.setEnabled(False)
        if filename is None:                                        # image file name .jpg
            filename = self.settings.value("filename", "")
        filename = str(filename)
        if not QtCore.QFile.exists(filename):
            self.errorMessage(
                self.tr("Error opening file"),
                self.tr("No such file: <b>%s</b>") % filename,
            )
            return False
        # assumes same name, but json extension
        self.status(str(self.tr("Loading %s...")) % osp.basename(str(filename)))
        
        label_file = osp.splitext(filename)[0] + ".json"
        
        if os.path.isfile(label_file):
            self.ir_old_shapes = []
            for item in LabelFile(label_file).shapes:
                self.ir_old_shapes.append(item)
        
        if self.output_dir:
            label_file_without_path = osp.basename(label_file)
            label_file = osp.join(self.output_dir, label_file_without_path)
        if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(label_file):     # check if label_file exists and has correct type
            try:
                self.labelFile = LabelFile(label_file)      # FIX LabelFile HERE
            except LabelFileError as e:
                self.errorMessage(
                    self.tr("Error opening file"),
                    self.tr(
                        "<p><b>%s</b></p>"
                        "<p>Make sure <i>%s</i> is a valid label file."
                    )
                    % (e, label_file),
                )
                self.status(self.tr("Error reading %s") % label_file)
                return False
            self.imageData = self.labelFile.imageData
            self.imagePath = osp.join(
                osp.dirname(label_file),
                self.labelFile.imagePath,
            )
            self.otherData = self.labelFile.otherData       # dont care
        else:
            self.imageData = LabelFile.load_image_file(filename)
            if self.imageData:
                self.imagePath = filename
            self.labelFile = None
        image = QtGui.QImage.fromData(self.imageData)   # load encoded image data

        if image.isNull():
            formats = [
                "*.{}".format(fmt.data().decode())
                for fmt in QtGui.QImageReader.supportedImageFormats()
            ]
            self.errorMessage(
                self.tr("Error opening file"),
                self.tr(
                    "<p>Make sure <i>{0}</i> is a valid image file.<br/>"
                    "Supported image formats: {1}</p>"
                ).format(filename, ",".join(formats)),
            )
            self.status(self.tr("Error reading %s") % filename)
            return False
        self.image = image                                  # image data
        self.filename = filename
        
        if self._config["keep_prev"]:
            prev_shapes = self.canvas.shapes
        self.canvas.loadPixmap(QtGui.QPixmap.fromImage(image))
        flags = {k: False for k in self._config["flags"] or []}
        if self.labelFile:                                  # if labelFile exists
            self.loadLabels(self.labelFile.shapes)                  # FIX loadLabels HERE
            if self.labelFile.flags is not None:
                flags.update(self.labelFile.flags)
        self.loadFlags(flags)
        if self._config["keep_prev"] and self.noShapes():       # check noShapes() /// Shapes are annotations
            self.loadShapes(prev_shapes, replace=False)         # load annotation from prev image
            self.setDirty()
        else:
            self.setClean()
        self.canvas.setEnabled(True)
        # set zoom values
        is_initial_load = not self.zoom_values
        if self.filename in self.zoom_values:
            self.zoomMode = self.zoom_values[self.filename][0]
            self.setZoom(self.zoom_values[self.filename][1])
        elif is_initial_load or not self._config["keep_prev_scale"]:
            self.adjustScale(initial=True)
        # set scroll values
        for orientation in self.scroll_values:
            if self.filename in self.scroll_values[orientation]:
                self.setScroll(
                    orientation, self.scroll_values[orientation][self.filename]
                )
        # set brightness contrast values
        dialog = BrightnessContrastDialog(
            utils.img_data_to_pil(self.imageData),
            self.onNewBrightnessContrast,
            parent=self,
        )
        brightness, contrast = self.brightnessContrast_values.get(
            self.filename, (None, None)
        )
        if self._config["keep_prev_brightness"] and self.recentFiles:
            brightness, _ = self.brightnessContrast_values.get(
                self.recentFiles[0], (None, None)
            )
        if self._config["keep_prev_contrast"] and self.recentFiles:
            _, contrast = self.brightnessContrast_values.get(
                self.recentFiles[0], (None, None)
            )
        if brightness is not None:
            dialog.slider_brightness.setValue(brightness)
        if contrast is not None:
            dialog.slider_contrast.setValue(contrast)
        self.brightnessContrast_values[self.filename] = (brightness, contrast)
        if brightness is not None or contrast is not None:
            dialog.onNewValue(None)
        self.paintCanvas()
        self.addRecentFile(self.filename)
        self.toggleActions(True)
        self.canvas.setFocus()
        self.status(str(self.tr("Loaded %s")) % osp.basename(str(filename)))
        return True

    def resizeEvent(self, event):
        if (
            self.canvas
            and not self.image.isNull()
            and self.zoomMode != self.MANUAL_ZOOM
        ):
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        value = int(100 * value)
        self.zoomWidget.setValue(value)
        self.zoom_values[self.filename] = (self.zoomMode, value)

    def scaleFitWindow(self):
        """Figure out the size of the pixmap to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def enableSaveImageWithData(self, enabled):
        self._config["store_data"] = enabled
        self.actions.saveWithImageData.setChecked(enabled)

    def closeEvent(self, event):
        if not self.mayContinue():
            event.ignore()
        self.settings.setValue("filename", self.filename if self.filename else "")
        self.settings.setValue("window/size", self.size())
        self.settings.setValue("window/position", self.pos())
        self.settings.setValue("window/state", self.saveState())
        self.settings.setValue("recentFiles", self.recentFiles)
        # ask the use for where to save the labels
        # self.settings.setValue('window/geometry', self.saveGeometry())

    def dragEnterEvent(self, event):
        extensions = [
            ".%s" % fmt.data().decode().lower()
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]
        if event.mimeData().hasUrls():
            items = [i.toLocalFile() for i in event.mimeData().urls()]
            if any([i.lower().endswith(tuple(extensions)) for i in items]):
                event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not self.mayContinue():
            event.ignore()
            return
        items = [i.toLocalFile() for i in event.mimeData().urls()]
        self.importDroppedImageFiles(items)

    # User Dialogs #

    def loadRecent(self, filename):
        if self.mayContinue():
            self.loadFile(filename)

    def openPrevImg(self, _value=False):
        keep_prev = self._config["keep_prev"]
        if QtWidgets.QApplication.keyboardModifiers() == (
            Qt.ControlModifier | Qt.ShiftModifier
        ):
            self._config["keep_prev"] = True

        if not self.mayContinue():
            return

        if len(self.imageList) <= 0:
            return

        if self.mode == "NORMAL" or self.mode == "None":
            self.ir_activated = False
            if self.filename is None:
                return

            currIndex = self.imageList.index(self.filename)
            if currIndex - 1 >= 0:
                filename = self.imageList[currIndex - 1]
                if filename:
                    self.loadFile(filename)

            self._config["keep_prev"] = keep_prev
        else:            
            currIndex = self.INTERPOLATION_list.index(self.filename)
            if currIndex - 1 >= 0:
                filename = self.INTERPOLATION_list[currIndex - 1]
                if filename:
                    self.loadFile(filename)

            self._config["keep_prev"] = keep_prev

    def openNextImg(self, _value=False, load=True):
        keep_prev = self._config["keep_prev"]
        if QtWidgets.QApplication.keyboardModifiers() == (
            Qt.ControlModifier | Qt.ShiftModifier
        ):
            self._config["keep_prev"] = True

        if not self.mayContinue():
            return

        if len(self.imageList) <= 0:
            return

        if self.mode == "NORMAL" or self.mode == "None":
            if self.interpolationrefine_list.checkBox.isChecked() and self.ir_name != "None" and self.ir_id != "None":
                found = False
                # original 
                for item in self.ir_old_shapes:
                    if item['label'] == self.ir_name and item['track_id'] == self.ir_id:
                        self.ir_old_shape = item['points']
                # modified
                for item in self.labelList:
                    if item.shape().label == self.ir_name and item.shape().track_id == self.ir_id:
                        found = True
                        self.ir_mod_shape = [[p.x(), p.y()] for p in item.shape().points]
                if found == False:
                    self.ir_old_shape = "None"
                    self.ir_mod_shape = "None"
                self.ir_activated = True

            filename = None
            if self.filename is None:
                filename = self.imageList[0]
            else:
                currIndex = self.imageList.index(self.filename)
                if currIndex + 1 < len(self.imageList):
                    filename = self.imageList[currIndex + 1]
                else:
                    filename = self.imageList[-1]
            self.filename = filename

            if self.filename and load:
                self.loadFile(self.filename)

            self._config["keep_prev"] = keep_prev
        else:
            currIndex = self.INTERPOLATION_list.index(self.filename)
            if currIndex + 1 < len(self.INTERPOLATION_list):
                filename = self.INTERPOLATION_list[currIndex + 1]
            else:
                filename = self.INTERPOLATION_list[-1]
            self.filename = filename

            if self.filename and load:
                self.loadFile(self.filename)

            self._config["keep_prev"] = keep_prev

    def openFile(self, _value=False):
        if not self.mayContinue():
            return
        path = osp.dirname(str(self.filename)) if self.filename else "."
        formats = [
            "*.{}".format(fmt.data().decode())
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]
        filters = self.tr("Image & Label files (%s)") % " ".join(
            formats + ["*%s" % LabelFile.suffix]
        )
        fileDialog = FileDialogPreview(self)
        fileDialog.setFileMode(FileDialogPreview.ExistingFile)
        fileDialog.setNameFilter(filters)
        fileDialog.setWindowTitle(
            self.tr("%s - Choose Image or Label file") % __appname__,
        )
        fileDialog.setWindowFilePath(path)
        fileDialog.setViewMode(FileDialogPreview.Detail)
        if fileDialog.exec_():
            fileName = fileDialog.selectedFiles()[0]
            if fileName:
                self.loadFile(fileName)

    def changeOutputDirDialog(self, _value=False):
        default_output_dir = self.output_dir
        if default_output_dir is None and self.filename:
            default_output_dir = osp.dirname(self.filename)
        if default_output_dir is None:
            default_output_dir = self.currentPath()

        output_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("%s - Save/Load Annotations in Directory") % __appname__,
            default_output_dir,
            QtWidgets.QFileDialog.ShowDirsOnly
            | QtWidgets.QFileDialog.DontResolveSymlinks,
        )
        output_dir = str(output_dir)

        if not output_dir:
            return

        self.output_dir = output_dir

        self.statusBar().showMessage(
            self.tr("%s . Annotations will be saved/loaded in %s")
            % ("Change Annotations Dir", self.output_dir)
        )
        self.statusBar().show()

        current_filename = self.filename
        self.importDirImages(self.lastOpenDir, load=False)

        if current_filename in self.imageList:
            # retain currently selected file
            self.fileListWidget.setCurrentRow(self.imageList.index(current_filename))
            self.fileListWidget.repaint()

    def saveFile(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        if self.labelFile:
            # DL20180323 - overwrite when in directory
            self._saveFile(self.labelFile.filename)
        elif self.output_file:
            self._saveFile(self.output_file)
            self.close()
        else:
            self._saveFile(self.saveFileDialog())

    def saveFileAs(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        self._saveFile(self.saveFileDialog())

    def saveFileDialog(self):
        caption = self.tr("%s - Choose File") % __appname__
        filters = self.tr("Label files (*%s)") % LabelFile.suffix
        if self.output_dir:
            dlg = QtWidgets.QFileDialog(self, caption, self.output_dir, filters)
        else:
            dlg = QtWidgets.QFileDialog(self, caption, self.currentPath(), filters)
        dlg.setDefaultSuffix(LabelFile.suffix[1:])
        dlg.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        dlg.setOption(QtWidgets.QFileDialog.DontConfirmOverwrite, False)
        dlg.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, False)
        basename = osp.basename(osp.splitext(self.filename)[0])
        if self.output_dir:
            default_labelfile_name = osp.join(
                self.output_dir, basename + LabelFile.suffix
            )
        else:
            default_labelfile_name = osp.join(
                self.currentPath(), basename + LabelFile.suffix
            )
        filename = dlg.getSaveFileName(
            self,
            self.tr("Choose File"),
            default_labelfile_name,
            self.tr("Label files (*%s)") % LabelFile.suffix,
        )
        if isinstance(filename, tuple):
            filename, _ = filename
        return filename

    def _saveFile(self, filename):
        if filename and self.saveLabels(filename):
            self.addRecentFile(filename)
            self.setClean()

    def closeFile(self, _value=False):
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    def getLabelFile(self):
        if self.filename.lower().endswith(".json"):
            label_file = self.filename
        else:
            label_file = osp.splitext(self.filename)[0] + ".json"

        return label_file

    def deleteFile(self):
        mb = QtWidgets.QMessageBox
        msg = self.tr(
            "You are about to permanently delete this label file, " "proceed anyway?"
        )
        answer = mb.warning(self, self.tr("Attention"), msg, mb.Yes | mb.No)
        if answer != mb.Yes:
            return

        label_file = self.getLabelFile()
        if osp.exists(label_file):
            os.remove(label_file)
            logger.info("Label file is removed: {}".format(label_file))

            item = self.fileListWidget.currentItem()
            item.setCheckState(Qt.Unchecked)

            self.resetState()

    # Message Dialogs. #
    def hasLabels(self):
        if self.noShapes():
            self.errorMessage(
                "No objects labeled",
                "You must label at least one object to save the file.",
            )
            return False
        return True

    def hasLabelFile(self):
        if self.filename is None:
            return False

        label_file = self.getLabelFile()
        return osp.exists(label_file)

    def mayContinue(self):
        if not self.dirty:
            return True
        mb = QtWidgets.QMessageBox
        msg = self.tr('Save annotations to "{}" before closing?').format(self.filename)
        answer = mb.question(
            self,
            self.tr("Save annotations?"),
            msg,
            mb.Save | mb.Discard | mb.Cancel,
            mb.Save,
        )
        if answer == mb.Discard:
            return True
        elif answer == mb.Save:
            self.saveFile()
            return True
        else:  # answer == mb.Cancel
            return False

    def errorMessage(self, title, message):
        return QtWidgets.QMessageBox.critical(
            self, title, "<p><b>%s</b></p>%s" % (title, message)
        )

    def informationMessage(self, title, message):
        return QtWidgets.QMessageBox.information(
            self, title, "<p><b>%s</b></p>%s" % (title, message)
        )

    def currentPath(self):
        return osp.dirname(str(self.filename)) if self.filename else "."

    def toggleKeepPrevMode(self):
        self._config["keep_prev"] = not self._config["keep_prev"]

    def removeSelectedPoint(self):
        self.canvas.removeSelectedPoint()
        self.canvas.update()
        if not self.canvas.hShape.points:
            self.canvas.deleteShape(self.canvas.hShape)
            self.remLabels([self.canvas.hShape])
            if self.noShapes():
                for action in self.actions.onShapesPresent:
                    action.setEnabled(False)
        self.setDirty()

    def deleteSelectedShape(self):
        # yes, no = QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No
        # msg = self.tr(
        #     "You are about to permanently delete {} polygons, " "proceed anyway?"
        # ).format(len(self.canvas.selectedShapes))
        # if yes == QtWidgets.QMessageBox.warning(
        #     self, self.tr("Attention"), msg, yes | no, yes
        # ):
        #     self.remLabels(self.canvas.deleteSelected())
        #     self.setDirty()
        #     if self.noShapes():
        #         for action in self.actions.onShapesPresent:
        #             action.setEnabled(False)
                    
        self.remLabels(self.canvas.deleteSelected())
        self.setDirty()
        if self.noShapes():
            for action in self.actions.onShapesPresent:
                action.setEnabled(False)

    def copyShape(self):
        self.canvas.endMove(copy=True)
        for shape in self.canvas.selectedShapes:
            self.addLabel(shape)
        self.labelList.clearSelection()
        self.IDList.clearSelection()
        self.setDirty()

    def moveShape(self):
        self.canvas.endMove(copy=False)
        self.setDirty()

    def openDirDialog(self, _value=False, dirpath=None):
        if not self.mayContinue():
            return

        defaultOpenDirPath = dirpath if dirpath else "."
        if self.lastOpenDir and osp.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        else:
            defaultOpenDirPath = osp.dirname(self.filename) if self.filename else "."

        targetDirPath = str(
            QtWidgets.QFileDialog.getExistingDirectory(
                self,
                self.tr("%s - Open Directory") % __appname__,
                defaultOpenDirPath,
                QtWidgets.QFileDialog.ShowDirsOnly
                | QtWidgets.QFileDialog.DontResolveSymlinks,
            )
        )
        self.importDirImages(targetDirPath)

    @property
    def imageList(self):
        lst = []
        for i in range(self.fileListWidget.count()):
            item = self.fileListWidget.item(i)
            lst.append(item.text())
        return lst

    def importDroppedImageFiles(self, imageFiles):
        extensions = [
            ".%s" % fmt.data().decode().lower()
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]

        self.filename = None
        for file in imageFiles:
            if file in self.imageList or not file.lower().endswith(tuple(extensions)):
                continue
            label_file = osp.splitext(file)[0] + ".json"
            if self.output_dir:
                label_file_without_path = osp.basename(label_file)
                label_file = osp.join(self.output_dir, label_file_without_path)
            item = QtWidgets.QListWidgetItem(file)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(label_file):
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.fileListWidget.addItem(item)

        if len(self.imageList) > 1:
            self.actions.openNextImg.setEnabled(True)
            self.actions.openPrevImg.setEnabled(True)

        self.openNextImg()

    def importDirImages(self, dirpath, pattern=None, load=True):
        self.actions.openNextImg.setEnabled(True)
        self.actions.openPrevImg.setEnabled(True)

        if not self.mayContinue() or not dirpath:
            return

        self.lastOpenDir = dirpath
        self.filename = None
        self.fileListWidget.clear()

        filenames = self.scanAllImages(dirpath)
        if pattern:
            try:
                filenames = [f for f in filenames if re.search(pattern, f)]
            except re.error:
                pass
        for filename in filenames:
            label_file = osp.splitext(filename)[0] + ".json"
            if self.output_dir:
                label_file_without_path = osp.basename(label_file)
                label_file = osp.join(self.output_dir, label_file_without_path)
            item = QtWidgets.QListWidgetItem(filename)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if QtCore.QFile.exists(label_file) and LabelFile.is_label_file(label_file):
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.fileListWidget.addItem(item)
        self.openNextImg(load=load)

    def scanAllImages(self, folderPath):
        extensions = [
            ".%s" % fmt.data().decode().lower()
            for fmt in QtGui.QImageReader.supportedImageFormats()
        ]

        images = []
        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relativePath = os.path.normpath(osp.join(root, file))
                    images.append(relativePath)
        images = natsort.os_sorted(images)
        return images