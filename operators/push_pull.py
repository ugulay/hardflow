# Push/Pull: SketchUp's signature tool. Hover a face, click to lock it, then
# drag along its normal (grid-snapped + vertex inference, with numeric entry) to
# extrude in or out; click again or Enter to apply. C keeps the starting face
# (copy/stack), R repeats the last distance.
#
# The hover/lock/drag/preview/cancel shell lives in face_tool._FaceDragModal;
# this file only adds the normal-axis drag, the extrude apply, and inference.
#
# Object Mode, active mesh. The face is picked by raycasting the scene, so the
# index must be valid on the base mesh -- generative modifiers that change the
# face count are not supported (a documented limitation, like the rest of v1).
from bpy.types import Operator

from .face_tool import _FaceDragModal
from ..core import raycast, geometry


class HARDFLOW_OT_push_pull(_FaceDragModal, Operator):
    bl_idname = "mesh.hardflow_push_pull"
    bl_label = "Hardflow Push/Pull"
    bl_description = "Extrude a face along its normal by dragging (SketchUp Push/Pull)"
    bl_options = {'REGISTER', 'UNDO'}

    _HOVER_FILL = (0.15, 0.8, 1.0, 0.18)   # hovered (loose) face tint
    _LOCK_FILL = (1.0, 0.6, 0.1, 0.22)     # locked (committed) face tint
    _snapshot_name = "hf_pushpull_base"
    _select_warning = "Select face(s) to push/pull"
    allow_negative = True                  # push (-) and pull (+) both valid

    _LAST_DISTANCE = 0.0   # remembered across runs -> R repeats the last amount

    # --- tool state ------------------------------------------------------

    def _init_tool(self, context, event):
        self.distance = 0.0       # signed extrude amount, meters
        self.copy = False         # keep the starting face (SketchUp Ctrl/Copy)

    # --- locking ---------------------------------------------------------

    def _lock_edit(self, context, event):
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
        self._base = geometry.snapshot_mesh(self.obj, self._snapshot_name)
        self._capture_axis_inference(self.axis_co, self.axis_dir)
        return True

    def _lock_face(self, context, co):
        """Freeze the picked face and build the drag axis from it. Snapshot the
        mesh so the live preview can reset before each re-extrude."""
        poly = self.obj.data.polygons[self.face_index]
        mw = self.obj.matrix_world
        self.axis_co = mw @ poly.center
        self.axis_dir = (mw.to_3x3() @ poly.normal).normalized()
        self.distance = 0.0
        self.typed = ""
        self.locked = True
        self._base = geometry.snapshot_mesh(self.obj, self._snapshot_name)
        self._capture_axis_inference(self.axis_co, self.axis_dir)

    # --- dragging / apply ------------------------------------------------

    def _refresh_preview(self):
        """Show the real extrude live: restore the snapshot, then re-extrude the
        locked face(s) by the current distance straight into the mesh. Routes
        through the edit-mesh in Edit Mode, the object mesh otherwise."""
        if self._base is None:
            return
        if self.edit:
            geometry.restore_edit_mesh(self.obj, self._base)
            if abs(self.distance) > 1e-6:
                geometry.edit_extrude_faces(self.obj, self._local_disp(),
                                            keep_original=self.copy)
            return
        geometry.restore_mesh(self.obj, self._base)
        if abs(self.distance) > 1e-6:
            geometry.extrude_faces(self.obj, [self.face_index],
                                   self._local_disp(), keep_original=self.copy)

    def _local_disp(self):
        world_disp = self.axis_dir * self.distance
        return self.obj.matrix_world.inverted_safe().to_3x3() @ world_disp

    def _update_drag(self, context, co):
        region, rv3d = context.region, context.region_data
        d = raycast.closest_axis_distance(region, rv3d, co,
                                          self.axis_co, self.axis_dir)
        self.distance = self._snap_axis_value(d, context)  # inference + grid
        self.typed = ""   # dragging clears a stale numeric entry

    def _set_value(self, v):
        self.distance = v

    def _repeat_last(self):
        self.distance = HARDFLOW_OT_push_pull._LAST_DISTANCE

    def _remember_last(self):
        if abs(self.distance) > 1e-6:
            HARDFLOW_OT_push_pull._LAST_DISTANCE = self.distance

    def _handle_key(self, context, event):
        # C: toggle "Copy" -- keep the starting face so the extrude stacks a new
        # volume on it (SketchUp's Ctrl push/pull, bound to C to stay clear of the
        # navigation modifiers).
        if event.type == 'C':
            self.copy = not self.copy
            if self.locked:
                self._refresh_preview()
            return True
        return False

    # --- HUD -------------------------------------------------------------

    def _hud_lines(self, context, prefs):
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
        return [
            top,
            ("Click face = lock    drag / type number = distance    "
             "X snap %s    C copy %s" % ('ON' if self.snap else 'OFF',
                                         'ON' if self.copy else 'OFF'), dim),
            ("Enter / click apply%s    Esc cancel" % repeat, dim),
        ]
