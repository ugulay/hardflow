# Object-Mode edge tools, so edge work doesn't need Edit Mode:
#   * Edge Bevel  -- pick an edge (or its loop), drag a width, [ ] segments.
#   * Loop Cut    -- pick an edge, insert an edge loop ([ ] = number of cuts).
#
# Both share _EdgePickModal (itself on face_tool._FaceDragModal): raycast-pick the
# nearest edge under the cursor (through generative modifiers) + draw it
# highlighted + the hover/lock/snapshot-preview/numeric/cancel shell. Each tool
# only adds its state, its apply, and its HUD.
from bpy.types import Operator
from mathutils import Vector

from .face_tool import _FaceDragModal
from ..core import raycast, geometry, grid
from ..preferences import get_prefs
from ..ui import draw as hud


class _EdgePickModal(_FaceDragModal):
    """Shared base for the Object-Mode edge tools: pick the nearest edge of the
    face under the cursor (mapping evaluated-mesh hits from generative modifiers
    back to a base face), and draw the picked edge highlighted."""

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')

    def _lock_edit(self, context, event):
        return False  # Object Mode only (Edit Mode has edit_bevel_edges etc.)

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


class HARDFLOW_OT_edge_bevel(_EdgePickModal, Operator):
    bl_idname = "mesh.hardflow_edge_bevel"
    bl_label = "Hardflow Edge Bevel"
    bl_description = "Bevel an edge by dragging, without entering Edit Mode"
    bl_options = {'REGISTER', 'UNDO'}

    _snapshot_name = "hf_edgebevel_base"
    allow_negative = False
    _LAST_WIDTH = 0.0   # remembered across runs -> R repeats the last width

    def _init_tool(self, context, event):
        self.width = 0.0
        self.segments = 2
        self.loop = False           # L: bevel the whole connected edge loop
        self._edge_key = None       # (vi, vj) edge under cursor / locked
        self._edge_world = None     # (Vector, Vector) world endpoints for drawing
        self._bevel_keys = None     # edges actually beveled (single or loop)
        self._lock_mouse_x = 0      # cursor x at lock -> horizontal drag = width
        self._scale = 0.01          # px -> meters, set from object size at lock

    def _lock_face(self, context, co):
        if self._edge_key is None:
            return
        self.width = 0.0
        self.typed = ""
        self.locked = True
        self._lock_mouse_x = co[0]
        self._scale = max(1e-4, max(self.obj.dimensions) / 400.0)
        self._base = geometry.snapshot_mesh(self.obj, self._snapshot_name)
        self._bevel_keys = self._compute_keys()

    def _compute_keys(self):
        """The edges to bevel: the picked edge, or its whole loop when L is on
        (computed from the pre-bevel mesh, before the preview mutates it)."""
        if self._edge_key is None:
            return []
        if self.loop:
            return geometry.edge_loop(self.obj, self._edge_key)
        return [self._edge_key]

    def _update_drag(self, context, co):
        dx = co[0] - self._lock_mouse_x
        w = max(0.0, dx * self._scale)        # drag right = wider
        self.width = grid.snap_scalar(w, get_prefs(context).grid_world, self.snap)
        self.typed = ""

    def _refresh_preview(self):
        if self._base is None or not self._bevel_keys:
            return
        geometry.restore_mesh(self.obj, self._base)
        if self.width > 1e-6:
            geometry.bevel_object_edges(self.obj, self._bevel_keys,
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
        # L: bevel the whole connected edge loop instead of the single edge.
        if event.type == 'L':
            self.loop = not self.loop
            if self.locked:
                self._bevel_keys = self._compute_keys()
                self._refresh_preview()
            return True
        return False

    def _hud_lines(self, context, prefs):
        accent = tuple(prefs.line_color)[:3] + (1.0,)
        dim = (0.72, 0.72, 0.72, 1.0)
        if not self.locked:
            top = (("Hover an edge, then click to bevel", accent)
                   if self._edge_key else ("Hover an edge to bevel", dim))
        else:
            typed = ("  [typing %s]" % self.typed) if self.typed else ""
            loop = "  (loop x%d)" % len(self._bevel_keys or []) if self.loop else ""
            top = ("Width:  %.3f m%s    Segments %d%s"
                   % (self.width, typed, self.segments, loop), accent)
        last = HARDFLOW_OT_edge_bevel._LAST_WIDTH
        repeat = ("    R repeat %.3f m" % last) if last > 1e-6 else ""
        return [
            top,
            ("Click edge = lock    drag / type = width    [ ] segments    "
             "L loop %s    X snap %s" % ('ON' if self.loop else 'OFF',
                                         'ON' if self.snap else 'OFF'), dim),
            ("Enter / click apply%s    Esc cancel" % repeat, dim),
        ]


class HARDFLOW_OT_loop_cut(_EdgePickModal, Operator):
    bl_idname = "mesh.hardflow_loop_cut"
    bl_label = "Hardflow Loop Cut"
    bl_description = "Insert an edge loop by picking an edge, without Edit Mode"
    bl_options = {'REGISTER', 'UNDO'}

    _snapshot_name = "hf_loopcut_base"
    allow_negative = False

    def _init_tool(self, context, event):
        self.cuts = 1
        self.slide = 0.0            # -1..1: position a single loop along the ring
        self._edge_key = None
        self._edge_world = None
        self._lock_mouse_x = 0      # cursor x at lock -> horizontal drag = slide

    def _lock_face(self, context, co):
        if self._edge_key is None:
            return
        self.typed = ""
        self.locked = True
        self.slide = 0.0
        self._lock_mouse_x = co[0]
        self._base = geometry.snapshot_mesh(self.obj, self._snapshot_name)
        self._refresh_preview()      # show the loop straight away

    def _update_drag(self, context, co):
        # Drag horizontally to slide a single inserted loop along its ring; full
        # -1..1 travel over ~250 px. Multiple loops stay evenly spaced.
        if self.cuts == 1:
            self.slide = max(-1.0, min(1.0, (co[0] - self._lock_mouse_x) / 250.0))
        self.typed = ""

    def _refresh_preview(self):
        if self._base is None or self._edge_key is None:
            return
        geometry.restore_mesh(self.obj, self._base)
        geometry.loop_cut(self.obj, self._edge_key, self.cuts, self.slide)

    def _set_value(self, v):
        try:
            self.cuts = max(1, min(20, int(round(v))))
            if self.cuts != 1:
                self.slide = 0.0      # slide only applies to a single loop
        except (ValueError, TypeError):
            pass

    def _repeat_last(self):
        pass

    def _remember_last(self):
        pass

    def _handle_key(self, context, event):
        # [ ] adjust the number of loops inserted at once.
        if event.type in {'LEFT_BRACKET', 'RIGHT_BRACKET'}:
            step = 1 if event.type == 'RIGHT_BRACKET' else -1
            self.cuts = max(1, min(20, self.cuts + step))
            if self.cuts != 1:
                self.slide = 0.0          # slide only applies to a single loop
            if self.locked:
                self._refresh_preview()
            return True
        return False

    def _hud_lines(self, context, prefs):
        accent = tuple(prefs.line_color)[:3] + (1.0,)
        dim = (0.72, 0.72, 0.72, 1.0)
        if not self.locked:
            top = (("Hover an edge, then click to add a loop", accent)
                   if self._edge_key else ("Hover an edge to loop-cut", dim))
        elif self.cuts == 1:
            typed = ("  [typing %s]" % self.typed) if self.typed else ""
            slide = ("    slide %+.0f%%" % (self.slide * 100.0)
                     if abs(self.slide) > 1e-3 else "")
            top = ("Loop Cut    Cuts %d%s%s" % (self.cuts, typed, slide), accent)
        else:
            typed = ("  [typing %s]" % self.typed) if self.typed else ""
            top = ("Loop Cut    Cuts %d%s" % (self.cuts, typed), accent)
        drag = "drag = slide    " if self.cuts == 1 else ""
        return [
            top,
            ("Click edge = insert    %s[ ] cuts    type = count    "
             "Enter apply    Esc cancel" % drag, dim),
        ]
