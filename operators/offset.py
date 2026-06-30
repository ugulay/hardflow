# Offset: pick a face, drag to inset its border inward by a measured thickness
# (SketchUp's Offset tool). Grid-snapped, with numeric entry; click again or
# Enter to apply. R repeats the last thickness.
#
# The hover/lock/drag/preview/cancel shell lives in face_tool._FaceDragModal;
# this file only adds the in-plane drag measure and the inset apply.
#
# Object Mode, active mesh. Like Push/Pull the face index comes from a raycast,
# so generative modifiers that change the face count are not supported.
from bpy.types import Operator

from .face_tool import _FaceDragModal
from ..core import raycast, geometry, grid
from ..preferences import get_prefs


class HARDFLOW_OT_offset(_FaceDragModal, Operator):
    bl_idname = "mesh.hardflow_offset"
    bl_label = "Hardflow Offset"
    bl_description = "Inset a face's border inward by a measured distance (SketchUp Offset)"
    bl_options = {'REGISTER', 'UNDO'}

    _HOVER_FILL = (0.15, 0.8, 1.0, 0.18)
    _LOCK_FILL = (0.2, 1.0, 0.5, 0.20)     # green-tinted lock fill
    _snapshot_name = "hf_offset_base"
    _select_warning = "Select face(s) to offset"
    allow_negative = False                 # inset thickness is never negative

    _LAST_THICKNESS = 0.0   # remembered across runs -> R repeats the last inset

    # --- tool state ------------------------------------------------------

    def _init_tool(self, context, event):
        self.thickness = 0.0
        self.plane_co = None      # world face center (the inset's plane)
        self.plane_no = None      # world face normal
        self.pick0 = None         # world point where the drag started

    # --- locking ---------------------------------------------------------

    def _lock_edit(self, context, event):
        """Edit Mode lock: build the inset plane from the selected faces' average
        center/normal and snapshot the edit-mesh for the live preview."""
        basis = geometry.selected_face_basis(self.obj)
        if basis is None:
            return False
        center, normal = basis
        mw = self.obj.matrix_world
        self.plane_co = mw @ center
        self.plane_no = (mw.to_3x3() @ normal).normalized()
        co = (event.mouse_region_x, event.mouse_region_y)
        region, rv3d = context.region, context.region_data
        self.pick0 = raycast.ray_to_plane(region, rv3d, co,
                                          self.plane_co, self.plane_no)
        self.thickness = 0.0
        self.typed = ""
        self.locked = True
        geometry.flush_edit_mesh(self.obj)   # sync selection before snapshot
        self._base = geometry.snapshot_mesh(self.obj, self._snapshot_name)
        return True

    def _lock_face(self, context, co):
        poly = self.obj.data.polygons[self.face_index]
        mw = self.obj.matrix_world
        self.plane_co = mw @ poly.center
        self.plane_no = (mw.to_3x3() @ poly.normal).normalized()
        region, rv3d = context.region, context.region_data
        self.pick0 = raycast.ray_to_plane(region, rv3d, co,
                                          self.plane_co, self.plane_no)
        self.thickness = 0.0
        self.typed = ""
        self.locked = True
        self._base = geometry.snapshot_mesh(self.obj, self._snapshot_name)

    # --- dragging / apply ------------------------------------------------

    def _refresh_preview(self):
        """Show the real inset live: restore the snapshot, then re-inset the
        locked face(s) by the current thickness. Routes through the edit-mesh in
        Edit Mode, the object mesh otherwise."""
        if self._base is None:
            return
        if self.edit:
            geometry.restore_edit_mesh(self.obj, self._base)
            if self.thickness > 1e-6:
                geometry.edit_inset_faces(self.obj, self.thickness)
            return
        geometry.restore_mesh(self.obj, self._base)
        if self.thickness > 1e-6:
            geometry.inset_faces(self.obj, [self.face_index], self.thickness)

    def _update_drag(self, context, co):
        region, rv3d = context.region, context.region_data
        p = raycast.ray_to_plane(region, rv3d, co, self.plane_co, self.plane_no)
        if p is None or self.pick0 is None:
            return
        d = (p - self.pick0).length
        self.thickness = grid.snap_scalar(d, get_prefs(context).grid_world,
                                          self.snap)
        self.typed = ""

    def _set_value(self, v):
        self.thickness = max(0.0, v)

    def _repeat_last(self):
        self.thickness = HARDFLOW_OT_offset._LAST_THICKNESS

    def _remember_last(self):
        if self.thickness > 1e-6:
            HARDFLOW_OT_offset._LAST_THICKNESS = self.thickness

    # --- HUD -------------------------------------------------------------

    def _hud_lines(self, context, prefs):
        accent = tuple(prefs.line_color)[:3] + (1.0,)
        dim = (0.72, 0.72, 0.72, 1.0)
        if not self.locked:
            top = ("Hover a face, then click to offset", accent)
        else:
            typed = ("  [typing %s]" % self.typed) if self.typed else ""
            top = ("Thickness:  %.3f m%s" % (self.thickness, typed), accent)
        last = HARDFLOW_OT_offset._LAST_THICKNESS
        repeat = ("    R repeat %.3f m" % last) if last > 1e-6 else ""
        return [
            top,
            ("Click face = lock    drag / type number = thickness    "
             "X snap %s" % ('ON' if self.snap else 'OFF'), dim),
            ("Enter / click apply%s    Esc cancel" % repeat, dim),
        ]
