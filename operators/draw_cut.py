# Main draw operator: draw a shape on screen, project to 3D, apply boolean.
#
# SHAPE: BOX / CIRCLE / POLY / NGON   MODE: CUT / SLICE / MAKE / INTERSECT / FACE / KNIFE
# Shortcuts (inside modal):
#   Left click    place point / start-finish shape
#   Enter         close POLY and apply
#   0-9 . (type)  lock the shape to an exact size (radius / extent / segment, m)
#   Backspace     edit a typed size, else delete last POLY point
#   Q/W/E/R       shape = BOX / CIRCLE / POLY / NGON
#   [ / ]         decrease / increase N-gon side count
#   Tab / Shift+Tab   cycle the mode (Cut/Slice/Make/Intersect/Face/Knife)
#   X             toggle snap
#   Right click / ESC  cancel
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty
from mathutils import Vector

from ..core import raycast, geometry, boolean, grid, snap, decal_math
from ..preferences import get_prefs
from ..ui import draw as hud


_SHAPES = [
    ('BOX', "Box", "Rectangle"),
    ('CIRCLE', "Circle", "Circle"),
    ('POLY', "Polygon", "Freeform polygon"),
    ('NGON', "N-gon", "Regular polygon (side count from preferences / [ ])"),
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
        # In-draw operations (v1.4): all baked into one cutter at commit.
        self.inset = 0.0          # offset the drawn loop in/out (m); -/= adjust
        self.rotation = 0.0       # in-plane shape rotation (rad); , / . adjust
        self.array_count = 1      # stamp N copies along an axis; A adjusts
        self.array_axis = 'X'     # array world axis; D cycles
        self.mirror_axis = ''     # live mirror across a world axis; M cycles
        self.bevel_cut = False    # add an angle-limited bevel to the cut; B toggles
        self.cutter_bevel = False  # chamfer the cutter itself (bevelled cut); C toggles
        self.grid_size = prefs.grid_world  # live grid spacing (Ctrl+Wheel adjusts)
        self.depth = 0.0          # explicit cutter depth (0 = auto pierce); PgUp/Dn
        self.points = []          # confirmed screen points (current view)
        self.world_points = []    # anchored 3D point per click; keeps a fixed
        #                           plane's shape locked in space when the view
        #                           changes mid-draw (parallel to self.points)
        self.cursor = (0, 0)      # current (snapped) mouse point
        self.typed = ""           # numeric size buffer: type an exact dimension
        self._raw_cursor = (0, 0)  # snapped cursor before any typed-size lock
        self._snap_hit = None     # (screen_point, kind) -- for visual marker
        self._surface_basis = None  # locked (origin,right,up,normal) in SURFACE
        self._surface_miss = False  # SURFACE ray missed -> fell back to VIEW
        self._edges_basis = None    # locked basis from selected edges (EDGES plane)
        self.committing = False
        self._preview = None        # live 3D cutter/face volume object
        self._collect_snap_geometry(context)

        # Grid Modeler workflow: if you enter with edge(s) selected in Edit Mode,
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
        context.area.tag_redraw()
        # Re-anchor placed points to the current view before doing anything, so an
        # orbit/zoom on a fixed plane leaves the shape where it was drawn.
        self._sync_points_from_world(context)

        if event.type == 'MOUSEMOVE':
            co = self._snap_screen(
                context, (event.mouse_region_x, event.mouse_region_y))
            # Shift: lock draw direction to angle steps relative to last point
            if event.shift and self.points:
                anchor = self.points[-1] if self.shape == 'POLY' else self.points[0]
                step = get_prefs(context).angle_step
                co = grid.snap_angle(anchor, co, step, True)
                self._snap_hit = None  # angle lock invalidates the geometry marker
            self._raw_cursor = co
            self._apply_numeric(context)  # lock size to a typed value, else = raw

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

        # Z: close the in-progress polygon immediately (Grid Modeler quick-close).
        elif event.type == 'Z' and event.value == 'PRESS':
            if self.shape == 'POLY' and len(self.points) >= 3:
                return self._commit(context)

        elif event.type == 'BACK_SPACE' and event.value == 'PRESS':
            if self.typed:                 # editing a typed size? trim it
                self.typed = self.typed[:-1]
                self._apply_numeric(context)
            elif self.points:
                self.points.pop()
                if self.world_points:
                    self.world_points.pop()

        elif event.type in {'Q', 'W', 'E', 'R'} and event.value == 'PRESS':
            self.shape = {'Q': 'BOX', 'W': 'CIRCLE', 'E': 'POLY',
                          'R': 'NGON'}[event.type]
            self.points = []
            self.world_points = []
            self.typed = ""

        elif (event.type in {'LEFT_BRACKET', 'RIGHT_BRACKET'}
              and event.value == 'PRESS'):
            step = 1 if event.type == 'RIGHT_BRACKET' else -1
            self.sides = max(3, min(64, self.sides + step))

        # Tab / Shift+Tab cycle the boolean mode (the number row now types an
        # exact size -- Grid Modeler / Boxcutter precision entry).
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
                import math
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

        elif event.type == 'V' and event.value == 'PRESS':
            self.geo = not self.geo

        # S: persist the live HUD settings (snap/geo/ND, grid, sides, plane) as
        # the defaults for the next draw session.
        elif event.type == 'S' and event.value == 'PRESS':
            self._save_settings(context)

        elif event.type in {'LEFT_ARROW', 'RIGHT_ARROW'} and event.value == 'PRESS':
            direction = 1 if event.type == 'RIGHT_ARROW' else -1
            if event.shift:
                # Shift + arrows: rotate the grid plane in place (Grid Modeler).
                import math
                self.plane_spin += direction * math.radians(
                    get_prefs(context).angle_step)
            else:
                order = self._PLANE_ORDER
                self.plane = order[(order.index(self.plane) + direction)
                                   % len(order)]
                self.points = []  # plane changed -> reset the half-drawn shape
                self.world_points = []
                self._surface_basis = None  # re-pick the surface on next click
                self._edges_basis = None    # re-read the selected edges for EDGES

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._cleanup(context)
            return {'CANCELLED'}

        # Ctrl+Wheel: live grid density (otherwise the wheel navigates the view).
        elif (event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'} and event.ctrl
              and event.value == 'PRESS'):
            factor = 2.0 if event.type == 'WHEELUPMOUSE' else 0.5
            self.grid_size = max(0.001, min(100.0, self.grid_size * factor))

        elif event.type in {'PAGE_UP', 'PAGE_DOWN'} and event.value == 'PRESS':
            step = self.grid_size
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
        rv3d = context.region_data
        origin = context.active_object.matrix_world.translation
        right, up = raycast.view_right_up(rv3d)
        return origin, right, up, raycast.view_direction(rv3d)

    def _surface_basis_at(self, context, screen_co):
        """Construction basis aligned to the face under screen_co:
        (origin, right, up, normal) from the surface hit, or None if the ray
        misses geometry."""
        region, rv3d = context.region, context.region_data
        ignore = [self._preview] if self._preview else None
        hit = raycast.ray_cast_surface_ex(context, region, rv3d, screen_co, ignore)
        if hit is None:
            return None
        location, normal, obj, index, matrix = hit
        # Smart tangent: align the on-surface grid to the hit face's dominant edge
        # so the drawn shape lines up with existing panel lines. Fall back to the
        # view's up (which beats world up on an angled face) when no edge is found.
        up_hint = raycast.face_edge_tangent(obj, index, matrix, normal)
        if up_hint is None:
            _vr, up_hint = raycast.view_right_up(rv3d)
        right, up, n = raycast.basis_from_normal(normal, up_hint=up_hint)
        return location.copy(), right, up, n

    def _lock_surface_basis(self, context, screen_co):
        """Capture and cache the surface basis at the first click so the whole
        shape stays on one plane. Falls back silently to VIEW if no surface."""
        self._surface_basis = self._surface_basis_at(context, screen_co)

    def _capture_edges_basis(self, context):
        """Grid Modeler 'grid plane on edge(s)': build a construction basis from
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
        # parallel selections degrade cleanly to a single-edge plane.
        vecs = [tuple(edge_vec(e)) for e in sel]
        main_i, partner_i = decal_math.best_edge_pair(vecs)
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

    def _plane_basis(self, context):
        """Origin, local axes and normal of the projection plane, after the live
        in-plane spin (Shift + arrows). VIEW = perpendicular to view; SURFACE =
        aligned to the picked face; EDGES = aligned to the selected edit-mesh
        edge(s); X/Y/Z = world-axis aligned (Grid Modeler grid)."""
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
                b = self._surface_basis_at(context, self.cursor)
            self._surface_miss = b is None
            basis = b if b is not None else self._view_basis(context)
        else:
            self._surface_miss = False
            right, up, normal = self._AXIS_BASIS[self.plane]
            origin = context.active_object.matrix_world.translation
            basis = (origin, right, up, normal)
        return self._apply_spin(basis)

    def _apply_spin(self, basis):
        """Rotate the plane's right/up axes around its normal by the live grid
        spin (Shift + arrows) -- Grid Modeler's 'rotate the grid plane'. The
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
        view changes mid-draw; VIEW plane ignores it and follows the camera."""
        self.points.append((screen_co[0], screen_co[1]))
        region, rv3d = context.region, context.region_data
        origin, right, up, normal = self._plane_basis(context)
        self.world_points.append(
            raycast.ray_to_plane(region, rv3d, screen_co, origin, normal))

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

    def _snap_screen(self, context, screen_co):
        """Snap the cursor in order: 1) vertex/edge geometry, 2) world grid,
        3) raw. self._snap_hit is set for the visual marker."""
        self._snap_hit = None

        # 1) geometry snap -- if present overrides grid (Grid Modeler precision)
        if self.geo and self._geo_enabled:
            hit = self._geo_snap(context, screen_co)
            if hit is not None:
                self._snap_hit = hit
                return (hit[0][0], hit[0][1])

        # 2) world-scale grid snap
        if self.snap:
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

    def _shape_screen_points(self):
        if self.shape == 'POLY':
            pts = list(self.points)
            if pts:
                pts = pts + [self.cursor]
            return pts
        if not self.points:
            return []
        a = self.points[0]
        b = self.points[1] if len(self.points) > 1 else self.cursor
        if self.shape == 'BOX':
            return grid.box_points(a, b)
        if self.shape == 'CIRCLE':
            return grid.circle_points(a, b)
        if self.shape == 'NGON':
            return grid.ngon_points(a, b, self.sides)
        return []

    def _draw_px(self, context):
        prefs = get_prefs(context)
        region = context.region
        self._sync_points_from_world(context)  # keep a fixed-plane shape anchored

        if self.snap:
            hud.draw_grid(self._grid_screen_verts(context),
                          tuple(prefs.grid_color))

        pts = self._shape_screen_points()
        closed = self.shape != 'POLY' or len(self.points) >= 2
        width = prefs.line_width * context.preferences.system.ui_scale
        hud.draw_shape(pts, tuple(prefs.line_color), closed=closed, width=width)
        hud.draw_points(self.points, tuple(prefs.line_color))

        # if vertex/edge snap caught, mark the cursor colored by its kind
        if self._snap_hit is not None:
            point, kind = self._snap_hit
            col = _SNAP_COLORS.get(kind, (1.0, 1.0, 1.0, 1.0))
            hud.draw_points([point], col, size=11.0)

        accent = tuple(prefs.line_color)[:3] + (1.0,)
        dim = (0.72, 0.72, 0.72, 1.0)
        plane_label = self.plane
        if self.plane == 'SURFACE' and self._surface_miss:
            plane_label = "SURFACE (no face -> VIEW)"
        status = (
            f"Shape {self.shape}    Mode {self.mode}    Plane {plane_label}"
            f"        Snap {'ON' if self.snap else 'OFF'}"
            f"    Geo {'ON' if self.geo else 'OFF'}"
            f"    ND {'ON' if self.nd else 'OFF'}"
        )
        # Hints split into short lines -> roomier than one long line.
        lines = [
            status,
            ("Q/W/E/R shape    [ ] sides    Tab mode    type = exact size    "
             "< > plane    Shift+< > rotate grid    Z close", dim),
            ("-/= inset    ,/. rotate    A array    D axis    M mirror    "
             "B bevel    O orient    G stamp", dim),
            ("Ctrl+Wheel grid    PgUp/Dn depth    X grid    V vertex    "
             "N non-destructive    S save settings    Enter apply    "
             "Esc cancel", dim),
        ]
        # Surface the in-draw operation state only when something is active.
        import math
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
        if self.bevel_cut:
            bits.append("bevel-on-cut")
        if self.cutter_bevel:
            bits.append("cutter bevel")
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
        hud.draw_hud(region, lines)

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
        # POLY: point count + last segment length
        last = uv(self.points[-1])
        cur = uv(self.cursor)
        seg = ""
        if last is not None and cur is not None:
            seg = "   last segment %.3f m" % (
                ((cur[0] - last[0]) ** 2 + (cur[1] - last[1]) ** 2) ** 0.5)
        return "Point: %d%s" % (len(self.points), seg)

    # --- live 3D preview -------------------------------------------------

    def _preview_screen_points(self):
        """Screen points defining the in-progress shape, including the hovering
        cursor (so the volume previews the segment being drawn)."""
        if self.shape == 'POLY':
            pts = list(self.points)
            if self.points:
                pts = pts + [self.cursor]
            return pts
        return self._shape_screen_points()

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
        screen_pts = self._preview_screen_points()
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

    def _update_preview(self, context):
        """Refresh the live preview object. Shown as a wireframe drawn in front,
        non-selectable, so it reads as a cutter cage over the model and never
        interferes with picking."""
        if self.edit:
            return  # Edit Mode: the 2D shape outline is the preview (no cage)
        try:
            mesh = self._build_preview_mesh(context)
        except Exception:  # noqa: BLE001 -- preview must never break the modal
            mesh = None
        if mesh is None:
            self._clear_preview()
            return
        if self._preview is None:
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

    def _clear_preview(self):
        if self._preview is not None and self._preview.name in bpy.data.objects:
            data = self._preview.data
            bpy.data.objects.remove(self._preview, do_unlink=True)
            if data is not None and data.users == 0:
                bpy.data.meshes.remove(data)
        self._preview = None

    # --- geometry application -------------------------------------------

    def _commit(self, context):
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
            screen_pts = self._shape_screen_points()
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

    # --- stamp / repeat last shape (v1.4, Boxcutter "lazorcut") ----------

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
        """KNIFE in Object Mode: score every drawn loop onto the active mesh
        (zero-depth, no boolean) via the object-data knife."""
        obj = context.active_object
        mw_inv = obj.matrix_world.inverted_safe()
        rot = mw_inv.to_3x3()
        scored = 0
        for corners, vd in sets:
            local = [mw_inv @ c for c in corners]
            scored += geometry.knife_polygon(obj, local, (rot @ vd).normalized())
        if scored == 0:
            self.report({'WARNING'}, "Knife cut scored nothing")

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
        """Add+apply modifier, delete the cutter. Clean up via finally even on
        failure. CUT/MAKE support multiple targets; SLICE works on the first.
        Uses the robust boolean path (solver fallback + cutter normal repair +
        diagnosis) and surfaces the outcome so a failed/degraded cut is never
        silent."""
        cleanup = get_prefs(context).cleanup_after_cut
        op = {'CUT': 'DIFFERENCE', 'MAKE': 'UNION',
              'INTERSECT': 'INTERSECT'}.get(self.mode)
        failures, fallbacks = [], []

        def cut(tgt, bop):
            ok, used, msg = boolean.robust_boolean(context, tgt, cutter, bop, solver)
            if not ok:
                failures.append(msg)
            else:
                if used != solver:
                    fallbacks.append(used)
                if cleanup:
                    geometry.cleanup_mesh(tgt)

        try:
            if self.mode == 'SLICE':
                target = targets[0]
                other = boolean.duplicate_object(context, target)
                cut(target, 'DIFFERENCE')
                cut(other, 'INTERSECT')
            else:  # CUT / MAKE
                for t in targets:
                    cut(t, op)
        finally:
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
            boolean.add_boolean(target, cutter, 'DIFFERENCE', solver)
            boolean.add_boolean(other, cutter, 'INTERSECT', solver)
        else:  # CUT / MAKE / INTERSECT
            for t in targets:
                boolean.add_boolean(t, cutter, op, solver)
        boolean.stash_cutter(context, cutter, targets[0])

    def _cleanup(self, context):
        self._clear_preview()  # discards the cage on cancel; no-op after commit
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        context.area.tag_redraw()
