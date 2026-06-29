# Pipe + cable/rope draw operators: draw a poly-line, convert it to a round
# tube (pipe) or a sagging cable. Simplified versions of the Grid Modeler
# "pipes" flow plus a hanging-cable tool.
#
# Both share one modal (the _CurveDraw mixin). The key precision fix over the
# old single-plane projection: every clicked point is ray-cast onto the actual
# surface under the cursor, so the tube hugs the model instead of sinking into
# it; when the ray misses (empty space) it falls back to a fixed view plane.
#
# Shortcuts (modal): LMB add point, Enter create, Backspace undo, Esc/RMB
#   cancel, Wheel radius, Ctrl+Wheel surface offset, Tab/S toggle surface snap,
#   V vertex/edge snap, X grid snap, (cable only) Shift+Wheel sag, MMB navigation.
#
# Snapping is the shared chain (core.snapping): vertex/edge -> surface/face ->
# grid -> free plane, each layer independently toggleable -- the same model the
# ADD draw tool uses, so every tool sticks/aligns the same way.
import bpy
from bpy.types import Operator

from ..core import raycast, geometry, transform, snapping
from ..preferences import get_prefs
from ..ui import draw as hud


class _CurveDraw:
    """Shared modal logic for drawing a poly-line on surfaces. Subclasses set
    `_title`, `_has_sag`, and override `_init_params` and `_commit`. Not an
    Operator itself -- the concrete tools mix it with bpy.types.Operator."""

    _title = "Pipe"
    _has_sag = False

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Run inside View3D")
            return {'CANCELLED'}
        # Fixed fallback plane (used only when the surface ray misses): through
        # the active object's origin, facing the camera at invoke time.
        rv3d = context.region_data
        obj = context.active_object
        self._origin = (obj.matrix_world.translation if obj is not None
                        else context.scene.cursor.location.copy())
        self._normal = raycast.view_direction(rv3d)
        self._pts = []            # confirmed 3D points (Vectors)
        self._cursor3d = None     # current 3D point
        self._on_surface = False  # did the last sample hit a surface?
        self._snap_kind = None    # VERT/MID/EDGE/FACE/GRID/None -- HUD marker

        prefs = get_prefs(context)
        # Session-local snap toggles, seeded from prefs and flipped live with the
        # same keys as the ADD tool (Tab/S surface, V vertex/edge, X grid).
        self._surface_lock = prefs.surface_snap
        self._geo_snap = prefs.geo_snap
        self._grid_snap = prefs.snap_enabled
        self._geo = snapping.collect_geo(context, prefs.snap_target)

        self._init_params(prefs)

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _init_params(self, prefs):
        """Pull the starting radius/offset/sag from preferences. Subclasses
        override to read their own keys."""
        self._radius = prefs.pipe_radius
        self._offset = prefs.pipe_offset
        self._sag = 0.0
        self._segments = 12

    def _sample(self, context, event):
        """Resolve the mouse to a 3D point through the shared snap chain:
        vertex/edge (exact) -> surface/face (offset along normal) -> grid ->
        free fallback plane. Each tier is independently toggleable."""
        region, rv3d = context.region, context.region_data
        coord = (event.mouse_region_x, event.mouse_region_y)
        prefs = get_prefs(context)
        self._on_surface = False

        # 1) vertex / edge snap -- exact, highest priority
        if self._geo_snap:
            hit = snapping.geo_snap_3d(region, rv3d, coord, self._geo,
                                       prefs.snap_pixels)
            if hit is not None:
                self._snap_kind = hit[1]
                return hit[0].copy()

        # 2) surface / face snap -- lift off the surface along its normal
        if self._surface_lock:
            surf = raycast.ray_cast_surface(context, region, rv3d, coord)
            if surf is not None:
                location, normal, _obj = surf
                self._on_surface = True
                self._snap_kind = 'FACE'
                return location + normal.normalized() * self._offset

        # 3) free point on the fallback plane, optionally locked to the grid
        point = raycast.ray_to_plane(region, rv3d, coord,
                                     self._origin, self._normal)
        if point is not None and self._grid_snap:
            self._snap_kind = 'GRID'
            return snapping.grid_snap_3d(point, prefs.grid_world, True)
        self._snap_kind = None
        return point

    def _adjust(self, event, sign):
        """Wheel live-tuning: bare = radius, Ctrl = surface offset, Shift =
        sag (cable only)."""
        if event.ctrl:
            self._offset += sign * 0.005
        elif event.shift and self._has_sag:
            self._sag = max(0.0, self._sag + sign * 0.02)
        else:
            self._radius = max(0.001, self._radius + sign * 0.005)

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            self._cursor3d = self._sample(context, event)

        elif event.type == 'WHEELUPMOUSE' and event.value == 'PRESS':
            self._adjust(event, +1)

        elif event.type == 'WHEELDOWNMOUSE' and event.value == 'PRESS':
            self._adjust(event, -1)

        elif event.type in {'TAB', 'S'} and event.value == 'PRESS':
            self._surface_lock = not self._surface_lock
            self._cursor3d = self._sample(context, event)

        elif event.type == 'V' and event.value == 'PRESS':
            self._geo_snap = not self._geo_snap
            self._cursor3d = self._sample(context, event)

        elif event.type == 'X' and event.value == 'PRESS':
            self._grid_snap = not self._grid_snap
            self._cursor3d = self._sample(context, event)

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if self._cursor3d is not None:
                self._pts.append(self._cursor3d.copy())

        elif event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            if len(self._pts) >= 2:
                return self._commit(context)

        elif event.type == 'BACK_SPACE' and event.value == 'PRESS':
            if self._pts:
                self._pts.pop()

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._cleanup(context)
            return {'CANCELLED'}

        elif event.type in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def _screen_points(self, context):
        region, rv3d = context.region, context.region_data
        pts3d = list(self._pts)
        if self._cursor3d is not None:
            pts3d = pts3d + [self._cursor3d]
        out = []
        for p in pts3d:
            s = raycast.world_to_screen(region, rv3d, p)
            if s is not None:
                out.append((s[0], s[1]))
        return out

    def _hud_lines(self):
        def onoff(flag):
            return "ON" if flag else "OFF"
        controls = ("Wheel radius · Ctrl+Wheel offset · "
                    "V vertex · S/Tab surface · X grid")
        params = "Radius %.3f m · Offset %.3f m" % (self._radius, self._offset)
        if self._has_sag:
            controls += " · Shift+Wheel sag"
            params += " · Sag %.3f m" % self._sag
        return [
            "%s — LMB point · Enter create · Backspace undo · Esc cancel"
            % self._title,
            controls,
            params,
            "Snap → vertex %s · surface %s · grid %s · now: %s"
            % (onoff(self._geo_snap), onoff(self._surface_lock),
               onoff(self._grid_snap), self._snap_kind or "free"),
        ]

    def _draw_px(self, context):
        prefs = get_prefs(context)
        pts = self._screen_points(context)
        hud.draw_shape(pts, tuple(prefs.line_color), closed=False)
        hud.draw_points(pts[:len(self._pts)], tuple(prefs.line_color))
        # Color the live cursor by the active snap kind, matching the ADD tool.
        if self._cursor3d is not None and self._snap_kind is not None:
            s = raycast.world_to_screen(context.region, context.region_data,
                                        self._cursor3d)
            if s is not None:
                col = hud.SNAP_COLORS.get(self._snap_kind, (1.0, 1.0, 1.0, 1.0))
                hud.draw_points([(s[0], s[1])], col, size=11.0)
        hud.draw_hud(context.region, self._hud_lines())

    def _finish_curve(self, context, curve):
        if curve is None:
            return
        obj = bpy.data.objects.new(curve.name, curve)
        context.collection.objects.link(obj)
        for o in list(context.selected_objects):
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj

    def _cleanup(self, context):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        context.area.tag_redraw()


class HARDFLOW_OT_pipe(_CurveDraw, Operator):
    bl_idname = "mesh.hardflow_pipe"
    bl_label = "Hardflow Pipe"
    bl_description = "Draw a line on the surface, convert it to a round pipe"
    bl_options = {'REGISTER', 'UNDO'}

    _title = "Pipe"
    _has_sag = False

    def _commit(self, context):
        try:
            curve = geometry.build_pipe(self._pts, radius=self._radius)
            self._finish_curve(context, curve)
        except Exception as ex:  # noqa: BLE001
            self.report({'ERROR'}, f"Hardflow Pipe: {ex}")
        self._cleanup(context)
        return {'FINISHED'}


class HARDFLOW_OT_cable(_CurveDraw, Operator):
    bl_idname = "mesh.hardflow_cable"
    bl_label = "Hardflow Cable"
    bl_description = ("Draw anchor points on the surface, connect them with a "
                      "sagging cable / rope")
    bl_options = {'REGISTER', 'UNDO'}

    _title = "Cable"
    _has_sag = True

    def _init_params(self, prefs):
        self._radius = prefs.cable_radius
        self._offset = prefs.pipe_offset
        self._sag = prefs.cable_sag
        self._segments = prefs.cable_segments

    def _commit(self, context):
        try:
            anchors = [(p[0], p[1], p[2]) for p in self._pts]
            pts = transform.cable_chain(
                anchors, segments=self._segments, sag=self._sag, axis=2)
            curve = geometry.build_pipe(pts, radius=self._radius,
                                        name="Hardflow_Cable")
            self._finish_curve(context, curve)
        except Exception as ex:  # noqa: BLE001
            self.report({'ERROR'}, f"Hardflow Cable: {ex}")
        self._cleanup(context)
        return {'FINISHED'}
