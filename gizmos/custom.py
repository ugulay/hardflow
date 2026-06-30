# Custom modal gizmo: drag a face along its normal to extrude it (Push/Pull as
# a viewport handle). Unlike the move/rotate/scale gizmos -- which wrap Blender's
# built-in transform operators -- Push/Pull changes geometry, so it needs the
# snapshot/restore live-preview lifecycle. A built-in arrow + property handler
# has no clean drag-start/drag-end hook for that, so this is a full custom Gizmo
# implementing invoke/modal/exit, mirroring operators/push_pull.py's proven path
# (snapshot_mesh -> restore + extrude each frame -> keep on confirm / roll back
# on cancel).
#
# The owning GizmoGroup (see groups.py) fills in _obj / _axis_co / _axis_dir and
# the placement matrix every refresh; this class only handles the drag.
import bpy
from bpy.types import Gizmo

from .shapes import arrow_tris
from ..preferences import get_prefs
from ..core import geometry, grid, raycast

_ARROW = arrow_tris()


class HARDFLOW_GT_drag_extrude(Gizmo):
    bl_idname = "HARDFLOW_GT_drag_extrude"

    # Everything the group writes onto us, plus our own drag state, must be
    # declared (Gizmo subclasses use __slots__, like the Blender templates).
    __slots__ = (
        "custom_shape",
        "_obj", "_edit", "_face_index", "_axis_co", "_axis_dir",
        "_base", "_distance", "_d0", "_snap", "_dragging",
    )

    # --- drawing / selection --------------------------------------------

    def draw(self, context):
        self.draw_custom_shape(self.custom_shape)

    def draw_select(self, context, select_id):
        self.draw_custom_shape(self.custom_shape, select_id=select_id)

    def setup(self):
        if not hasattr(self, "custom_shape"):
            self.custom_shape = self.new_custom_shape('TRIS', _ARROW)
        self._base = None
        self._dragging = False
        self._distance = 0.0

    # --- drag lifecycle --------------------------------------------------

    def invoke(self, context, event):
        self._snap = get_prefs(context).snap_enabled
        self._distance = 0.0
        self._dragging = True
        co = (event.mouse_region_x, event.mouse_region_y)
        # Capture the starting position along the axis so the drag delta -- not
        # the absolute projection (which equals the arrow length) -- drives it.
        self._d0 = raycast.closest_axis_distance(
            context.region, context.region_data, co,
            self._axis_co, self._axis_dir)
        if self._edit:
            geometry.flush_edit_mesh(self._obj)
        self._base = geometry.snapshot_mesh(self._obj, "hf_gizmo_pushpull")
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        co = (event.mouse_region_x, event.mouse_region_y)
        d = raycast.closest_axis_distance(
            context.region, context.region_data, co,
            self._axis_co, self._axis_dir) - self._d0
        snap = self._snap
        if 'SNAP' in tweak:          # Ctrl inverts the snap state, like the tools
            snap = not snap
        d = grid.snap_scalar(d, get_prefs(context).grid_world, snap)
        self._distance = d
        self._apply()
        context.area.header_text_set("Hardflow Push/Pull:  %.4f m" % d)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _apply(self):
        """Reset to the snapshot, then re-extrude by the current distance -- the
        same live-preview pattern as the modal Push/Pull operator."""
        obj = self._obj
        if self._base is None:
            return
        local = (obj.matrix_world.inverted_safe().to_3x3()
                 @ (self._axis_dir * self._distance))
        if self._edit:
            geometry.restore_edit_mesh(obj, self._base)
            if abs(self._distance) > 1e-6:
                geometry.edit_extrude_faces(obj, local)
        else:
            geometry.restore_mesh(obj, self._base)
            if abs(self._distance) > 1e-6:
                geometry.extrude_faces(obj, [self._face_index], local)

    def exit(self, context, cancel):
        context.area.header_text_set(None)
        self._dragging = False
        obj = getattr(self, "_obj", None)
        if cancel and self._base is not None and obj is not None:
            if self._edit:
                geometry.restore_edit_mesh(obj, self._base)
            else:
                geometry.restore_mesh(obj, self._base)
        if getattr(self, "_base", None) is not None:
            geometry.free_mesh(self._base)
            self._base = None
