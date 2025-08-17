# fomo/features/picking.py
from PyQt5 import QtCore, QtGui
import numpy as np
from pathlib import Path
import re

from .realtime_extraction import extract_particles_on_exit

# Distance in pixels at which annotations become fully transparent.
FADE_DIST = 10

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
        # Save original viewer geometry when entering picking mode so we can
        # restore it exactly on exit without incremental growth.
        self._window_geometry = None
        # Plane editing state
        self._plane_editing = False
        self._plane_marker_items = []
        self._plane_points_world = []
        self._editing_paths = None  # (raw_path, xyz_path) when editing existing filaments
        self._drag_index = None
        self._dragging = False
        # Track whether the current drag target was an existing point or a new one
        self._drag_existing = False

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
            # Persist full geometry so the window can be restored precisely.
            self._window_geometry = self.viewer.saveGeometry()
            self._window_width = self.viewer.width()
            h = self.viewer.height()
            side_w = int(self._window_width * 0.25)
            self.viewer.picking_panel.setFixedWidth(side_w)
            self.viewer.picking_panel.setVisible(True)
            self.viewer.resize(self._window_width + side_w * 3, h)
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
        extract_particles_on_exit(self.viewer)

        self.cleanup_empty_model_dirs()

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

        # Clean up status tags and reset status label
        #
        # When particles are picked or positions edited, ``finish_plane``
        # appends a " | Points exported" message to the main status label.
        # The label grows with every picking session which in turn expands
        # the window's minimum width.  Subsequent calls to ``enter`` capture
        # this wider geometry causing the window to grow on every
        # enter/exit cycle.  Remove any transient status messages and reset
        # the label before restoring the original geometry so that the
        # window size remains stable.
        self._remove_status_tag(" | PICKING MODE ACTIVATED")
        self._remove_status_tag(" | Points exported")
        if hasattr(self.viewer, "_update_status"):
            try:
                self.viewer._update_status()
                if hasattr(self.viewer.lbl, "adjustSize"):
                    self.viewer.lbl.adjustSize()
            except Exception:
                pass

        # Remove any marker that might remain from picking
        if hasattr(self.viewer, "clear_marker_xy"):
            try:
                self.viewer.clear_marker_xy()
            except Exception:
                pass

        # Ensure normal view is restored/redrawn
        if hasattr(self.viewer, "_refresh_views"):
            self.viewer._refresh_views(delayed_xz=self.viewer.xz_visible)
            if hasattr(self.viewer.lbl, "adjustSize"):
                try:
                    self.viewer.lbl.adjustSize()
                except Exception:
                    pass

        # Hide side panel and restore original window geometry
        try:
            if self._window_geometry is not None:
                self.viewer.picking_panel.setVisible(False)
                self.viewer.picking_panel.setFixedWidth(0)
                # Restore the exact geometry captured on entry
                try:
                    self.viewer.restoreGeometry(self._window_geometry)
                except Exception:
                    # Fallback if restoreGeometry unavailable
                    geom = self.viewer.geometry()
                    self.viewer.setGeometry(geom.x(), geom.y(),
                                            self._window_width or geom.width(),
                                            geom.height())
                if self._window_width is not None:
                    self.viewer.resize(self._window_width, self.viewer.height())
        except Exception:
            pass
        self._window_geometry = None
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

    def cancel_points(self):
        """Clear any in-progress points defining a new plane."""
        self._points.clear()

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

    def cleanup_empty_model_dirs(self):
        """Remove empty volume directories for the current tomogram."""
        try:
            tomogram_path = Path(self.viewer.files[self.viewer.idx])
            tomogram_name = tomogram_path.stem
            root_dir = Path.cwd() / "fomo_dynamo_catalogue"
            tomo_dir = root_dir / "tomograms"
            if not tomo_dir.exists():
                return
            removed = False
            for d in list(tomo_dir.iterdir()):
                if d.is_dir() and d.name.endswith(tomogram_name) and not any(d.iterdir()):
                    try:
                        d.rmdir()
                        removed = True
                    except Exception:
                        pass
            if removed:
                try:
                    if not any(tomo_dir.iterdir()):
                        tomo_dir.rmdir()
                        if not any(root_dir.iterdir()):
                            root_dir.rmdir()
                except Exception:
                    pass
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
            return tuple(float(c) for c in world)
        else:
            return float(x), float(y), float(self.viewer.z)

    def volume_to_plane(self, x, y, z):
        """Project a world coordinate (x, y, z) into plane-local (px, py)."""
        if not (self.has_plane() and self._plane_origin is not None):
            return float(x), float(y)

        w = np.array([x, y, z], dtype=np.float32)
        vec = w - self._plane_origin
        px = float(np.dot(vec, self._plane_a)) + self._plane_half_w
        py = float(np.dot(vec, self._plane_v))
        return px, py
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

        origin = self._plane_origin
        a = self._plane_a
        v = self._plane_v
        b = self._plane_b
        half_w = self._plane_half_w
        height = self._plane_height

        fade_dist = FADE_DIST  # distance at which annotations become fully transparent

        projected = []  # (idx, x, y, alpha) for visible points
        for idx, w in enumerate(self._plane_points_world):
            w = np.array(w, dtype=np.float32)
            vec = w - origin
            dist = abs(np.dot(vec, b)) if b is not None else 0.0
            if dist > fade_dist:
                continue
            alpha = max(0.0, 1.0 - dist / fade_dist)
            x = float(np.dot(vec, a))
            y = float(np.dot(vec, v))
            if x < -half_w or x > half_w or y < 0 or y > height:
                continue
            px = x + half_w
            py = y
            half = 3
            color = QtGui.QColor(0, 0, 255, int(alpha * 255))
            pen = QtGui.QPen(color)
            pen.setWidth(2)
            pen.setCosmetic(True)
            h = scene.addLine(px - half, py, px + half, py, pen)
            vline = scene.addLine(px, py - half, px, py + half, pen)
            self._plane_marker_items.extend([h, vline])
            projected.append((idx, px, py, alpha))

        for (pi, x1, y1, a1), (ci, x2, y2, a2) in zip(projected, projected[1:]):
            if ci == pi + 1:
                alpha = (a1 + a2) / 2.0
                color = QtGui.QColor(0, 0, 255, int(alpha * 255))
                pen = QtGui.QPen(color)
                pen.setWidth(2)
                pen.setCosmetic(True)
                line = scene.addLine(x1, y1, x2, y2, pen)
                self._plane_marker_items.append(line)

    def _find_nearest_plane_point(self, view_pos, threshold=5):
        if not self._plane_points_world or self._plane_origin is None:
            return None
        px, py = view_pos
        origin = self._plane_origin
        a = self._plane_a
        v = self._plane_v
        half_w = self._plane_half_w
        nearest = None
        min_dist = float("inf")
        for idx, w in enumerate(self._plane_points_world):
            vec = np.array(w, dtype=np.float32) - origin
            x = float(np.dot(vec, a)) + half_w
            y = float(np.dot(vec, v))
            dist = float(np.hypot(px - x, py - y))
            if dist < threshold and dist < min_dist:
                nearest = idx
                min_dist = dist
        return nearest

    def add_plane_marker(self, view_pos, world_pos):
        if not self._plane_editing:
            return
        idx = self._find_nearest_plane_point(view_pos)
        if idx is not None:
            self._drag_index = idx
            self._dragging = False
            self._drag_existing = True
        else:
            self._plane_points_world.append(tuple(float(c) for c in world_pos))
            self._redraw_plane_annotations()
            self._drag_index = len(self._plane_points_world) - 1
            self._dragging = False
            wx, wy, wz = world_pos
            self._drag_existing = False
            print(f"X={int(round(wx))} Y={int(round(wy))} Z={int(round(wz))}")

    def move_plane_marker(self, x, y):
        if not self._plane_editing or self._drag_index is None:
            return
        wx, wy, wz = self.map_xy_to_volume(x, y)
        self._plane_points_world[self._drag_index] = (float(wx), float(wy), float(wz))
        self._dragging = True
        self._redraw_plane_annotations()

    def release_plane_marker(self):
        if not self._plane_editing:
            return
        if self._drag_index is not None:
            if self._drag_existing and not self._dragging:
                try:
                    self._plane_points_world.pop(self._drag_index)
                except Exception:
                    pass
                self._redraw_plane_annotations()
        self._drag_index = None
        self._dragging = False
        self._drag_existing = False

    def _extract_particles(self, points, overwrite_tbl: Path = None):
        panel = getattr(self.viewer, "picking_panel", None)
        if panel is None:
            return None
        smooth_radius = getattr(panel.smooth_radius, "value", lambda: 5)()
        smooth_interval = getattr(panel.smooth_interval, "value", lambda: 2)()
        dz = getattr(panel.subunits_dz, "value", lambda: 7)()
        dphi = getattr(panel.subunits_dphi, "value", lambda: 20)()
        pts = np.array(points, dtype=np.float32)
        if pts.shape[0] < 2:
            return None
        diffs = np.diff(pts, axis=0)
        dists = np.linalg.norm(diffs, axis=1)
        cum = np.concatenate(([0.0], np.cumsum(dists)))
        if cum[-1] <= 0:
            return None
        s = np.arange(0, cum[-1] + 1e-6, smooth_interval)
        resampled = np.stack([np.interp(s, cum, pts[:, i]) for i in range(3)], axis=1)
        radius = max(1, int(round(smooth_radius / smooth_interval)))
        kernel = np.ones(2 * radius + 1, dtype=np.float32)
        kernel /= kernel.sum()
        padded = np.pad(resampled, ((radius, radius), (0, 0)), mode="edge")
        smooth = np.stack(
            [np.convolve(padded[:, i], kernel, mode="valid") for i in range(3)],
            axis=1,
        )
        diffs = np.diff(smooth, axis=0)
        dists = np.linalg.norm(diffs, axis=1)
        cum = np.concatenate(([0.0], np.cumsum(dists)))
        s = np.arange(0, cum[-1] + 1e-6, dz)
        sampled = np.stack([np.interp(s, cum, smooth[:, i]) for i in range(3)], axis=1)
        tangents = np.zeros_like(sampled)
        if len(sampled) > 1:
            tangents[1:-1] = sampled[2:] - sampled[:-2]
            tangents[0] = sampled[1] - sampled[0]
            tangents[-1] = sampled[-1] - sampled[-2]
        norms = np.linalg.norm(tangents, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        tangents /= norms
        tdrot = np.degrees(np.arctan2(tangents[:, 0], tangents[:, 1]))
        tilt = np.degrees(np.arccos(tangents[:, 2]))
        idx = np.arange(len(tdrot))
        narot = (-tdrot + idx * dphi + 180) % 360 - 180
        # Prepare Dynamo raw.tbl output
        tomogram_path = Path(self.viewer.files[self.viewer.idx])
        tomogram_name = tomogram_path.stem

        root_dir = Path.cwd() / "fomo_dynamo_catalogue"
        tomo_dir = root_dir / "tomograms"
        tomo_dir.mkdir(parents=True, exist_ok=True)

        target_dir = None
        tomogram_number = None
        if overwrite_tbl is not None:
            outfile = Path(overwrite_tbl)
            target_dir = outfile.parent
            m = re.match(r"^volume_(\d+)_", target_dir.name)
            if m:
                tomogram_number = int(m.group(1))
        else:
            for d in tomo_dir.iterdir():
                if d.is_dir() and d.name.endswith(tomogram_name):
                    target_dir = d
                    m = re.match(r"^volume_(\d+)_", d.name)
                    if m:
                        tomogram_number = int(m.group(1))
                    break
            if target_dir is None:
                existing = []
                for d in tomo_dir.iterdir():
                    m = re.match(r"^volume_(\d+)_", d.name)
                    if m:
                        existing.append(int(m.group(1)))
                tomogram_number = max(existing or [0]) + 1
                target_dir = tomo_dir / f"volume_{tomogram_number}_{tomogram_name}"
                target_dir.mkdir(parents=True, exist_ok=True)

        filament_number = None
        if overwrite_tbl is None:
            existing_filaments = []
            for f in target_dir.glob("raw_*.tbl"):
                m = re.match(r"raw_(\d+)\.tbl", f.name)
                if m:
                    existing_filaments.append(int(m.group(1)))
            filament_number = max(existing_filaments or [0]) + 1

        n = len(sampled)
        tag = np.arange(1, n + 1)
        ones = np.ones(n, dtype=int)
        zeros = np.zeros(n)
        data = np.column_stack([
            tag,            # 1 tag
            ones,           # 2 aligned
            ones,           # 3 averaged
            tangents[:, 0], # 4 dx
            tangents[:, 1], # 5 dy
            tangents[:, 2], # 6 dz
            tdrot,          # 7 tdrot
            tilt,           # 8 tilt
            narot,          # 9 narot
            zeros,          # 10 cc
            zeros,          # 11 cc2
            zeros,          # 12 cpu
            ones,           # 13 ftype
            np.full(n, -60),# 14 ymintilt
            np.full(n, 60), # 15 ymaxtilt
            np.full(n, -60),# 16 xmintilt
            np.full(n, 60), # 17 xmaxtilt
            zeros,          # 18 fs1
            zeros,          # 19 fs2
            np.full(n, tomogram_number), # 20 tomo
            zeros,          # 21 reg
            zeros,          # 22 class
            zeros,          # 23 annotation
            sampled[:, 0],  # 24 x
            sampled[:, 1],  # 25 y
            sampled[:, 2],  # 26 z
            zeros,          # 27 dshift
            zeros,          # 28 daxis
            zeros,          # 29 dnarot
            zeros,          # 30 dcc
            zeros,          # 31 otag
            ones,           # 32 npar
            zeros,          # 33
            zeros,          # 34 ref
            zeros,          # 35 sref
        ])

        fmt = [
            '%d', '%d', '%d',
            '%.6f', '%.6f', '%.6f',
            '%.2f', '%.2f', '%.2f',
            '%d', '%d', '%d',
            '%d', '%d', '%d', '%d', '%d',
            '%d', '%d', '%d',
            '%d', '%d', '%d',
            '%.1f', '%.1f', '%.1f',
            '%d', '%d', '%d', '%d',
            '%d', '%d', '%d', '%d', '%d'
        ]

        if overwrite_tbl is not None:
            outfile = Path(overwrite_tbl)
        else:
            outfile = target_dir / f"raw_{filament_number:03d}.tbl"
        np.savetxt(outfile, data, fmt=fmt, delimiter=" ")
        # Return path and the smoothed backbone for rendering
        return outfile, smooth

    def finish_plane(self):
        exported = False
        if self._plane_points_world:
            try:
                existing_raw = existing_xyz = None
                if self._editing_paths is not None:
                    existing_raw, existing_xyz = self._editing_paths
                result = self._extract_particles(self._plane_points_world, overwrite_tbl=existing_raw)
                if result is not None:
                    outfile, smooth = result
                    pts_arr = np.array(self._plane_points_world, dtype=np.float32)
                    if existing_xyz is not None:
                        xyz_path = Path(existing_xyz)
                    else:
                        xyz_path = outfile.with_name(outfile.name.replace("raw_", "xyz_").replace(".tbl", ".csv"))
                    np.savetxt(xyz_path, pts_arr, fmt="%.6f", delimiter=",")
                    if hasattr(self.viewer, "add_model"):
                        try:
                            self.viewer.add_model(outfile, smooth)
                        except Exception:
                            pass
                    exported = True
            except Exception:
                pass
        self._editing_paths = None
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
            if exported:
                # Temporarily replace the picking-mode tag with an export
                # confirmation so the status bar width doesn't grow.
                self._remove_status_tag(" | PICKING MODE ACTIVATED")
                self._remove_status_tag(" | Points exported")
                self._append_status(" | Points exported")

                def _restore_export_status():
                    # Remove the export notice and re-display picking mode if
                    # still active.
                    self._remove_status_tag(" | Points exported")
                    if self._active:
                        self._append_status(" | PICKING MODE ACTIVATED")
                    if hasattr(self.viewer, "lbl") and hasattr(self.viewer.lbl, "adjustSize"):
                        try:
                            self.viewer.lbl.adjustSize()
                        except Exception:
                            pass

                QtCore.QTimer.singleShot(2000, _restore_export_status)
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
