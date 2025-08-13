import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

class HistogramWidget(QtWidgets.QWidget):
    contrast_changed = QtCore.pyqtSignal(float, float)

    def __init__(self, hist, edges, init_min, init_max, verbose=False, parent=None):
        super().__init__(parent)
        self.hist, self.edges = hist, edges
        self._verbose = verbose
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
