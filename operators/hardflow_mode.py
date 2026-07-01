# HardFlow Mode -- the "Shadowing Engine" shell for the streamlined draw verbs.
#
# What "shadowing" means here (and what it does NOT):
#   You cannot wrap Blender's native `mesh.knife_tool` / `mesh.extrude_*` modal
#   operators and intercept their mouse events -- a modal operator that INVOKEs
#   another modal does not get to filter the child's events. So HardFlow Mode does
#   the only thing that works: it *shadows* the native tool. It owns its own modal
#   loop, reads the raw mouse, routes it through core/raycast + core/snapping +
#   core/grid (the Ghost Grid), and calls bmesh via the pure core builders
#   directly. That IS the hijack.
#
# `_HardflowModeModal` is the shared shell (the modal-hijack loop + Ghost-Grid
# snap chain + per-session Command-Pattern undo journal + HUD). Each verb --
# Knife, Extrude, ... -- is a thin subclass that only fills `_build()` (what the
# drawn footprint becomes on commit) plus its optional per-verb keys. This mirrors
# the existing shared bases: face_tool._FaceDragModal and pipe._CurveDraw.
#
# Layer rule respected: this operator (ops) reaches DOWN into core only. The whole
# tool session is ONE operator invocation, which Blender records as a single
# (atomic) undo step on FINISHED -- the per-modal atomic macro.
import bpy
from bpy.types import Operator
from mathutils import Vector

from ..core import raycast, grid, snapping, geometry, command
from ..preferences import get_prefs
from ..ui import draw as hud
from . import base


# Ghost-Grid construction planes cycled with the arrow keys.
_PLANES = ('VIEW', 'X', 'Y', 'Z')


class _HardflowModeModal:
    """Shared shell for the HardFlow Mode verbs: draw a snapped polyline on the
    Ghost Grid, then commit it into geometry. Owns the modal loop, the snap chain,
    the plane cycle, the per-session CommandManager and the HUD; subclasses only
    fill the commit.

    Subclass contract:
        verb                       : short label for the HUD / reports.
        _MIN_POINTS                : points required before commit (default 3).
        _build(context)            : turn self.world_points into geometry and
                                     return a report string; runs inside the
                                     atomic commit (raise to cancel cleanly).
        _init_verb(context)        : optional per-verb state (default no-op).
        _handle_verb_key(ctx, ev)  : optional extra keys; return True if consumed.
        _verb_hud()                : optional extra HUD text (default "").
    """

    verb = "Mode"
    _MIN_POINTS = 3
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

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
        self._plane = 'VIEW'                     # construction plane (arrow keys)
        self._commands = command.CommandManager()
        self._mesh_cmds = []                    # MeshSnapshotCommands to free()
        self._basis = self._plane_basis(context)

        # Pre-collect snap geometry once; verts/edges don't move while drawing.
        self.geo = (snapping.collect_geo(context, prefs.snap_target)
                    if prefs.geo_snap else None)
        self._init_verb(context)

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
            # snapping chain, not to Blender's tool. Re-derive the basis first so
            # the VIEW plane tracks the current orbit.
            self._basis = self._plane_basis(context)
            self._cursor = self._snap_screen(context, co)

        elif event.value == 'PRESS' and self._handle_verb_key(context, event):
            pass                                # verb consumed the key (e.g. depth)

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if self._cursor is not None:
                self._commands.do(base.PlacePointCommand(
                    self.world_points, self._cursor.copy()))

        elif event.type == 'BACK_SPACE' and event.value == 'PRESS':
            self._commands.undo()               # step one placement back

        elif event.type == 'X' and event.value == 'PRESS':
            self.snap = not self.snap

        elif (event.type in {'LEFT_ARROW', 'RIGHT_ARROW'}
              and event.value == 'PRESS'):
            self._cycle_plane(1 if event.type == 'RIGHT_ARROW' else -1)
            self._basis = self._plane_basis(context)
            self._cursor = self._snap_screen(context, co)

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
             (core/snapping.geo_snap_3d); overrides the grid so precision wins.
          2) Ghost Grid -- project onto the construction plane, round the plane's
             (u, v) meter coordinate to the grid (core/grid.snap_world).
          3) raw plane hit -- when snap is off.

        The ONE place the three core modules are composed; every verb shares it."""
        region, rv3d = context.region, context.region_data
        self._snap_kind = None

        if self.geo is not None and self.geo.enabled:
            hit = snapping.geo_snap_3d(region, rv3d, screen_co, self.geo,
                                       self._snap_px)
            if hit is not None:
                point, kind = hit
                self._snap_kind = kind
                return point

        origin, right, up, normal = self._basis
        world = raycast.ray_to_plane(region, rv3d, screen_co, origin, normal)
        if world is None:
            return None
        u, v = raycast.world_to_plane_uv(world, origin, right, up)
        if self.snap:
            u, v = grid.snap_world(u, v, self._grid, True)
            self._snap_kind = 'GRID'
        return raycast.plane_uv_to_world(u, v, origin, right, up)

    def _origin(self, context):
        """The construction-plane origin: the active object's origin when there is
        one, else the 3D cursor (so Extrude works from an empty scene)."""
        obj = context.active_object
        if obj is not None:
            return obj.matrix_world.translation.copy()
        return context.scene.cursor.location.copy()

    def _plane_basis(self, context):
        """(origin, right, up, normal) for the current construction plane. VIEW
        faces the camera through the origin; X / Y / Z are the world axis planes."""
        origin = self._origin(context)
        if self._plane == 'VIEW':
            rv3d = context.region_data
            right, up = raycast.view_right_up(rv3d)
            return origin, right, up, raycast.view_direction(rv3d)
        normal = {'X': Vector((1.0, 0.0, 0.0)),
                  'Y': Vector((0.0, 1.0, 0.0)),
                  'Z': Vector((0.0, 0.0, 1.0))}[self._plane]
        right, up, n = raycast.basis_from_normal(normal)
        return origin, right, up, n

    def _cycle_plane(self, step):
        self._plane = _PLANES[(_PLANES.index(self._plane) + step) % len(_PLANES)]

    # --- commit / teardown ------------------------------------------------

    def _commit(self, context):
        """Run the verb's `_build`, then clear the in-modal journal so the whole
        session hands off as ONE Blender undo step (the per-modal atomic macro).
        A raising `_build` cancels cleanly -- nothing is committed."""
        if len(self.world_points) < self._MIN_POINTS:
            self.report({'WARNING'}, "%s needs at least %d points"
                        % (self.verb, self._MIN_POINTS))
            return {'RUNNING_MODAL'}
        try:
            message = self._build(context)
        except Exception as ex:   # noqa: BLE001 -- report, never crash the modal
            self.report({'ERROR'}, "HardFlow %s: %s" % (self.verb, ex))
            self._cleanup(context)
            return {'CANCELLED'}
        self._commands.clear()           # hand the net change to Blender's undo
        self.report({'INFO'}, message or "HardFlow Mode: %s done" % self.verb)
        self._cleanup(context)
        return {'FINISHED'}

    def _cleanup(self, context):
        # Free every mesh snapshot regardless of undo/redo-stack state (a
        # committed edit keeps the mutated mesh; a cancelled one was already
        # restored by undo_all). free() is idempotent.
        for cmd in self._mesh_cmds:
            cmd.free()
        self._mesh_cmds = []
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        if context.area is not None:
            context.area.tag_redraw()

    # --- default subclass hooks ------------------------------------------

    def _init_verb(self, context):
        pass

    def _handle_verb_key(self, context, event):
        return False

    def _verb_hud(self):
        return ""

    def _build(self, context):
        raise NotImplementedError

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
            ("HardFlow Mode %s  --  %d pt   plane %s   snap %s%s"
             % (self.verb, len(self.world_points), self._plane,
                'ON' if self.snap else 'OFF', self._verb_hud()),
             line[:3] + (1.0,)),
            ("Click add   Backspace undo   ←/→ plane   "
             "Z / Enter / dbl-click commit   X snap   Esc cancel   [%s]"
             % snap_txt, (0.72, 0.72, 0.72, 1.0)),
        ])


class HARDFLOW_OT_mode_knife(_HardflowModeModal, Operator):
    """HardFlow Mode Knife: draw a snapped polyline on the Ghost Grid and score it
    onto the active mesh. The reference verb for the modal-hijack + Ghost-Grid snap
    + Command-Pattern undo architecture."""

    bl_idname = "mesh.hardflow_mode_knife"
    bl_label = "HardFlow Mode Knife"
    bl_description = ("Snapped polyline knife driven by the HardFlow core snapping "
                      "+ command modules")

    verb = "Knife"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')

    def _build(self, context):
        """Score the drawn footprint onto the active mesh as a MeshSnapshotCommand,
        recorded in the in-modal journal so the knife is undoable mid-session too."""
        obj = context.active_object
        mw_inv = obj.matrix_world.inverted_safe()
        local = [mw_inv @ w for w in self.world_points]
        view_dir = mw_inv.to_3x3() @ raycast.view_direction(context.region_data)

        def _score(o):
            geometry.knife_polygon(o, local, view_dir)

        knife = base.MeshSnapshotCommand(obj, _score, label="Knife",
                                         snapshot_name="hf_mode_knife")
        self._mesh_cmds.append(knife)
        self._commands.do(knife)         # snapshot 'before' + score, recorded
        return "HardFlow Mode: knifed the drawn footprint"


class HARDFLOW_OT_mode_extrude(_HardflowModeModal, Operator):
    """HardFlow Mode Extrude: draw a snapped footprint on the Ghost Grid, then
    extrude it into a solid along the plane normal. The 'draw a shape, make it a
    thing' verb -- the SketchUp Push/Pull-from-nothing flow, on the shared shell.
    PageUp / PageDown set the extrude depth."""

    bl_idname = "mesh.hardflow_mode_extrude"
    bl_label = "HardFlow Mode Extrude"
    bl_description = ("Draw a snapped footprint on the Ghost Grid and extrude it "
                      "into a solid")

    verb = "Extrude"

    def _init_verb(self, context):
        self.depth = max(self._grid * 4.0, 0.1)   # PageUp/PageDown adjust

    def _handle_verb_key(self, context, event):
        if event.type in {'PAGE_UP', 'PAGE_DOWN'}:
            step = self._grid if event.type == 'PAGE_UP' else -self._grid
            self.depth = max(self._grid, round(self.depth + step, 6))
            return True
        return False

    def _verb_hud(self):
        return "   depth %.3f m (PgUp/PgDn)" % self.depth

    def _build(self, context):
        """Build a prism from the drawn footprint, extruded along the plane normal,
        and drop it in as a new active object."""
        origin, right, up, normal = self._basis
        me = geometry.build_prism(self.world_points, normal, self.depth)
        if me is None:
            raise RuntimeError("degenerate footprint")
        obj = bpy.data.objects.new("Hardflow_Extrude", me)
        context.collection.objects.link(obj)
        for o in context.selected_objects:
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return ("HardFlow Mode: extruded a %d-gon solid (depth %.3f m)"
                % (len(self.world_points), self.depth))
