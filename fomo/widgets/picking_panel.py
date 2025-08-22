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
        self.subunits_dz.setValue(7)
        _disable_scroll(self.subunits_dz)
        form.addRow("Subunits dz (in pixels, 1/3 to 1/2 of the Helical pitch, if known)", self.subunits_dz)
        self.subunits_dphi = QtWidgets.QDoubleSpinBox()
        self.subunits_dphi.setValue(20)
        _disable_scroll(self.subunits_dphi)
        form.addRow("Subunits dphi (in degrees, 1/3 to 1/2 of the Helical twist, if known)", self.subunits_dphi)
        self.box_size = QtWidgets.QDoubleSpinBox()
        self.box_size.setValue(40)
        _disable_scroll(self.box_size)
        form.addRow("Box size (in pixels)", self.box_size)
        v.addLayout(form)
        self.addWidget(params_widget)

    def wheelEvent(self, event):
        """
        Ignore wheel events so scrolling the tomogram doesn't
        unintentionally resize the panel splitter.
        """
        event.ignore()