# fomo/features/picking.py
from PyQt5 import QtCore, QtGui
import numpy as np

class PickingModeHandler:
    """
    Encapsulates filament picking + custom-plane definition and rendering.
    Keeps logic separate from the main viewer for easier maintenance.
    """

    def __init__(self, viewer):
        self.viewer = viewer
        self._active = False
        self._points = []  # [(x,y,z), (x,y,z)]
        self._saved_layout = None  # (xz_visible, hist_visible)

    # -------- Public API --------
    def is_active(self):
        return self._active

    def enter(self):
        """Activate picking mode: arrow cursor, hide heavy panels, save layout."""
        if self._active:
            return
        self._active = True
        self._points.clear()

        # Save and hide layout components for performance
        xz_vis = getattr(self.viewer, "xz_visible", True)
        hist_vis = bool(self.viewer.hist_widget.isVisible()) if self.viewer.hist_widget else False
        self._saved_layout = (xz_vis, hist_vis)

        if self.viewer.hist_widget:
            self.viewer.hist_widget.setVisible(False)
        self.viewer.top_split.setVisible(False)
        self.viewer.xz_visible = False

        # Cursor: arrow + no-drag in picking mode
        self._set_cursor(True)

        # Optional: if viewer supports disabling file switching
        if hasattr(self.viewer, "disable_file_switching"):
            self.viewer.disable_file_switching(True)

        # UI status
        self._append_status(" | PICKING MODE ACTIVATED")

    def exit(self):
        """Deactivate picking mode: restore layout, hand cursor, clear picks."""
        if not self._active:
            return
        self._active = False
        self._points.clear()

        # Restore layout
        if self._saved_layout is not None:
            xz_vis, hist_vis = self._saved_layout
            self.viewer.xz_visible = xz_vis
            self.viewer.top_split.setVisible(xz_vis)
            if hist_vis and self.viewer.hist_widget:
                self.viewer.hist_widget.setVisible(True)
        self._saved_layout = None

        # Cursor back to hand-drag
        self._set_cursor(False)

        if hasattr(self.viewer, "disable_file_switching"):
            self.viewer.disable_file_switching(False)

        # Clean up status tag
        self._remove_status_tag(" | PICKING MODE ACTIVATED")

        # Ensure normal view is restored/redrawn
        if hasattr(self.viewer, "_refresh_views"):
            self.viewer._refresh_views(delayed_xz=self.viewer.xz_visible)

    def add_point_under_cursor(self):
        """Add a pick at current cursor position on the XY view."""
        if not self._active:
            return
        pos = self.viewer.view_xy.mapToScene(self.viewer.view_xy.mapFromGlobal(QtGui.QCursor.pos()))
        x = int(np.clip(round(pos.x()), 0, self.viewer.X - 1))
        y = int(np.clip(round(pos.y()), 0, self.viewer.Y - 1))
        z = int(self.viewer.z)
        self._add_point((x, y, z))

    def _add_point(self, p):
        """Internal: add a point and act when we have two."""
        self._points.append(p)

        # Optional marker if viewer provides it
        if hasattr(self.viewer, "draw_marker_xy"):
            try:
                self.viewer.draw_marker_xy(p[0], p[1], QtGui.QColor(255, 0, 0))
            except Exception:
                pass

        if len(self._points) == 2:
            p1, p2 = self._points
            self._show_custom_plane(p1, p2)
            # keep points or clear — choose to clear to allow new pair immediately
            self._points.clear()

    # -------- Helpers --------
    def _set_cursor(self, picking: bool):
        """Switch cursors for both views."""
        for view in (self.viewer.view_xy, self.viewer.view_xz):
            if hasattr(view, "set_cursor_mode"):
                view.set_cursor_mode(picking)
            else:
                # Fallback if method missing
                if picking:
                    view.setDragMode(view.NoDrag)
                    view.viewport().setCursor(QtCore.Qt.ArrowCursor)
                else:
                    view.setDragMode(view.ScrollHandDrag)
                    view.viewport().unsetCursor()

    def _append_status(self, suffix: str):
        try:
            self.viewer.lbl.setText(self.viewer.lbl.text() + suffix)
        except Exception:
            pass

    def _remove_status_tag(self, tag: str):
        try:
            self.viewer.lbl.setText(self.viewer.lbl.text().replace(tag, ""))
        except Exception:
            pass

    # -------- Custom plane rendering --------
    def _show_custom_plane(self, p1, p2):
        """
        Resample and render a custom plane in the XY view using a plane
        defined by two picked points. Keeps it lightweight (NumPy only).
        """
        vol = self.viewer.data  # shape (Z, Y, X)
        Z, Y, X = vol.shape

        # Basis from p1->p2
        p1 = np.array(p1, dtype=np.float32)
        p2 = np.array(p2, dtype=np.float32)
        v = p2 - p1
        nv = np.linalg.norm(v)
        if nv < 1e-6:
            return
        v = v / nv  # "new Z" axis for the plane direction

        # Build orthonormal frame (v, a, b) where a,b span the plane
        # Start with a provisional axis not colinear with v
        up = np.array([0, 0, 1], dtype=np.float32)
        if abs(np.dot(v, up)) > 0.9:
            up = np.array([0, 1, 0], dtype=np.float32)
        a = np.cross(v, up)
        a_norm = np.linalg.norm(a)
        if a_norm < 1e-6:
            a = np.array([1, 0, 0], dtype=np.float32)
            a_norm = 1.0
        a /= a_norm
        b = np.cross(v, a)
        b /= max(np.linalg.norm(b), 1e-6)

        # Sampling grid: width fixed at 40 px along 'a', height along 'b'
        width = 40
        half_w = width // 2

        # Height — pick something meaningful: distance between z's OR full span between p1 and p2
        # We’ll use Euclidean distance projected onto v for stability:
        height = int(round(nv)) or 1

        # Build grid (iy along b, ix along a)
        ix = np.arange(-half_w, half_w, dtype=np.float32)
        iy = np.arange(0, height, dtype=np.float32)
        grid_x, grid_y = np.meshgrid(ix, iy)  # shape (H, W)

        # Coordinates in volume space
        coords = (p1[None, None, :] +
                  grid_x[..., None] * a[None, None, :] +
                  grid_y[..., None] * v[None, None, :])  # (H, W, 3)

        # Trilinear interpolation (vectorized)
        plane = self._trilinear(vol, coords)

        # Display in XY view
        qimg, _ = self.viewer._qimg_from_slice(plane)
        self.viewer.view_xy.set_image(qimg)
        self.viewer.view_xy.dynamic_fit = True
        self.viewer.view_xy.fit_height()

    @staticmethod
    def _trilinear(vol, coords):
        """
        vol: (Z, Y, X), coords: (H, W, 3) in (x, y, z) order
        Returns: (H, W) float32
        """
        Z, Y, X = vol.shape
        x = coords[..., 0]
        y = coords[..., 1]
        z = coords[..., 2]

        # Clamp to valid range
        x = np.clip(x, 0, X - 1)
        y = np.clip(y, 0, Y - 1)
        z = np.clip(z, 0, Z - 1)

        x0 = np.floor(x).astype(np.int32); x1 = np.clip(x0 + 1, 0, X - 1)
        y0 = np.floor(y).astype(np.int32); y1 = np.clip(y0 + 1, 0, Y - 1)
        z0 = np.floor(z).astype(np.int32); z1 = np.clip(z0 + 1, 0, Z - 1)

        xd = x - x0; yd = y - y0; zd = z - z0

        c000 = vol[z0, y0, x0]
        c100 = vol[z0, y0, x1]
        c010 = vol[z0, y1, x0]
        c110 = vol[z0, y1, x1]
        c001 = vol[z1, y0, x0]
        c101 = vol[z1, y0, x1]
        c011 = vol[z1, y1, x0]
        c111 = vol[z1, y1, x1]

        c00 = c000 * (1 - xd) + c100 * xd
        c01 = c001 * (1 - xd) + c101 * xd
        c10 = c010 * (1 - xd) + c110 * xd
        c11 = c011 * (1 - xd) + c111 * xd

        c0 = c00 * (1 - yd) + c10 * yd
        c1 = c01 * (1 - yd) + c11 * yd

        c = c0 * (1 - zd) + c1 * zd
        return c.astype(np.float32)
