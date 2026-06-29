# Main draw operator: draw a shape on screen, project to 3D, apply boolean.
#
# SHAPE: BOX / CIRCLE / POLY / NGON      MODE: CUT / SLICE / MAKE
# Shortcuts (inside modal):
#   Left click    place point / start-finish shape
#   Enter         close POLY and apply
#   Backspace     delete last POLY point
#   Q/W/E/R       shape = BOX / CIRCLE / POLY / NGON
#   [ / ]         decrease / increase N-gon side count
#   1/2/3         mode  = CUT / SLICE / MAKE
#   X             toggle snap
#   Right click / ESC  cancel
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty
from mathutils import Vector

from ..core import raycast, geometry, boolean, grid, snap
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
    ('FACE', "Face", "Create a new face (create face, not boolean)"),
]

# Vertex/edge snap cursor colors (kind -> RGBA)
_SNAP_COLORS = {
    'VERT': (1.0, 0.9, 0.2, 1.0),   # yellow = vertex
    'MID':  (0.3, 1.0, 0.4, 1.0),   # green  = edge midpoint
    'EDGE': (0.3, 0.9, 1.0, 1.0),   # blue   = on edge
}


class HARDFLOW_OT_draw(Operator):
    bl_idname = "mesh.hardflow_draw"
    bl_label = "Hardflow Draw"
    bl_options = {'REGISTER', 'UNDO'}

    shape: EnumProperty(name="Shape", items=_SHAPES, default='BOX')
    mode: EnumProperty(name="Mode", items=_MODES, default='CUT')

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Run inside View3D")
            return {'CANCELLED'}

        prefs = get_prefs(context)
        self.snap = prefs.snap_enabled
        self.geo = prefs.geo_snap        # vertex/edge snap (overrides grid)
        self.nd = prefs.non_destructive  # non-destructive: leave a live modifier
        self.plane = 'VIEW'              # projection plane: VIEW / X / Y / Z
        self.sides = prefs.ngon_sides    # N-gon side count (adjust live with [ ])
        self.points = []          # confirmed screen points
        self.cursor = (0, 0)      # current (snapped) mouse point
        self._snap_hit = None     # (screen_point, kind) -- for visual marker
        self.committing = False
        self._collect_snap_geometry(context)

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    # --- event loop ------------------------------------------------------

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            co = self._snap_screen(
                context, (event.mouse_region_x, event.mouse_region_y))
            # Shift: lock draw direction to angle steps relative to last point
            if event.shift and self.points:
                anchor = self.points[-1] if self.shape == 'POLY' else self.points[0]
                step = get_prefs(context).angle_step
                co = grid.snap_angle(anchor, co, step, True)
                self._snap_hit = None  # angle lock invalidates the geometry marker
            self.cursor = co

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            p = self.cursor
            if self.shape == 'POLY':
                self.points.append(p)
            else:  # BOX / CIRCLE: two clicks
                if not self.points:
                    self.points.append(p)
                else:
                    self.points.append(p)
                    return self._commit(context)

        elif event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            if self.shape == 'POLY' and len(self.points) >= 3:
                return self._commit(context)

        elif event.type == 'BACK_SPACE' and event.value == 'PRESS':
            if self.points:
                self.points.pop()

        elif event.type in {'Q', 'W', 'E', 'R'} and event.value == 'PRESS':
            self.shape = {'Q': 'BOX', 'W': 'CIRCLE', 'E': 'POLY',
                          'R': 'NGON'}[event.type]
            self.points = []

        elif (event.type in {'LEFT_BRACKET', 'RIGHT_BRACKET'}
              and event.value == 'PRESS'):
            step = 1 if event.type == 'RIGHT_BRACKET' else -1
            self.sides = max(3, min(64, self.sides + step))

        elif event.type in {'ONE', 'TWO', 'THREE', 'FOUR'} and event.value == 'PRESS':
            self.mode = {'ONE': 'CUT', 'TWO': 'SLICE', 'THREE': 'MAKE',
                         'FOUR': 'FACE'}[event.type]

        elif event.type == 'X' and event.value == 'PRESS':
            self.snap = not self.snap

        elif event.type == 'N' and event.value == 'PRESS':
            self.nd = not self.nd

        elif event.type == 'V' and event.value == 'PRESS':
            self.geo = not self.geo

        elif event.type in {'LEFT_ARROW', 'RIGHT_ARROW'} and event.value == 'PRESS':
            order = self._PLANE_ORDER
            step = 1 if event.type == 'RIGHT_ARROW' else -1
            self.plane = order[(order.index(self.plane) + step) % len(order)]
            self.points = []  # plane changed -> reset the half-drawn shape

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._cleanup(context)
            return {'CANCELLED'}

        # Allow viewport navigation while drawing (orbit/zoom/pan).
        elif event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
                            'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    # --- world-scale snap (v0.2) ----------------------------------------

    _PLANE_ORDER = ['VIEW', 'X', 'Y', 'Z']

    # World bases (right, up, normal) for axis-aligned planes.
    _AXIS_BASIS = {
        'X': (Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((1, 0, 0))),
        'Y': (Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, 1, 0))),
        'Z': (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))),
    }

    def _plane_basis(self, context):
        """Origin, local axes and normal of the projection plane.
        VIEW = perpendicular to view; X/Y/Z = world-axis aligned (Grid Modeler
        grid)."""
        rv3d = context.region_data
        origin = context.active_object.matrix_world.translation
        if self.plane == 'VIEW':
            right, up = raycast.view_right_up(rv3d)
            normal = raycast.view_direction(rv3d)
        else:
            right, up, normal = self._AXIS_BASIS[self.plane]
        return origin, right, up, normal

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
                u, v = grid.snap_world(u, v, prefs.grid_world, True)
                world = raycast.plane_uv_to_world(u, v, origin, right, up)
                screen = raycast.world_to_screen(region, rv3d, world)
                if screen is not None:
                    return (screen[0], screen[1])

        # 3) raw mouse point
        return (screen_co[0], screen_co[1])

    # --- vertex / edge snap (v0.2) --------------------------------------

    # On very dense meshes projecting every vertex on each mouse move is
    # expensive; above this threshold geometry snap turns off.
    _GEO_MAX_VERTS = 20000

    def _collect_snap_geometry(self, context):
        """Collect the target's world-space vertex / edge-midpoint / edge lists
        once (the object does not move during the modal). _geo_enabled only
        means 'is the mesh light enough for snap'; toggling is via self.geo."""
        obj = context.active_object
        me = obj.data
        self._geo_enabled = len(me.vertices) <= self._GEO_MAX_VERTS
        self._geo_verts = []
        self._geo_mids = []
        self._geo_edges = []
        if not self._geo_enabled:
            if self.geo:
                self.report({'INFO'}, "Vertex snap: mesh too dense, disabled")
            return
        mw = obj.matrix_world
        self._geo_verts = [mw @ v.co for v in me.vertices]
        for e in me.edges:
            i, j = e.vertices
            self._geo_edges.append((i, j))
            self._geo_mids.append((self._geo_verts[i] + self._geo_verts[j]) * 0.5)

    def _geo_snap(self, context, screen_co):
        """Nearest vertex/midpoint/edge screen point to the cursor.
        Returns ((x, y), kind) ('VERT'/'MID'/'EDGE') or None."""
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
        hit = snap.nearest_point(screen_co, vscr, thr)
        if hit is not None:
            return (hit[1], 'VERT')

        hit = snap.nearest_point(screen_co, to_screen(self._geo_mids), thr)
        if hit is not None:
            return (hit[1], 'MID')

        segs = [(vscr[i], vscr[j]) for (i, j) in self._geo_edges]
        hit = snap.nearest_on_segments(screen_co, segs, thr)
        if hit is not None:
            return (hit[1], 'EDGE')
        return None

    def _grid_screen_verts(self, context):
        """Convert the visible world grid into a screen-space LINES vertex list."""
        prefs = get_prefs(context)
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
                                        prefs.grid_world)
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

        if self.snap:
            hud.draw_grid(self._grid_screen_verts(context),
                          tuple(prefs.grid_color))

        pts = self._shape_screen_points()
        closed = self.shape != 'POLY' or len(self.points) >= 2
        hud.draw_shape(pts, tuple(prefs.line_color), closed=closed)
        hud.draw_points(self.points, tuple(prefs.line_color))

        # if vertex/edge snap caught, mark the cursor colored by its kind
        if self._snap_hit is not None:
            point, kind = self._snap_hit
            col = _SNAP_COLORS.get(kind, (1.0, 1.0, 1.0, 1.0))
            hud.draw_points([point], col, size=11.0)

        accent = tuple(prefs.line_color)[:3] + (1.0,)
        dim = (0.72, 0.72, 0.72, 1.0)
        status = (
            f"Shape {self.shape}    Mode {self.mode}    Plane {self.plane}"
            f"        Snap {'ON' if self.snap else 'OFF'}"
            f"    Geo {'ON' if self.geo else 'OFF'}"
            f"    ND {'ON' if self.nd else 'OFF'}"
        )
        # Hints split into two short lines -> roomier than one long line.
        lines = [
            status,
            ("Q/W/E/R shape    [ ] sides    1-4 mode    < > plane    Shift angle-lock",
             dim),
            ("X grid    V vertex    N non-destructive    Enter apply    Esc cancel",
             dim),
        ]
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

    # --- geometry application -------------------------------------------

    def _commit(self, context):
        try:
            self._build_and_apply(context)
        except Exception as ex:  # close the draw mode cleanly
            self.report({'ERROR'}, f"Hardflow: {ex}")
        self._cleanup(context)
        return {'FINISHED'}

    def _build_and_apply(self, context):
        region = context.region
        rv3d = context.region_data
        target = context.active_object
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

        origin, right, up, normal = self._plane_basis(context)
        corners = [raycast.ray_to_plane(region, rv3d, p, origin, normal)
                   for p in screen_pts]
        if any(c is None for c in corners):
            self.report({'WARNING'}, "Plane edge-on; shape could not be projected")
            return

        # FACE: not boolean; create a single face object from the drawn shape.
        if self.mode == 'FACE':
            self._build_face(context, corners)
            return

        targets = self._targets(context)
        # The cutter must pierce all targets -> size it to the thickest target.
        thickness = max(geometry.estimate_thickness(t) for t in targets)

        # The cutter is extruded along the plane normal (view direction in VIEW).
        cutter_mesh = geometry.build_prism(corners, normal, thickness)
        if cutter_mesh is None:
            self.report({'WARNING'}, "Invalid shape")
            return
        cutter = bpy.data.objects.new("hf_cutter", cutter_mesh)
        context.collection.objects.link(cutter)

        solver = prefs.default_solver
        if self.nd:
            self._apply_nondestructive(context, targets, cutter, solver)
        else:
            self._apply_destructive(context, targets, cutter, solver)

    def _targets(self, context):
        """If multi-object mode is on, all selected meshes (CUT/MAKE); otherwise
        only the active object. SLICE/FACE always operate on the active one."""
        active = context.active_object
        if get_prefs(context).multi_object and self.mode in {'CUT', 'MAKE'}:
            sel = [o for o in context.selected_objects if o.type == 'MESH']
            return sel if sel else [active]
        return [active]

    def _build_face(self, context, corners):
        """Create a new single-face object from the drawn shape (create face)."""
        mesh = geometry.build_face(corners)
        if mesh is None:
            self.report({'WARNING'}, "Invalid face")
            return
        obj = bpy.data.objects.new("Hardflow_Face", mesh)
        context.collection.objects.link(obj)
        for o in list(context.selected_objects):
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj

    def _apply_destructive(self, context, targets, cutter, solver):
        """Add+apply modifier, delete the cutter. Clean up via finally even on
        failure. CUT/MAKE support multiple targets; SLICE works on the first."""
        cleanup = get_prefs(context).cleanup_after_cut
        op = {'CUT': 'DIFFERENCE', 'MAKE': 'UNION'}.get(self.mode)
        try:
            if self.mode == 'SLICE':
                target = targets[0]
                other = boolean.duplicate_object(context, target)
                boolean.apply_boolean(context, target, cutter, 'DIFFERENCE', solver)
                boolean.apply_boolean(context, other, cutter, 'INTERSECT', solver)
                if cleanup:
                    geometry.cleanup_mesh(target)
                    geometry.cleanup_mesh(other)
            else:  # CUT / MAKE
                for t in targets:
                    boolean.apply_boolean(context, t, cutter, op, solver)
                    if cleanup:
                        geometry.cleanup_mesh(t)
        finally:
            bpy.data.objects.remove(cutter, do_unlink=True)

    def _apply_nondestructive(self, context, targets, cutter, solver):
        """Leave a live modifier, stash the cutter in the 'Hardflow Cutters'
        collection."""
        op = {'CUT': 'DIFFERENCE', 'MAKE': 'UNION'}.get(self.mode)
        if self.mode == 'SLICE':
            target = targets[0]
            other = boolean.duplicate_object(context, target)
            boolean.add_boolean(target, cutter, 'DIFFERENCE', solver)
            boolean.add_boolean(other, cutter, 'INTERSECT', solver)
        else:  # CUT / MAKE
            for t in targets:
                boolean.add_boolean(t, cutter, op, solver)
        boolean.stash_cutter(context, cutter, targets[0])

    def _cleanup(self, context):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        context.area.tag_redraw()
