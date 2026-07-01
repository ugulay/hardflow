# Offset: pick a face, drag to inset its border inward by a measured thickness
# (the Offset tool). Grid-snapped, with numeric entry; click again or
# Enter to apply. R repeats the last thickness.
#
# The hover/lock/drag/preview/cancel shell lives in face_tool._FaceDragModal;
# this file only adds the in-plane drag measure and the inset apply.
#
# Object Mode, active mesh. Like Push/Pull the face index comes from a raycast;
# a hit past the base mesh (a generative modifier added it) is mapped back to the
# nearest base face by the shared base -- best-effort for topology-changing mods.
from bpy.types import Operator

from .face_tool import _FaceDragModal
from ..core import raycast, geometry, grid, snap
from ..core import offset as inset_math
from ..preferences import get_prefs


class HARDFLOW_OT_offset(_FaceDragModal, Operator):
    bl_idname = "mesh.hardflow_offset"
    bl_label = "Hardflow Offset"
    bl_description = "Inset a face's border inward by a measured distance (Offset)"
    bl_options = {'REGISTER', 'UNDO'}

    _HOVER_FILL = (0.15, 0.8, 1.0, 0.18)
    _LOCK_FILL = (0.2, 1.0, 0.5, 0.20)     # green-tinted lock fill
    _snapshot_name = "hf_offset_base"
    _select_warning = "Select face(s) to offset"
    allow_negative = True                  # the EXTRUDE phase can recess inward

    _LAST_THICKNESS = 0.0   # remembered across runs -> R repeats the last inset

    # --- tool state ------------------------------------------------------

    def _init_tool(self, context, event):
        self.thickness = 0.0
        self.distance = 0.0       # phase-2 extrude amount (recess/raise depth)
        self.phase = 'OFFSET'     # OFFSET -> EXTRUDE (press E to chain)
        self.plane_co = None      # world face center (the inset's plane)
        self.plane_no = None      # world face normal
        self.pick0 = None         # world point where the drag started
        self._offset_infer = []   # in-plane thickness inference candidates

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
        self._begin_edit(restore=geometry.restore_edit_mesh)
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
        self._begin_edit()
        self._capture_offset_inference()

    def _capture_offset_inference(self):
        """In-plane thickness inference: the distances at which the inset border
        would line up with a real feature, so the offset can snap the border onto
        another vertex / coplanar edge of the face. Every other mesh vertex that is
        coplanar with the locked face and projects inside its boundary becomes a
        candidate (its distance to the nearest boundary edge). Object Mode only;
        Edit Mode keeps grid snap. Captured once from the pre-edit mesh."""
        self._offset_infer = []
        if self.edit or self.face_index < 0:
            return
        src = self._base if self._base is not None else self.obj.data
        if src is None or len(src.vertices) > 50000:
            return
        poly = src.polygons[self.face_index]
        right, up, normal = raycast.basis_from_normal(self.plane_no)
        origin = self.plane_co
        mw = self.obj.matrix_world
        boundary = [raycast.world_to_plane_uv(mw @ src.vertices[vi].co,
                                              origin, right, up)
                    for vi in poly.vertices]
        face_vi = set(poly.vertices)
        tol = max(1e-4, max(self.obj.dimensions) * 1e-3)
        interior = []
        for v in src.vertices:
            if v.index in face_vi:
                continue
            d = (mw @ v.co) - origin
            if abs(d.dot(normal)) > tol:          # not in the face plane
                continue
            uv = (d.dot(right), d.dot(up))
            if grid.point_in_polygon(uv, boundary):
                interior.append(uv)
        self._offset_infer = inset_math.inset_inference_candidates(boundary,
                                                                   interior)

    # --- dragging / apply ------------------------------------------------

    def _mutate(self, obj):
        """Re-inset the locked face (and, in the EXTRUDE phase, extrude the inner
        face) by the current value -- the edit only; the session command restores
        the snapshot first. Routes through the edit-mesh in Edit Mode."""
        if self.thickness <= 1e-6:
            return
        if self.edit:
            if self.phase == 'EXTRUDE':
                geometry.edit_inset_extrude_faces(obj, self.thickness,
                                                  self._extrude_vec())
            else:
                geometry.edit_inset_faces(obj, self.thickness)
        elif self.phase == 'EXTRUDE':
            geometry.inset_extrude_faces(obj, [self.face_index],
                                         self.thickness, self._extrude_vec())
        else:
            geometry.inset_faces(obj, [self.face_index], self.thickness)

    def _extrude_vec(self):
        """Object-local extrude vector for the inner face: the face normal scaled
        by the (signed) recess/raise depth."""
        world = self.plane_no * self.distance
        return self.obj.matrix_world.inverted_safe().to_3x3() @ world

    def _update_drag(self, context, co):
        region, rv3d = context.region, context.region_data
        if self.phase == 'OFFSET':
            p = raycast.ray_to_plane(region, rv3d, co,
                                     self.plane_co, self.plane_no)
            if p is None or self.pick0 is None:
                return
            d = (p - self.pick0).length
            self.thickness = self._snap_offset(d, context)
        else:  # EXTRUDE: drag along the face normal (signed), with inference
            d = raycast.closest_axis_distance(region, rv3d, co,
                                              self.plane_co, self.plane_no)
            self.distance = self._snap_axis_value(d, context)
        self.typed = ""

    def _snap_offset(self, value, context):
        """Inference-then-grid snap for the inset thickness: snap the border onto a
        coplanar feature first (`_offset_infer`), grid otherwise. Sets
        self._infer_hit for the HUD. Returns the snapped thickness."""
        self._infer_hit = False
        if not self.snap:
            return value
        prefs = get_prefs(context)
        tol = max(1e-4, prefs.grid_world * 0.5)
        inferred = snap.snap_to_candidates(value, self._offset_infer, tol)
        if inferred != value and inferred > 0.0:
            self._infer_hit = True
            return inferred
        return grid.snap_scalar(value, prefs.grid_world, True)

    def _set_value(self, v):
        if self.phase == 'OFFSET':
            self.thickness = max(0.0, v)
        else:
            self.distance = v

    def _handle_key(self, context, event):
        # E: lock the current inset and chain into extruding the inner face
        # (the recess / raised-panel combo). Only from a non-zero offset.
        if (event.type == 'E' and self.locked and self.phase == 'OFFSET'
                and self.thickness > 1e-6):
            self.phase = 'EXTRUDE'
            self.typed = ""
            # Inference for the recess depth: snap to real feature heights.
            self._capture_axis_inference(self.plane_co, self.plane_no)
            return True
        return False

    def _repeat_last(self):
        # R repeats the last inset thickness -- only meaningful while still
        # setting the offset. In the EXTRUDE phase the thickness is locked, so
        # overwriting it here would silently corrupt the in-progress recess.
        if self.phase != 'OFFSET':
            return
        self.thickness = HARDFLOW_OT_offset._LAST_THICKNESS

    def _remember_last(self):
        if self.thickness > 1e-6:
            HARDFLOW_OT_offset._LAST_THICKNESS = self.thickness

    # --- HUD -------------------------------------------------------------

    def _hud_lines(self, context, prefs):
        accent = tuple(prefs.line_color)[:3] + (1.0,)
        dim = (0.72, 0.72, 0.72, 1.0)
        typed = ("  [typing %s]" % self.typed) if self.typed else ""
        if not self.locked:
            top = ("Hover a face, then click to offset", accent)
            line2 = ("Click face = lock    drag / type number = thickness    "
                     "X snap %s" % ('ON' if self.snap else 'OFF'), dim)
        elif self.phase == 'OFFSET':
            infer = "  -> on geometry" if self._infer_hit else ""
            top = ("Thickness:  %.3f m%s%s" % (self.thickness, typed, infer),
                   accent)
            line2 = ("drag / type = thickness    E = then extrude (recess/panel)"
                     "    X snap %s" % ('ON' if self.snap else 'OFF'), dim)
        else:  # EXTRUDE
            infer = "  -> on geometry" if self._infer_hit else ""
            top = ("Depth:  %+.3f m%s%s    (inset %.3f m)"
                   % (self.distance, typed, infer, self.thickness), accent)
            line2 = ("drag / type = recess depth (- in / + out)    "
                     "X snap %s" % ('ON' if self.snap else 'OFF'), dim)
        last = HARDFLOW_OT_offset._LAST_THICKNESS
        repeat = ("    R repeat %.3f m" % last) if last > 1e-6 else ""
        return [
            top,
            line2,
            ("Enter / click apply%s    Esc cancel" % repeat, dim),
        ]
