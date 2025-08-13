# fomo/accel.py
import time
from PyQt5 import QtCore

class ScrollAccelerator:
    """
    Helper class to handle accelerated scroll wheel motion for slice navigation.
    """
    def __init__(self, base_step=4, streak_threshold=2.0, streak_mult=0.01, streak_max=4, verbose=False, name="view"):
        self._BASE_STEP = int(base_step)
        self._STREAK_THRESHOLD = float(streak_threshold)
        self._STREAK_MULT = float(streak_mult)
        self._STREAK_MAX = int(streak_max)
        self._verbose = verbose
        self._name = name

        self._wheel_last_ts = 0.0
        self._wheel_streak = 0

    def process_wheel_event(self, ev):
        """
        Given a QWheelEvent, returns the step count (positive or negative)
        for slice movement. Returns None if Control is pressed (zooming case).
        """
        if ev.modifiers() & QtCore.Qt.ControlModifier:
            return None

        dy = ev.angleDelta().y()  # typical notch: ±120
        if dy == 0:
            return 0

        now = time.perf_counter()
        dt = now - self._wheel_last_ts if self._wheel_last_ts else 999
        self._wheel_last_ts = now

        # Update streak if scrolling fast enough
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

        return step
