# Push/Pull: SketchUp's signature tool. Hover a face, click to lock it, then
# drag along its normal (grid-snapped, with numeric entry) to extrude in or out;
# click again or Enter to apply.
#
# Object Mode, active mesh. The face is picked by raycasting the scene, so the
# index must be valid on the base mesh -- generative modifiers that change the
# face count are not supported (a documented limitation, like the rest of v1).
import bpy
from bpy.types import Operator
from mathutils import Vector

from ..core import raycast, geometry, grid, snap
from ..preferences import get_prefs
from ..ui import draw as hud


# Highlight colors for the hovered (loose) vs locked (committed) face.
_HOVER_FILL = (0.15, 0.8, 1.0, 0.18)
_LOCK_FILL = (1.0, 0.6, 0.1, 0.22)


class HARDFLOW_OT_push_pull(Operator):
    bl_idname = "mesh.hardflow_push_pull"
    bl_label = "Hardflow Push/Pull"
    bl_description = "Extrude a face along its normal by dragging (SketchUp Push/Pull)"
    bl_options = {'REGISTER', 'UNDO'}

    _LAST_DISTANCE = 0.0   # remembered across runs -> R repeats the last amount

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode in {'OBJECT', 'EDIT_MESH'})

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Run inside View3D")
            return {'CANCELLED'}
        self.obj = context.active_object
        self.edit = context.mode == 'EDIT_MESH'   # Edit Mode = drag selected faces
        self.snap = get_prefs(context).snap_enabled
        self.face_index = -1      # face under the cursor (Object Mode pick)
        self.locked = False       # has a face been picked?
        self.axis_co = None       # world-space face center (drag axis origin)
        self.axis_dir = None      # world-space face normal (drag axis)
        self.distance = 0.0       # signed extrude amount, meters
        self.copy = False         # keep the starting face (SketchUp Ctrl/Copy)
        self.typed = ""           # numeric entry buffer
        self._infer = []          # candidate extrude heights (vertex inference)
        self._infer_hit = False   # drag currently snapped to geometry
        self._base = None         # mesh snapshot for the live preview
        self._committed = False

        # Edit Mode: there is no hover-pick -- lock straight onto the selected
        # faces and drag along their averaged normal.
        if self.edit and not self._lock_edit(context):
            self.report({'WARNING'}, "Select face(s) to push/pull")
            return {'CANCELLED'}

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        try:
            context.window_manager.modal_handler_add(self)
        except Exception:  # never orphan the draw handler if the modal won't start
            self._cleanup(context)
            raise
        return {'RUNNING_MODAL'}

    def _lock_edit(self, context):
        """Edit Mode lock: build the drag axis from the average center/normal of
        the selected faces and snapshot the edit-mesh for the live preview."""
        basis = geometry.selected_face_basis(self.obj)
        if basis is None:
            return False
        center, normal = basis
        mw = self.obj.matrix_world
        self.axis_co = mw @ center
        self.axis_dir = (mw.to_3x3() @ normal).normalized()
        self.distance = 0.0
        self.typed = ""
        self.locked = True
        geometry.flush_edit_mesh(self.obj)   # sync selection before snapshot
        self._base = geometry.snapshot_mesh(self.obj, "hf_pushpull_base")
        self._capture_inference()
        return True

    # --- event loop ------------------------------------------------------

    def modal(self, context, event):
        context.area.tag_redraw()
        co = (event.mouse_region_x, event.mouse_region_y)

        if event.type == 'MOUSEMOVE':
            if self.locked:
                self._update_distance(context, co)
                self._refresh_preview()
            else:
                self._hover_face(context, co)

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if not self.locked:
                if self.face_index >= 0:
                    self._lock_face()
            else:
                return self._commit(context)

        elif (event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS'
              and self.locked):
            return self._commit(context)

        elif event.type == 'X' and event.value == 'PRESS':
            self.snap = not self.snap

        # C: toggle "Copy" -- keep the starting face so the extrude stacks a new
        # volume on it (SketchUp's Ctrl push/pull, bound to C to stay clear of the
        # navigation modifiers).
        elif event.type == 'C' and event.value == 'PRESS':
            self.copy = not self.copy
            if self.locked:
                self._refresh_preview()

        # R: repeat the last committed distance on the locked face.
        elif event.type == 'R' and event.value == 'PRESS' and self.locked:
            self.distance = HARDFLOW_OT_push_pull._LAST_DISTANCE
            self.typed = ""
            self._refresh_preview()

        elif self.locked and event.value == 'PRESS' and self._edit_typed(event):
            self._refresh_preview()  # numeric entry handled

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._cleanup(context)
            return {'CANCELLED'}

        elif event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
                            'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    # --- picking / dragging ---------------------------------------------

    def _hover_face(self, context, co):
        """Raycast the active object's own mesh; remember the polygon index under
        the cursor (-1 when the cursor misses the object)."""
        from bpy_extras import view3d_utils
        region, rv3d = context.region, context.region_data
        v = Vector((co[0], co[1]))
        ray_dir = view3d_utils.region_2d_to_vector_3d(region, rv3d, v)
        ray_o = view3d_utils.region_2d_to_origin_3d(region, rv3d, v)
        mw_inv = self.obj.matrix_world.inverted_safe()
        local_o = mw_inv @ ray_o
        local_d = mw_inv.to_3x3() @ ray_dir
        ok, _loc, _nrm, index = self.obj.ray_cast(local_o, local_d)
        # ray_cast indexes the EVALUATED mesh; clamp to the base mesh range so
        # every downstream obj.data.polygons[...] access stays in bounds (and we
        # never pick a face that doesn't exist without modifiers).
        self.face_index = index if (ok and index < len(self.obj.data.polygons)) \
            else -1

    def _lock_face(self):
        """Freeze the picked face and build the drag axis from it. Snapshot the
        mesh so the live preview can reset before each re-extrude."""
        poly = self.obj.data.polygons[self.face_index]
        mw = self.obj.matrix_world
        self.axis_co = mw @ poly.center
        self.axis_dir = (mw.to_3x3() @ poly.normal).normalized()
        self.distance = 0.0
        self.typed = ""
        self.locked = True
        self._base = geometry.snapshot_mesh(self.obj, "hf_pushpull_base")
        self._capture_inference()

    def _capture_inference(self):
        """Project the locked object's vertices onto the drag axis to get the
        candidate extrude heights the drag can infer/snap to (SketchUp-style
        inference: e.g. snap to the height of another feature). Captured once from
        the pre-extrude snapshot; skipped on very dense meshes."""
        src = self._base if self._base is not None else self.obj.data
        if src is None or len(src.vertices) > 50000:
            self._infer = []
            return
        mw = self.obj.matrix_world
        co, ax = self.axis_co, self.axis_dir
        self._infer = sorted({round((mw @ v.co - co).dot(ax), 6)
                              for v in src.vertices})

    def _refresh_preview(self):
        """Show the real extrude live: restore the snapshot, then re-extrude the
        locked face(s) by the current distance straight into the mesh. Routes
        through the edit-mesh in Edit Mode, the object mesh otherwise."""
        if self._base is None:
            return
        if self.edit:
            geometry.restore_edit_mesh(self.obj, self._base)
            if abs(self.distance) > 1e-6:
                local_vec = self._local_disp()
                geometry.edit_extrude_faces(self.obj, local_vec,
                                            keep_original=self.copy)
            return
        geometry.restore_mesh(self.obj, self._base)
        if abs(self.distance) > 1e-6:
            geometry.extrude_faces(self.obj, [self.face_index],
                                   self._local_disp(), keep_original=self.copy)

    def _local_disp(self):
        world_disp = self.axis_dir * self.distance
        return self.obj.matrix_world.inverted_safe().to_3x3() @ world_disp

    def _update_distance(self, context, co):
        region, rv3d = context.region, context.region_data
        d = raycast.closest_axis_distance(region, rv3d, co,
                                          self.axis_co, self.axis_dir)
        prefs = get_prefs(context)
        self._infer_hit = False
        if not self.snap:
            self.distance = d
        else:
            # Inference first: snap to a real vertex height under the drag, else
            # fall back to the world grid (SketchUp's geometry inference).
            tol = max(1e-4, prefs.grid_world * 0.5)
            inferred = snap.snap_to_candidates(d, self._infer, tol)
            if inferred != d:
                self.distance = inferred
                self._infer_hit = True
            else:
                self.distance = grid.snap_scalar(d, prefs.grid_world, True)
        self.typed = ""   # dragging clears a stale numeric entry

    def _edit_typed(self, event):
        """Build a numeric distance from key presses. Returns True if consumed."""
        digits = {'ZERO': '0', 'ONE': '1', 'TWO': '2', 'THREE': '3',
                  'FOUR': '4', 'FIVE': '5', 'SIX': '6', 'SEVEN': '7',
                  'EIGHT': '8', 'NINE': '9',
                  'NUMPAD_0': '0', 'NUMPAD_1': '1', 'NUMPAD_2': '2',
                  'NUMPAD_3': '3', 'NUMPAD_4': '4', 'NUMPAD_5': '5',
                  'NUMPAD_6': '6', 'NUMPAD_7': '7', 'NUMPAD_8': '8',
                  'NUMPAD_9': '9'}
        if event.type in digits:
            self.typed += digits[event.type]
        elif event.type in {'PERIOD', 'NUMPAD_PERIOD'} and '.' not in self.typed:
            self.typed += '.'
        elif event.type == 'MINUS':
            self.typed = self.typed[1:] if self.typed.startswith('-') \
                else '-' + self.typed
        elif event.type == 'BACK_SPACE':
            self.typed = self.typed[:-1]
        else:
            return False
        try:
            self.distance = float(self.typed)
        except ValueError:
            pass  # partial entry like "-" or "." -> keep last good distance
        return True

    # --- visual feedback -------------------------------------------------

    def _face_screen_points(self, context):
        if self.edit or self.face_index < 0:   # Edit Mode: rely on mesh highlight
            return []
        poly = self.obj.data.polygons[self.face_index]
        mw = self.obj.matrix_world
        region, rv3d = context.region, context.region_data
        verts = self.obj.data.vertices
        pts = []
        for vi in poly.vertices:
            s = raycast.world_to_screen(region, rv3d, mw @ verts[vi].co)
            if s is None:
                return []
            pts.append((s[0], s[1]))
        return pts

    def _draw_px(self, context):
        prefs = get_prefs(context)
        pts = self._face_screen_points(context)
        if pts:
            fill = _LOCK_FILL if self.locked else _HOVER_FILL
            hud.draw_face_fill(pts, fill)
            hud.draw_shape(pts, tuple(prefs.line_color), closed=True)

        accent = tuple(prefs.line_color)[:3] + (1.0,)
        dim = (0.72, 0.72, 0.72, 1.0)
        if not self.locked:
            top = ("Hover a face, then click to push/pull", accent)
        else:
            typed = ("  [typing %s]" % self.typed) if self.typed else ""
            copy = "  (copy)" if self.copy else ""
            infer = "  -> on geometry" if self._infer_hit else ""
            top = ("Distance:  %.3f m%s%s%s"
                   % (self.distance, typed, copy, infer), accent)
        last = HARDFLOW_OT_push_pull._LAST_DISTANCE
        repeat = ("    R repeat %.3f m" % last) if abs(last) > 1e-6 else ""
        lines = [
            top,
            ("Click face = lock    drag / type number = distance    "
             "X snap %s    C copy %s" % ('ON' if self.snap else 'OFF',
                                         'ON' if self.copy else 'OFF'), dim),
            ("Enter / click apply%s    Esc cancel" % repeat, dim),
        ]
        hud.draw_hud(context.region, lines)

    # --- apply -----------------------------------------------------------

    def _commit(self, context):
        # The live preview already wrote the extrude into the mesh; just make
        # sure it reflects the final distance, then keep it.
        try:
            self._refresh_preview()
        except Exception as ex:
            self.report({'ERROR'}, f"Hardflow: {ex}")
        if abs(self.distance) > 1e-6:                  # remember for R repeat
            HARDFLOW_OT_push_pull._LAST_DISTANCE = self.distance
        self._committed = True
        self._cleanup(context)
        return {'FINISHED'}

    def _cleanup(self, context):
        # Cancelled mid-preview -> roll the mesh back to the snapshot.
        if self._base is not None:
            if not self._committed:
                if self.edit:
                    geometry.restore_edit_mesh(self.obj, self._base)
                else:
                    geometry.restore_mesh(self.obj, self._base)
            geometry.free_mesh(self._base)
            self._base = None
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        context.area.tag_redraw()
