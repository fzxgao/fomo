import time
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

class SliceView(QtWidgets.QGraphicsView):
    clicked = QtCore.pyqtSignal(int, int)
    wheel_delta = QtCore.pyqtSignal(int)

    def __init__(self, *, verbose=False, name="view",
                 scroll_base=4, scroll_threshold=2.0,
                 scroll_mult=0.01, scroll_max_streak=4):
        super().__init__()
        self._verbose = verbose
        self._name = name

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
        
    def set_cursor_mode(self, picking):
        """Switch between hand-drag and normal arrow cursor for picking mode."""
        if picking:
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            self.viewport().setCursor(QtCore.Qt.ArrowCursor)
        else:
            self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
            self.viewport().unsetCursor()

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
            step = 1.001 ** ev.angleDelta().y()
            self.scale(step, step)
            self.dynamic_fit = False
        else:
            dy = ev.angleDelta().y()
            if dy != 0:
                now = time.perf_counter()
                dt = now - self._wheel_last_ts if self._wheel_last_ts else 999
                self._wheel_last_ts = now

                if dt < self._STREAK_THRESHOLD:
                    self._wheel_streak = min(self._wheel_streak + 1, self._STREAK_MAX)
                else:
                    self._wheel_streak = 0

                ticks = abs(dy) / 120.0
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

    def set_cursor_mode(self, picking):
        if picking:
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            self.viewport().setCursor(QtCore.Qt.ArrowCursor)
        else:
            self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
            self.viewport().unsetCursor()
