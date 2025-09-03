from pathlib import Path
import re
import numpy as np
from PyQt5 import QtCore, QtWidgets, QtGui

from emfile import read as read_em
from fomo.widgets.slice_view import SliceView


def _disable_scroll(widget):
    widget.wheelEvent = lambda event: event.ignore()


def _wrap_label(text: str) -> QtWidgets.QLabel:
    lbl = QtWidgets.QLabel(text)
    lbl.setWordWrap(True)
    lbl.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
    lbl.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
    return lbl


class SubboxingWidget(QtWidgets.QWidget):
    """Subboxing tab with interactive views and calculated parameters.

    - Interactive: shows XY, YZ, XZ slices of the refined volume.
    - Calculated parameters: fixed-height (300px) scrollable form with wrapped labels.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._vol = None  # Numpy volume as (Z, Y, X)
        self._minv = 0.0
        self._maxv = 1.0
        self._cx = 0
        self._cy = 0
        self._cz = 0

        layout = QtWidgets.QVBoxLayout(self)

        # Interactive section
        layout.addWidget(QtWidgets.QLabel("Interactive"))
        self.view_xy = SliceView(name="subbox_XY")
        self.view_yz = SliceView(name="subbox_YZ")
        self.view_xz = SliceView(name="subbox_XZ")
        for v in (self.view_xy, self.view_yz, self.view_xz):
            v.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            v.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            v.setMinimumHeight(100)
            v.dynamic_fit = True
        layout.addWidget(self.view_xy, 1)
        layout.addWidget(self.view_yz, 1)
        layout.addWidget(self.view_xz, 1)

        # Click handlers: update (cx, cy, cz) and refresh all views
        self.view_xy.clicked.connect(self._clicked_xy)
        self.view_yz.clicked.connect(self._clicked_yz)
        self.view_xz.clicked.connect(self._clicked_xz)

        # Calculated parameters (fixed height, scrollable)
        layout.addWidget(QtWidgets.QLabel("Calculated parameters"))
        self.calc_scroll = QtWidgets.QScrollArea()
        self.calc_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.calc_scroll.setWidgetResizable(True)
        self.calc_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.calc_scroll.setFixedHeight(300)
        calc_inner = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(calc_inner)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        # Tube diameter (Å)
        self.tube_diam = QtWidgets.QDoubleSpinBox()
        self.tube_diam.setDecimals(3)
        self.tube_diam.setRange(-1e9, 1e9)
        self.tube_diam.setValue(0.0)
        self.tube_diam.setToolTip("In angstroms")
        _disable_scroll(self.tube_diam)
        form.addRow(_wrap_label("Tube diameter"), self.tube_diam)

        # Symmetry (text)
        self.symmetry = QtWidgets.QLineEdit("C1")
        form.addRow(_wrap_label("Symmetry"), self.symmetry)

        # Twist (deg)
        self.twist = QtWidgets.QDoubleSpinBox()
        self.twist.setDecimals(3)
        self.twist.setRange(-1e9, 1e9)
        self.twist.setValue(-59.4)
        self.twist.setToolTip("In degrees: positive values are right-handed helix")
        _disable_scroll(self.twist)
        form.addRow(_wrap_label("Twist"), self.twist)

        # Rise (Å)
        self.rise = QtWidgets.QDoubleSpinBox()
        self.rise.setDecimals(3)
        self.rise.setRange(-1e9, 1e9)
        self.rise.setValue(23.0)
        self.rise.setToolTip("In angstroms")
        _disable_scroll(self.rise)
        form.addRow(_wrap_label("Rise"), self.rise)

        # Number of unique asymmetrical units
        self.n_unique = QtWidgets.QSpinBox()
        self.n_unique.setRange(0, 1_000_000)
        self.n_unique.setValue(1)
        _disable_scroll(self.n_unique)
        form.addRow(
            _wrap_label("Number of unique asymmetrical units"), self.n_unique
        )

        # Number of subunits per repeating segment
        self.n_per_segment = QtWidgets.QSpinBox()
        self.n_per_segment.setRange(0, 1_000_000)
        self.n_per_segment.setValue(6)
        _disable_scroll(self.n_per_segment)
        form.addRow(
            _wrap_label("Number of subunits per repeating segment"),
            self.n_per_segment,
        )

        self.calc_scroll.setWidget(calc_inner)
        layout.addWidget(self.calc_scroll)

        # Try auto-loading the latest refined average
        QtCore.QTimer.singleShot(0, self._auto_load_latest)

    # ---- Public API ----
    def set_volume(self, vol: np.ndarray, minv: float, maxv: float):
        """Set the 3D volume (Z, Y, X) and update all interactive views."""
        if vol is None or vol.ndim != 3:
            self.clear_volume()
            return
        self._vol = vol
        self._minv = float(minv)
        self._maxv = float(maxv if maxv != minv else (minv + 1.0))
        Z, Y, X = vol.shape
        self._cx = X // 2
        self._cy = Y // 2
        self._cz = Z // 2
        self._refresh_all()

    def clear_volume(self):
        self._vol = None
        for v in (self.view_xy, self.view_yz, self.view_xz):
            v.scene().clear()
            v.pixmap_item = v.scene().addPixmap(QtGui.QPixmap())
            v.hide_crosshair()

    # ---- Auto-load latest average ----
    def _auto_load_latest(self):
        try:
            catalogue = Path.cwd() / "fomo_dynamo_catalogue" / "alignments"
            try:
                candidates = list(
                    catalogue.glob("*/results/ite_*/averages/average_ref_001_ite_*.em")
                )
            except Exception:
                candidates = []
            if not candidates:
                return
            latest = max(candidates, key=lambda p: p.stat().st_mtime)
            nums = re.findall(r"\d+", latest.name)
            if not nums:
                return
            # Load and orient like viewer._load_latest_refined_average
            header, vol = read_em(latest)
            vol = np.transpose(vol, (2, 1, 0))
            # Derive display contrast similarly
            amin = float(vol.min())
            amax = float(vol.max())
            amean = float(vol.mean())
            if amax <= amin:
                minv, maxv = amin, amax
            else:
                rng = (amax - amin) / 3.0
                minv, maxv = amean - rng, amean + rng
            self.set_volume(vol, minv, maxv)
        except Exception:
            # Silent best-effort auto load
            pass

    # ---- Internals ----
    def _norm_to_qimage(self, arr2d: np.ndarray) -> QtGui.QImage:
        # Match viewer contrast scaling and memory layout expectations
        arr = np.ascontiguousarray(np.asarray(arr2d, dtype=np.float32))
        rng = self._maxv - self._minv
        if rng == 0:
            rng = 1.0
        arr8 = np.clip((arr - self._minv) / rng, 0.0, 1.0)
        arr8 = (arr8 * 255).astype(np.uint8, copy=False)
        h, w = arr8.shape
        # Use bytesPerLine = w (like in viewer._update_refined_slice)
        return QtGui.QImage(arr8.data, w, h, w, QtGui.QImage.Format_Grayscale8)

    def _refresh_all(self):
        if self._vol is None:
            return
        Z, Y, X = self._vol.shape
        self._cx = int(np.clip(self._cx, 0, X - 1))
        self._cy = int(np.clip(self._cy, 0, Y - 1))
        self._cz = int(np.clip(self._cz, 0, Z - 1))

        # XY: z fixed
        qimg_xy = self._norm_to_qimage(self._vol[self._cz, :, :])
        self.view_xy.set_image(qimg_xy)
        self.view_xy.set_crosshair(self._cx, self._cy)

        # YZ: x fixed -> shape (Z, Y)
        qimg_yz = self._norm_to_qimage(self._vol[:, :, self._cx])
        self.view_yz.set_image(qimg_yz)
        self.view_yz.set_crosshair(self._cy, self._cz)

        # XZ: y fixed -> shape (Z, X)
        qimg_xz = self._norm_to_qimage(self._vol[:, self._cy, :])
        self.view_xz.set_image(qimg_xz)
        self.view_xz.set_crosshair(self._cx, self._cz)

    def _clicked_xy(self, x, y):
        if self._vol is None:
            return
        self._cx, self._cy = int(x), int(y)
        self._refresh_all()

    def _clicked_yz(self, x, y):
        if self._vol is None:
            return
        # x = Y, y = Z in the YZ view
        self._cy, self._cz = int(x), int(y)
        self._refresh_all()

    def _clicked_xz(self, x, y):
        if self._vol is None:
            return
        # x = X, y = Z in the XZ view
        self._cx, self._cz = int(x), int(y)
        self._refresh_all()
