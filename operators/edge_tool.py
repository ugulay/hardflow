# Edge Bevel: bevel an edge by dragging, in Object Mode (no Edit Mode needed).
# Hover an edge (raycast a face, pick its nearest edge), click to lock it, then
# drag or type a width and adjust segments with [ ]; click again or Enter to
# apply. R repeats the last width.
#
# Built on face_tool._FaceDragModal: the hover/lock/drag/snapshot-preview/numeric/
# cancel shell is shared; this file overrides the pick (edge instead of face),
# the apply (bevel), and the edge-line drawing.
from bpy.types import Operator
from mathutils import Vector

from .face_tool import _FaceDragModal
from ..core import raycast, geometry, grid
from ..preferences import get_prefs
from ..ui import draw as hud


class HARDFLOW_OT_edge_bevel(_FaceDragModal, Operator):
    bl_idname = "mesh.hardflow_edge_bevel"
    bl_label = "Hardflow Edge Bevel"
    bl_description = "Bevel an edge by dragging, without entering Edit Mode"
    bl_options = {'REGISTER', 'UNDO'}

    _snapshot_name = "hf_edgebevel_base"
    allow_negative = False
    _LAST_WIDTH = 0.0   # remembered across runs -> R repeats the last width

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')

    # --- tool state ------------------------------------------------------

    def _init_tool(self, context, event):
        self.width = 0.0
        self.segments = 2
        self._edge_key = None       # (vi, vj) edge under cursor / locked
        self._edge_world = None     # (Vector, Vector) world endpoints for drawing
        self._lock_mouse_x = 0      # cursor x at lock -> horizontal drag = width
        self._scale = 0.01          # px -> meters, set from object size at lock

    def _lock_edit(self, context, event):
        return False  # Object Mode only (Edit Mode has edit_bevel_edges)

    # --- pick ------------------------------------------------------------

    def _hover_face(self, context, co):
        """Raycast the active mesh; remember the nearest polygon edge to the hit
        point (for highlight + lock), or clear when the cursor misses."""
        from bpy_extras import view3d_utils
        region, rv3d = context.region, context.region_data
        v = Vector((co[0], co[1]))
        ray_dir = view3d_utils.region_2d_to_vector_3d(region, rv3d, v)
        ray_o = view3d_utils.region_2d_to_origin_3d(region, rv3d, v)
        mw_inv = self.obj.matrix_world.inverted_safe()
        ok, loc, _nrm, index = self.obj.ray_cast(
            mw_inv @ ray_o, mw_inv.to_3x3() @ ray_dir)
        if ok and index >= len(self.obj.data.polygons):
            index = geometry.nearest_face_to_point(self.obj, loc)  # past base mesh
        if not ok or index < 0:
            self.face_index = -1
            self._edge_key = self._edge_world = None
            return
        self.face_index = index
        key = geometry.nearest_edge_on_face(self.obj, index, loc)
        self._edge_key = key
        if key is None:
            self._edge_world = None
            return
        mw = self.obj.matrix_world
        verts = self.obj.data.vertices
        self._edge_world = (mw @ verts[key[0]].co, mw @ verts[key[1]].co)

    def _lock_face(self, context, co):
        if self._edge_key is None:
            return
        self.width = 0.0
        self.typed = ""
        self.locked = True
        self._lock_mouse_x = co[0]
        self._scale = max(1e-4, max(self.obj.dimensions) / 400.0)
        self._base = geometry.snapshot_mesh(self.obj, self._snapshot_name)

    # --- drag / apply ----------------------------------------------------

    def _update_drag(self, context, co):
        dx = co[0] - self._lock_mouse_x
        w = max(0.0, dx * self._scale)        # drag right = wider
        self.width = grid.snap_scalar(w, get_prefs(context).grid_world, self.snap)
        self.typed = ""

    def _refresh_preview(self):
        if self._base is None or self._edge_key is None:
            return
        geometry.restore_mesh(self.obj, self._base)
        if self.width > 1e-6:
            geometry.bevel_object_edges(self.obj, [self._edge_key],
                                        self.width, self.segments)

    def _set_value(self, v):
        self.width = max(0.0, v)

    def _repeat_last(self):
        self.width = HARDFLOW_OT_edge_bevel._LAST_WIDTH

    def _remember_last(self):
        if self.width > 1e-6:
            HARDFLOW_OT_edge_bevel._LAST_WIDTH = self.width

    def _handle_key(self, context, event):
        # [ ] adjust the bevel segment count (wheel stays free for navigation).
        if event.type in {'LEFT_BRACKET', 'RIGHT_BRACKET'}:
            step = 1 if event.type == 'RIGHT_BRACKET' else -1
            self.segments = max(1, min(12, self.segments + step))
            if self.locked:
                self._refresh_preview()
            return True
        return False

    # --- drawing ---------------------------------------------------------

    def _draw_px(self, context):
        prefs = get_prefs(context)
        if self._edge_world is not None:
            region, rv3d = context.region, context.region_data
            a = raycast.world_to_screen(region, rv3d, self._edge_world[0])
            b = raycast.world_to_screen(region, rv3d, self._edge_world[1])
            if a is not None and b is not None:
                col = ((1.0, 0.6, 0.1, 1.0) if self.locked
                       else tuple(prefs.line_color)[:3] + (1.0,))
                hud.draw_shape([(a[0], a[1]), (b[0], b[1])], col, closed=False)
        hud.draw_hud(context.region, self._hud_lines(context, prefs))

    def _hud_lines(self, context, prefs):
        accent = tuple(prefs.line_color)[:3] + (1.0,)
        dim = (0.72, 0.72, 0.72, 1.0)
        if not self.locked:
            top = (("Hover an edge, then click to bevel", accent)
                   if self._edge_key else ("Hover an edge to bevel", dim))
        else:
            typed = ("  [typing %s]" % self.typed) if self.typed else ""
            top = ("Width:  %.3f m%s    Segments %d"
                   % (self.width, typed, self.segments), accent)
        last = HARDFLOW_OT_edge_bevel._LAST_WIDTH
        repeat = ("    R repeat %.3f m" % last) if last > 1e-6 else ""
        return [
            top,
            ("Click edge = lock    drag / type = width    [ ] segments    "
             "X snap %s" % ('ON' if self.snap else 'OFF'), dim),
            ("Enter / click apply%s    Esc cancel" % repeat, dim),
        ]
