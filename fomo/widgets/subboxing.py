from pathlib import Path
import os
import re
import math
import numpy as np
from PyQt5 import QtCore, QtWidgets, QtGui

import mrcfile
from emfile import read as read_em
from fomo.widgets.slice_view import SliceView
from fomo.features.picking import FADE_DIST


def _disable_scroll(widget):
    widget.wheelEvent = lambda event: event.ignore()


def _wrap_label(text: str) -> QtWidgets.QLabel:
    lbl = QtWidgets.QLabel(text)
    lbl.setWordWrap(True)
    lbl.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
    lbl.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
    return lbl


class _AxisGlyph(QtWidgets.QWidget):
    """Tiny axes glyph drawn in a dedicated widget.

    Draws an L-shaped axis with labels: horizontal (x_label) to the right,
    vertical (y_label) upwards. Styled in white to match the UI.
    """

    def __init__(self, x_label: str, y_label: str, parent=None):
        super().__init__(parent)
        self._x_label = str(x_label)
        self._y_label = str(y_label)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Preferred)
        self.setFixedWidth(42)
        self.setMinimumHeight(44)
        self._margin = 4

    def sizeHint(self):  # pragma: no cover - layout sizing
        return QtCore.QSize(42, 44)

    def paintEvent(self, event):  # pragma: no cover - GUI painting
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        col = QtGui.QColor(255, 255, 255)
        pen = QtGui.QPen(col)
        pen.setWidth(1)
        p.setPen(pen)

        w = self.width()
        h = self.height()
        m = self._margin
        L = max(8, min(14, h // 3))  # small
        ox = m + 8  # shift slightly from very edge
        oy = h - m - 6

        # axes lines
        p.drawLine(ox, oy, ox + L, oy)      # horizontal (x)
        p.drawLine(ox, oy, ox, oy - L)      # vertical (y)

        # labels
        font = p.font()
        font.setPointSizeF(8.0)
        p.setFont(font)
        fm = QtGui.QFontMetrics(font)
        # Horizontal label at end of axis, clamped inside widget and aligned to the line
        tx_w = fm.horizontalAdvance(self._x_label)
        x_text_x = min(w - tx_w - 2, ox + L + 2)
        x_text_y = min(h - 2, oy + fm.ascent() - 2)
        p.drawText(QtCore.QPointF(x_text_x, x_text_y), self._x_label)
        # Vertical label near top of vertical axis
        ty_w = fm.horizontalAdvance(self._y_label)
        y_text_x = max(2, ox - ty_w - 2)
        p.drawText(QtCore.QPointF(y_text_x, oy - L - 2), self._y_label)


class SubboxingWidget(QtWidgets.QWidget):
    """Subboxing tab with interactive views and calculated parameters.

    - Interactive: shows XY (top), XZ (middle), YZ (bottom) slices.
    - Calculated parameters: fixed-height (300px) scrollable form with wrapped labels.
    """

    def __init__(self, *args, verbose=False, **kwargs):
        super().__init__(*args, **kwargs)
        # Verbose mode: take explicit flag or fall back to FOMO_VERBOSE env var
        env_verbose = os.environ.get("FOMO_VERBOSE", "") not in ("", "0", "false", "False")
        self._verbose = bool(verbose) or env_verbose
        self._vol = None  # Numpy volume as (Z, Y, X)
        self._minv = 0.0
        self._maxv = 1.0
        self._cx = 0
        self._cy = 0
        self._cz = 0
        self._pix_A = None  # pixel size (Angstroms)

        # Point picking state
        self._asu_points: list[list[tuple[int, int, int]]] = []
        self._current_asu = None
        self._current_idx = None

        # Colors for ASUs (first = red)
        self._asu_colors: list[QtGui.QColor] = []
        self._ensure_asu_colors(16)

        # Marker items per view
        self._marker_items_xy: list[QtWidgets.QGraphicsItem] = []
        self._marker_items_yz: list[QtWidgets.QGraphicsItem] = []
        self._marker_items_xz: list[QtWidgets.QGraphicsItem] = []
        # Overlay items (labels/arcs) per view
        self._overlay_items_yz: list[QtWidgets.QGraphicsItem] = []  # YZ twist arcs/labels
        self._overlay_items_xz: list[QtWidgets.QGraphicsItem] = []  # XZ rise labels

        layout = QtWidgets.QVBoxLayout(self)

        # Interactive section
        layout.addWidget(QtWidgets.QLabel("Interactive"))

        # Interactive parameters moved from calculated section
        inter_form = QtWidgets.QFormLayout()
        inter_form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)

        self.n_unique = QtWidgets.QSpinBox()
        self.n_unique.setRange(1, 1_000_000)
        self.n_unique.setValue(1)
        _disable_scroll(self.n_unique)
        # Changing unique ASUs clears interactive picks to avoid inconsistencies
        self.n_unique.valueChanged.connect(self._clear_interactive_points_on_param_change)
        inter_form.addRow(
            _wrap_label("Number of unique asymmetrical units"), self.n_unique
        )

        self.n_per_segment = QtWidgets.QSpinBox()
        self.n_per_segment.setRange(1, 1_000_000)
        self.n_per_segment.setValue(6)
        _disable_scroll(self.n_per_segment)
        # Changing per-segment count clears interactive picks to avoid inconsistencies
        self.n_per_segment.valueChanged.connect(self._clear_interactive_points_on_param_change)
        inter_form.addRow(
            _wrap_label("Number of subunits per repeating segment"),
            self.n_per_segment,
        )
        layout.addLayout(inter_form)
        self.view_xy = SliceView(name="subbox_XY", sample_scale=2)
        self.view_yz = SliceView(name="subbox_YZ", sample_scale=2)
        self.view_xz = SliceView(name="subbox_XZ", sample_scale=2)
        for v in (self.view_xy, self.view_yz, self.view_xz):
            v.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            v.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            v.setMinimumHeight(100)
            v.dynamic_fit = True
            v.setFocusPolicy(QtCore.Qt.StrongFocus)
            v.installEventFilter(self)
            # Force default arrow cursor and disable hand-drag mode
            v.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            v.viewport().setCursor(QtCore.Qt.ArrowCursor)
        # Add views in order: YZ (top), XZ (middle), XY (bottom)
        layout.addWidget(self.view_yz, 1)
        layout.addWidget(self.view_xz, 1)
        layout.addWidget(self.view_xy, 1)

        # Axes overlays inside each view's bottom-left black margin
        # Orientation per spec:
        #  - Top: Y vertical, X horizontal
        #  - Middle: Z vertical, X horizontal
        #  - Bottom: Y vertical, Z horizontal
        self._axis_overlay_yz = _AxisGlyph(x_label="x", y_label="y", parent=self.view_yz.viewport())
        self._axis_overlay_xz = _AxisGlyph(x_label="x", y_label="z", parent=self.view_xz.viewport())
        self._axis_overlay_xy = _AxisGlyph(x_label="z", y_label="y", parent=self.view_xy.viewport())
        for ow in (self._axis_overlay_yz, self._axis_overlay_xz, self._axis_overlay_xy):
            ow.setStyleSheet("background: transparent;")
            ow.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
            ow.show()

        # Click handlers: update (cx, cy, cz) and refresh all views
        # Top: XY
        self.view_yz.clicked.connect(self._clicked_yz)
        # Middle: XZ
        self.view_xz.clicked.connect(self._clicked_xz)
        # Bottom: YZ
        self.view_xy.clicked.connect(self._clicked_xy)
        # Extended click handling (ctrl/left/right)
        self.view_yz.clicked_ex.connect(lambda x, y, b, m: self._on_click_ex("YZ", x, y, b, m))
        self.view_xz.clicked_ex.connect(lambda x, y, b, m: self._on_click_ex("XZ", x, y, b, m))
        self.view_xy.clicked_ex.connect(lambda x, y, b, m: self._on_click_ex("XY", x, y, b, m))

        # Slow scroll accumulators and connections (10x slower)
        self._scroll_slow_factor = 0.1
        self._scroll_accum_z = 0.0
        self._scroll_accum_x = 0.0
        self._scroll_accum_y = 0.0
        # Scroll wheel slicing per-plane
        # Top XY: scroll Z
        self.view_yz.wheel_delta.connect(self._scroll_x)
        # Middle XZ: scroll Y
        self.view_xz.wheel_delta.connect(self._scroll_y)
        # Bottom YZ: scroll X
        self.view_xy.wheel_delta.connect(self._scroll_z)

        # Bottom: import + calculate buttons (separate rows)
        self.btn_import_refined = QtWidgets.QPushButton("Import refined coordinates")
        self.btn_calc_helical = QtWidgets.QPushButton("Calculate helical parameters")
        layout.addWidget(self.btn_import_refined)
        layout.addWidget(self.btn_calc_helical)

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

        # Filament diameter (Å)
        self.filament_diam = QtWidgets.QDoubleSpinBox()
        self.filament_diam.setDecimals(3)
        self.filament_diam.setRange(-1e9, 1e9)
        self.filament_diam.setValue(150.0)
        self.filament_diam.setToolTip("In angstroms")
        _disable_scroll(self.filament_diam)
        form.addRow(_wrap_label("Filament diameter"), self.filament_diam)

        # Symmetry (text)
        self.symmetry = QtWidgets.QLineEdit("C1")
        form.addRow(_wrap_label("Symmetry"), self.symmetry)

        # Twist (deg) + handedness toggle (L/R)
        self.twist = QtWidgets.QDoubleSpinBox()
        self.twist.setDecimals(3)
        self.twist.setRange(-1e9, 1e9)
        self.twist.setValue(59.4)
        self.twist.setToolTip("In degrees; sign set by L/R toggle (R=positive, L=negative)")
        _disable_scroll(self.twist)
        twist_row = QtWidgets.QWidget()
        thr = QtWidgets.QHBoxLayout(twist_row)
        thr.setContentsMargins(0, 0, 0, 0)
        thr.addWidget(self.twist, 1)
        # L/R radio toggle
        self.handed_L = QtWidgets.QRadioButton("L")
        self.handed_R = QtWidgets.QRadioButton("R")
        self.handed_R.setChecked(True)
        btns = QtWidgets.QButtonGroup(twist_row)
        btns.addButton(self.handed_L)
        btns.addButton(self.handed_R)
        togg = QtWidgets.QWidget()
        togg_l = QtWidgets.QHBoxLayout(togg)
        togg_l.setContentsMargins(6, 0, 0, 0)
        togg_l.addWidget(self.handed_L)
        togg_l.addWidget(self.handed_R)
        thr.addWidget(togg)
        form.addRow(_wrap_label("Twist"), twist_row)
        # Update Twist sign when toggled
        self.handed_L.toggled.connect(lambda _: self._apply_handedness_to_twist())
        self.handed_R.toggled.connect(lambda _: self._apply_handedness_to_twist())

        # Rise (Å)
        self.rise = QtWidgets.QDoubleSpinBox()
        self.rise.setDecimals(3)
        self.rise.setRange(-1e9, 1e9)
        self.rise.setValue(23.0)
        self.rise.setToolTip("In angstroms")
        _disable_scroll(self.rise)
        form.addRow(_wrap_label("Rise"), self.rise)

        # Bottom of calculated section
        # Plot coordinates button (requested above Calculate subboxed)
        self.btn_plot_coords = QtWidgets.QPushButton("Plot calculated coordinates")
        form.addRow(self.btn_plot_coords)

        self.btn_calc_subboxed = QtWidgets.QPushButton("Calculate subboxed coordinates")
        form.addRow(self.btn_calc_subboxed)

        # Parameters for RELION export of subboxed particles (appear above the export button)
        # Output subboxed pixel size (A/px)
        self.output_subboxed_angpix = QtWidgets.QDoubleSpinBox()
        self.output_subboxed_angpix.setDecimals(3)
        self.output_subboxed_angpix.setMinimum(0.001)
        self.output_subboxed_angpix.setMaximum(100000.0)
        self.output_subboxed_angpix.setValue(2.0)
        self.output_subboxed_angpix.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        _disable_scroll(self.output_subboxed_angpix)
        form.addRow(_wrap_label("Output subboxed pixel size"), self.output_subboxed_angpix)

        # Subbox size (pixels)
        self.subboxed_warpbox = QtWidgets.QSpinBox()
        self.subboxed_warpbox.setMinimum(1)
        self.subboxed_warpbox.setMaximum(1_000_000)
        self.subboxed_warpbox.setValue(78)
        self.subboxed_warpbox.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        _disable_scroll(self.subboxed_warpbox)
        form.addRow(_wrap_label("Subbox size (pixels)"), self.subboxed_warpbox)

        # Particle diameter (angstroms)
        self.warp_subboxed_diameter = QtWidgets.QSpinBox()
        self.warp_subboxed_diameter.setMinimum(1)
        self.warp_subboxed_diameter.setMaximum(1_000_000)
        self.warp_subboxed_diameter.setValue(150)
        self.warp_subboxed_diameter.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        _disable_scroll(self.warp_subboxed_diameter)
        form.addRow(_wrap_label("Particle diameter (angstroms)"), self.warp_subboxed_diameter)

        self.btn_export_relion = QtWidgets.QPushButton("Export subboxed coordinates to RELION")
        form.addRow(self.btn_export_relion)

        self.calc_scroll.setWidget(calc_inner)
        layout.addWidget(self.calc_scroll)

        # Wire buttons
        self.btn_calc_helical.clicked.connect(self._calculate_helical_parameters)
        # Emit signals for actions handled in the main viewer
        self.btn_import_refined.clicked.connect(lambda: self.import_refined_requested.emit())
        self.btn_export_relion.clicked.connect(lambda: self.export_subboxed_requested.emit())
        self.btn_calc_subboxed.clicked.connect(lambda: self.calculate_subboxed_requested.emit())
        self.btn_plot_coords.clicked.connect(self._toggle_plot_coordinates)

        # Try auto-loading the latest refined average
        QtCore.QTimer.singleShot(0, self._auto_load_latest)

    # Signals for external actions
    import_refined_requested = QtCore.pyqtSignal()
    export_subboxed_requested = QtCore.pyqtSignal()
    calculate_subboxed_requested = QtCore.pyqtSignal()

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
        # Plotted (generated) points become invalid when the volume changes
        self._reset_plotted_points()

    def clear_volume(self):
        self._vol = None
        for v in (self.view_xy, self.view_yz, self.view_xz):
            v.scene().clear()
            v.pixmap_item = v.scene().addPixmap(QtGui.QPixmap())
            v.hide_crosshair()
        # Reset picking state
        self._asu_points.clear()
        self._current_asu = None
        self._current_idx = None
        # Also reset generated/plot points
        self._reset_plotted_points()

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

        # YZ: x fixed -> transpose to make Z horizontal (width=Z, height=Y)
        yz = self._vol[:, :, self._cx]  # (Z, Y)
        qimg_yz = self._norm_to_qimage(yz.T)  # (Y, Z)
        self.view_yz.set_image(qimg_yz)
        # Crosshair: x=Z, y=Y
        self.view_yz.set_crosshair(self._cz, self._cy)

        # XZ: y fixed -> transpose to make Z horizontal (width=Z, height=X)
        # Then rotate by 180° (flip both axes) as requested
        xz = self._vol[:, self._cy, :]  # (Z, X)
        xz_t = xz.T  # (X, Z)
        xz_t_flip = np.flip(xz_t, axis=(0, 1))  # 180° rotation
        qimg_xz = self._norm_to_qimage(xz_t_flip)
        self.view_xz.set_image(qimg_xz)
        # Crosshair: image coords after 180° flip
        Z, Y, X = self._vol.shape
        cx_disp = (Z - 1) - int(self._cz)
        cy_disp = (X - 1) - int(self._cx)
        self.view_xz.set_crosshair(cx_disp, cy_disp)
        # Position axes overlays inside the views
        self._position_axis_overlays()
        # Draw markers
        self._render_markers()

    def _clicked_xy(self, x, y):
        if self._vol is None:
            return
        self._cx, self._cy = int(x), int(y)
        self._refresh_all()

    def _clicked_yz(self, x, y):
        if self._vol is None:
            return
        # x = Z, y = Y in the YZ view (transposed)
        self._cz, self._cy = int(x), int(y)
        self._refresh_all()

    def _clicked_xz(self, x, y):
        if self._vol is None:
            return
        # x = Z, y = X in the XZ view (transposed)
        # After 180° rotation, both axes are flipped
        Z, Y, X = self._vol.shape
        self._cz, self._cx = int((Z - 1) - x), int((X - 1) - y)
        self._refresh_all()

    # ---- Mouse wheel slicing functions ----
    def _scroll_z(self, step: int):
        if self._vol is None:
            return
        Z = self._vol.shape[0]
        self._scroll_accum_z += float(step) * float(self._scroll_slow_factor)
        moved = 0
        while self._scroll_accum_z >= 1.0:
            moved += 1
            self._scroll_accum_z -= 1.0
        while self._scroll_accum_z <= -1.0:
            moved -= 1
            self._scroll_accum_z += 1.0
        if moved != 0:
            self._cz = int(np.clip(self._cz + moved, 0, Z - 1))
            self._refresh_all()

    def _scroll_x(self, step: int):
        if self._vol is None:
            return
        X = self._vol.shape[2]
        self._scroll_accum_x += float(step) * float(self._scroll_slow_factor)
        moved = 0
        while self._scroll_accum_x >= 1.0:
            moved += 1
            self._scroll_accum_x -= 1.0
        while self._scroll_accum_x <= -1.0:
            moved -= 1
            self._scroll_accum_x += 1.0
        if moved != 0:
            self._cx = int(np.clip(self._cx + moved, 0, X - 1))
            self._refresh_all()

    def _scroll_y(self, step: int):
        if self._vol is None:
            return
        Y = self._vol.shape[1]
        self._scroll_accum_y += float(step) * float(self._scroll_slow_factor)
        moved = 0
        while self._scroll_accum_y >= 1.0:
            moved += 1
            self._scroll_accum_y -= 1.0
        while self._scroll_accum_y <= -1.0:
            moved -= 1
            self._scroll_accum_y += 1.0
        if moved != 0:
            self._cy = int(np.clip(self._cy + moved, 0, Y - 1))
            self._refresh_all()

    # ---- Picking & rendering ----
    def _ensure_asu_colors(self, n: int):
        if len(self._asu_colors) >= n:
            return
        if not self._asu_colors:
            self._asu_colors.append(QtGui.QColor(255, 0, 0))  # first = red
        for _ in range(n - len(self._asu_colors)):
            idx = len(self._asu_colors)
            hue = int(360 * ((idx - 1) / max(1, n - 1)))
            c = QtGui.QColor()
            c.setHsv(hue, 255, 255)
            self._asu_colors.append(c)

    def _on_click_ex(self, view_name: str, x: int, y: int, button: int, modifiers: int):
        if self._vol is None:
            return
        mods = QtCore.Qt.KeyboardModifiers(modifiers)
        btn = QtCore.Qt.MouseButton(button)
        # Map 2D to 3D coordinate
        if view_name == "XY":
            xyz = (int(x), int(y), int(self._cz))
        elif view_name == "YZ":  # transposed: (Z, Y)
            xyz = (int(self._cx), int(y), int(x))
        else:  # XZ transposed: (Z, X) with 180° rotation (flip both axes)
            Z, Y, X = self._vol.shape
            xi = int((X - 1) - y)
            zi = int((Z - 1) - x)
            xyz = (xi, int(self._cy), zi)

        # Ctrl+Left starts a new ASU
        if (btn == QtCore.Qt.LeftButton) and (mods & QtCore.Qt.ControlModifier):
            if len(self._asu_points) >= int(self.n_unique.value()):
                return
            self._asu_points.append([xyz])
            self._current_asu = len(self._asu_points) - 1
            self._current_idx = 0
            self._ensure_asu_colors(len(self._asu_points))
            self._refresh_all()
            self._reset_plotted_points()
            return

        # Left click appends to current ASU
        if btn == QtCore.Qt.LeftButton:
            if self._current_asu is None:
                return
            pts = self._asu_points[self._current_asu]
            if len(pts) >= int(self.n_per_segment.value()):
                return
            pts.append(xyz)
            self._current_idx = len(pts) - 1
            self._refresh_all()
            self._reset_plotted_points()
            return

        # Right click adjusts current point
        if btn == QtCore.Qt.RightButton:
            if self._current_asu is None:
                return
            pts = self._asu_points[self._current_asu]
            if not pts:
                return
            idx = self._current_idx if self._current_idx is not None else len(pts) - 1
            idx = int(np.clip(idx, 0, len(pts) - 1))
            pts[idx] = xyz
            self._refresh_all()
            self._reset_plotted_points()

    def _render_markers(self):
        # Remove old markers
        for items in (self._marker_items_xy, self._marker_items_yz, self._marker_items_xz):
            for it in items:
                try:
                    it.scene().removeItem(it)
                except Exception:
                    pass
            items.clear()
        # Remove old overlays
        for items in (self._overlay_items_yz, self._overlay_items_xz):
            for it in items:
                try:
                    it.scene().removeItem(it)
                except Exception:
                    pass
            items.clear()
        # Remove previously plotted generated markers (circles)
        for items in (getattr(self, "_plot_marker_items_xy", []),
                      getattr(self, "_plot_marker_items_yz", []),
                      getattr(self, "_plot_marker_items_xz", [])):
            for it in items:
                try:
                    it.scene().removeItem(it)
                except Exception:
                    pass
            try:
                items.clear()
            except Exception:
                pass
        if self._vol is None:
            return
        # Base half-length of marker crosses (scene units before supersampling)
        # Make crosses 4x smaller than previous (4 -> 1)
        half = 1
        fade_dist = FADE_DIST
        Z, Y, X = self._vol.shape
        xc = (X - 1) / 2.0
        yc = (Y - 1) / 2.0
        zc = (Z - 1) / 2.0
        pixA = self._pixel_size_A()
        for asu_idx, pts in enumerate(self._asu_points):
            if not pts:
                continue
            base_col = self._asu_colors[min(asu_idx, len(self._asu_colors) - 1)]
            for (x, y, z) in pts:
                # XY view: fade by distance from current Z
                dist_xy = abs(int(z) - int(self._cz))
                if dist_xy <= fade_dist:
                    alpha = max(0.0, 1.0 - (dist_xy / float(fade_dist)))
                    col_xy = QtGui.QColor(base_col)
                    col_xy.setAlpha(int(alpha * 255))
                    pen_xy = QtGui.QPen(col_xy)
                    pen_xy.setWidth(2)
                    pen_xy.setCosmetic(True)
                    sxy = getattr(self.view_xy, "_sample_scale", 1)
                    self._marker_items_xy.extend(
                        self._add_cross(self.view_xy.scene(), x * sxy, y * sxy, half * sxy, pen_xy)
                    )
                # YZ view (bottom): fade by distance from current X, draw at (Z, Y)
                dist_yz = abs(int(x) - int(self._cx))
                if dist_yz <= fade_dist:
                    alpha = max(0.0, 1.0 - (dist_yz / float(fade_dist)))
                    col_yz = QtGui.QColor(base_col)
                    col_yz.setAlpha(int(alpha * 255))
                    pen_yz = QtGui.QPen(col_yz)
                    pen_yz.setWidth(2)
                    pen_yz.setCosmetic(True)
                    syz = getattr(self.view_yz, "_sample_scale", 1)
                    self._marker_items_yz.extend(
                        self._add_cross(self.view_yz.scene(), z * syz, y * syz, half * syz, pen_yz)
                    )
                # XZ view (middle): fade by distance from current Y, draw at (Z, X)
                dist_xz = abs(int(y) - int(self._cy))
                if dist_xz <= fade_dist:
                    alpha = max(0.0, 1.0 - (dist_xz / float(fade_dist)))
                    col_xz = QtGui.QColor(base_col)
                    col_xz.setAlpha(int(alpha * 255))
                    pen_xz = QtGui.QPen(col_xz)
                    pen_xz.setWidth(2)
                    pen_xz.setCosmetic(True)
                    sxz = getattr(self.view_xz, "_sample_scale", 1)
                    # 180° flip: display coords are reversed along both axes
                    z_disp = (Z - 1 - int(z)) * sxz
                    x_disp = (X - 1 - int(x)) * sxz
                    self._marker_items_xz.extend(
                        self._add_cross(self.view_xz.scene(), z_disp, x_disp, half * sxz, pen_xz)
                    )

            # Overlays per segment: YZ twist arcs, XZ rise labels
            for (x1, y1, z1), (x2, y2, z2) in zip(pts, pts[1:]):
                # YZ twist arc: both points near current X slice
                dx1 = abs(int(x1) - int(self._cx))
                dx2 = abs(int(x2) - int(self._cx))
                if dx1 <= fade_dist and dx2 <= fade_dist:
                    a1f = max(0.0, 1.0 - dx1 / float(fade_dist))
                    a2f = max(0.0, 1.0 - dx2 / float(fade_dist))
                    alpha = (a1f + a2f) / 2.0
                    # Angle in YZ plane with vertex at (yc, zc)
                    ang1 = math.degrees(math.atan2(float(y1) - yc, float(z1) - zc)) % 360.0
                    ang2 = math.degrees(math.atan2(float(y2) - yc, float(z2) - zc)) % 360.0
                    d_ccw = (ang2 - ang1) % 360.0
                    if d_ccw <= 180.0:
                        start = ang1
                        sweep = d_ccw
                    else:
                        start = ang2
                        sweep = 360.0 - d_ccw
                    twist_deg = sweep
                    # Draw arc in YZ view (x=Z, y=Y)
                    syz = getattr(self.view_yz, "_sample_scale", 1)
                    cz_s = float(zc) * syz
                    cy_s = float(yc) * syz
                    R = 20.0 * syz
                    rect = QtCore.QRectF(cz_s - R, cy_s - R, 2 * R, 2 * R)
                    path = QtGui.QPainterPath()
                    path.arcMoveTo(rect, start)
                    path.arcTo(rect, start, sweep)
                    col_arc = QtGui.QColor(base_col)
                    col_arc.setAlpha(int(alpha * 255))
                    pen = QtGui.QPen(col_arc)
                    pen.setWidth(2)
                    pen.setCosmetic(True)
                    arc_item = self.view_yz.scene().addPath(path, pen)
                    self._overlay_items_yz.append(arc_item)
                    # Label near arc midpoint
                    mid_ang = (start + sweep / 2.0) * math.pi / 180.0
                    tx = cz_s + (R + 10.0) * math.cos(mid_ang)
                    ty = cy_s + (R + 10.0) * math.sin(mid_ang)
                    txt = QtWidgets.QGraphicsTextItem(f"{twist_deg:.1f}°")
                    txt.setDefaultTextColor(QtGui.QColor(col_arc))
                    txt.setPos(tx, ty)
                    self.view_yz.scene().addItem(txt)
                    self._overlay_items_yz.append(txt)

                # XZ rise label: both points near current Y slice
                dy1 = abs(int(y1) - int(self._cy))
                dy2 = abs(int(y2) - int(self._cy))
                if dy1 <= fade_dist and dy2 <= fade_dist:
                    a1 = max(0.0, 1.0 - dy1 / float(fade_dist))
                    a2 = max(0.0, 1.0 - dy2 / float(fade_dist))
                    alpha = (a1 + a2) / 2.0
                    riseA = abs(float(x2) - float(x1)) * pixA
                    label = f"rise {riseA:.2f} Å"
                    sxz = getattr(self.view_xz, "_sample_scale", 1)
                    # 180° flip: invert coordinates when placing label
                    mz = (float(z1) + float(z2)) * 0.5
                    mx = (Z - 1 - mz) * sxz  # horizontal position (Z)
                    mx = float(mx)
                    myx = (float(x1) + float(x2)) * 0.5
                    my = (X - 1 - myx) * sxz  # vertical position (X)
                    text_item = QtWidgets.QGraphicsTextItem(label)
                    col_txt = QtGui.QColor(255, 255, 255, int(alpha * 255))
                    text_item.setDefaultTextColor(col_txt)
                    text_item.setPos(mx + 4, my + 4)
                    self.view_xz.scene().addItem(text_item)
                    self._overlay_items_xz.append(text_item)

        # Draw generated/plotted coordinates as circles (same visual size as crosses)
        plot_pts = getattr(self, "_plotted_points", None)
        if plot_pts:
            self._plot_marker_items_xy = []
            self._plot_marker_items_yz = []
            self._plot_marker_items_xz = []
            for asu_idx, pts in enumerate(plot_pts):
                if not pts:
                    continue
                base_col = self._asu_colors[min(asu_idx, len(self._asu_colors) - 1)]
                for (x, y, z) in pts:
                    # XY view: fade by distance from current Z
                    dist_xy = abs(int(z) - int(self._cz))
                    if dist_xy <= fade_dist:
                        alpha = max(0.0, 1.0 - (dist_xy / float(fade_dist)))
                        col_xy = QtGui.QColor(base_col)
                        col_xy.setAlpha(int(alpha * 255))
                        pen_xy = QtGui.QPen(col_xy)
                        pen_xy.setWidth(2)
                        pen_xy.setCosmetic(True)
                        sxy = getattr(self.view_xy, "_sample_scale", 1)
                        self._plot_marker_items_xy.append(
                            self._add_circle(self.view_xy.scene(), x * sxy, y * sxy, half * sxy, pen_xy)
                        )
                    # YZ view (x fixed): draw at (Z, Y)
                    dist_yz = abs(int(x) - int(self._cx))
                    if dist_yz <= fade_dist:
                        alpha = max(0.0, 1.0 - (dist_yz / float(fade_dist)))
                        col_yz = QtGui.QColor(base_col)
                        col_yz.setAlpha(int(alpha * 255))
                        pen_yz = QtGui.QPen(col_yz)
                        pen_yz.setWidth(2)
                        pen_yz.setCosmetic(True)
                        syz = getattr(self.view_yz, "_sample_scale", 1)
                        self._plot_marker_items_yz.append(
                            self._add_circle(self.view_yz.scene(), z * syz, y * syz, half * syz, pen_yz)
                        )
                    # XZ view (y fixed): draw at (Z, X)
                    dist_xz = abs(int(y) - int(self._cy))
                    if dist_xz <= fade_dist:
                        alpha = max(0.0, 1.0 - (dist_xz / float(fade_dist)))
                        col_xz = QtGui.QColor(base_col)
                        col_xz.setAlpha(int(alpha * 255))
                        pen_xz = QtGui.QPen(col_xz)
                        pen_xz.setWidth(2)
                        pen_xz.setCosmetic(True)
                        sxz = getattr(self.view_xz, "_sample_scale", 1)
                        z_disp = (Z - 1 - int(z)) * sxz
                        x_disp = (X - 1 - int(x)) * sxz
                        self._plot_marker_items_xz.append(
                            self._add_circle(self.view_xz.scene(), z_disp, x_disp, half * sxz, pen_xz)
                        )

    @staticmethod
    def _add_cross(scene: QtWidgets.QGraphicsScene, x: int, y: int, half: int, pen: QtGui.QPen):
        items = []
        items.append(scene.addLine(x - half, y, x + half, y, pen))
        items.append(scene.addLine(x, y - half, x, y + half, pen))
        return items

    @staticmethod
    def _add_circle(scene: QtWidgets.QGraphicsScene, x: float, y: float, radius: float, pen: QtGui.QPen):
        rect = QtCore.QRectF(x - radius, y - radius, 2 * radius, 2 * radius)
        item = scene.addEllipse(rect, pen)
        return item
    
    # Axis glyph is rendered in a separate widget next to each view.

    # ---- Keyboard handling ----
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress and event.key() == QtCore.Qt.Key_Backspace:
            self._delete_last_point()
            return True
        if event.type() == QtCore.QEvent.Resize:
            if obj in (self.view_xy, self.view_yz, self.view_xz):
                QtCore.QTimer.singleShot(0, self._position_axis_overlays)
        
        return super().eventFilter(obj, event)

    def _position_axis_overlays(self):
        try:
            pairs = (
                (self.view_yz, self._axis_overlay_yz),
                (self.view_xz, self._axis_overlay_xz),
                (self.view_xy, self._axis_overlay_xy),
            )
        except Exception:
            return
        for view, ow in pairs:
            try:
                if not ow or not view:
                    continue
                vp = view.viewport()
                if ow.height() <= 0:
                    ow.resize(ow.sizeHint())
                x = 6
                y = max(0, vp.height() - ow.height() - 6)
                ow.move(int(x), int(y))
                ow.raise_()
            except Exception:
                pass

    def _delete_last_point(self):
        if not self._asu_points:
            return
        asu_idx = self._current_asu
        # If no active ASU, pick the last non-empty one
        if asu_idx is None or asu_idx >= len(self._asu_points) or not self._asu_points[asu_idx]:
            for i in range(len(self._asu_points) - 1, -1, -1):
                if self._asu_points[i]:
                    asu_idx = i
                    break
            else:
                return
        pts = self._asu_points[asu_idx]
        try:
            pts.pop()
        except Exception:
            return
        # Remove empty ASU to keep things tidy
        if not pts:
            try:
                self._asu_points.pop(asu_idx)
            except Exception:
                pass
            if self._asu_points:
                self._current_asu = len(self._asu_points) - 1
                last_pts = self._asu_points[self._current_asu]
                self._current_idx = len(last_pts) - 1 if last_pts else None
            else:
                self._current_asu = None
                self._current_idx = None
        else:
            self._current_asu = asu_idx
            self._current_idx = len(pts) - 1 if pts else None
        self._refresh_all()
        self._reset_plotted_points()

    def _clear_interactive_points_on_param_change(self):
        """Clear all user-added crosses and any plotted circles when ASU/segment inputs change."""
        # Clear picked points (crosses)
        self._asu_points.clear()
        self._current_asu = None
        self._current_idx = None
        # Clear plotted circles as well to avoid mismatch with new parameters
        self._reset_plotted_points()
        # Redraw views without markers
        self._refresh_all()

    # ---- Handedness helpers ----
    def _is_left_handed(self) -> bool:
        try:
            return bool(self.handed_L.isChecked())
        except Exception:
            return False

    def _apply_handedness_to_twist(self):
        try:
            v = abs(float(self.twist.value()))
            if self._is_left_handed():
                v = -v
            self.twist.blockSignals(True)
            self.twist.setValue(v)
            self.twist.blockSignals(False)
        except Exception:
            pass

    # ---- Parameter calculations ----
    def _pixel_size_A(self) -> float:
        if self._pix_A is not None:
            return self._pix_A
        root = Path.cwd() / "warp_tiltseries" / "reconstruction"
        pix = 1.0
        try:
            files = sorted([p for p in root.glob("*.mrc") if p.is_file()])
            if files:
                with mrcfile.open(files[0], permissive=True) as mrc:
                    vs = getattr(mrc, "voxel_size", None)
                    if vs is not None:
                        pix = float(vs.x)
        except Exception:
            pass
        self._pix_A = pix
        return pix

    def _calculate_helical_parameters(self):
        if self._vol is None or not self._asu_points:
            return
        Z, Y, X = self._vol.shape
        xc = (X - 1) / 2.0
        yc = (Y - 1) / 2.0
        zc = (Z - 1) / 2.0
        pixA = self._pixel_size_A()

        radii = []
        delta_angles = []
        rises = []
        for asu_idx, pts in enumerate(self._asu_points):
            if not pts:
                continue
            if self._verbose:
                try:
                    print(f"[subboxing] ASU {asu_idx}: {len(pts)} points", flush=True)
                except Exception:
                    pass
            # Per-point diameter (using radius in XZ plane)
            for j, (x, _y, z) in enumerate(pts):
                r_pix = math.hypot(float(x) - xc, float(z) - zc)
                radii.append(r_pix)
                if self._verbose:
                    try:
                        diamA = 2.0 * r_pix * pixA
                        print(f"[subboxing]   pt {j:02d}: diameter = {diamA:.3f} Å", flush=True)
                    except Exception:
                        pass
            # Per-segment twist/rise between consecutive points
            for j in range(len(pts) - 1):
                x1, y1, z1 = pts[j]
                x2, y2, z2 = pts[j + 1]
                # Twist = angle ABC between BA and BC in YZ, B=center (yc,zc)
                bay = float(y1) - yc
                baz = float(z1) - zc
                bcy = float(y2) - yc
                bcz = float(z2) - zc
                n1 = math.hypot(bay, baz)
                n2 = math.hypot(bcy, bcz)
                if n1 > 0 and n2 > 0:
                    cos_th = (bay * bcy + baz * bcz) / (n1 * n2)
                    cos_th = max(-1.0, min(1.0, cos_th))
                    twist_deg = math.degrees(math.acos(cos_th))
                else:
                    twist_deg = 0.0
                delta_angles.append(twist_deg)
                # Rise = vertical distance in XZ (|ΔX|) in Angstroms
                riseA = abs(float(x2) - float(x1)) * pixA
                rises.append(riseA)
                if self._verbose:
                    try:
                        print(f"[subboxing]   seg {j:02d}->{j+1:02d}: twist = {twist_deg:.3f}°  rise = {riseA:.3f} Å", flush=True)
                    except Exception:
                        pass

        if radii:
            self.filament_diam.setValue(2.0 * float(np.mean(radii)) * pixA)
        if delta_angles:
            mean_twist = float(np.mean(delta_angles))
            # Apply handedness sign: R=positive, L=negative
            if self._is_left_handed():
                mean_twist = -mean_twist
            self.twist.setValue(mean_twist)
        if rises:
            self.rise.setValue(float(np.mean(rises)))

    # ---- Plotting generated coordinates ----
    def _reset_plotted_points(self):
        # Remove any existing plotted markers from scenes
        for items in (
            getattr(self, "_plot_marker_items_xy", []),
            getattr(self, "_plot_marker_items_yz", []),
            getattr(self, "_plot_marker_items_xz", []),
        ):
            for it in list(items):
                try:
                    it.scene().removeItem(it)
                except Exception:
                    pass
            try:
                items.clear()
            except Exception:
                pass
        self._plotted_points = []
        self._plot_marker_items_xy = []
        self._plot_marker_items_yz = []
        self._plot_marker_items_xz = []
        # Update button label state
        try:
            self._update_plot_button_text()
        except Exception:
            pass

    def _has_plotted_points(self) -> bool:
        pts = getattr(self, "_plotted_points", None)
        if not pts:
            return False
        return any(bool(p) for p in pts)

    def _update_plot_button_text(self):
        if not hasattr(self, "btn_plot_coords"):
            return
        if self._has_plotted_points():
            self.btn_plot_coords.setText("Clear plotted coordinates")
        else:
            self.btn_plot_coords.setText("Plot calculated coordinates")

    def _clear_plotted_coordinates(self):
        self._reset_plotted_points()

    def _toggle_plot_coordinates(self):
        if self._has_plotted_points():
            self._clear_plotted_coordinates()
        else:
            self._plot_coordinates()
        # Ensure label reflects current state
        try:
            self._update_plot_button_text()
        except Exception:
            pass

    def _symmetry_order(self) -> int:
        try:
            s = (self.symmetry.text() or "").strip().upper()
        except Exception:
            s = "C1"
        m = re.match(r"^[CD]?(\d+)$", s) or re.match(r"^[CD](\d+)$", s)
        if m:
            try:
                n = int(m.group(1))
                return max(1, n)
            except Exception:
                return 1
        # also handle like "C3" or "D7" with extra characters
        m2 = re.search(r"(\d+)", s)
        if m2:
            try:
                return max(1, int(m2.group(1)))
            except Exception:
                pass
        return 1

    def _plot_coordinates(self):
        # Validate prerequisites
        n_unique_req = int(self.n_unique.value())
        if self._vol is None or n_unique_req <= 0:
            return
        if len(self._asu_points) < n_unique_req or any((not pts) for pts in self._asu_points[:n_unique_req]):
            QtWidgets.QToolTip.showText(
                QtGui.QCursor.pos(),
                "Please add a starting point for each unique asymmetric unit",
                self.btn_plot_coords,
            )
            return

        # Compute generated points based on tube diameter, twist, rise, and symmetry
        pixA = self._pixel_size_A()
        if pixA <= 0:
            pixA = 1.0
        try:
            filament_diam_A = float(self.filament_diam.value())
        except Exception:
            filament_diam_A = 0.0
        try:
            twist_deg = float(self.twist.value())
        except Exception:
            twist_deg = 0.0
        try:
            rise_A = float(self.rise.value())
        except Exception:
            rise_A = 0.0
        # radius in pixels
        r_pix = max(0.0, (filament_diam_A * 0.5) / pixA)
        rise_pix = rise_A / pixA
        Z, Y, X = self._vol.shape
        xc = (X - 1) / 2.0
        yc = (Y - 1) / 2.0
        zc = (Z - 1) / 2.0

        n_steps = int(max(1, int(self.n_per_segment.value())))
        # Prepare container and generate per ASU
        plotted = []
        for asu_idx in range(min(len(self._asu_points), n_unique_req)):
            seed_pts = self._asu_points[asu_idx]
            if not seed_pts:
                plotted.append([])
                continue
            # Use the first point as the starting reference
            x0, y0, z0 = seed_pts[0]
            # Angle in YZ plane (0 deg at +Z, CCW towards +Y)
            theta0 = math.atan2(float(y0) - yc, float(z0) - zc)
            pts = []
            for k in range(n_steps):
                theta = theta0 + math.radians(twist_deg) * k
                x = float(x0) + rise_pix * k
                z = float(zc) + r_pix * math.cos(theta)
                y = float(yc) + r_pix * math.sin(theta)
                # Clamp to volume bounds and store as ints
                xi = int(np.clip(round(x), 0, X - 1))
                yi = int(np.clip(round(y), 0, Y - 1))
                zi = int(np.clip(round(z), 0, Z - 1))
                pts.append((xi, yi, zi))
            plotted.append(pts)

        self._plotted_points = plotted
        # Update label and redraw
        try:
            self._update_plot_button_text()
        except Exception:
            pass
        self._refresh_all()
