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
        # Store last confirmed pair defining the custom plane
        self._line = None  # (p1, p2) as float32 arrays
        self._base_z = 0.0  # viewer.z when _line was set
        # Parameters describing the current custom plane
        self._plane_origin = None
        self._plane_a = None
        self._plane_v = None
        self._plane_half_w = 0
        self._plane_height = 0
        self._plane_b = None
        self._window_width = None
        # Plane editing state
        self._plane_editing = False
        self._plane_marker_items = []
        self._plane_points_world = []

    # -------- Public API --------
    def is_active(self):
        return self._active

    def enter(self):
        """Activate picking mode: arrow cursor, hide heavy panels, save layout."""
        if self._active:
            return
        self._active = True
        self._points.clear()
        self._line = None

        # Save and hide layout components for performance
        xz_vis = getattr(self.viewer, "xz_visible", True)
        hist_vis = bool(self.viewer.hist_widget.isVisible()) if self.viewer.hist_widget else False
        self._saved_layout = (xz_vis, hist_vis)

        if self.viewer.hist_widget:
            self.viewer.hist_widget.setVisible(False)
        self.viewer.top_split.setVisible(False)
        self.viewer.xz_visible = False
        try:
            type(self.viewer).last_hist_visible = False
        except Exception:
            pass

        # Show side panel and expand window width by 25%
        try:
            self._window_width = self.viewer.width()
            side_w = int(self._window_width * 0.25)
            self.viewer.picking_panel.setFixedWidth(side_w)
            self.viewer.picking_panel.setVisible(True)
            self.viewer.resize(self._window_width + side_w*3, self.viewer.height())
        except Exception:
            pass

        # Hide any existing crosshair when picking
        if hasattr(self.viewer, "_hide_crosshair"):
            self.viewer._hide_crosshair()

        # Cursor: arrow + no-drag in picking mode
        self._set_cursor(True)

        # Disable file switching
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
        self.finish_plane()


        # Restore layout
        if self._saved_layout is not None:
            xz_vis, hist_vis = self._saved_layout
            self.viewer.xz_visible = xz_vis
            self.viewer.top_split.setVisible(xz_vis)
            if hist_vis and self.viewer.hist_widget:
                self.viewer.hist_widget.setVisible(True)
            try:
                type(self.viewer).last_hist_visible = hist_vis
            except Exception:
                pass
        self._saved_layout = None

        # Cursor back to hand-drag
        self._set_cursor(False)

        if hasattr(self.viewer, "disable_file_switching"):
            self.viewer.disable_file_switching(False)

        # Clean up status tag
        self._remove_status_tag(" | PICKING MODE ACTIVATED")

        # Remove any marker that might remain from picking
        if hasattr(self.viewer, "clear_marker_xy"):
            try:
                self.viewer.clear_marker_xy()
            except Exception:
                pass

        # Ensure normal view is restored/redrawn
        if hasattr(self.viewer, "_refresh_views"):
            self.viewer._refresh_views(delayed_xz=self.viewer.xz_visible)

        # Hide side panel and restore window width
        try:
            if self._window_width is not None:
                self.viewer.picking_panel.setVisible(False)
                self.viewer.picking_panel.setFixedWidth(0)
                self.viewer.resize(self._window_width, self.viewer.height())
        except Exception:
            pass
        self._window_width = None

    def add_point_under_cursor(self):
        """Add a pick at current cursor position on the XY view."""
        if not self._active:
            return
        pos = self.viewer.view_xy.mapToScene(
            self.viewer.view_xy.mapFromGlobal(QtGui.QCursor.pos())
        )
        x = int(np.clip(round(pos.x()), 0, self.viewer.view_xy.img_w - 1))
        y = int(np.clip(round(pos.y()), 0, self.viewer.view_xy.img_h - 1))
        xw, yw, zw = self.map_xy_to_volume(x, y)
        self._add_point((xw, yw, zw))

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
    def has_plane(self):
        """Return True if a custom plane is currently displayed."""
        return self._line is not None
    def map_xy_to_volume(self, x, y):
        """Map XY view pixel coordinates to original volume coordinates."""
        if self.has_plane() and self._plane_origin is not None:
            world = (
                self._plane_origin
                + (x - self._plane_half_w) * self._plane_a
                + y * self._plane_v
            )
            return tuple(int(round(c)) for c in world)
        else:
            return int(x), int(y), int(self.viewer.z)
    def _show_custom_plane(self, p1, p2):
        """Store picked points and render their orthogonal plane."""
        p1 = np.array(p1, dtype=np.float32)
        p2 = np.array(p2, dtype=np.float32)
        self._line = (p1.copy(), p2.copy())
        self._base_z = float(self.viewer.z)
        self._plane_points_world.clear()
        self._clear_plane_annotations()
        self._render_plane(p1, p2)
        self._plane_editing = True

    def update_plane_for_z(self, z):
        """Rebuild the custom plane translated along the original Z axis."""
        if not self.has_plane():
            return
        offset = float(z) - self._base_z
        p1, p2 = self._line
        shift = np.array([0.0, 0.0, offset], dtype=np.float32)
        self._render_plane(p1 + shift, p2 + shift)

    def _render_plane(self, p1, p2):
        """Resample and render a custom plane in the XY view."""
        vol = self.viewer.data  # shape (Z, Y, X)
        Z, Y, X = vol.shape

        v = p2 - p1
        nv = np.linalg.norm(v)
        if nv < 1e-6:
            return
        v = v / nv  # "new Z" axis for the plane direction

        # Build orthonormal frame (v, a, b) where a,b span the plane
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

        # Store plane parameters for coordinate mapping
        self._plane_origin = p1.copy()
        self._plane_a = a
        self._plane_v = v
        self._plane_half_w = half_w
        # Height — pick something meaningful: distance between z's OR full span between p1 and p2
        # We’ll use Euclidean distance projected onto v for stability:
        height = int(round(nv)) or 1
        self._plane_height = height
        self._plane_b = b

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
        self._redraw_plane_annotations()
    # ----- Plane annotation helpers -----
    def is_plane_editing(self):
        return self._plane_editing

    def _clear_plane_annotations(self):
        scene = self.viewer.view_xy.scene()
        for item in self._plane_marker_items:
            try:
                scene.removeItem(item)
            except Exception:
                pass
        self._plane_marker_items.clear()

    def _redraw_plane_annotations(self):
        scene = self.viewer.view_xy.scene()
        for item in self._plane_marker_items:
            try:
                scene.removeItem(item)
            except Exception:
                pass
        self._plane_marker_items.clear()

        if not self._plane_points_world or self._plane_origin is None:
            return

        pen = QtGui.QPen(QtGui.QColor(0, 0, 255))
        pen.setWidth(2)
        pen.setCosmetic(True)

        origin = self._plane_origin
        a = self._plane_a
        v = self._plane_v
        b = self._plane_b
        half_w = self._plane_half_w
        height = self._plane_height

        projected = []  # (idx, x, y) for visible points
        for idx, w in enumerate(self._plane_points_world):
            w = np.array(w, dtype=np.float32)
            vec = w - origin
            if b is not None and abs(np.dot(vec, b)) > 0.5:
                continue
            x = float(np.dot(vec, a))
            y = float(np.dot(vec, v))
            if x < -half_w or x > half_w or y < 0 or y > height:
                continue
            px = x + half_w
            py = y
            half = 3
            h = scene.addLine(px - half, py, px + half, py, pen)
            vline = scene.addLine(px, py - half, px, py + half, pen)
            self._plane_marker_items.extend([h, vline])
            projected.append((idx, px, py))

        for (pi, x1, y1), (ci, x2, y2) in zip(projected, projected[1:]):
            if ci == pi + 1:
                line = scene.addLine(x1, y1, x2, y2, pen)
                self._plane_marker_items.append(line)

    def add_plane_marker(self, view_pos, world_pos):
        if not self._plane_editing:
            return
        self._plane_points_world.append(tuple(float(c) for c in world_pos))
        self._redraw_plane_annotations()
        wx, wy, wz = world_pos
        print(f"X={int(round(wx))} Y={int(round(wy))} Z={int(round(wz))}")

    def finish_plane(self):
        self._clear_plane_annotations()
        self._line = None
        self._plane_origin = None
        self._plane_a = None
        self._plane_v = None
        self._plane_half_w = 0
        self._plane_height = 0
        self._plane_b = None
        self._plane_editing = False
        self._plane_points_world.clear()
        try:
            self.viewer._refresh_views(delayed_xz=self.viewer.xz_visible)
        except Exception:
            pass

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
