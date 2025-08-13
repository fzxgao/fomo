#!/usr/bin/env python3
import sys, os, glob, math, argparse, time
from collections import OrderedDict
import numpy as np
import mrcfile
from PyQt5 import QtCore, QtGui, QtWidgets

# ---------------- Utility ----------------
def list_mrcs(path):
    if os.path.isdir(path):
        files = sorted(glob.glob(os.path.join(path, "*.mrc")) +
                       glob.glob(os.path.join(path, "*.rec")) +
                       glob.glob(os.path.join(path, "*.mrcs")))
        return files
    else:
        d = os.path.dirname(path) or "."
        files = sorted(glob.glob(os.path.join(d, "*.mrc")) +
                       glob.glob(os.path.join(d, "*.rec")) +
                       glob.glob(os.path.join(d, "*.mrcs")))
        if path not in files and os.path.exists(path):
            files.append(path)
            files = sorted(files)
        return files

def subsampled_histogram(memmap_arr, bins=256, max_voxels=2_000_000):
    Z, Y, X = memmap_arr.shape
    total = Z * Y * X
    if total <= max_voxels:
        vals = memmap_arr.ravel()
    else:
        stride = int(math.ceil(total / max_voxels))
        vals = memmap_arr.ravel()[::stride]
    vals = vals.astype(np.float32)
    hist, edges = np.histogram(vals, bins=bins)
    return hist, edges

def fast_header_stats(mrc, data, fallback_max_voxels=2_000_000):
    """Use header amin/amax/amean if valid, else subsample quickly."""
    amin = getattr(mrc.header, "amin", None)
    amax = getattr(mrc.header, "amax", None)
    amean = getattr(mrc.header, "amean", None)
    try:
        if amin is not None and amax is not None:
            amin = float(amin); amax = float(amax)
            if np.isfinite(amin) and np.isfinite(amax) and amax > amin:
                mean = float(amean) if amean is not None and np.isfinite(amean) else 0.5*(amin+amax)
                return amin, amax, mean
    except Exception:
        pass
    Z, Y, X = data.shape
    total = Z*Y*X
    if total <= fallback_max_voxels:
        sample = np.asarray(data, dtype=np.float32).ravel()
    else:
        stride = int(math.ceil(total / fallback_max_voxels))
        sample = np.asarray(data.ravel()[::stride], dtype=np.float32)
    smin = float(np.min(sample))
    smax = float(np.max(sample))
    smean = float(np.mean(sample))
    return smin, smax, smean

# ---------------- Cache ----------------
class SliceCache:
    def __init__(self, capacity=128):
        self.capacity = capacity
        self._data = OrderedDict()
    def get(self, key):
        return self._data.get(key)
    def put(self, key, value):
        if key in self._data:
            self._data.pop(key)
        self._data[key] = value
        while len(self._data) > self.capacity:
            self._data.popitem(last=False)
    def clear(self):
        self._data.clear()

# ---------------- Views ----------------
class SliceView(QtWidgets.QGraphicsView):
    clicked = QtCore.pyqtSignal(int, int)
    wheel_delta = QtCore.pyqtSignal(int)

    def __init__(self, *, verbose=False, name="view",
                 scroll_base=4, scroll_threshold=2.0,
                 scroll_mult=0.01, scroll_max_streak=4):
        super().__init__()
        self._verbose = verbose
        self._name = name

        # Acceleration tuning (from CLI or defaults)
        self._BASE_STEP = int(scroll_base)
        self._STREAK_THRESHOLD = float(scroll_threshold)
        self._STREAK_MULT = float(scroll_mult)
        self._STREAK_MAX = int(scroll_max_streak)

        self.setScene(QtWidgets.QGraphicsScene(self))
        self.pixmap_item = self.scene().addPixmap(QtGui.QPixmap())
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(20, 20, 20)))
        pen = QtGui.QPen(QtGui.QColor(255, 235, 59))
        pen.setCosmetic(True)
        self.hline = self.scene().addLine(0, 0, 1, 0, pen)
        self.vline = self.scene().addLine(0, 0, 0, 1, pen)
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.img_w = 1
        self.img_h = 1
        self.dynamic_fit = True

        # wheel acceleration state
        self._wheel_last_ts = 0.0
        self._wheel_streak = 0

    def set_image(self, qimg):
        self.img_w = qimg.width()
        self.img_h = qimg.height()
        self.pixmap_item.setPixmap(QtGui.QPixmap.fromImage(qimg))
        self.scene().setSceneRect(0, 0, self.img_w, self.img_h)
        if self.dynamic_fit:
            self.fit_height()
        self.viewport().update()

    def set_crosshair(self, x, y):
        self.hline.setLine(0, y + 0.5, self.img_w, y + 0.5)
        self.vline.setLine(x + 0.5, 0, x + 0.5, self.img_h)

    def fit_height(self):
        rect = self.sceneRect()
        vh = self.viewport().height()
        if rect.height() > 0 and vh > 0:
            scale = vh / rect.height()
            self.resetTransform()
            self.scale(scale, scale)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.dynamic_fit:
            self.fit_height()

    def wheelEvent(self, ev):
        if ev.modifiers() & QtCore.Qt.ControlModifier:
            # Zoom (no acceleration)
            step = 1.001 ** ev.angleDelta().y()
            self.scale(step, step)
            self.dynamic_fit = False
        else:
            # Slice Z with acceleration
            dy = ev.angleDelta().y()  # typical notch: ±120
            if dy != 0:
                now = time.perf_counter()
                dt = now - self._wheel_last_ts if self._wheel_last_ts else 999
                self._wheel_last_ts = now

                # streak update
                if dt < self._STREAK_THRESHOLD:
                    self._wheel_streak = min(self._wheel_streak + 1, self._STREAK_MAX)
                else:
                    self._wheel_streak = 0

                ticks = abs(dy) / 120.0  # supports hi-res wheels
                mult = 1.0 + self._wheel_streak * self._STREAK_MULT
                step_mag = max(1, int(round(self._BASE_STEP * ticks * mult)))
                step = step_mag if dy > 0 else -step_mag

                if self._verbose:
                    print(f"[{self._name}.wheel] dy={dy} dt={dt*1e3:.0f}ms streak={self._wheel_streak} mult={mult:.2f} -> step={step}")

                self.wheel_delta.emit(step)
        ev.accept()

    def mousePressEvent(self, ev):
        if ev.button() == QtCore.Qt.LeftButton:
            pos = self.mapToScene(ev.pos())
            x = int(np.clip(round(pos.x()), 0, self.img_w - 1))
            y = int(np.clip(round(pos.y()), 0, self.img_h - 1))
            self.clicked.emit(x, y)
        super().mousePressEvent(ev)

# ---------------- Histogram ----------------
class HistogramWidget(QtWidgets.QWidget):
    contrast_changed = QtCore.pyqtSignal(float, float)
    def __init__(self, hist, edges, init_min, init_max, verbose=False):
        super().__init__()
        self.hist, self.edges = hist, edges
        self._verbose = verbose
        # thresholds (clamped into edges range so lines stay in view)
        self.min_val, self.max_val = init_min, init_max
        self._clamp_thresholds()
        self.setMinimumWidth(80)
        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)

    def _clamp_thresholds(self):
        if len(self.edges) == 0:
            return
        lo, hi = float(self.edges[0]), float(self.edges[-1])
        eps = 1e-6 * max(1.0, abs(hi - lo))
        self.min_val = float(np.clip(self.min_val, lo, hi - eps))
        self.max_val = float(np.clip(self.max_val, lo + eps, hi))
        if self.min_val >= self.max_val:
            self.min_val = lo
            self.max_val = hi

    def paintEvent(self, ev):
        painter = QtGui.QPainter(self)
        rect = self.rect()
        if len(self.hist) == 0 or len(self.edges) == 0:
            painter.fillRect(rect, QtGui.QColor(30, 30, 30))
            return
        max_h = max(self.hist) if len(self.hist) else 1
        for i, h in enumerate(self.hist):
            x0 = rect.left() + int(i / len(self.hist) * rect.width())
            x1 = rect.left() + int((i + 1) / len(self.hist) * rect.width())
            y = rect.bottom() - int(h / max_h * rect.height())
            painter.fillRect(QtCore.QRect(x0, y, x1 - x0, rect.bottom() - y),
                             QtGui.QColor(180, 180, 180))

        # Clamp values into edges span to keep lines visible
        lo, hi = float(self.edges[0]), float(self.edges[-1])
        vmin = float(np.clip(self.min_val, lo, hi))
        vmax = float(np.clip(self.max_val, lo, hi))

        for val, color in [(vmin, QtGui.QColor(0, 255, 0)),
                           (vmax, QtGui.QColor(255, 0, 0))]:
            xpos = rect.left() + int((val - lo) / (hi - lo) * rect.width())
            painter.setPen(QtGui.QPen(color, 2))
            painter.drawLine(xpos, rect.top(), xpos, rect.bottom())

    def mousePressEvent(self, ev):
        self._update_handle(ev, from_press=True)

    def mouseMoveEvent(self, ev):
        self._update_handle(ev, from_press=False)

    def _value_from_pos(self, ev):
        rect = self.rect()
        lo, hi = float(self.edges[0]), float(self.edges[-1])
        t = (ev.pos().x() - rect.left()) / max(1, rect.width())
        return lo + np.clip(t, 0.0, 1.0) * (hi - lo)

    def _update_handle(self, ev, from_press=False):
        if len(self.edges) == 0:
            return
        which = None
        if from_press:
            if ev.button() == QtCore.Qt.LeftButton:
                which = "min"
            elif ev.button() == QtCore.Qt.RightButton:
                which = "max"
            else:
                return
        else:
            buttons = ev.buttons()
            if buttons & QtCore.Qt.LeftButton:
                which = "min"
            elif buttons & QtCore.Qt.RightButton:
                which = "max"
            else:
                return

        val = self._value_from_pos(ev)
        lo, hi = float(self.edges[0]), float(self.edges[-1])
        eps = 1e-6 * max(1.0, abs(hi - lo))
        if which == "min":
            self.min_val = min(max(val, lo), self.max_val - eps)
        else:
            self.max_val = max(min(val, hi), self.min_val + eps)

        self._clamp_thresholds()
        self.contrast_changed.emit(self.min_val, self.max_val)
        self.update()

# ---------------- Main Viewer ----------------
class TomoViewer(QtWidgets.QWidget):
    last_contrast = None
    last_hist_visible = True

    def __init__(self, path, verbose=False,
                 scroll_base=4, scroll_threshold=2.0,
                 scroll_mult=0.01, scroll_max_streak=4):
        super().__init__()
        self._verbose = verbose
        self._sv_params = dict(scroll_base=scroll_base,
                               scroll_threshold=scroll_threshold,
                               scroll_mult=scroll_mult,
                               scroll_max_streak=scroll_max_streak)

        self.files = list_mrcs(path)
        if not self.files:
            raise SystemExit("No MRC files found.")
        self.idx = 0 if os.path.isdir(path) else self.files.index(path)
        # Keep mmap handles open
        self.mrc_handles = [mrcfile.mmap(f, permissive=True) for f in self.files]
        self.cache = SliceCache(128)
        self._xz_timer = None
        self.xz_visible = True
        self._built_scroll_conn = False

        # NEW: Scroll debounce timer
        self._scroll_timer = QtCore.QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.timeout.connect(self._scroll_commit)


        self._build_ui()
        # enforce 1/4 histogram width on resize
        self.top_split.installEventFilter(self)
        self.load_file(self.idx)

    # ----- Verbose window size logging -----
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._verbose:
            sz = self.size()
            print(f"[window.resize] {sz.width()}x{sz.height()}")

    # ----- Event filter to enforce 1/4 width histogram on resize -----
    def eventFilter(self, obj, event):
        if obj is self.top_split and event.type() == QtCore.QEvent.Resize:
            QtCore.QTimer.singleShot(0, self._set_hist_quarter)
        return super().eventFilter(obj, event)

    def _set_hist_quarter(self):
        if not self.hist_widget or not self.hist_widget.isVisible():
            return
        if not self.top_split.isVisible():
            return
        total = max(self.top_split.width(), 1)
        hist_w = max(total // 4, self.hist_widget.minimumWidth())
        xz_w = max(total - hist_w, 1)
        self.top_split.setSizes([xz_w, hist_w])

    # ---------- UI ----------
    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        v.addWidget(self.splitter, 1)

        self.top_split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.view_xz = SliceView(verbose=self._verbose, name="XZ", **self._sv_params)
        self.top_split.addWidget(self.view_xz)
        self.hist_widget = None
        self.splitter.addWidget(self.top_split)

        bottom = QtWidgets.QWidget()
        bl = QtWidgets.QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        self.view_xy = SliceView(verbose=self._verbose, name="XY", **self._sv_params)
        bl.addWidget(self.view_xy, 1)
        self.scroll_z = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        bl.addWidget(self.scroll_z)
        self.splitter.addWidget(bottom)
        self.splitter.setSizes([300, 600])

        self.view_xy.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view_xy.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view_xz.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view_xz.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)


        self.lbl = QtWidgets.QLabel()
        v.addWidget(self.lbl)

        self.splitter.splitterMoved.connect(lambda *_: self._fit_views_only())
        self.top_split.splitterMoved.connect(lambda *_: self._fit_views_only())

        self.view_xy.clicked.connect(self._clicked_xy)
        self.view_xz.clicked.connect(self._clicked_xz)
        self.view_xy.wheel_delta.connect(self._step_z)
        self.view_xz.wheel_delta.connect(self._step_z)

        QtWidgets.QShortcut(QtGui.QKeySequence("1"), self, self._prev_file)
        QtWidgets.QShortcut(QtGui.QKeySequence("2"), self, self._next_file)
        QtWidgets.QShortcut(QtGui.QKeySequence("H"), self, self._toggle_hist)
        QtWidgets.QShortcut(QtGui.QKeySequence("Z"), self, self._toggle_xz)
        QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Up), self, lambda: self._step_z(4))
        QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Down), self, lambda: self._step_z(-4))

    # ---------- Loading ----------
    def load_file(self, idx):
        self._cancel_xz_timer()

        mrc = self.mrc_handles[idx]
        data = mrc.data  # memmap
        self.data = data
        self.Z, self.Y, self.X = data.shape
        self.x, self.y, self.z = self.X // 2, self.Y // 2, self.Z // 2

        self.cache.clear()
        self.view_xy.dynamic_fit = True
        self.view_xz.dynamic_fit = True

        # Contrast from header/subsample (fast)
        if TomoViewer.last_contrast:
            self.minv, self.maxv = TomoViewer.last_contrast
        else:
            amin, amax, amean = fast_header_stats(mrc, data)
            span = (amax - amin) / 2.0
            if span <= 0:
                self.minv, self.maxv = amin, amax
            else:
                rng = span / 1.5  # ~50% extra contrast
                self.minv, self.maxv = (amean - rng, amean + rng)

        # Histogram: only if XZ visible & requested
        if self.hist_widget:
            self.hist_widget.setParent(None)
            self.hist_widget = None
        if self.xz_visible and TomoViewer.last_hist_visible:
            hist, edges = subsampled_histogram(self.data)
            # Clamp initial thresholds into view range
            init_min, init_max = self.minv, self.maxv
            lo, hi = float(edges[0]), float(edges[-1])
            eps = 1e-6 * max(1.0, abs(hi - lo))
            init_min = float(np.clip(init_min, lo, hi - eps))
            init_max = float(np.clip(init_max, lo + eps, hi))
            self.hist_widget = HistogramWidget(hist, edges, init_min, init_max, verbose=self._verbose)
            self.hist_widget.contrast_changed.connect(self._set_contrast)
            self.top_split.addWidget(self.hist_widget)
            self.hist_widget.setVisible(True)
            self._set_hist_quarter()

        # Z scrollbar (connect only once)
        if not self._built_scroll_conn:
            self.scroll_z.valueChanged.connect(self._set_z)
            self._built_scroll_conn = True
        self.scroll_z.blockSignals(True)
        self.scroll_z.setRange(0, self.Z - 1)
        self.scroll_z.setValue(self.z)
        self.scroll_z.blockSignals(False)

        # Defer first render
        self.top_split.setVisible(self.xz_visible)
        QtCore.QTimer.singleShot(0, lambda: self._initial_paint())

    def _initial_paint(self):
        self._refresh_views(delayed_xz=self.xz_visible)
        self._set_hist_quarter()

    # ---------- Zero-copy QImage ----------
    def _qimg_from_slice(self, arr):
        arr8 = np.clip((arr - self.minv) / (self.maxv - self.minv), 0, 1)
        arr8 = (arr8 * 255).astype(np.uint8, copy=False)
        h, w = arr8.shape
        qimg = QtGui.QImage(arr8.data, w, h, arr8.strides[0], QtGui.QImage.Format_Grayscale8)
        return qimg, arr8  # keep numpy buffer alive via cache

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
        qimg, buf = self._qimg_from_slice(self.data[:, y, :])  # strided read (only when visible)
        self.cache.put(key, (qimg, buf))
        return (qimg, buf)

    # ---------- Rendering ----------
    def _refresh_views(self, delayed_xz=False):
        qimg_xy, _ = self._get_xy(self.z)
        self.view_xy.set_image(qimg_xy)
        self.view_xy.set_crosshair(self.x, self.y)

        if delayed_xz and self.xz_visible:
            self._schedule_xz_update()
        else:
            self._cancel_xz_timer()

        self._fit_views_only()
        self._update_status()

    def _update_xz_immediate(self):
        if not self.xz_visible:
            return
        qimg_xz, _ = self._get_xz(self.y)
        self.view_xz.set_image(qimg_xz)
        self.view_xz.set_crosshair(self.x, self.z)
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

    # ---------- Status / fit ----------
    def _fit_views_only(self):
        if self.view_xy.dynamic_fit:
            self.view_xy.fit_height()
        if self.xz_visible and self.view_xz.dynamic_fit:
            self.view_xz.fit_height()

    def _update_status(self):
        self.lbl.setText(f"{os.path.basename(self.files[self.idx])}  X:{self.x} Y:{self.y} Z:{self.z}")

    # ---------- Interactions ----------
    def _clicked_xy(self, x, y):
        self.x, self.y = x, y
        self._refresh_views(delayed_xz=self.xz_visible)

    def _clicked_xz(self, x, z):
        if not self.xz_visible:
            return
        self.x, self.z = x, z
        self.scroll_z.setValue(self.z)
        self._refresh_views(delayed_xz=self.xz_visible)

    def _step_z(self, step):
        self.z = int(np.clip(self.z + step, 0, self.Z - 1))
        self.scroll_z.blockSignals(True)
        self.scroll_z.setValue(self.z)
        self.scroll_z.blockSignals(False)
        # Cancel any existing pending render
        self._scroll_timer.stop()
        self._scroll_timer.start(10)  # 10 ms debounce

    def _set_z(self, val):
        self.z = val
        self._refresh_views(delayed_xz=self.xz_visible)

    def _set_contrast(self, minv, maxv):
        self.minv, self.maxv = minv, maxv
        TomoViewer.last_contrast = (minv, maxv)
        self.cache.clear()
        self._refresh_views(delayed_xz=self.xz_visible)
        self._set_hist_quarter()

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
                # clamp thresholds to show lines
                init_min, init_max = self.minv, self.maxv
                lo, hi = float(edges[0]), float(edges[-1])
                eps = 1e-6 * max(1.0, abs(hi - lo))
                init_min = float(np.clip(init_min, lo, hi - eps))
                init_max = float(np.clip(init_max, lo + eps, hi))
                self.hist_widget = HistogramWidget(hist, edges, init_min, init_max, verbose=self._verbose)
                self.hist_widget.contrast_changed.connect(self._set_contrast)
                self.top_split.addWidget(self.hist_widget)
            self.hist_widget.setVisible(True)
            TomoViewer.last_hist_visible = True
            self._set_hist_quarter()

    # NEW: Commit scroll changes after debounce
    def _scroll_commit(self):
        qimg_xy, _ = self._get_xy(self.z)
        self.view_xy.set_image(qimg_xy)
        self.view_xy.set_crosshair(self.x, self.y)
        if self.xz_visible:
            self.view_xz.set_crosshair(self.x, self.z)
        self._update_status()


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
                    self.hist_widget = HistogramWidget(hist, edges, init_min, init_max, verbose=self._verbose)
                    self.hist_widget.contrast_changed.connect(self._set_contrast)
                    self.top_split.addWidget(self.hist_widget)
                self.hist_widget.setVisible(True)
            self._update_xz_immediate()
            self._fit_views_only()
            self._set_hist_quarter()

    # ---------- File navigation (clamped) ----------
    def _prev_file(self):
        if self.idx > 0:
            self.idx -= 1
            self.load_file(self.idx)

    def _next_file(self):
        if self.idx < len(self.files) - 1:
            self.idx += 1
            self.load_file(self.idx)

# ---------------- Main ----------------
def main():
    parser = argparse.ArgumentParser(description="Fast MRC viewer (fomo)")
    parser.add_argument("path", help="MRC file or folder")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose tracing to stdout")

    # Scroll acceleration flags (with your requested defaults)
    parser.add_argument("--scroll-base", type=int, default=4,
                        help="Base slices per notch (default: 4)")
    parser.add_argument("--scroll-threshold", type=float, default=2.0,
                        help="Seconds between wheel events to count as fast (default: 2.0)")
    parser.add_argument("--scroll-mult", type=float, default=0.01,
                        help="Per-streak multiplier (default: 0.01)")
    parser.add_argument("--scroll-max-streak", type=int, default=4,
                        help="Max streak growth steps (default: 4)")

    args = parser.parse_args()

    verbose = args.verbose or os.environ.get("FOMO_VERBOSE", "") not in ("", "0", "false", "False")
    path = os.path.abspath(args.path)
    files = list_mrcs(path)
    if not files:
        sys.exit("No MRC files found.")

    app = QtWidgets.QApplication(sys.argv)
    w = TomoViewer(
        path,
        verbose=verbose,
        scroll_base=args.scroll_base,
        scroll_threshold=args.scroll_threshold,
        scroll_mult=args.scroll_mult,
        scroll_max_streak=args.scroll_max_streak,
    )
    w.resize(800, 850)  # <-- default window size
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
