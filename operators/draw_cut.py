# Main draw operator: draw a shape on screen, project to 3D, apply boolean.
#
# SHAPE: BOX / CIRCLE / POLY / NGON / SLOT / STAR / ARC
# MODE: CUT / SLICE / MAKE / JOIN / INTERSECT / FACE / KNIFE
# Shortcuts (inside modal):
#   Left click    place point / start-finish shape
#   Enter         close POLY and apply
#   0-9 . (type)  lock the shape to an exact size (radius / extent / segment, m)
#   Backspace     edit a typed size, else delete last POLY point
#   Q/W/E/R/T/Y/U shape = BOX / CIRCLE / POLY / NGON / SLOT / STAR / ARC
#   [ / ]         decrease / increase N-gon sides (ARC: sweep angle)
#   Tab / Shift+Tab   cycle the mode (Cut/Slice/Make/Intersect/Face/Knife)
#   X             toggle snap
#   Right click / ESC  cancel
import math

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty
from mathutils import Vector

from ..core import (raycast, geometry, boolean, grid, snap, decal_math, command,
                    preview_cache)
from ..preferences import get_prefs
from ..ui import draw as hud
from . import base


_SHAPES = [
    ('BOX', "Box", "Rectangle"),
    ('CIRCLE', "Circle", "Circle"),
    ('POLY', "Polygon", "Freeform polygon"),
    ('NGON', "N-gon", "Regular polygon (side count from preferences / [ ])"),
    ('SLOT', "Slot", "Rounded-rectangle / stadium (cap segments from [ ])"),
    ('STAR', "Star", "N-pointed star (point count from [ ])"),
    ('ARC', "Arc", "Filled circular sector / pie wedge (sweep from [ ])"),
]
_MODES = [
    ('CUT', "Cut", "Boolean DIFFERENCE"),
    ('SLICE', "Slice", "Slice the object in two"),
    ('MAKE', "Make", "Add geometry (UNION)"),
    ('JOIN', "Join", "Add the drawn shape as a separate solid (no boolean)"),
    ('INTERSECT', "Intersect", "Boolean INTERSECT (keep only what's inside the drawn volume)"),
    ('FACE', "Face", "Create a new face (create face, not boolean)"),
    ('KNIFE', "Knife", "Score the surface only (zero-depth cut, no boolean)"),
]

# Boolean solver for the CUT/MAKE/INTERSECT modes. DEFAULT defers to the
# preferences solver; the rest mirror Blender's native Polyline Trim choices.
_SOLVERS = [
    ('DEFAULT', "Default", "Use the Boolean Solver set in the preferences"),
    ('EXACT', "Exact", "Accurate, handles overlaps, slower"),
    ('FAST', "Fast", "Fast, no overlap support"),
    ('MANIFOLD', "Manifold", "Fastest; manifold meshes only (Blender 4.5+)"),
]

# Cutter extrude orientation (Blender's Polyline Trim Project/Fixed):
#   FIXED   -- extrude every corner along one shared direction (the drawing
#              plane normal): a straight prism.
#   PROJECT -- extrude each corner along its own camera ray, so the cut tapers
#              with perspective and matches the screen-space drawing exactly.
#              Identical to FIXED in an orthographic view (rays are parallel).
_ORIENTS = [
    ('FIXED', "Fixed", "Straight extrude along the drawing plane normal"),
    ('PROJECT', "Project", "Taper the cut along the camera rays (perspective)"),
]

# Vertex/edge snap cursor colors live in ui.draw so every tool shares them.
_SNAP_COLORS = hud.SNAP_COLORS


class HARDFLOW_OT_draw(Operator):
    bl_idname = "mesh.hardflow_draw"
    bl_label = "Hardflow Draw"
    bl_options = {'REGISTER', 'UNDO'}

    shape: EnumProperty(name="Shape", items=_SHAPES, default='BOX')
    mode: EnumProperty(name="Mode", items=_MODES, default='CUT')
    solver: EnumProperty(name="Solver", items=_SOLVERS, default='DEFAULT')
    orientation: EnumProperty(name="Orientation", items=_ORIENTS, default='FIXED')

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode in {'OBJECT', 'EDIT_MESH'})

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Run inside View3D")
            return {'CANCELLED'}

        prefs = get_prefs(context)
        self.edit = context.mode == 'EDIT_MESH'  # draw into the active edit-mesh
        self.snap = prefs.snap_enabled
        self.geo = prefs.geo_snap        # vertex/edge snap (overrides grid)
        self.nd = prefs.non_destructive  # non-destructive: leave a live modifier
        self.plane = prefs.default_plane  # saved projection plane (S saves it)
        self.plane_spin = 0.0            # live in-plane grid rotation (Shift+arrows)
        self.sides = prefs.ngon_sides    # N-gon side count (adjust live with [ ])
        self.arc_sweep = 1.5707963267948966  # ARC sector sweep (rad); [ ] adjusts
        # In-draw operations (v1.4): all baked into one cutter at commit. The
        # defaults are seeded from the "Cutter Options" preferences so they can be
        # preset from the N-panel, then live-tweaked with the modal keys.
        self.inset = prefs.draw_inset       # offset the drawn loop in/out; -/= adjust
        self.rotation = 0.0       # in-plane shape rotation (rad); , / . adjust
        self.array_count = prefs.draw_array_count   # stamp N copies; A adjusts
        self.array_axis = prefs.draw_array_axis     # array world axis; D cycles
        self.mirror_axis = ''     # live mirror across a world axis; M cycles
        self.bevel_cut = prefs.draw_bevel_cut       # bevel the cut edge; B toggles
        self.cutter_bevel = prefs.draw_cutter_bevel  # chamfer the cutter; C toggles
        self.live_bool = prefs.live_boolean_preview  # live boolean result; J toggles
        self._live_cmd = None     # base.LivePreviewCommand owning the temp mod(s)
        # Distance gate for the live boolean re-sync: skip re-pointing the temp
        # modifier(s) until the cutter cage has moved a little, so a high-poly
        # target isn't re-evaluated on sub-pixel jitter (core/preview_cache).
        self._live_gate = preview_cache.PreviewGate(prefs.grid_world * 0.1)
        self._live_targets = None  # last target set the gate accepted (id set)
        self.grid_size = prefs.grid_world  # live grid spacing (Ctrl+Wheel adjusts)
        self.depth = 0.0          # explicit cutter depth (0 = auto pierce); PgUp/Dn
        self.points = []          # confirmed screen points (current view)
        self.world_points = []    # anchored 3D point per click; keeps a fixed
        #                           plane's shape locked in space when the view
        #                           changes mid-draw (parallel to self.points)
        # Per-session journal for the placement clicks (screen + world lists move
        # together as one PlacePointCommand macro), so Backspace = undo() and the
        # reset keys = clear(). Same command vocabulary as face_tool / hardflow_mode.
        self._commands = command.CommandManager()
        self.cursor = (0, 0)      # current (snapped) mouse point
        self.typed = ""           # numeric size buffer: type an exact dimension
        self._raw_cursor = (0, 0)  # snapped cursor before any typed-size lock
        self._snap_hit = None     # (screen_point, kind) -- for visual marker
        self._surface_basis = None  # locked (origin,right,up,normal) in SURFACE
        self._surface_hold = None   # last good SURFACE plane, held over a ray miss
        self._surface_miss = False  # SURFACE ray missed -> fell back to VIEW
        self._edges_basis = None    # locked basis from selected edges (EDGES plane)
        self._forced_main_key = None  # Ctrl+Click main-edge override (vert-idx set)
        self.grid_origin = None     # H: re-anchor the snap grid to a chosen point
        self._preview = None        # live 3D cutter/face volume object
        self._preview_sig = None    # last-built preview signature (dirty check)
        self._collect_snap_geometry(context)

        # Edge-grid workflow: if you enter with edge(s) selected in Edit Mode,
        # start on the EDGES plane (grid laid on the selection).
        if self.edit:
            self._edges_basis = self._capture_edges_basis(context)
            if self._edges_basis is not None:
                self.plane = 'EDGES'

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        try:
            context.window_manager.modal_handler_add(self)
        except Exception:  # never orphan the draw handler if the modal won't start
            self._cleanup(context)
            raise
        return {'RUNNING_MODAL'}

    # --- event loop ------------------------------------------------------

    def modal(self, context, event):
        # A raise anywhere in the modal body would otherwise leave the registered
        # GPU draw handler firing against a dead operator and any HF_LivePreview
        # temp modifiers stuck on the targets. Guard it: clean up and bail.
        try:
            return self._modal(context, event)
        except Exception as ex:  # noqa: BLE001
            self.report({'ERROR'}, "Hardflow: %s" % ex)
            try:
                self._cleanup(context)
            except Exception:  # noqa: BLE001
                pass
            return {'CANCELLED'}

    def _modal(self, context, event):
        context.area.tag_redraw()
        # Re-anchor placed points to the current view before doing anything, so an
        # orbit/zoom on a fixed plane leaves the shape where it was drawn.
        self._sync_points_from_world(context)

        if event.type == 'MOUSEMOVE':
            # Ctrl held = force incremental grid snap for this move even when the
            # persistent snap toggle is off (and bypass geometry snap), so Ctrl is
            # a momentary "snap precisely to the grid" the way BoxCutter does it.
            co = self._snap_screen(
                context, (event.mouse_region_x, event.mouse_region_y),
                force_grid=event.ctrl)
            # Shift: lock draw direction to angle steps relative to last point
            if event.shift and self.points:
                anchor = self.points[-1] if self.shape == 'POLY' else self.points[0]
                step = get_prefs(context).angle_step
                co = grid.snap_angle(anchor, co, step, True)
                self._snap_hit = None  # angle lock invalidates the geometry marker
            self._raw_cursor = co
            self._apply_numeric(context)  # lock size to a typed value, else = raw

        # Ctrl+Click on the EDGES plane: set the main grid axis to the selected
        # edge under the cursor (override the automatic longest-edge pick),
        # instead of placing a draw point.
        elif (event.type == 'LEFTMOUSE' and event.value == 'PRESS'
              and event.ctrl and self.plane == 'EDGES'):
            key = self._pick_selected_edge(
                context, (event.mouse_region_x, event.mouse_region_y))
            if key is not None:
                self._forced_main_key = key
                self._edges_basis = self._capture_edges_basis(context)

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            p = self.cursor
            # SURFACE mode: lock the construction plane to the face under the
            # first click so the whole shape stays on one stable plane.
            if (self.plane == 'SURFACE' and not self.points
                    and self._surface_basis is None):
                self._lock_surface_basis(context, p)
            self._place_point(context, p)
            self.typed = ""   # next POLY segment starts a fresh numeric entry
            # BOX / CIRCLE / NGON finish on the second click; POLY keeps going.
            if self.shape != 'POLY' and len(self.points) >= 2:
                return self._commit(context)

        # Double-click closes an in-progress polyline (parity with Blender's
        # native Polyline Trim finish). The triggering second press already
        # placed the final point, so just close on >=3 points.
        elif event.type == 'LEFTMOUSE' and event.value == 'DOUBLE_CLICK':
            if self.shape == 'POLY' and len(self.points) >= 3:
                return self._commit(context)

        elif event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            if self.shape == 'POLY' and len(self.points) >= 3:
                return self._commit(context)

        # Z: close the in-progress polygon immediately (quick-close).
        elif event.type == 'Z' and event.value == 'PRESS':
            if self.shape == 'POLY' and len(self.points) >= 3:
                return self._commit(context)

        elif event.type == 'BACK_SPACE' and event.value == 'PRESS':
            if self.typed:                 # editing a typed size? trim it
                self.typed = self.typed[:-1]
                self._apply_numeric(context)
            elif self.points:
                self._commands.undo()   # pops the screen + world point together

        elif event.type in {'Q', 'W', 'E', 'R', 'T', 'Y', 'U'} \
                and event.value == 'PRESS':
            self.shape = {'Q': 'BOX', 'W': 'CIRCLE', 'E': 'POLY', 'R': 'NGON',
                          'T': 'SLOT', 'Y': 'STAR', 'U': 'ARC'}[event.type]
            self.points = []
            self.world_points = []
            self._commands.clear()   # drop the half-drawn shape's journal
            self.typed = ""

        elif (event.type in {'LEFT_BRACKET', 'RIGHT_BRACKET'}
              and event.value == 'PRESS'):
            step = 1 if event.type == 'RIGHT_BRACKET' else -1
            # On ARC the bracket keys grow / shrink the sector sweep (15deg steps,
            # clamped to a full turn); for the other shapes they set the side /
            # point / cap-segment count.
            if self.shape == 'ARC':
                self.arc_sweep = max(math.radians(15),
                                     min(math.tau,
                                         self.arc_sweep + step * math.radians(15)))
            else:
                self.sides = max(3, min(64, self.sides + step))

        # Tab / Shift+Tab cycle the boolean mode (the number row now types an
        # exact size -- precision entry).
        elif event.type == 'TAB' and event.value == 'PRESS':
            order = [m[0] for m in _MODES]
            step = -1 if event.shift else 1
            self.mode = order[(order.index(self.mode) + step) % len(order)]
            self.typed = ""

        # Numeric size entry: type a distance to lock the shape's size (radius /
        # extent / segment length) in plane metres, along the cursor direction.
        elif event.type in self._DIGIT_KEYS and event.value == 'PRESS':
            self.typed += self._DIGIT_KEYS[event.type]
            self._apply_numeric(context)

        # --- in-draw operations (v1.4) -----------------------------------
        elif event.type in {'MINUS', 'EQUAL'} and event.value == 'PRESS':
            step = self.grid_size
            self.inset += step if event.type == 'EQUAL' else -step

        elif event.type in {'COMMA', 'PERIOD', 'NUMPAD_PERIOD'} \
                and event.value == 'PRESS':
            # A '.' while typing a number is the decimal point; otherwise (and for
            # ',') it nudges the in-plane shape rotation.
            if (event.type in {'PERIOD', 'NUMPAD_PERIOD'} and self.typed
                    and '.' not in self.typed):
                self.typed += '.'
                self._apply_numeric(context)
            elif event.type == 'NUMPAD_PERIOD' and not self.typed:
                self.typed = "0."
                self._apply_numeric(context)
            else:
                step = math.radians(get_prefs(context).angle_step)
                self.rotation += step if event.type == 'PERIOD' else -step

        elif event.type == 'A' and event.value == 'PRESS':
            self.array_count = self.array_count % 6 + 1  # cycle 1..6

        elif event.type == 'D' and event.value == 'PRESS':
            self.array_axis = {'X': 'Y', 'Y': 'Z', 'Z': 'X'}[self.array_axis]

        elif event.type == 'M' and event.value == 'PRESS':
            self.mirror_axis = {'': 'X', 'X': 'Y', 'Y': 'Z', 'Z': ''}[self.mirror_axis]

        elif event.type == 'B' and event.value == 'PRESS':
            self.bevel_cut = not self.bevel_cut

        elif event.type == 'C' and event.value == 'PRESS':
            self.cutter_bevel = not self.cutter_bevel  # chamfer the cutter walls

        elif event.type == 'O' and event.value == 'PRESS':
            # Toggle Fixed <-> Project extrude (perspective taper).
            self.orientation = ('PROJECT' if self.orientation == 'FIXED'
                                else 'FIXED')

        elif event.type == 'G' and event.value == 'PRESS':
            return self._stamp_last(context)   # repeat the previous shape

        elif event.type == 'X' and event.value == 'PRESS':
            self.snap = not self.snap

        elif event.type == 'N' and event.value == 'PRESS':
            self.nd = not self.nd

        elif event.type == 'J' and event.value == 'PRESS':
            # Toggle the live boolean RESULT preview (temp modifier on the target).
            self.live_bool = not self.live_bool
            if not self.live_bool:
                self._clear_live_boolean(context)

        elif event.type == 'V' and event.value == 'PRESS':
            self.geo = not self.geo

        # H: set / clear the grid origin. Re-anchors the snap lattice (and the
        # visible grid) to the point under the cursor on the current plane --
        # 'move the grid origin'. Press again to revert to the default.
        elif event.type == 'H' and event.value == 'PRESS':
            if self.grid_origin is not None:
                self.grid_origin = None
            elif self.plane != 'VIEW':
                region, rv3d = context.region, context.region_data
                origin, _r, _u, normal = self._plane_basis(context)
                self.grid_origin = raycast.ray_to_plane(
                    region, rv3d, self.cursor, origin, normal)

        # S: persist the live HUD settings (snap/geo/ND, grid, sides, plane) as
        # the defaults for the next draw session.
        elif event.type == 'S' and event.value == 'PRESS':
            self._save_settings(context)

        elif event.type in {'LEFT_ARROW', 'RIGHT_ARROW'} and event.value == 'PRESS':
            direction = 1 if event.type == 'RIGHT_ARROW' else -1
            if event.shift:
                # Shift + arrows: rotate the grid plane in place.
                self.plane_spin += direction * math.radians(
                    get_prefs(context).angle_step)
            else:
                order = self._PLANE_ORDER
                self.plane = order[(order.index(self.plane) + direction)
                                   % len(order)]
                self.points = []  # plane changed -> reset the half-drawn shape
                self.world_points = []
                self._commands.clear()      # and drop its placement journal
                self._surface_basis = None  # re-pick the surface on next click
                self._surface_hold = None   # drop any held plane from the old pass
                self._edges_basis = None    # re-read the selected edges for EDGES
                self._forced_main_key = None  # drop the Ctrl+Click main-edge pick
                self.grid_origin = None     # the old origin is off the new plane

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._cleanup(context)
            return {'CANCELLED'}

        # Ctrl+Wheel: live grid density (otherwise the wheel navigates the view).
        elif (event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} and event.ctrl
              and event.value == 'PRESS'):
            factor = 2.0 if event.type == 'WHEELUPMOUSE' else 0.5
            self.grid_size = max(0.001, min(100.0, self.grid_size * factor))

        elif event.type in {'PAGE_UP', 'PAGE_DOWN'} and event.value == 'PRESS':
            # Depth steps by one grid cell; Shift = a fine 1/10-cell step for
            # measured, incremental depth control.
            step = self.grid_size * (0.1 if event.shift else 1.0)
            self.depth = max(0.0, self.depth
                             + (step if event.type == 'PAGE_UP' else -step))

        # Allow viewport navigation while drawing (orbit/zoom/pan).
        elif event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
                            'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}

        self._update_preview(context)
        return {'RUNNING_MODAL'}

    # --- world-scale snap (v0.2) ----------------------------------------

    _PLANE_ORDER = ['VIEW', 'SURFACE', 'EDGES', 'X', 'Y', 'Z']

    # World bases (right, up, normal) for axis-aligned planes.
    _AXIS_BASIS = {
        'X': (Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((1, 0, 0))),
        'Y': (Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, 1, 0))),
        'Z': (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))),
    }

    def _view_basis(self, context):
        origin = context.active_object.matrix_world.translation
        return raycast.view_basis(context.region_data, origin)

    def _surface_basis_at(self, context, screen_co):
        """Construction basis aligned to the face under screen_co (delegates to
        the shared raycast.surface_basis_at). Ignores the live preview cage so the
        ray hits the real model, not the wire overlay."""
        ignore = [self._preview] if self._preview else None
        return raycast.surface_basis_at(
            context, context.region, context.region_data, screen_co, ignore)

    def _lock_surface_basis(self, context, screen_co):
        """Capture and cache the surface basis at the first click so the whole
        shape stays on one plane. If the click just missed the surface, fall back
        to the last face hovered (the held plane) rather than dropping to the
        object-centre VIEW plane; only a click that never saw a surface falls to
        VIEW."""
        self._surface_basis = (self._surface_basis_at(context, screen_co)
                               or self._surface_hold)

    def _capture_edges_basis(self, context):
        """'Grid plane on edge(s)': build a construction basis from
        the selected edit-mesh edges -- one edge gives a plane along that edge +
        its face normal, two edges give the plane they span. Cached because the
        selection doesn't change during the draw. Returns the basis tuple or None
        (not in Edit Mode / nothing selected)."""
        if context.mode != 'EDIT_MESH':
            return None
        import bmesh
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        sel = [e for e in bm.edges if e.select]
        if not sel:
            return None
        mw = obj.matrix_world
        rot = mw.to_3x3()

        def edge_vec(e):
            return rot @ (e.verts[1].co - e.verts[0].co)

        def edge_mid(e):
            return (e.verts[0].co + e.verts[1].co) * 0.5

        # Pick the main (longest) edge + its most-perpendicular partner, so the
        # grid axis is the dominant selected edge regardless of bmesh order, and
        # parallel selections degrade cleanly to a single-edge plane. A Ctrl+Click
        # main-edge override (self._forced_main_key, an edge's vertex-index set)
        # forces that edge as the main axis when it's part of the selection.
        vecs = [tuple(edge_vec(e)) for e in sel]
        forced = None
        forced_key = getattr(self, "_forced_main_key", None)
        if forced_key is not None:
            for i, e in enumerate(sel):
                if frozenset((e.verts[0].index, e.verts[1].index)) == forced_key:
                    forced = i
                    break
        main_i, partner_i = decal_math.best_edge_pair(vecs, forced_main=forced)
        if partner_i is not None:
            r, u, n = decal_math.basis_from_two_edges(vecs[main_i], vecs[partner_i])
            origin = mw @ ((edge_mid(sel[main_i]) + edge_mid(sel[partner_i])) * 0.5)
        else:
            e = sel[main_i]
            if e.link_faces:
                nrm = rot @ e.link_faces[0].normal
            else:
                nrm = raycast.view_direction(context.region_data)
            r, u, n = decal_math.basis_from_edge(vecs[main_i], tuple(nrm))
            origin = mw @ edge_mid(e)
        return (origin, Vector(r), Vector(u), Vector(n))

    def _pick_selected_edge(self, context, screen_co):
        """The selected edit-mesh edge nearest `screen_co`, as its vertex-index
        frozenset -- the Ctrl+Click 'set main edge' target. Projects each selected
        edge to the screen and takes the closest segment. None outside Edit Mode /
        with no selection / when every endpoint projects off-screen."""
        if context.mode != 'EDIT_MESH':
            return None
        import bmesh
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        sel = [e for e in bm.edges if e.select]
        if not sel:
            return None
        region, rv3d = context.region, context.region_data
        mw = obj.matrix_world
        segs = []
        for e in sel:
            a = raycast.world_to_screen(region, rv3d, mw @ e.verts[0].co)
            b = raycast.world_to_screen(region, rv3d, mw @ e.verts[1].co)
            segs.append((a, b) if a is not None and b is not None else (None, None))
        hit = snap.nearest_on_segments((screen_co[0], screen_co[1]), segs, 1e9)
        if hit is None:
            return None
        e = sel[hit[0]]
        return frozenset((e.verts[0].index, e.verts[1].index))

    def _plane_basis(self, context):
        """Origin, local axes and normal of the projection plane, after the live
        in-plane spin (Shift + arrows). VIEW = perpendicular to view; SURFACE =
        aligned to the picked face; EDGES = aligned to the selected edit-mesh
        edge(s); X/Y/Z = world-axis aligned (world grid)."""
        if self.plane == 'VIEW':
            self._surface_miss = False
            basis = self._view_basis(context)
        elif self.plane == 'EDGES':
            b = self._edges_basis or self._capture_edges_basis(context)
            self._surface_miss = b is None
            basis = b if b is not None else self._view_basis(context)
        elif self.plane == 'SURFACE':
            b = self._surface_basis
            if b is None:
                # Before the first click, preview-track the face under the cursor.
                live = self._surface_basis_at(context, self.cursor)
                if live is not None:
                    self._surface_hold = live   # remember the last face hovered
                # On a miss, hold the last good surface plane instead of dropping
                # to the object-centre VIEW plane -- that jump reads as the cursor
                # "going behind" the surface.
                b = live if live is not None else self._surface_hold
            self._surface_miss = b is None
            basis = b if b is not None else self._view_basis(context)
        else:
            self._surface_miss = False
            right, up, normal = self._AXIS_BASIS[self.plane]
            origin = context.active_object.matrix_world.translation
            basis = (origin, right, up, normal)
        basis = self._apply_spin(basis)
        # H 'move grid origin': re-anchor the lattice to a chosen on-plane point
        # (kept coplanar by capture + cleared on plane change). VIEW tracks the
        # camera, so a fixed origin there wouldn't stay on-plane -- skip it.
        if self.grid_origin is not None and self.plane != 'VIEW':
            o, r, u, n = basis
            basis = (self.grid_origin, r, u, n)
        return basis

    def _apply_spin(self, basis):
        """Rotate the plane's right/up axes around its normal by the live grid
        spin (Shift + arrows) -- 'rotate the grid plane'. The
        normal and origin are unchanged."""
        if abs(self.plane_spin) < 1e-9:
            return basis
        from mathutils import Matrix
        origin, right, up, normal = basis
        rot = Matrix.Rotation(self.plane_spin, 3, normal)
        return origin, rot @ right, rot @ up, normal

    def _place_point(self, context, screen_co):
        """Record a clicked point as both its screen position and its anchored 3D
        world position on the current construction plane. The world anchor lets a
        fixed plane (SURFACE/EDGES/X/Y/Z) keep the shape locked in space when the
        view changes mid-draw; VIEW plane ignores it and follows the camera. Both
        lists move together as one journal entry, so Backspace undoes both."""
        region, rv3d = context.region, context.region_data
        origin, right, up, normal = self._plane_basis(context)
        w = raycast.ray_to_plane(region, rv3d, screen_co, origin, normal)
        if w is None:
            # Plane edge-on to the view: fall back to a view-facing plane through
            # the same origin so the anchor is never None -- a None anchor would
            # desync this point from the rest on the next orbit.
            w = raycast.ray_to_plane(
                region, rv3d, screen_co, origin, raycast.view_direction(rv3d))
        self._record_placement((screen_co[0], screen_co[1]), w)

    def _record_placement(self, screen_pt, world_pt):
        """Append one click to the screen + world point lists as a single journal
        entry (a two-child MacroCommand), so Backspace (undo) removes both
        together and the reset keys (clear) drop them cleanly. No bpy/context
        here -> unit-testable on a stand-in self."""
        self._commands.do(command.MacroCommand([
            base.PlacePointCommand(self.points, screen_pt),
            base.PlacePointCommand(self.world_points, world_pt),
        ]))

    def _sync_points_from_world(self, context):
        """Re-project the anchored 3D points back to screen for the *current*
        view, so a shape on a fixed plane stays put when the user orbits/zooms
        mid-draw. VIEW plane intentionally tracks the camera, so it is left
        alone. A point that projects off-screen keeps its last screen value."""
        if self.plane == 'VIEW' or not self.world_points:
            return
        region, rv3d = context.region, context.region_data
        for i, w in enumerate(self.world_points):
            if w is None or i >= len(self.points):
                continue
            s = raycast.world_to_screen(region, rv3d, w)
            if s is not None:
                self.points[i] = (s[0], s[1])

    def _snap_screen(self, context, screen_co, force_grid=False):
        """Snap the cursor in order: 1) vertex/edge geometry, 2) world grid,
        3) raw. self._snap_hit is set for the visual marker. `force_grid` (Ctrl
        held) forces the world-grid snap on and skips geometry snap -- a momentary
        precise incremental snap regardless of the persistent toggles."""
        self._snap_hit = None

        # 1) geometry snap -- if present overrides grid (precision snap). Ctrl
        # (force_grid) bypasses it to lock straight onto the grid.
        if self.geo and self._geo_enabled and not force_grid:
            hit = self._geo_snap(context, screen_co)
            if hit is not None:
                self._snap_hit = hit
                return (hit[0][0], hit[0][1])

        # 2) world-scale grid snap
        if self.snap or force_grid:
            prefs = get_prefs(context)
            region, rv3d = context.region, context.region_data
            origin, right, up, normal = self._plane_basis(context)
            p3d = raycast.ray_to_plane(region, rv3d, screen_co, origin, normal)
            if p3d is not None:
                u, v = raycast.world_to_plane_uv(p3d, origin, right, up)
                u, v = grid.snap_world(u, v, self.grid_size, True)
                world = raycast.plane_uv_to_world(u, v, origin, right, up)
                screen = raycast.world_to_screen(region, rv3d, world)
                if screen is not None:
                    return (screen[0], screen[1])

        # 3) raw mouse point
        return (screen_co[0], screen_co[1])

    # --- numeric size entry (type an exact dimension) -------------------

    _DIGIT_KEYS = {
        'ZERO': '0', 'ONE': '1', 'TWO': '2', 'THREE': '3', 'FOUR': '4',
        'FIVE': '5', 'SIX': '6', 'SEVEN': '7', 'EIGHT': '8', 'NINE': '9',
        'NUMPAD_0': '0', 'NUMPAD_1': '1', 'NUMPAD_2': '2', 'NUMPAD_3': '3',
        'NUMPAD_4': '4', 'NUMPAD_5': '5', 'NUMPAD_6': '6', 'NUMPAD_7': '7',
        'NUMPAD_8': '8', 'NUMPAD_9': '9',
    }

    def _numeric_value(self):
        """The positive metre value currently typed, or None for an empty /
        partial / non-positive entry."""
        try:
            v = float(self.typed)
        except ValueError:
            return None
        return v if v > 0.0 else None

    def _apply_numeric(self, context):
        """Lock self.cursor so the drawn shape's size (anchor -> cursor) equals
        the typed distance in plane metres, along the current cursor direction.
        With no valid number typed, the cursor is just the snapped raw point."""
        v = self._numeric_value()
        if v is None or not self.points:
            self.cursor = self._raw_cursor
            return
        region, rv3d = context.region, context.region_data
        origin, right, up, normal = self._plane_basis(context)
        anchor = self.points[-1] if self.shape == 'POLY' else self.points[0]
        a3 = raycast.ray_to_plane(region, rv3d, anchor, origin, normal)
        c3 = raycast.ray_to_plane(region, rv3d, self._raw_cursor, origin, normal)
        if a3 is None or c3 is None:
            self.cursor = self._raw_cursor
            return
        a_uv = raycast.world_to_plane_uv(a3, origin, right, up)
        c_uv = raycast.world_to_plane_uv(c3, origin, right, up)
        lu, lv = grid.lock_distance(a_uv, c_uv, v)
        world = raycast.plane_uv_to_world(lu, lv, origin, right, up)
        screen = raycast.world_to_screen(region, rv3d, world)
        self.cursor = (screen[0], screen[1]) if screen is not None \
            else self._raw_cursor

    # --- vertex / edge snap (v0.2) --------------------------------------

    # On very dense meshes projecting every vertex on each mouse move is
    # expensive; above this threshold geometry snap turns off.
    _GEO_MAX_VERTS = 20000

    def _collect_snap_geometry(self, context):
        """Collect the target's world-space vertex / edge-midpoint / edge lists
        once (the object does not move during the modal). _geo_enabled only
        means 'is the mesh light enough for snap'; toggling is via self.geo."""
        obj = context.active_object
        mw = obj.matrix_world
        # Read the live edit-mesh in Edit Mode (unapplied), object data otherwise.
        if self.edit:
            import bmesh
            bm = bmesh.from_edit_mesh(obj.data)
            verts = [mw @ v.co for v in bm.verts]
            edges = [(e.verts[0].index, e.verts[1].index) for e in bm.edges]
        else:
            me = obj.data
            verts = [mw @ v.co for v in me.vertices]
            edges = [tuple(e.vertices) for e in me.edges]
        self._geo_enabled = len(verts) <= self._GEO_MAX_VERTS
        self._geo_verts = []
        self._geo_mids = []
        self._geo_edges = []
        if not self._geo_enabled:
            if self.geo:
                self.report({'INFO'}, "Vertex snap: mesh too dense, disabled")
            return
        self._geo_verts = verts
        for i, j in edges:
            self._geo_edges.append((i, j))
            self._geo_mids.append((self._geo_verts[i] + self._geo_verts[j]) * 0.5)

    def _geo_snap(self, context, screen_co):
        """Nearest vertex/midpoint/edge screen point to the cursor, disambiguated
        so the *geometrically closest* target wins (vertex priority only breaks
        near-ties). Returns ((x, y), kind) ('VERT'/'MID'/'EDGE') or None."""
        prefs = get_prefs(context)
        region, rv3d = context.region, context.region_data
        thr = prefs.snap_pixels

        def to_screen(world_pts):
            out = []
            for w in world_pts:
                s = raycast.world_to_screen(region, rv3d, w)
                out.append((s[0], s[1]) if s is not None else None)
            return out

        vscr = to_screen(self._geo_verts)
        segs = [(vscr[i], vscr[j]) for (i, j) in self._geo_edges]
        candidates = [
            ('VERT', snap.nearest_point(screen_co, vscr, thr)),
            ('MID', snap.nearest_point(screen_co, to_screen(self._geo_mids), thr)),
            ('EDGE', snap.nearest_on_segments(screen_co, segs, thr)),
        ]
        best = snap.resolve_snap(candidates)
        if best is None:
            return None
        kind, hit = best
        return (hit[1], kind)

    def _grid_screen_verts(self, context):
        """Convert the visible world grid into a screen-space LINES vertex list."""
        region, rv3d = context.region, context.region_data
        origin, right, up, normal = self._plane_basis(context)
        us, vs = [], []
        for c in ((0, 0), (region.width, 0),
                  (0, region.height), (region.width, region.height)):
            p = raycast.ray_to_plane(region, rv3d, c, origin, normal)
            if p is None:
                return []  # plane edge-on: grid cannot be drawn
            u, v = raycast.world_to_plane_uv(p, origin, right, up)
            us.append(u); vs.append(v)
        segs = grid.world_grid_segments(min(us), max(us), min(vs), max(vs),
                                        self.grid_size)
        verts = []
        for (u1, v1), (u2, v2) in segs:
            a = raycast.world_to_screen(
                region, rv3d, raycast.plane_uv_to_world(u1, v1, origin, right, up))
            b = raycast.world_to_screen(
                region, rv3d, raycast.plane_uv_to_world(u2, v2, origin, right, up))
            if a is not None and b is not None:
                verts.append((a[0], a[1]))
                verts.append((b[0], b[1]))
        return verts

    # --- visual feedback ------------------------------------------------

    def _shape_corners(self, a, b):
        """The two-point shape (BOX/CIRCLE/NGON) corners from diagonal/center a
        and edge b, in whatever 2D space a and b live in (screen pixels or plane
        u,v meters). POLY is handled by the caller."""
        if self.shape == 'BOX':
            return grid.box_points(a, b)
        if self.shape == 'CIRCLE':
            return grid.circle_points(a, b)
        if self.shape == 'NGON':
            return grid.ngon_points(a, b, self.sides)
        if self.shape == 'SLOT':
            return grid.slot_points(a, b, self.sides)
        if self.shape == 'STAR':
            return grid.star_points(a, b, self.sides)
        if self.shape == 'ARC':
            return grid.arc_points(a, b, self.sides, self.arc_sweep)
        return []

    def _shape_screen_points(self, context):
        if self.shape == 'POLY':
            pts = list(self.points)
            if pts:
                pts = pts + [self.cursor]
            return pts
        if not self.points:
            return []
        a = self.points[0]
        b = self.points[1] if len(self.points) > 1 else self.cursor
        # VIEW faces the camera -> a screen-aligned outline is correct. On a
        # fixed plane (SURFACE/EDGES/X/Y/Z) build the shape in the plane's (u, v)
        # meter space instead, so its edges line up with the surface grid and the
        # preview foreshortens onto the plane (in-plane, on-surface feel)
        # rather than reading as a flat screen overlay.
        if self.plane == 'VIEW':
            return self._shape_corners(a, b)
        return self._plane_shape_screen(context, a, b)

    def _plane_shape_screen(self, context, a, b):
        """Build a two-point shape on the active fixed plane: convert the two
        screen anchors to the plane's (u, v) meters, lay out the box/circle/n-gon
        there (so it is plane-axis-aligned), then project each corner back to
        screen for display. Falls back to a screen-space outline if the plane is
        edge-on or a corner projects off-screen."""
        region, rv3d = context.region, context.region_data
        origin, right, up, normal = self._plane_basis(context)
        a3 = raycast.ray_to_plane(region, rv3d, a, origin, normal)
        b3 = raycast.ray_to_plane(region, rv3d, b, origin, normal)
        if a3 is None or b3 is None:
            return self._shape_corners(a, b)
        a_uv = raycast.world_to_plane_uv(a3, origin, right, up)
        b_uv = raycast.world_to_plane_uv(b3, origin, right, up)
        out = []
        for u, v in self._shape_corners(a_uv, b_uv):
            w = raycast.plane_uv_to_world(u, v, origin, right, up)
            s = raycast.world_to_screen(region, rv3d, w)
            if s is None:
                return self._shape_corners(a, b)
            out.append((s[0], s[1]))
        return out

    def _draw_px(self, context):
        prefs = get_prefs(context)
        region = context.region
        self._sync_points_from_world(context)  # keep a fixed-plane shape anchored

        if self.snap:
            hud.draw_grid(self._grid_screen_verts(context),
                          tuple(prefs.grid_color))

        # Dynamic alignment guides: light up a full-span dashed line whenever the
        # live cursor is square (same screen X or Y) with a placed point -- the
        # BoxCutter-style hint that the next corner lines up with an earlier one.
        if self.points and self.cursor is not None:
            hud.draw_alignment_guides(region, self.points, self.cursor)

        pts = self._shape_screen_points(context)
        closed = self.shape != 'POLY' or len(self.points) >= 2
        width = prefs.line_width * context.preferences.system.ui_scale
        hud.draw_shape(pts, tuple(prefs.line_color), closed=closed, width=width)
        hud.draw_points(self.points, tuple(prefs.line_color))

        # if vertex/edge snap caught, mark the cursor with the premium ring + dot
        # marker, colored by its kind (shared with every other draw tool).
        if self._snap_hit is not None:
            point, kind = self._snap_hit
            col = _SNAP_COLORS.get(kind, (1.0, 1.0, 1.0, 1.0))
            hud.draw_snap_marker(point, color=col)

        accent = tuple(prefs.line_color)[:3] + (1.0,)
        dim = (0.72, 0.72, 0.72, 1.0)
        plane_label = self.plane
        if self.plane == 'SURFACE' and self._surface_miss:
            plane_label = "SURFACE (no face -> VIEW)"
        elif self.plane == 'EDGES':
            plane_label = "EDGES (Ctrl+Click = set main)"
        status = (
            f"Shape {self.shape}    Mode {self.mode}    Plane {plane_label}"
            f"        Snap {'ON' if self.snap else 'OFF'}"
            f"    Geo {'ON' if self.geo else 'OFF'}"
            f"    ND {'ON' if self.nd else 'OFF'}"
        )
        # The common toggles/cycles now live in the bottom shortcut bar; the HUD
        # keeps the status plus one compact line for the less-frequent keys.
        lines = [
            status,
            ("Q/W/E/R/T/Y/U shape    type = exact size    < > plane    "
             "Shift+< > rotate    Ctrl=snap grid    Ctrl+Wheel grid    "
             "PgUp/Dn depth (Shift fine)    H origin    G stamp    S save", dim),
        ]
        # Surface the in-draw operation state only when something is active.
        bits = []
        if abs(self.inset) > 1e-9:
            bits.append("inset %.3f m" % self.inset)
        if abs(self.rotation) > 1e-9:
            bits.append("rot %.0f°" % math.degrees(self.rotation))
        if self.array_count > 1:
            bits.append("array x%d %s" % (self.array_count, self.array_axis))
        if self.mirror_axis:
            bits.append("mirror %s" % self.mirror_axis)
        if abs(self.plane_spin) > 1e-9:
            bits.append("grid spin %.0f°" % math.degrees(self.plane_spin))
        if self._forced_main_key is not None:
            bits.append("main edge set")
        if self.grid_origin is not None:
            bits.append("grid origin set")
        if self.bevel_cut:
            bits.append("bevel-on-cut")
        if self.cutter_bevel:
            bits.append("cutter bevel")
        if self.live_bool:
            bits.append("live boolean")
        if self.orientation == 'PROJECT':
            bits.append("project")
        if self.depth > 1e-6:
            bits.append("depth %.3f m" % self.depth)
        bits.append("grid %.3f m" % self.grid_size)
        if self.typed:
            bits.insert(0, "size %s m (typing)" % self.typed)
        if bits:
            lines.insert(1, ("   ".join(bits), accent))
        measure = self._measure(context)
        if measure:
            lines.insert(0, (measure, accent))  # measurement line accented, on top
        hud.draw_hud(region, lines, title="Draw Cut", accent=accent)

        # Premium shortcut bar along the bottom: the pressable toggles/cycles with
        # their live engaged state (accent key box = ON / current mode).
        hud.draw_shortcut_bar(region, [
            ("Tab", self.mode.title()),
            ("[ ]", "Sides/Arc"),
            ("B", "Bevel", self.bevel_cut),
            ("C", "Cutter Bvl", self.cutter_bevel),
            ("J", "Live Bool", self.live_bool),
            ("O", "Project", self.orientation == 'PROJECT'),
            ("M", "Mirror", bool(self.mirror_axis)),
            ("V", "Vertex", self.geo),
            ("N", "Non-Destr", self.nd),
            ("Enter", "Apply"),
            ("Esc", "Cancel"),
        ])

    def _measure(self, context):
        """Return the world-scale size of the shape being drawn, in meters."""
        if not self.points:
            return ""
        region, rv3d = context.region, context.region_data
        origin, right, up, normal = self._plane_basis(context)

        def uv(screen_co):
            p = raycast.ray_to_plane(region, rv3d, screen_co, origin, normal)
            if p is None:
                return None
            return raycast.world_to_plane_uv(p, origin, right, up)

        a = uv(self.points[0])
        b = uv(self.points[1] if len(self.points) > 1 else self.cursor)
        if a is None or b is None:
            return ""
        if self.shape == 'BOX':
            return "Size:  %.3f x %.3f m" % (abs(b[0] - a[0]), abs(b[1] - a[1]))
        if self.shape == 'CIRCLE':
            r = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            return "Radius:  %.3f m   Diameter:  %.3f m" % (r, 2 * r)
        if self.shape == 'NGON':
            r = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            return "Sides:  %d   Radius:  %.3f m" % (self.sides, r)
        if self.shape == 'SLOT':
            return "Slot:  %.3f x %.3f m" % (abs(b[0] - a[0]), abs(b[1] - a[1]))
        if self.shape == 'STAR':
            r = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            return "Star:  %d points   Radius:  %.3f m" % (self.sides, r)
        if self.shape == 'ARC':
            r = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            return "Arc:  %.0f deg   Radius:  %.3f m" % (
                math.degrees(self.arc_sweep), r)
        # POLY: point count + last segment length
        last = uv(self.points[-1])
        cur = uv(self.cursor)
        seg = ""
        if last is not None and cur is not None:
            seg = "   last segment %.3f m" % (
                ((cur[0] - last[0]) ** 2 + (cur[1] - last[1]) ** 2) ** 0.5)
        return "Point: %d%s" % (len(self.points), seg)

    # --- live 3D preview -------------------------------------------------

    def _preview_screen_points(self, context):
        """Screen points defining the in-progress shape, including the hovering
        cursor (so the volume previews the segment being drawn)."""
        if self.shape == 'POLY':
            pts = list(self.points)
            if self.points:
                pts = pts + [self.cursor]
            return pts
        return self._shape_screen_points(context)

    _AXIS_VEC = {
        'X': Vector((1.0, 0.0, 0.0)),
        'Y': Vector((0.0, 1.0, 0.0)),
        'Z': Vector((0.0, 0.0, 1.0)),
    }

    def _processed_corner_sets(self, context, screen_pts):
        """World corner sets for the drawn shape after the in-draw operations
        (v1.4): in-plane rotation + inset, then replicated for Array and Mirror.
        Returns (sets, normal) where sets is a list of (corners, view_dir); or
        ([], None) when the shape can't be projected onto the plane."""
        from ..core import offset as offset_mod
        region, rv3d = context.region, context.region_data
        origin, right, up, normal = self._plane_basis(context)
        world = [raycast.ray_to_plane(region, rv3d, p, origin, normal)
                 for p in screen_pts]
        if any(c is None for c in world):
            return [], None

        # Rotation + inset happen in the plane's (u, v) meter space.
        uv = [raycast.world_to_plane_uv(c, origin, right, up) for c in world]
        if abs(self.rotation) > 1e-9:
            uv = grid.rotate_2d(uv, self.rotation)
        if abs(self.inset) > 1e-9:
            off = offset_mod.offset_polygon(uv, self.inset)
            if off is not None:
                uv = off
        base = [raycast.plane_uv_to_world(u, v, origin, right, up) for u, v in uv]

        # Array: stamp N copies edge-to-edge along a world axis.
        sets = [(base, normal)]
        if self.array_count > 1:
            axis = self._AXIS_VEC[self.array_axis]
            idx = {'X': 0, 'Y': 1, 'Z': 2}[self.array_axis]
            coords = [c[idx] for c in base]
            step = max(coords) - min(coords)
            if step < 1e-6:
                step = self.grid_size
            sets = [([c + axis * (step * i) for c in base], normal)
                    for i in range(self.array_count)]

        # Mirror: reflect every set across the plane through the object origin.
        if self.mirror_axis:
            o = context.active_object.matrix_world.translation
            nrm = self._AXIS_VEC[self.mirror_axis]

            def reflect(p):
                return p - nrm * (2.0 * (p - o).dot(nrm))

            mirrored = [([reflect(c) for c in corners],
                         (vd - nrm * (2.0 * vd.dot(nrm))).normalized())
                        for corners, vd in sets]
            sets = sets + mirrored
        return sets, normal

    def _build_preview_mesh(self, context):
        """Build the real 3D cutter volume (or FACE mesh) for the shape currently
        on screen, in world space. Returns mesh data or None when the shape is not
        yet valid (too few points, edge-on plane, self-intersecting, ...)."""
        screen_pts = self._preview_screen_points(context)
        if len(screen_pts) < 3:
            return None
        if self.shape == 'POLY' and grid.is_self_intersecting(screen_pts):
            return None
        if self.mode == 'KNIFE':
            return None  # scoring only -> the 2D outline is the whole preview
        sets, _normal = self._processed_corner_sets(context, screen_pts)
        if not sets:
            return None
        if self.mode == 'FACE':
            return geometry.build_faces(sets, name="hf_preview")
        return geometry.build_prisms(sets, self._thickness(context),
                                     name="hf_preview",
                                     apex=self._project_apex(context.region_data))

    def _thickness(self, context):
        """Cutter depth: the explicit live thickness (PgUp/PgDn) when set, else a
        depth large enough to pierce all targets."""
        if self.depth > 1e-6:
            return self.depth
        return max(geometry.estimate_thickness(t)
                   for t in self._targets(context))

    def _project_apex(self, rv3d):
        """World-space camera position for PROJECT orientation, else None. Each
        cutter corner is extruded along its own ray from this apex, giving the
        perspective taper of Blender's Polyline Trim Project mode. Returns None
        for FIXED, or in an orthographic view (parallel rays -> same as FIXED)."""
        if (self.orientation != 'PROJECT' or rv3d is None
                or not rv3d.is_perspective):
            return None
        return rv3d.view_matrix.inverted_safe().translation.copy()

    def _preview_signature(self):
        """A cheap hashable snapshot of everything that determines the live cutter
        volume. Two consecutive modal events with an equal signature build an
        identical cage, so the rebuild can be skipped. The placed points are kept
        in current-view screen space (re-anchored every event by
        `_sync_points_from_world`), so an orbit/zoom changes them and forces a
        rebuild; the world-space cage is regenerated from those + the cursor."""
        origin = self.grid_origin
        return (
            self.shape, self.mode, self.sides, round(self.arc_sweep, 5),
            round(self.inset, 5), round(self.rotation, 5),
            self.array_count, self.array_axis, self.mirror_axis,
            self.cutter_bevel, self.orientation, round(self.depth, 5),
            round(self.grid_size, 6), self.plane, round(self.plane_spin, 5),
            None if origin is None
            else (round(origin.x, 4), round(origin.y, 4), round(origin.z, 4)),
            (round(self.cursor[0], 1), round(self.cursor[1], 1)),
            tuple((round(p[0], 1), round(p[1], 1)) for p in self.points),
            self.live_bool,
        )

    def _update_preview(self, context):
        """Refresh the live preview object. Shown as a wireframe drawn in front,
        non-selectable, so it reads as a cutter cage over the model and never
        interferes with picking. When the live boolean preview is on, a temporary
        Boolean modifier on the target then shows the actual cut result."""
        if self.edit:
            return  # Edit Mode: the 2D shape outline is the preview (no cage)
        # The modal rebuilds the preview on every event (mouse-move included). Within
        # one snapped grid cell the signature is stable, so skip the bmesh rebuild +
        # live-boolean re-evaluation when nothing relevant changed -- the dominant
        # responsiveness win while dragging. A missing cage forces a rebuild even on
        # a stable signature.
        sig = self._preview_signature()
        if sig == self._preview_sig and self._preview is not None:
            return
        self._preview_sig = sig
        try:
            mesh = self._build_preview_mesh(context)
        except Exception:  # noqa: BLE001 -- preview must never break the modal
            mesh = None
        if mesh is None:
            self._clear_preview()
        elif self._preview is None:
            self._preview = bpy.data.objects.new("hf_preview", mesh)
            context.collection.objects.link(self._preview)
            self._preview.display_type = 'WIRE'
            self._preview.show_in_front = True
            self._preview.hide_select = True
        else:
            old = self._preview.data
            self._preview.data = mesh
            if old is not None and old.users == 0:
                bpy.data.meshes.remove(old)
        self._sync_live_boolean(context)

    def _clear_preview(self):
        if self._preview is not None and self._preview.name in bpy.data.objects:
            data = self._preview.data
            bpy.data.objects.remove(self._preview, do_unlink=True)
            if data is not None and data.users == 0:
                bpy.data.meshes.remove(data)
        self._preview = None

    # --- live boolean preview (the actual cut result, drawn before commit) ----

    @staticmethod
    def _world_aabb(obj):
        """World-space axis-aligned bounding box of `obj` (its local bound_box
        corners transformed by matrix_world), as (min, max) for the pure
        core.preview_cache overlap test. None for an object with no bounds."""
        mw = obj.matrix_world
        corners = [mw @ Vector(c) for c in obj.bound_box]
        return preview_cache.aabb([(c.x, c.y, c.z) for c in corners])

    def _clear_live_boolean(self, context):
        """Strip the live-preview boolean modifier(s) via the LivePreviewCommand.
        Idempotent; called before the real cut on commit and on cancel."""
        if self._live_cmd is not None:
            self._live_cmd.clear(context)
        self._live_targets = None
        self._live_gate.reset()

    def _sync_live_boolean(self, context):
        """Show the actual boolean RESULT on the target(s) while drawing, through
        the named base.LivePreviewCommand: a temporary Boolean modifier pointing
        at the live cutter cage, so Blender's viewport evaluates the real
        subtraction/union as the shape changes. Active only for the boolean modes
        (Cut/Make/Intersect) with a valid cutter, the live preview on, and the
        target light enough; stripped otherwise. The temp modifier is always
        removed before the real cut (see `_commit`).

        High-poly guard (core/preview_cache): a target is previewed only when it
        is under the vertex cap AND its world bounding box actually overlaps the
        cutter cage's -- so a heavy mesh the cut isn't near never carries the temp
        modifier. A distance gate then skips re-pointing the modifiers on sub-grid
        cursor jitter, so the boolean isn't re-evaluated every frame while idle."""
        op = {'CUT': 'DIFFERENCE', 'MAKE': 'UNION',
              'INTERSECT': 'INTERSECT'}.get(self.mode)
        if not (self.live_bool and op is not None and self._preview is not None):
            self._clear_live_boolean(context)
            return
        cap = get_prefs(context).live_preview_max_verts
        # Pad the cutter box a touch so a target just grazing the cut still counts.
        cutter_box = preview_cache.expand_aabb(
            self._world_aabb(self._preview), self.grid_size * 0.5)
        targets = [
            t for t in self._targets(context)
            if t is not None and t.type == 'MESH'
            and len(t.data.vertices) <= cap
            and preview_cache.boxes_overlap(cutter_box, self._world_aabb(t))]

        if self._live_cmd is None:
            self._live_cmd = base.LivePreviewCommand(self._preview, op)
            self._live_cmd.execute()
        # Always re-sync when the target set, the operation, or the cutter object
        # changed (a modifier must be added / stripped / retargeted); otherwise
        # let the distance gate throttle redundant re-points on tiny cursor moves.
        # (The preview object keeps its identity across frames -- only its mesh
        # data is swapped -- so Blender re-evaluates the boolean when the cage
        # changes even on a gated frame.)
        # Identify the target set by name (stable across frames -- bpy wrapper
        # identity / id() is not), so the gate can actually recognise "same set".
        target_ids = frozenset(t.name for t in targets)
        changed = (target_ids != self._live_targets
                   or op != self._live_cmd.operation
                   or self._live_cmd.cutter is not self._preview)
        center = None
        if cutter_box is not None:
            lo, hi = cutter_box
            center = tuple((lo[i] + hi[i]) * 0.5 for i in range(3))
        if not changed and center is not None \
                and not self._live_gate.should_update(center):
            return
        self._live_targets = target_ids
        # The wire cutter cage is rebuilt each frame, so re-point every sync.
        self._live_cmd.cutter = self._preview
        self._live_cmd.operation = op
        self._live_cmd.refresh(targets)

    # --- geometry application -------------------------------------------

    def _commit(self, context):
        self._clear_live_boolean(context)  # strip temp preview mods before the cut
        self._clear_preview()  # drop the visual cage before building the real one
        try:
            self._build_and_apply(context)
        except Exception as ex:  # close the draw mode cleanly
            self.report({'ERROR'}, f"Hardflow: {ex}")
        self._cleanup(context)
        return {'FINISHED'}

    def _build_and_apply(self, context):
        prefs = get_prefs(context)

        # POLY: on commit only the clicked points; do not include the hovering
        # cursor.
        if self.shape == 'POLY':
            screen_pts = list(self.points)
        else:
            screen_pts = self._shape_screen_points(context)
        if len(screen_pts) < 3:
            return

        # A self-intersecting polygon produces a broken cutter -> warn and cancel.
        if self.shape == 'POLY' and grid.is_self_intersecting(screen_pts):
            self.report({'WARNING'},
                        "Polygon self-intersects; cut cancelled")
            return

        sets, normal = self._processed_corner_sets(context, screen_pts)
        if not sets:
            self.report({'WARNING'}, "Plane edge-on; shape could not be projected")
            return
        self._remember()             # for the G stamp/repeat key

        # Edit Mode: write the shape straight into the active edit-mesh -- faces
        # for MAKE/FACE, knife scores for CUT/SLICE/KNIFE -- no cutter object.
        if self.edit:
            self._build_and_apply_edit(context, sets)
            return

        # FACE: not boolean; create a face object from the drawn shape(s).
        if self.mode == 'FACE':
            self._build_face(context, sets)
            return

        # KNIFE: zero-depth score on the active mesh, no boolean.
        if self.mode == 'KNIFE':
            self._knife_object(context, sets)
            return

        # JOIN: add the drawn volume as its own solid object, no boolean (parity
        # with Blender's Polyline Trim "Join" mode).
        if self.mode == 'JOIN':
            self._build_solid(context, sets)
            return

        targets = self._targets(context)
        # Array/Mirror copies are baked into one cutter mesh; depth = live
        # thickness when set, else big enough to pierce all targets. apex tapers
        # the cutter with perspective in PROJECT orientation (None = Fixed).
        cutter_mesh = geometry.build_prisms(
            sets, self._thickness(context),
            apex=self._project_apex(context.region_data))
        if cutter_mesh is None:
            self.report({'WARNING'}, "Invalid shape")
            return
        if self.cutter_bevel:
            self._chamfer_cutter(cutter_mesh)
        cutter = bpy.data.objects.new("hf_cutter", cutter_mesh)
        context.collection.objects.link(cutter)

        solver = prefs.default_solver if self.solver == 'DEFAULT' else self.solver
        if self.nd:
            self._apply_nondestructive(context, targets, cutter, solver)
        else:
            self._apply_destructive(context, targets, cutter, solver)
        if self.bevel_cut:
            self._bevel_on_cut(targets)
        # Cut-to-Trim bridge: route a pipe / panel line along the drawn boundary,
        # draped onto the (now cut) surface -- the Hard-Surface -> Decal link.
        self._auto_trim(context, sets, targets)

    # --- Cut-to-Trim bridge (Hard-Surface -> Decal) ---------------------

    def _trim_collection(self, context):
        """Get/create the collection that gathers the auto cut-boundary trims."""
        coll = bpy.data.collections.get("Hardflow Trim")
        if coll is None:
            coll = bpy.data.collections.new("Hardflow Trim")
            context.scene.collection.children.link(coll)
        return coll

    def _auto_trim(self, context, sets, targets):
        """Route a pipe / panel line along the drawn cut boundary (draped onto the
        active target so it hugs the recess) -- so a boolean cut is instantly
        detailed with a panel line / cable, like scoring with a knife and having
        the seam appear. The drawn footprint IS the boundary, so it always matches
        the cut. Non-destructive: separate curve objects in a 'Hardflow Trim'
        collection, parented to the target. Wrapped so a failure never aborts the
        cut that already succeeded."""
        from ..core import snapping, transform
        prefs = get_prefs(context)
        mode = prefs.auto_trim_after_cut
        if mode == 'OFF' or not sets or not targets:
            return
        radius = prefs.auto_trim_radius
        lift = prefs.auto_trim_lift
        if mode == 'PANEL' and lift == 0.0:
            lift = -radius            # a panel line sits slightly recessed
        target = targets[0]
        try:
            coll = self._trim_collection(context)
            made = 0
            for corners, _vd in sets:
                ring = transform.dedup_ring([(c.x, c.y, c.z) for c in corners])
                if len(ring) < 3:
                    continue
                draped = snapping.drape_path(context, ring, segments=4,
                                             lift=lift, target='ACTIVE')
                pts = [(v.x, v.y, v.z) for v in draped]
                curve = geometry.build_pipe(pts, radius=radius, name="HF_Trim",
                                            closed=True)
                if curve is None:
                    continue
                obj = bpy.data.objects.new("HF_Trim", curve)
                coll.objects.link(obj)
                obj.parent = target
                obj.matrix_parent_inverse = target.matrix_world.inverted_safe()
                made += 1
            if made:
                self.report({'INFO'},
                            "Cut-to-Trim: %d boundary line(s) added" % made)
        except Exception as ex:  # noqa: BLE001 -- the cut already committed
            self.report({'WARNING'}, "Cut-to-Trim skipped: %s" % ex)

    # --- stamp / repeat last shape (v1.4, repeat / stamp) ---------------

    _LAST = None  # class-level: the last committed shape, replayed with G

    _STAMP_KEYS = ('shape', 'mode', 'sides', 'plane', 'inset', 'rotation',
                   'array_count', 'array_axis', 'mirror_axis', 'bevel_cut',
                   'orientation')

    def _remember(self):
        """Snapshot the just-committed shape (clicked points + all parameters) so
        the next draw session can replay it with G."""
        data = {'points': list(self.points)}
        for key in self._STAMP_KEYS:
            data[key] = getattr(self, key)
        HARDFLOW_OT_draw._LAST = data

    def _stamp_last(self, context):
        """Replay the previous shape+size+params at the same screen location."""
        last = HARDFLOW_OT_draw._LAST
        if last is None or len(last['points']) < 2:
            self.report({'INFO'}, "No previous shape to stamp")
            return {'RUNNING_MODAL'}
        for key in self._STAMP_KEYS:
            setattr(self, key, last[key])
        self.points = list(last['points'])
        # Stamp replays the stored screen points in the current view and commits
        # immediately, so there are no live anchors to keep in sync.
        self.world_points = []
        self._clear_live_boolean(context)
        self._clear_preview()
        try:
            self._build_and_apply(context)
        except Exception as ex:  # noqa: BLE001
            self.report({'ERROR'}, f"Hardflow: {ex}")
        self._cleanup(context)
        return {'FINISHED'}

    def _save_settings(self, context):
        """Write the live HUD toggles back to the addon preferences so the next
        draw session starts with them. Saves the session-level settings shown in
        the status line (snap/geo/ND, grid spacing, N-gon sides, plane); shape
        and mode stay per-entry-point (driven by the menu/pie item)."""
        prefs = get_prefs(context)
        prefs.snap_enabled = self.snap
        prefs.geo_snap = self.geo
        prefs.non_destructive = self.nd
        prefs.grid_world = self.grid_size
        prefs.ngon_sides = self.sides
        prefs.default_plane = self.plane
        self.report({'INFO'}, "Hardflow: draw settings saved as default")

    def _targets(self, context):
        """If multi-object mode is on, all selected meshes (CUT/MAKE); otherwise
        only the active object. SLICE/FACE always operate on the active one."""
        active = context.active_object
        if (get_prefs(context).multi_object
                and self.mode in {'CUT', 'MAKE', 'INTERSECT'}):
            sel = [o for o in context.selected_objects if o.type == 'MESH']
            return sel if sel else [active]
        return [active]

    def _build_face(self, context, sets):
        """Create a new face object from the drawn shape(s) -- one n-gon per
        Array/Mirror copy, all in one mesh (create face)."""
        mesh = geometry.build_faces(sets)
        if mesh is None:
            self.report({'WARNING'}, "Invalid face")
            return
        obj = bpy.data.objects.new("Hardflow_Face", mesh)
        context.collection.objects.link(obj)
        for o in list(context.selected_objects):
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj

    def _build_solid(self, context, sets):
        """JOIN: create a separate solid object from the drawn shape(s) -- the
        extruded prism volume, added to the scene without any boolean. The
        Polyline Trim "Join" mode: block out new geometry next to the model."""
        mesh = geometry.build_prisms(
            sets, self._thickness(context),
            apex=self._project_apex(context.region_data))
        if mesh is None:
            self.report({'WARNING'}, "Invalid shape")
            return
        obj = bpy.data.objects.new("Hardflow_Solid", mesh)
        context.collection.objects.link(obj)
        for o in list(context.selected_objects):
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj

    def _knife_object(self, context, sets):
        """KNIFE in Object Mode: score the drawn loop(s) onto the active mesh
        (zero-depth, no boolean). Prefers Blender's view-accurate `knife_project`,
        which clips the score to the exact drawn outline; falls back to the
        footprint-restricted object-data knife when the viewport operator can't
        run (no region / edge-on plane / projection failure)."""
        if self._knife_project_object(context, sets):
            return
        obj = context.active_object
        mw_inv = obj.matrix_world.inverted_safe()
        rot = mw_inv.to_3x3()
        scored = 0
        for corners, vd in sets:
            local = [mw_inv @ c for c in corners]
            scored += geometry.knife_polygon(obj, local, (rot @ vd).normalized())
        if scored == 0:
            self.report({'WARNING'}, "Knife cut scored nothing")

    def _knife_project_object(self, context, sets):
        """Pixel-accurate knife via `bpy.ops.mesh.knife_project`: build a wire
        cutter from the drawn loop(s) and project it along the *current* view onto
        the active mesh, so the score follows the exact drawn silhouette instead of
        a full-width bisect per face. Returns True on success, False to let
        `_knife_object` fall back to the footprint knife.

        Runs in the modal's own VIEW_3D context. The cutter must be the only OTHER
        selected object (the target alone enters Edit Mode -- both entering at once
        would leave knife_project with no projector), so we add it after the mode
        switch. Always restores Object Mode + the user's active object."""
        region = context.region
        rv3d = context.region_data
        obj = context.active_object
        if (region is None or rv3d is None or context.area is None
                or context.area.type != 'VIEW_3D' or obj is None
                or context.mode != 'OBJECT'):
            return False
        import bmesh
        cme = bpy.data.meshes.new("HF_KnifeCutter")
        bm = bmesh.new()
        built = 0
        for corners, _vd in sets:
            if len(corners) < 2:
                continue
            vs = [bm.verts.new((c.x, c.y, c.z)) for c in corners]
            for i in range(len(vs)):
                try:
                    bm.edges.new((vs[i], vs[(i + 1) % len(vs)]))
                except ValueError:
                    pass               # duplicate edge from a repeated corner
            built += 1
        if built == 0:
            bm.free()
            bpy.data.meshes.remove(cme)
            return False
        bm.to_mesh(cme)
        bm.free()
        cutter = bpy.data.objects.new("HF_KnifeCutter", cme)
        context.collection.objects.link(cutter)
        context.view_layer.update()
        ok = False
        try:
            with context.temp_override(area=context.area, region=region,
                                       region_data=rv3d):
                bpy.ops.object.select_all(action='DESELECT')
                context.view_layer.objects.active = obj
                obj.select_set(True)             # ONLY the target enters Edit Mode
                bpy.ops.object.mode_set(mode='EDIT')
                cutter.select_set(True)          # the projector (object-level)
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.knife_project(cut_through=False)
                bpy.ops.object.mode_set(mode='OBJECT')
            ok = True
        except Exception as ex:
            self.report({'WARNING'}, "knife_project failed (%s); using footprint"
                        % type(ex).__name__)
            try:
                if obj.mode != 'OBJECT':
                    with context.temp_override(area=context.area, region=region):
                        bpy.ops.object.mode_set(mode='OBJECT')
            except Exception:
                pass
            ok = False
        finally:
            if cutter.name in bpy.data.objects:
                bpy.data.objects.remove(cutter, do_unlink=True)
            try:
                context.view_layer.objects.active = obj
                obj.select_set(True)
            except Exception:
                pass
        return ok

    def _bevel_on_cut(self, targets):
        """Add a small angle-limited bevel to each cut target so the cut edge
        reads as chamfered without a second operator (v1.4 bevel-on-cut). The
        chamfer width scales to each target's size so it stays subtle on large
        objects and visible on small ones."""
        from math import radians
        from ..core import transform
        for t in targets:
            if "HF_CutBevel" in t.modifiers:
                continue
            bev = t.modifiers.new("HF_CutBevel", 'BEVEL')
            bev.width = transform.adaptive_dimension(
                max(t.dimensions), fraction=0.01, min_value=0.0005, max_value=0.25)
            bev.segments = 2
            bev.limit_method = 'ANGLE'
            bev.angle_limit = radians(30.0)
            bev.harden_normals = True
            bev.use_clamp_overlap = True

    def _chamfer_cutter(self, mesh):
        """Bevel every edge of the cutter mesh so the cut leaves chamfered walls
        (C toggle). The width scales to the cutter's own size, capped so a thin
        cutter doesn't collapse (geometry.bevel_cutter clamps overlap too)."""
        from ..core import transform
        co = [v.co for v in mesh.vertices]
        if not co:
            return
        size = max((max(c[i] for c in co) - min(c[i] for c in co))
                   for i in range(3))
        width = transform.adaptive_dimension(
            size, fraction=0.06, min_value=0.0005,
            max_value=max(0.001, size * 0.3))
        geometry.bevel_cutter(mesh, width)

    def _build_and_apply_edit(self, context, sets):
        """Edit Mode commit: project the drawn shape(s) into the active mesh.
        MAKE/JOIN/FACE add n-gon faces; CUT/SLICE/KNIFE score the loops onto the
        surface. Honours the same snap/grid/plane + in-draw pipeline."""
        obj = context.active_object
        mw_inv = obj.matrix_world.inverted_safe()
        rot = mw_inv.to_3x3()
        if self.mode in {'MAKE', 'FACE', 'JOIN'}:
            ok = False
            for corners, _vd in sets:
                ok |= geometry.edit_add_face(obj, [mw_inv @ c for c in corners])
            if not ok:
                self.report({'WARNING'}, "Invalid face")
            return
        # CUT / SLICE / KNIFE -> knife score along each loop's edge planes.
        scored = 0
        for corners, vd in sets:
            local = [mw_inv @ c for c in corners]
            scored += geometry.edit_knife_polygon(obj, local,
                                                  (rot @ vd).normalized())
        if scored == 0:
            self.report({'WARNING'}, "Knife cut scored nothing")

    def _apply_destructive(self, context, targets, cutter, solver):
        """Apply the cutter to the target(s) as an ATOMIC boolean chain: every cut
        commits, or on the first solver failure the whole chain rolls back -- never
        a half-cut target or a half-sliced pair (the crash-safety goal behind the
        Command-Pattern layer). Each cut is a base.BooleanCutCommand (the robust
        boolean path: solver fallback + cutter normal repair + diagnosis) run
        inside one MacroCommand, and the outcome is surfaced so a failed/degraded
        cut is never silent. Cleans up the cutter (and any spare slice duplicate)
        via finally even on failure. CUT/MAKE/INTERSECT support multiple targets;
        SLICE works on the first."""
        prefs = get_prefs(context)
        cleanup = prefs.cleanup_after_cut
        dissolve = prefs.cut_dissolve_ngons
        fix_shading = prefs.fix_shading_after_cut
        op = {'CUT': 'DIFFERENCE', 'MAKE': 'UNION',
              'INTERSECT': 'INTERSECT'}.get(self.mode)
        failures, fallbacks = [], []
        # Fix Shading: snapshot each target's clean normals BEFORE the cut, so the
        # transfer bound afterwards reflects the pre-cut surface onto the n-gons.
        # Map target name -> (helper, created_now): created_now is False when
        # capture_normal_source reused a helper from a prior successful cut, so a
        # rollback below leaves that still-referenced helper alone.
        normal_sources = {}
        if fix_shading:
            for t in targets:
                if t is not None and t.type == 'MESH':
                    created = not boolean.has_normal_source(t)
                    normal_sources[t.name] = (
                        boolean.capture_normal_source(context, t), created)

        # Build the chain. SLICE = DIFFERENCE on the target + INTERSECT on a
        # duplicate (kept as the carved-off piece); CUT/MAKE/INTERSECT = the same
        # op on every target. Each command snapshots its own target under a
        # distinct name so their rollbacks don't collide.
        other = None
        if self.mode == 'SLICE':
            other = boolean.duplicate_object(context, targets[0])
            cut_targets = [(targets[0], 'DIFFERENCE'), (other, 'INTERSECT')]
        else:  # CUT / MAKE / INTERSECT
            cut_targets = [(t, op) for t in targets]
        cmds = [base.BooleanCutCommand(context, tgt, cutter, bop, solver,
                                       snapshot_name="hf_cut_%d" % i)
                for i, (tgt, bop) in enumerate(cut_targets)]
        macro = command.MacroCommand(cmds, label="Boolean chain")

        try:
            try:
                macro.execute()      # atomic: a failing cut rolls the rest back
            except Exception as ex:  # noqa: BLE001 -- report, never crash the modal
                failures.append(str(ex))
            else:
                # Committed cleanly: post-process each cut target + note a drop to
                # the less-accurate FAST solver (a Manifold/EXACT auto-pick is an
                # equal-accuracy speed choice, so it stays quiet).
                for c, (tgt, _bop) in zip(cmds, cut_targets):
                    if c.solver_used == 'FAST' and solver != 'FAST':
                        fallbacks.append('FAST')
                    if cleanup:
                        geometry.cleanup_mesh(tgt)
                    if dissolve:
                        # Re-quad the n-gons the cut left (topology cleanup, opt-in).
                        geometry.dissolve_boolean_ngons(tgt)
                    # Fix Shading: bind the pre-cut normal snapshot back onto the
                    # cut target so its new n-gons shade flat, not smeared.
                    entry = normal_sources.get(tgt.name)
                    if entry is not None:
                        boolean.add_normal_transfer(tgt, entry[0])
            # A rolled-back slice leaves an inconsistent spare duplicate (its
            # target was restored); drop it (and its copied mesh) rather than
            # orphan it.
            if other is not None and failures:
                me = other.data
                if other.name in bpy.data.objects:
                    bpy.data.objects.remove(other, do_unlink=True)
                if me is not None and me.users == 0:
                    bpy.data.meshes.remove(me)
            # A failed cut leaves the targets untouched, so the pre-cut normal
            # snapshots are useless -- drop them rather than orphan hidden helpers.
            # BUT only the ones this cut created: a reused helper is still bound to
            # a prior successful cut's Data Transfer, so removing it would break
            # that earlier cut's shading.
            if failures and normal_sources:
                for src, created in normal_sources.values():
                    if not created:
                        continue
                    sme = src.data
                    if src.name in bpy.data.objects:
                        bpy.data.objects.remove(src, do_unlink=True)
                    if sme is not None and sme.users == 0:
                        bpy.data.meshes.remove(sme)
        finally:
            for c in cmds:
                c.free()             # drop every snapshot datablock
            bpy.data.objects.remove(cutter, do_unlink=True)
        self._report_boolean(failures, fallbacks)

    def _report_boolean(self, failures, fallbacks):
        """Tell the user what the boolean did: warn on failure (with the mesh
        diagnosis), note a solver fallback, otherwise stay quiet."""
        if failures:
            self.report({'WARNING'}, failures[0])
        elif fallbacks:
            self.report({'INFO'}, "Cut done (%s solver fallback)" % fallbacks[0])

    def _apply_nondestructive(self, context, targets, cutter, solver):
        """Leave a live modifier, stash the cutter in the 'Hardflow Cutters'
        collection."""
        op = {'CUT': 'DIFFERENCE', 'MAKE': 'UNION',
              'INTERSECT': 'INTERSECT'}.get(self.mode)
        if self.mode == 'SLICE':
            target = targets[0]
            other = boolean.duplicate_object(context, target)
            # Each half needs its OWN cutter, parented to that half. A single
            # shared cutter can only be parented to one half, so moving the other
            # half would leave its INTERSECT boolean pointing at a cutter that no
            # longer tracks it -- the slice would break on transform.
            cutter_other = boolean.duplicate_object(context, cutter,
                                                    name_suffix="_slice_cutter")
            boolean.add_boolean(target, cutter, 'DIFFERENCE', solver)
            boolean.add_boolean(other, cutter_other, 'INTERSECT', solver)
            boolean.stash_cutter(context, cutter, target)
            boolean.stash_cutter(context, cutter_other, other)
            affected = [target, other]
        else:  # CUT / MAKE / INTERSECT
            for t in targets:
                boolean.add_boolean(t, cutter, op, solver)
            boolean.stash_cutter(context, cutter, targets[0])
            affected = list(targets)
        # A fresh HF_Bool appends to the BOTTOM of the stack -- below any existing
        # Bevel / Weighted Normal, which would cut the wrong (already-shaded)
        # result. Reorder into hard-surface order (booleans on top) so the live
        # preview matches a later bake.
        if get_prefs(context).sort_modifiers_after_cut:
            from .hardops import sort_modifier_stack
            for t in affected:
                sort_modifier_stack(t)

    def _cleanup(self, context):
        self._clear_live_boolean(context)  # strip any temp preview mods first
        self._clear_preview()  # discards the cage on cancel; no-op after commit
        # Drop the placement journal: on commit the net change is the cutter (one
        # Blender undo step); on cancel the placements only touched the in-memory
        # point lists, which die with the operator -- so clear(), never undo_all().
        self._commands.clear()
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        context.area.tag_redraw()
