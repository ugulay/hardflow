# HardFlow Mode -- reference prototype for the "modal hijack" architecture.
#
# What "hijack" means in this codebase (and what it does NOT mean):
#   You cannot wrap Blender's native `mesh.knife_tool` / `mesh.extrude_*` modal
#   operators and intercept their mouse events -- a modal operator that INVOKEs
#   another modal does not get to filter the child's events. So the whole draw /
#   push_pull / offset / edge_tool family already does the only thing that works:
#   it *shadows* the native tool. It owns its own modal loop, reads the raw mouse,
#   routes it through core/raycast + core/snapping + core/grid (the Ghost Grid),
#   and calls bmesh (via the pure core builders) directly. That IS the hijack.
#
# This operator is the minimal, self-contained demonstration of that pattern for
# a Knife, plus the Command-Pattern journal (core/command.py) driving in-modal
# undo. It is deliberately small so it reads as a template; the production draw
# tool (operators/draw_cut.py) is the full-featured version of the same shell.
#
# Layer rule respected: this operator (ops) reaches DOWN into core only.
import bpy
from bpy.types import Operator
from mathutils import Vector

from ..core import raycast, grid, snapping, geometry, command
from ..preferences import get_prefs
from ..ui import draw as hud
from . import base


class HARDFLOW_OT_mode_knife(Operator):
    """HardFlow Mode Knife (prototype): draw a snapped polyline on the Ghost Grid
    and score it onto the active mesh. Demonstrates the modal-hijack + Ghost-Grid
    snap + Command-Pattern undo architecture on the shared core modules."""

    bl_idname = "mesh.hardflow_mode_knife"
    bl_label = "HardFlow Mode Knife (Prototype)"
    bl_description = ("Prototype: snapped polyline knife driven by the HardFlow "
                      "core snapping + command modules")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')

    # --- lifecycle -------------------------------------------------------

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Run inside the 3D Viewport")
            return {'CANCELLED'}
        prefs = get_prefs(context)
        self.snap = prefs.snap_enabled          # X toggles the Ghost Grid snap
        self._grid = prefs.grid_world           # Ghost Grid spacing (meters)
        self._snap_px = prefs.snap_pixels       # geometry-snap capture radius
        self.world_points = []                  # placed points, world space
        self._cursor = None                     # live snapped cursor (world)
        self._snap_kind = None                  # 'VERT'/'MID'/'EDGE'/'GRID'/None
        self._commands = command.CommandManager()
        self._mesh_cmds = []                    # MeshSnapshotCommands to free()

        # Ghost Grid basis: a view-facing plane through the active object origin.
        # (SURFACE / X / Y / Z planes drop in here later -- same as draw_cut.)
        self._basis = self._view_basis(context)

        # Pre-collect snap geometry once; verts/edges don't move while drawing.
        self.geo = (snapping.collect_geo(context, prefs.snap_target)
                    if prefs.geo_snap else None)

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        try:
            context.window_manager.modal_handler_add(self)
        except Exception:   # never orphan the draw handler if modal won't start
            self._cleanup(context)
            raise
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        context.area.tag_redraw()
        co = (event.mouse_region_x, event.mouse_region_y)

        if event.type == 'MOUSEMOVE':
            # THE hijack: the raw mouse position is handed straight to the core
            # snapping chain, not to Blender's tool. Everything downstream sees a
            # grid/geometry-locked point, which is the whole "flow" feel.
            self._cursor = self._snap_screen(context, co)

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if self._cursor is not None:
                self._commands.do(base.PlacePointCommand(
                    self.world_points, self._cursor.copy()))

        elif event.type == 'BACK_SPACE' and event.value == 'PRESS':
            self._commands.undo()               # step one placement back

        elif event.type == 'X' and event.value == 'PRESS':
            self.snap = not self.snap

        elif (event.type in {'RET', 'NUMPAD_ENTER', 'Z'}
              and event.value == 'PRESS'):
            return self._commit(context)

        elif event.type == 'LEFTMOUSE' and event.value == 'DOUBLE_CLICK':
            return self._commit(context)

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._commands.undo_all()           # nothing committed yet: roll back
            self._cleanup(context)
            return {'CANCELLED'}

        elif event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
                            'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}             # let the user orbit / zoom

        return {'RUNNING_MODAL'}

    # --- the snapping chain (the "Ghost Grid") ---------------------------

    def _snap_screen(self, context, screen_co):
        """Route the raw 2D mouse position through the shared core snapping chain
        and return a 3D world point (or None if the ray misses the plane):

          1) geometry snap -- nearest vertex / edge-midpoint / on-edge point
             (core/snapping.geo_snap_3d, itself core/snap.resolve_snap); this
             overrides the grid so precision beats the lattice.
          2) Ghost Grid -- project onto the construction plane, then round the
             plane's (u, v) meter coordinate to the grid (core/grid.snap_world).
          3) raw plane hit -- when snap is off.

        Sets self._snap_kind for the on-screen marker. This is the ONE place the
        three core modules are composed; every draw tool shares this shape."""
        region, rv3d = context.region, context.region_data
        self._snap_kind = None

        # 1) geometry snap (vertex / edge / midpoint) wins over the grid.
        if self.geo is not None and self.geo.enabled:
            hit = snapping.geo_snap_3d(region, rv3d, screen_co, self.geo,
                                       self._snap_px)
            if hit is not None:
                point, kind = hit
                self._snap_kind = kind
                return point

        # 2) project onto the plane, snap the (u, v) to the Ghost Grid.
        origin, right, up, normal = self._basis
        world = raycast.ray_to_plane(region, rv3d, screen_co, origin, normal)
        if world is None:
            return None
        u, v = raycast.world_to_plane_uv(world, origin, right, up)
        if self.snap:
            u, v = grid.snap_world(u, v, self._grid, True)
            self._snap_kind = 'GRID'
        return raycast.plane_uv_to_world(u, v, origin, right, up)

    def _view_basis(self, context):
        rv3d = context.region_data
        origin = context.active_object.matrix_world.translation
        right, up = raycast.view_right_up(rv3d)
        return origin, right, up, raycast.view_direction(rv3d)

    # --- commit / teardown ------------------------------------------------

    def _commit(self, context):
        """Score the drawn footprint onto the active mesh as a MeshSnapshotCommand
        (base.py). It joins the in-modal journal alongside the point commands, so
        the knife is undoable mid-session too. On success the journal is cleared
        and the snapshots freed: the whole session is now ONE operator invocation,
        which Blender records as a single (atomic) undo step on FINISHED -- we do
        NOT push per-step undo of our own."""
        if len(self.world_points) < 3:
            self.report({'WARNING'}, "Need at least 3 points to knife")
            return {'RUNNING_MODAL'}
        obj = context.active_object
        mw_inv = obj.matrix_world.inverted_safe()
        local = [mw_inv @ w for w in self.world_points]
        view_dir = mw_inv.to_3x3() @ raycast.view_direction(context.region_data)

        def _score(o):
            geometry.knife_polygon(o, local, view_dir)

        knife = base.MeshSnapshotCommand(obj, _score, label="Knife",
                                         snapshot_name="hf_mode_knife")
        self._mesh_cmds.append(knife)
        try:
            self._commands.do(knife)     # snapshot 'before' + score, recorded
        except Exception as ex:   # noqa: BLE001 -- prototype: report, don't crash
            self.report({'ERROR'}, "HardFlow knife: %s" % ex)
            self._cleanup(context)
            return {'CANCELLED'}
        self._commands.clear()           # hand the net change to Blender's undo
        self.report({'INFO'}, "HardFlow Mode: knifed the drawn footprint")
        self._cleanup(context)
        return {'FINISHED'}

    def _cleanup(self, context):
        # Free every mesh snapshot regardless of undo/redo-stack state (a
        # committed edit keeps the mutated mesh; a cancelled one was already
        # restored by undo_all above). free() is idempotent.
        for cmd in self._mesh_cmds:
            cmd.free()
        self._mesh_cmds = []
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        if context.area is not None:
            context.area.tag_redraw()

    # --- HUD --------------------------------------------------------------

    def _draw_px(self, context):
        prefs = get_prefs(context)
        region, rv3d = context.region, context.region_data
        line = tuple(prefs.line_color)

        # Placed points + the rubber-band segment to the live cursor.
        screen = []
        for w in self.world_points:
            s = raycast.world_to_screen(region, rv3d, w)
            if s is not None:
                screen.append((s[0], s[1]))
        preview = list(screen)
        if self._cursor is not None:
            c = raycast.world_to_screen(region, rv3d, self._cursor)
            if c is not None:
                preview.append((c[0], c[1]))
        if len(preview) >= 2:
            closed = len(self.world_points) >= 3 and self._cursor is None
            hud.draw_shape(preview, line, closed=closed)

        # Snap marker at the live cursor, colored by what it locked onto.
        if self._cursor is not None:
            c = raycast.world_to_screen(region, rv3d, self._cursor)
            if c is not None:
                mark = {
                    'VERT': (1.0, 0.9, 0.2, 1.0),   # yellow = vertex
                    'MID': (0.2, 1.0, 0.4, 1.0),    # green  = midpoint
                    'EDGE': (0.3, 0.6, 1.0, 1.0),   # blue   = on-edge
                    'GRID': (1.0, 1.0, 1.0, 0.7),   # white  = grid
                }.get(self._snap_kind, line)
                r = 6.0
                box = [(c[0] - r, c[1] - r), (c[0] + r, c[1] - r),
                       (c[0] + r, c[1] + r), (c[0] - r, c[1] + r)]
                hud.draw_shape(box, mark, closed=True)

        snap_txt = self._snap_kind or "free"
        hud.draw_hud(region, [
            ("HardFlow Mode Knife  --  %d point(s)   snap: %s"
             % (len(self.world_points), 'ON' if self.snap else 'OFF'),
             line[:3] + (1.0,)),
            ("Click add    Backspace undo    Z / Enter / dbl-click close    "
             "X snap    Esc cancel    [%s]" % snap_txt, (0.72, 0.72, 0.72, 1.0)),
        ])
