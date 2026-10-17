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

from .shapes import arrow_tris, ring_tris
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
        # Slots the owning group fills in each refresh. Default them so an invoke
        # on a not-yet-populated / hidden gizmo bails cleanly instead of raising
        # AttributeError on an unassigned __slots__ member.
        self._obj = None
        self._edit = False
        self._face_index = -1
        self._axis_co = None
        self._axis_dir = None

    # --- drag lifecycle --------------------------------------------------

    def invoke(self, context, event):
        if self._obj is None or self._axis_dir is None:
            return {'FINISHED'}      # gizmo not populated -> nothing to drag
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
        # A raise here never reaches exit(), which is the only place the mesh
        # snapshot is freed and the preview rolled back -- so a failure would
        # leave an orphan "hf_gizmo_pushpull" mesh in bpy.data and the object
        # stuck half-extruded. Roll back as if the drag was cancelled.
        try:
            return self._modal(context, event, tweak)
        except Exception:  # noqa: BLE001
            try:
                self.exit(context, True)
            except Exception:  # noqa: BLE001
                pass
            return {'FINISHED'}

    def _modal(self, context, event, tweak):
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
        if context.area is not None:
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
        if context.area is not None:
            context.area.header_text_set(None)
        self._dragging = False
        obj = getattr(self, "_obj", None)
        if cancel and getattr(self, "_base", None) is not None and obj is not None:
            if self._edit:
                geometry.restore_edit_mesh(obj, self._base)
            else:
                geometry.restore_mesh(obj, self._base)
        if getattr(self, "_base", None) is not None:
            geometry.free_mesh(self._base)
            self._base = None


_RING = ring_tris()


class HARDFLOW_GT_drag_inset(Gizmo):
    """Offset as a viewport handle: a flat ring lying in the plane of the
    selected face(s) that you drag inward to inset their border.

    Same live-preview contract as the Push/Pull gizmo above (snapshot -> restore
    + re-inset each frame -> keep on confirm, roll back on cancel), but the drag
    is measured IN the face plane rather than along its normal: a ring pulled
    toward the face centre is the operation, where an arrow out of the surface
    would read as an extrude. The owning GizmoGroup fills in _obj / _axis_co /
    _plane_dir and the placement matrix every refresh.
    """

    bl_idname = "HARDFLOW_GT_drag_inset"

    __slots__ = (
        "custom_shape",
        "_obj", "_axis_co", "_plane_dir",
        "_base", "_thickness", "_d0", "_snap", "_dragging",
    )

    def draw(self, context):
        self.draw_custom_shape(self.custom_shape)

    def draw_select(self, context, select_id):
        self.draw_custom_shape(self.custom_shape, select_id=select_id)

    def setup(self):
        if not hasattr(self, "custom_shape"):
            self.custom_shape = self.new_custom_shape('TRIS', _RING)
        self._base = None
        self._dragging = False
        self._thickness = 0.0
        self._obj = None
        self._axis_co = None
        self._plane_dir = None

    def invoke(self, context, event):
        if self._obj is None or self._plane_dir is None:
            return {'FINISHED'}      # not populated yet -> nothing to drag
        self._snap = get_prefs(context).snap_enabled
        self._thickness = 0.0
        self._dragging = True
        co = (event.mouse_region_x, event.mouse_region_y)
        # Measure along an in-plane axis through the face centre, so dragging
        # the ring toward the middle grows the inset.
        self._d0 = raycast.closest_axis_distance(
            context.region, context.region_data, co,
            self._axis_co, self._plane_dir)
        geometry.flush_edit_mesh(self._obj)
        self._base = geometry.snapshot_mesh(self._obj, "hf_gizmo_inset")
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        # As in the Push/Pull gizmo: a raise never reaches exit(), which is the
        # only place the snapshot is freed, so roll back as a cancelled drag.
        try:
            return self._modal(context, event, tweak)
        except Exception:  # noqa: BLE001
            try:
                self.exit(context, True)
            except Exception:  # noqa: BLE001
                pass
            return {'FINISHED'}

    def _modal(self, context, event, tweak):
        co = (event.mouse_region_x, event.mouse_region_y)
        d = self._d0 - raycast.closest_axis_distance(
            context.region, context.region_data, co,
            self._axis_co, self._plane_dir)
        snap = self._snap
        if 'SNAP' in tweak:          # Ctrl inverts the snap state, like the tools
            snap = not snap
        d = grid.snap_scalar(d, get_prefs(context).grid_world, snap)
        self._thickness = max(0.0, d)       # an inset never goes negative
        self._apply()
        if context.area is not None:
            context.area.header_text_set(
                "Hardflow Offset:  %.4f m" % self._thickness)
            context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _apply(self):
        """Reset to the snapshot, then re-inset by the current thickness."""
        if self._base is None:
            return
        geometry.restore_edit_mesh(self._obj, self._base)
        if self._thickness > 1e-6:
            geometry.edit_inset_faces(self._obj, self._thickness)

    def exit(self, context, cancel):
        if context.area is not None:
            context.area.header_text_set(None)
        self._dragging = False
        obj = getattr(self, "_obj", None)
        if cancel and getattr(self, "_base", None) is not None and obj is not None:
            geometry.restore_edit_mesh(obj, self._base)
        if getattr(self, "_base", None) is not None:
            geometry.free_mesh(self._base)
            self._base = None
