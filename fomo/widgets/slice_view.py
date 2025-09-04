import time
import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets

class SliceView(QtWidgets.QGraphicsView):
    clicked = QtCore.pyqtSignal(int, int)
    dragged = QtCore.pyqtSignal(int, int)
    released = QtCore.pyqtSignal()
    wheel_delta = QtCore.pyqtSignal(int)
    # Extended signal including mouse button and keyboard modifiers (as ints)
    clicked_ex = QtCore.pyqtSignal(int, int, int, int)

    def __init__(self, *, verbose=False, name="view",
                 scroll_base=4, scroll_threshold=2.0,
                 scroll_mult=0.01, scroll_max_streak=4,
                 sample_scale=1):
        super().__init__()
        self._verbose = verbose
        self._name = name

        self._BASE_STEP = int(scroll_base)
        self._STREAK_THRESHOLD = float(scroll_threshold)
        self._STREAK_MULT = float(scroll_mult)
        self._STREAK_MAX = int(scroll_max_streak)
        self._sample_scale = int(sample_scale) if int(sample_scale) > 0 else 1

        self.setScene(QtWidgets.QGraphicsScene(self))
        self.pixmap_item = self.scene().addPixmap(QtGui.QPixmap())
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(20, 20, 20)))
        pen = QtGui.QPen(QtGui.QColor(255, 235, 59))
        pen.setCosmetic(True)
        self.hline = self.scene().addLine(0, 0, 1, 0, pen)
        self.vline = self.scene().addLine(0, 0, 0, 1, pen)
        self.hline.setVisible(False)
        self.vline.setVisible(False)
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        # Displayed image dimensions (scene coordinates)
        self.img_w = 1
        self.img_h = 1
        # Source image dimensions (logical pixel grid)
        self.src_w = 1
        self.src_h = 1
        self.dynamic_fit = True
        self._drag_active = False

        self._wheel_last_ts = 0.0
        self._wheel_streak = 0

        self._picking_mode = False
        self._tmp_drag_mode = None

    def set_image(self, qimg):
        # Original image size
        self.src_w = qimg.width()
        self.src_h = qimg.height()
        # Displayed size with supersampling
        self.img_w = self.src_w * self._sample_scale
        self.img_h = self.src_h * self._sample_scale
        if self._sample_scale != 1:
            try:
                qimg_disp = qimg.scaled(
                    self.img_w,
                    self.img_h,
                    transformMode=QtCore.Qt.FastTransformation,
                )
            except Exception:
                qimg_disp = qimg
        else:
            qimg_disp = qimg
        self.pixmap_item.setPixmap(QtGui.QPixmap.fromImage(qimg_disp))
        self.scene().setSceneRect(0, 0, self.img_w, self.img_h)
        if self.dynamic_fit:
            self.fit_height()
        self.viewport().update()

    def set_crosshair(self, x, y):
        sx = x * self._sample_scale
        sy = y * self._sample_scale
        self.hline.setLine(0, sy + 0.5, self.img_w, sy + 0.5)
        self.vline.setLine(sx + 0.5, 0, sx + 0.5, self.img_h)
        self.hline.setVisible(True)
        self.vline.setVisible(True)

    def hide_crosshair(self):
        self.hline.setVisible(False)
        self.vline.setVisible(False)

    def set_cursor_mode(self, picking):
        """Switch between hand-drag and normal arrow cursor for picking mode."""
        self._picking_mode = picking
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
        if ev.button() in (QtCore.Qt.LeftButton, QtCore.Qt.RightButton):
            pos = self.mapToScene(ev.pos())
            x_f, y_f = pos.x(), pos.y()
            if 0 <= x_f < self.img_w and 0 <= y_f < self.img_h:
                x = int(np.clip(round(x_f / self._sample_scale), 0, self.src_w - 1))
                y = int(np.clip(round(y_f / self._sample_scale), 0, self.src_h - 1))
                if ev.button() == QtCore.Qt.LeftButton:
                    self.clicked.emit(x, y)
                    self._drag_active = True
                # Always emit extended click with button + modifiers
                self.clicked_ex.emit(x, y, int(ev.button()), int(ev.modifiers()))
            else:
                if self._picking_mode:
                    self._tmp_drag_mode = self.dragMode()
                    self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
                super().mousePressEvent(ev)
                return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._drag_active:
            pos = self.mapToScene(ev.pos())
            x = int(np.clip(round(pos.x() / self._sample_scale), 0, self.src_w - 1))
            y = int(np.clip(round(pos.y() / self._sample_scale), 0, self.src_h - 1))
            self.dragged.emit(x, y)
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == QtCore.Qt.LeftButton and self._drag_active:
            self._drag_active = False
            self.released.emit()
        super().mouseReleaseEvent(ev)
        if self._tmp_drag_mode is not None:
            if self._picking_mode:
                self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            else:
                self.setDragMode(self._tmp_drag_mode)
            self._tmp_drag_mode = None
