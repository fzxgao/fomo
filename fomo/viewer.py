#!/usr/bin/env python3
import sys, os, glob, math, argparse, time
from collections import OrderedDict
import numpy as np
import mrcfile
from PyQt5 import QtCore, QtGui, QtWidgets

# Import features from other modules
from fomo.core.cache import SliceCache
from fomo.core.sampling import subsampled_histogram
from fomo.io.mrcio import fast_header_stats
from fomo.widgets.slice_view import SliceView
from fomo.widgets.histogram import HistogramWidget
from fomo.features.picking import PickingModeHandler

# ---------------- Utility ----------------
def list_mrcs(path):
    """Return a sorted list of MRC/REC/MRCS files for the given path or directory."""
    if os.path.isdir(path):
        files = sorted(
            glob.glob(os.path.join(path, "*.mrc")) +
            glob.glob(os.path.join(path, "*.rec")) +
            glob.glob(os.path.join(path, "*.mrcs"))
        )
        return files
    else:
        d = os.path.dirname(path) or "."
        files = sorted(
            glob.glob(os.path.join(d, "*.mrc")) +
            glob.glob(os.path.join(d, "*.rec")) +
            glob.glob(os.path.join(d, "*.mrcs"))
        )
        if path not in files and os.path.exists(path):
            files.append(path)
            files = sorted(files)
        return files

# ---------------- Main Viewer ----------------
class TomoViewer(QtWidgets.QWidget):
    """
    Main application window for FOMO MRC viewer.
    Manages file loading, slice display, histogram, picking mode, and interaction logic.
    """

    last_contrast = None
    last_hist_visible = True

    def __init__(self, path, verbose=False,
                 scroll_base=4, scroll_threshold=2.0,
                 scroll_mult=0.01, scroll_max_streak=4):
        super().__init__()
        self._verbose = verbose
        self._sv_params = dict(
            scroll_base=scroll_base,
            scroll_threshold=scroll_threshold,
            scroll_mult=scroll_mult,
            scroll_max_streak=scroll_max_streak
        )

        # File list & mmap handles
        self.files = list_mrcs(path)
        if not self.files:
            raise SystemExit("No MRC files found.")
        self.idx = 0 if os.path.isdir(path) else self.files.index(path)
        self.mrc_handles = [mrcfile.mmap(f, permissive=True) for f in self.files]
        self.cache = SliceCache(128)

        # XZ visibility, picking state
        self.xz_visible = True
        self._built_scroll_conn = False
        self._xz_timer = None
        self.crosshair_visible = False 
        # Track small cross markers in the XY view (for picking etc.)
        self._xy_marker_items = []
        self._xy_marker_z = None

        # Scroll debounce timer
        self._scroll_timer = QtCore.QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._scroll_commit)

        # Picking mode handler
        self.picking_handler = PickingModeHandler(self)

        # Build UI
        self._build_ui()
        self.top_split.installEventFilter(self)
        self.load_file(self.idx)

    # ---------- Verbose window resize ----------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._verbose:
            sz = self.size()
            print(f"[window.resize] {sz.width()}x{sz.height()}")

    # ---------- Event filter ----------
    def eventFilter(self, obj, event):
        if obj is self.top_split and event.type() == QtCore.QEvent.Resize:
            QtCore.QTimer.singleShot(0, self._set_hist_quarter)
        return super().eventFilter(obj, event)

    # ---------- UI builder ----------
    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        v.addWidget(self.splitter, 1)

        # Top: XZ + histogram
        self.top_split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.view_xz = SliceView(verbose=self._verbose, name="XZ", **self._sv_params)
        self.top_split.addWidget(self.view_xz)
        self.hist_widget = None
        self.splitter.addWidget(self.top_split)

        # Bottom: XY + scrollbar
        bottom = QtWidgets.QWidget()
        bl = QtWidgets.QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        self.view_xy = SliceView(verbose=self._verbose, name="XY", **self._sv_params)
        bl.addWidget(self.view_xy, 1)
        self.scroll_z = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        bl.addWidget(self.scroll_z)
        self.splitter.addWidget(bottom)
        self.splitter.setSizes([300, 600])

        # No scrollbars on slice views
        for view in (self.view_xy, self.view_xz):
            view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        self.lbl = QtWidgets.QLabel()
        v.addWidget(self.lbl)

        self.splitter.splitterMoved.connect(lambda *_: self._fit_views_only())
        self.top_split.splitterMoved.connect(lambda *_: self._fit_views_only())

        self.view_xy.clicked.connect(self._clicked_xy)
        self.view_xz.clicked.connect(self._clicked_xz)
        self.view_xy.wheel_delta.connect(self._step_z)
        self.view_xz.wheel_delta.connect(self._step_z)

        # Shortcuts
        self._sc_prev = QtWidgets.QShortcut(
            QtGui.QKeySequence("1"), self, self._prev_file
        )
        self._sc_next = QtWidgets.QShortcut(
            QtGui.QKeySequence("2"), self, self._next_file
        )
        QtWidgets.QShortcut(QtGui.QKeySequence("H"), self, self._toggle_hist)
        QtWidgets.QShortcut(QtGui.QKeySequence("Z"), self, self._toggle_xz)
        QtWidgets.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Up), self, lambda: self._step_z(4)
        )
        QtWidgets.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Down), self, lambda: self._step_z(-4)
        )
        QtWidgets.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_Escape), self, self._hide_crosshair
        )

        # --- Picking mode shortcuts ---
        QtWidgets.QShortcut(
            QtGui.QKeySequence("P"),
            self,
            self.picking_handler.enter,
            context=QtCore.Qt.ApplicationShortcut,
        )
        QtWidgets.QShortcut(
            QtGui.QKeySequence("Shift+P"),
            self,
            self.picking_handler.exit,
            context=QtCore.Qt.ApplicationShortcut,
        )

    # ---------- File loading ----------
    def load_file(self, idx):
        self._cancel_xz_timer()
        self.clear_marker_xy()

        mrc = self.mrc_handles[idx]
        data = mrc.data  # memmap
        self.data = data
        self.Z, self.Y, self.X = data.shape
        self.x, self.y, self.z = self.X // 2, self.Y // 2, self.Z // 2

        self.cache.clear()
        self.view_xy.dynamic_fit = True
        self.view_xz.dynamic_fit = True

        # Contrast from header/subsample
        if TomoViewer.last_contrast:
            self.minv, self.maxv = TomoViewer.last_contrast
        else:
            amin, amax, amean = fast_header_stats(mrc, data)
            span = (amax - amin) / 2.0
            if span <= 0:
                self.minv, self.maxv = amin, amax
            else:
                rng = span / 1.5
                self.minv, self.maxv = (amean - rng, amean + rng)

        # Histogram
        if self.hist_widget:
            self.hist_widget.setParent(None)
            self.hist_widget = None
        if self.xz_visible and TomoViewer.last_hist_visible:
            hist, edges = subsampled_histogram(self.data)
            init_min, init_max = self.minv, self.maxv
            lo, hi = float(edges[0]), float(edges[-1])
            eps = 1e-6 * max(1.0, abs(hi - lo))
            init_min = float(np.clip(init_min, lo, hi - eps))
            init_max = float(np.clip(init_max, lo + eps, hi))
            self.hist_widget = HistogramWidget(hist=hist, edges=edges,
                                               init_min=init_min, init_max=init_max,
                                               verbose=self._verbose)
            self.hist_widget.contrast_changed.connect(self._set_contrast)
            self.top_split.addWidget(self.hist_widget)
            self.hist_widget.setVisible(True)
            self._set_hist_quarter()

        # Scrollbar
        if not self._built_scroll_conn:
            self.scroll_z.valueChanged.connect(self._set_z)
            self._built_scroll_conn = True
        self.scroll_z.blockSignals(True)
        self.scroll_z.setRange(0, self.Z - 1)
        self.scroll_z.setValue(self.z)
        self.scroll_z.blockSignals(False)

        # Restore layout from picking mode exit
        self.top_split.setVisible(self.xz_visible)

        QtCore.QTimer.singleShot(0, lambda: self._initial_paint())

    def _initial_paint(self):
        self._refresh_views(delayed_xz=self.xz_visible)
        self._set_hist_quarter()

    # ---------- Histogram sizing ----------
    def _set_hist_quarter(self):
        if not self.hist_widget or not self.hist_widget.isVisible():
            return
        if not self.top_split.isVisible():
            return
        total = max(self.top_split.width(), 1)
        hist_w = max(total // 4, self.hist_widget.minimumWidth())
        xz_w = max(total - hist_w, 1)
        self.top_split.setSizes([xz_w, hist_w])

    # ---------- Zero-copy QImage ----------
    def _qimg_from_slice(self, arr):
        arr8 = np.clip((arr - self.minv) / (self.maxv - self.minv), 0, 1)
        arr8 = (arr8 * 255).astype(np.uint8, copy=False)
        h, w = arr8.shape
        qimg = QtGui.QImage(arr8.data, w, h, arr8.strides[0], QtGui.QImage.Format_Grayscale8)
        return qimg, arr8

    def _get_xy(self, z):
        key = ('xy', z)
        cached = self.cache.get(key)
        if cached:
            return cached
        qimg, buf = self._qimg_from_slice(self.data[z, :, :])
        self.cache.put(key, (qimg, buf))
        return (qimg, buf)

    def _get_xz(self, y):
        key = ('xz', y)
        cached = self.cache.get(key)
        if cached:
            return cached
        qimg, buf = self._qimg_from_slice(self.data[:, y, :])
        self.cache.put(key, (qimg, buf))
        return (qimg, buf)

    # ---------- Rendering ----------
    def _refresh_views(self, delayed_xz=False):
        qimg_xy, _ = self._get_xy(self.z)
        self.view_xy.set_image(qimg_xy)
        if self.crosshair_visible:
            self.view_xy.set_crosshair(self.x, self.y)
        else:
            self.view_xy.hide_crosshair()  # Use the new method

        if delayed_xz and self.xz_visible:
            self._schedule_xz_update()
        else:
            self._cancel_xz_timer()

        self._fit_views_only()
        self._update_status()
        self._update_xy_marker_visibility()

    def _update_xz_immediate(self):
        if not self.xz_visible:
            return
        qimg_xz, _ = self._get_xz(self.y)
        self.view_xz.set_image(qimg_xz)
        if self.crosshair_visible:
            self.view_xz.set_crosshair(self.x, self.z)
        else:
            self.view_xz.hide_crosshair()
        self._set_hist_quarter()

    def _schedule_xz_update(self, delay_ms=250):
        self._cancel_xz_timer()
        self._xz_timer = QtCore.QTimer(self)
        self._xz_timer.setSingleShot(True)
        self._xz_timer.timeout.connect(self._update_xz_immediate)
        self._xz_timer.start(delay_ms)

    def _cancel_xz_timer(self):
        if self._xz_timer is not None:
            try:
                self._xz_timer.stop()
            except Exception:
                pass
            self._xz_timer = None
    # ---------- Status / fitting ----------
    def _fit_views_only(self):
        if self.view_xy.dynamic_fit:
            self.view_xy.fit_height()
        if self.xz_visible and self.view_xz.dynamic_fit:
            self.view_xz.fit_height()

    def _update_status(self):
        status = f"{os.path.basename(self.files[self.idx])}  X:{self.x} Y:{self.y} Z:{self.z}"
        if self.picking_handler.is_active():
            status += " | PICKING MODE ACTIVATED"
        self.lbl.setText(status)

    # ---------- Click interactions ----------
    def _clicked_xy(self, x, y):
        if not self.picking_handler.is_active():
            self.crosshair_visible = True  # Show crosshair after first click
        self.x, self.y = x, y
        self._refresh_views(delayed_xz=self.xz_visible)
        if self.picking_handler.is_active():
            self.picking_handler.add_point_under_cursor()

    def _clicked_xz(self, x, z):
        if not self.xz_visible:
            return
        if not self.picking_handler.is_active():
            self.crosshair_visible = True  # Show crosshair after first click
        self.x, self.z = x, z
        self.scroll_z.setValue(self.z)
        self._refresh_views(delayed_xz=self.xz_visible)
    
    def _hide_crosshair(self):
        self.crosshair_visible = False
        self.view_xy.hide_crosshair()
        self.view_xz.hide_crosshair()

    # ---------- XY marker drawing ----------
    def clear_marker_xy(self):
        scene = self.view_xy.scene()
        for item in self._xy_marker_items:
            try:
                scene.removeItem(item)
            except Exception:
                pass
        self._xy_marker_items.clear()
        self._xy_marker_z = None

    def _update_xy_marker_visibility(self):
        visible = bool(self._xy_marker_items) and self._xy_marker_z == self.z
        for item in self._xy_marker_items:
            item.setVisible(visible)

    def draw_marker_xy(self, x, y, color):
        """Draw a small cross marker at (x, y) in the XY view."""
        self.clear_marker_xy()
        scene = self.view_xy.scene()

        pen = QtGui.QPen(color)
        pen.setWidth(2)
        pen.setCosmetic(True)
        half = 3  # ~6 px total length
        h = scene.addLine(x - half, y, x + half, y, pen)
        v = scene.addLine(x, y - half, x, y + half, pen)
        self._xy_marker_items.extend([h, v])
        self._xy_marker_z = self.z
        self._update_xy_marker_visibility()

    # ---------- Scrolling ----------
    def _step_z(self, step):
        self.z = int(np.clip(self.z + step, 0, self.Z - 1))
        self.scroll_z.blockSignals(True)
        self.scroll_z.setValue(self.z)
        self.scroll_z.blockSignals(False)
        self._scroll_timer.stop()
        self._scroll_timer.start(10)
        self._update_xy_marker_visibility()

    def _set_z(self, val):
        self.z = val
        self._refresh_views(delayed_xz=self.xz_visible)

    # ---------- Contrast ----------
    def _set_contrast(self, minv, maxv):
        self.minv, self.maxv = minv, maxv
        TomoViewer.last_contrast = (minv, maxv)
        self.cache.clear()
        self._refresh_views(delayed_xz=self.xz_visible)
        self._set_hist_quarter()

    # ---------- Toggles ----------
    def _toggle_hist(self):
        if not self.xz_visible:
            TomoViewer.last_hist_visible = not TomoViewer.last_hist_visible
            return
        if self.hist_widget and self.hist_widget.isVisible():
            self.hist_widget.setVisible(False)
            TomoViewer.last_hist_visible = False
        else:
            if not self.hist_widget:
                hist, edges = subsampled_histogram(self.data)
                init_min, init_max = self.minv, self.maxv
                lo, hi = float(edges[0]), float(edges[-1])
                eps = 1e-6 * max(1.0, abs(hi - lo))
                init_min = float(np.clip(init_min, lo, hi - eps))
                init_max = float(np.clip(init_max, lo + eps, hi))
                self.hist_widget = HistogramWidget(hist=hist, edges=edges,
                                                   init_min=init_min, init_max=init_max,
                                                   verbose=self._verbose)
                self.hist_widget.contrast_changed.connect(self._set_contrast)
                self.top_split.addWidget(self.hist_widget)
            self.hist_widget.setVisible(True)
            TomoViewer.last_hist_visible = True
            self._set_hist_quarter()

    def _toggle_xz(self):
        self.xz_visible = not self.xz_visible
        self._cancel_xz_timer()
        self.top_split.setVisible(self.xz_visible)
        if self.xz_visible:
            if TomoViewer.last_hist_visible:
                if not self.hist_widget:
                    hist, edges = subsampled_histogram(self.data)
                    init_min, init_max = self.minv, self.maxv
                    lo, hi = float(edges[0]), float(edges[-1])
                    eps = 1e-6 * max(1.0, abs(hi - lo))
                    init_min = float(np.clip(init_min, lo, hi - eps))
                    init_max = float(np.clip(init_max, lo + eps, hi))
                    self.hist_widget = HistogramWidget(hist=hist, edges=edges,
                                                       init_min=init_min, init_max=init_max,
                                                       verbose=self._verbose)
                    self.hist_widget.contrast_changed.connect(self._set_contrast)
                    self.top_split.addWidget(self.hist_widget)
                self.hist_widget.setVisible(True)
            self._update_xz_immediate()
            self._fit_views_only()
            self._set_hist_quarter()

    # ---------- File navigation ----------
    def _prev_file(self):
        if self.idx > 0:
            self.idx -= 1
            self.load_file(self.idx)

    def _next_file(self):
        if self.idx < len(self.files) - 1:
            self.idx += 1
            self.load_file(self.idx)


    def disable_file_switching(self, disable: bool):
        """Enable or disable shortcuts that switch between tomograms."""
        self._sc_prev.setEnabled(not disable)
        self._sc_next.setEnabled(not disable)

    # ---------- Scroll commit ----------
    def _scroll_commit(self):
        qimg_xy, _ = self._get_xy(self.z)
        self.view_xy.set_image(qimg_xy)
        if self.crosshair_visible:
            self.view_xy.set_crosshair(self.x, self.y)
            if self.xz_visible:
                self.view_xz.set_crosshair(self.x, self.z)
        else:
            self.view_xy.hide_crosshair()
            if self.xz_visible:
                self.view_xz.hide_crosshair()
        self._update_status()
        self._update_xy_marker_visibility()