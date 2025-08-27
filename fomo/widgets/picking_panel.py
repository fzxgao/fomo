from PyQt5 import QtCore, QtWidgets

def _disable_scroll(widget):
    """Prevent mouse wheel events from altering widget value."""
    widget.wheelEvent = lambda event: event.ignore()

class ModelListWidget(QtWidgets.QListWidget):
    """List widget that allows deleting models with Del key and activating on double click."""
    modelActivated = QtCore.pyqtSignal(str)
    modelDeleted = QtCore.pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.itemDoubleClicked.connect(self._emit_activation)

    def _emit_activation(self, item):
        self.modelActivated.emit(item.text())

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Delete:
            items = list(self.selectedItems())
            for item in items:
                name = item.text()
                row = self.row(item)
                self.takeItem(row)
                self.modelDeleted.emit(name)
            event.accept()
        else:
            super().keyPressEvent(event)


class PickingSidePanel(QtWidgets.QSplitter):
    """Side panel shown in picking mode with models list and filament parameters."""

    def __init__(self, *args, **kwargs):
        super().__init__(QtCore.Qt.Vertical, *args, **kwargs)
        self._build_models_panel()
        self._build_params_panel()
        self._build_live_refinement_section()

    # -------- Models panel --------
    def _build_models_panel(self):
        models_widget = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(models_widget)
        v.addWidget(QtWidgets.QLabel("Models"))
        self.model_list = ModelListWidget()
        v.addWidget(self.model_list, 1)
        self.addWidget(models_widget)

    # -------- Filament parameters panel --------
    def _build_params_panel(self):
        params_widget = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(params_widget)
        v.addWidget(QtWidgets.QLabel("Filament parameters"))
        form = QtWidgets.QFormLayout()
        self.smooth_radius = QtWidgets.QDoubleSpinBox()
        self.smooth_radius.setValue(5)
        _disable_scroll(self.smooth_radius)
        form.addRow("Smoothing radius (in pixels)", self.smooth_radius)
        self.smooth_interval = QtWidgets.QDoubleSpinBox()
        self.smooth_interval.setValue(2)
        _disable_scroll(self.smooth_interval)
        form.addRow("Interval in backbone for smoothing (in pixels)", self.smooth_interval)
        self.subunits_dz = QtWidgets.QDoubleSpinBox()
        self.subunits_dz.setValue(5)
        _disable_scroll(self.subunits_dz)
        form.addRow("Subunits dz (in pixels, 1/3 to 1/2 of the Helical pitch, if known)", self.subunits_dz)
        self.subunits_dphi = QtWidgets.QDoubleSpinBox()
        self.subunits_dphi.setValue(20)
        _disable_scroll(self.subunits_dphi)
        form.addRow("Subunits dphi (in degrees, 1/3 to 1/2 of the Helical twist, if known)", self.subunits_dphi)
        self.box_size = QtWidgets.QDoubleSpinBox()
        self.box_size.setValue(52)
        _disable_scroll(self.box_size)
        form.addRow("Box size (in pixels)", self.box_size)
        v.addLayout(form)
        self.addWidget(params_widget)

    # -------- Live refinement --------
    def _build_live_refinement_section(self):
        widget = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(widget)
        v.addWidget(QtWidgets.QLabel("Live refinement"))
        hl = QtWidgets.QHBoxLayout()
        self.refined_views = []
        self.refined_sliders = []
        for axis in ("X", "Y", "Z"):
            vb = QtWidgets.QVBoxLayout()
            label = QtWidgets.QLabel(f"{axis}")
            label.setFrameShape(QtWidgets.QFrame.Box)
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setFixedSize(60, 60)
            self.refined_views.append(label)
            vb.addWidget(label)
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self.refined_sliders.append(slider)
            vb.addWidget(slider)
            hl.addLayout(vb)
        v.addLayout(hl)
        btns = QtWidgets.QVBoxLayout()
        import_row = QtWidgets.QHBoxLayout()
        self.import_left = QtWidgets.QToolButton()
        self.import_left.setArrowType(QtCore.Qt.LeftArrow)
        import_row.addWidget(self.import_left)
        self.import_btn = QtWidgets.QPushButton("Import refined coordinates")
        import_row.addWidget(self.import_btn)
        self.import_right = QtWidgets.QToolButton()
        self.import_right.setArrowType(QtCore.Qt.RightArrow)
        import_row.addWidget(self.import_right)
        btns.addLayout(import_row)
        self.export_relion_btn = QtWidgets.QPushButton("Export to RELION")
        btns.addWidget(self.export_relion_btn)
        v.addLayout(btns)
        self.addWidget(widget)

    def wheelEvent(self, event):
        """
        Ignore wheel events so scrolling the tomogram doesn't
        unintentionally resize the panel splitter.
        """
        event.ignore()