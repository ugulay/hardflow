# Push/Pull: a direct-modeling tool. Hover a face, click to lock it, then
# drag along its normal (grid-snapped + vertex inference, with numeric entry) to
# extrude in or out; click again or Enter to apply. C keeps the starting face
# (copy/stack), R repeats the last distance.
#
# The hover/lock/drag/preview/cancel shell lives in face_tool._FaceDragModal;
# this file only adds the normal-axis drag, the extrude apply, and inference.
#
# Object Mode, active mesh. The face is picked by raycasting the scene; a hit on
# geometry a generative modifier added (face index past the base mesh) is mapped
# back to the nearest base face by the shared base (geometry.nearest_face_to_point)
# -- exact for deform-only modifiers, best-effort for topology-changing ones.
import bpy
from bpy.types import Operator
from bpy.props import FloatProperty, IntProperty, BoolProperty

from .face_tool import _FaceDragModal
from ..preferences import get_prefs
from ..core import raycast, geometry, boolean, transform


class HARDFLOW_OT_push_pull(_FaceDragModal, Operator):
    bl_idname = "mesh.hardflow_push_pull"
    bl_label = "Hardflow Push/Pull"
    bl_description = "Extrude a face along its normal by dragging (Push/Pull)"
    bl_options = {'REGISTER', 'UNDO'}

    # Redo (F9 "Adjust Last Operation") + scripting properties. The modal drag
    # writes distance/copy/face_index as it runs, so on commit Blender can re-run
    # execute() non-modally with an adjustable distance -- and the tool becomes
    # callable from Python. The interactive path still goes through invoke().
    distance: FloatProperty(
        name="Distance", description="Extrude distance along the face normal",
        default=0.0, unit='LENGTH')
    copy: BoolProperty(
        name="Copy", description="Keep the starting face and stack a new volume",
        default=False)
    dissolve: BoolProperty(
        name="Manifold",
        description="Manifold push: an INWARD push cuts the volume the face "
                    "sweeps out of the mesh (boolean) instead of extruding into "
                    "it, so it leaves a clean pocket -- or a hole when it goes "
                    "all the way through -- with no buried side walls. Outward "
                    "pulls stay a plain extrude",
        default=False)
    face_index: IntProperty(
        name="Face Index", default=-1, options={'HIDDEN'})

    _HOVER_FILL = (0.15, 0.8, 1.0, 0.18)   # hovered (loose) face tint
    _LOCK_FILL = (1.0, 0.6, 0.1, 0.22)     # locked (committed) face tint
    _snapshot_name = "hf_pushpull_base"
    _select_warning = "Select face(s) to push/pull"
    _hud_title = "Push / Pull"
    allow_negative = True                  # push (-) and pull (+) both valid

    _LAST_DISTANCE = 0.0   # remembered across runs -> R repeats the last amount

    # --- tool state ------------------------------------------------------

    def _init_tool(self, context, event):
        self.distance = 0.0       # signed extrude amount, meters
        self.copy = False         # keep the starting face (Ctrl push/pull copy)
        # Manifold push: seeded from the preference, toggled live with D.
        # Off by default -- the plain extrude is unchanged.
        self.dissolve = get_prefs(context).extrude_manifold
        self._ctx = context       # kept for the boolean (robust_boolean needs it)
        self._final = False       # commit frame -> never skip the boolean
        self._manifold_note = ""  # what the last Manifold push did, for the HUD

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
        self._begin_edit(restore=geometry.restore_edit_mesh)
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
        self._begin_edit()
        self._capture_axis_inference(self.axis_co, self.axis_dir)

    # --- dragging / apply ------------------------------------------------

    def _mutate(self, obj):
        """Re-extrude the locked face(s) by the current distance -- the edit only;
        the session command restores the pre-extrude snapshot first. Routes
        through the edit-mesh in Edit Mode, the object mesh otherwise."""
        if abs(self.distance) <= 1e-6:
            return
        if self._manifold_push(obj, self._local_disp()):
            return
        if self.edit:
            geometry.edit_extrude_faces(obj, self._local_disp(),
                                        keep_original=self.copy)
        else:
            geometry.extrude_faces(obj, [self.face_index], self._local_disp(),
                                   keep_original=self.copy)

    # --- Manifold push (issue #5) ----------------------------------------

    def _manifold_push(self, obj, disp):
        """Cut the volume the face sweeps out of the mesh instead of extruding
        into it: the swept prism becomes a boolean cutter, so an inward push
        leaves a clean pocket (or a hole, pushed all the way through) with no
        side walls buried in the solid.

        Only for an inward push in Object Mode with Manifold on; everything else
        returns False so the caller runs the plain extrude. A failed cutter or a
        failed solver also returns False -- the push still happens, just the old
        way, and the HUD says so. On a mesh heavier than the live-preview cap the
        drag previews the plain extrude and the boolean runs on the commit frame
        (`_final`), so a mouse-move never waits on a heavy boolean."""
        self._manifold_note = ""
        if not self.dissolve or self.edit or self.copy:
            return False
        if not (0 <= self.face_index < len(obj.data.polygons)):
            return False
        poly = obj.data.polygons[self.face_index]
        if not transform.push_is_inward(poly.normal, disp):
            return False
        context = self._ctx
        prefs = get_prefs(context)
        if not self._final and len(obj.data.vertices) > prefs.live_preview_max_verts:
            self._manifold_note = "manifold on commit"
            return False
        # Cutting a volume out of something that has no volume is meaningless
        # (and a DIFFERENCE on an open mesh can eat it), so an open / broken
        # target keeps the plain extrude.
        if boolean.mesh_health(obj)['non_manifold']:
            self._manifold_note = "open mesh -> plain extrude"
            return False

        mw = obj.matrix_world
        corners = [mw @ obj.data.vertices[i].co for i in poly.vertices]
        if len(corners) < 3:
            return False
        push = (mw.to_3x3() @ poly.normal).normalized() * -1.0
        offset, thickness = transform.sweep_prism_span(self.distance)
        mesh = geometry.build_prism([c + push * offset for c in corners],
                                    push, thickness, name="hf_push_cutter")
        if mesh is None:
            self._manifold_note = "cutter failed"
            return False
        cutter = bpy.data.objects.new("hf_push_cutter", mesh)
        context.collection.objects.link(cutter)
        try:
            solver = prefs.default_solver
            ok, _used, msg = boolean.robust_boolean(context, obj, cutter,
                                                    'DIFFERENCE', solver)
        finally:
            bpy.data.objects.remove(cutter, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        if not ok:
            self._manifold_note = "boolean failed -> plain extrude"
            return False
        return True

    def _commit(self, context):
        # The drag may have skipped the boolean on a heavy mesh; the commit frame
        # re-applies at full fidelity before the journal is handed to undo.
        self._final = True
        return super()._commit(context)

    def _local_disp(self):
        world_disp = self.axis_dir * self.distance
        return self.obj.matrix_world.inverted_safe().to_3x3() @ world_disp

    def _update_drag(self, context, co):
        self._ctx = context
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
        # volume on it (Ctrl push/pull copy, bound to C to stay clear of the
        # navigation modifiers).
        self._ctx = context
        if event.type == 'C':
            self.copy = not self.copy
            if self.locked:
                self._refresh_preview()
            return True
        # D: toggle Manifold -- dissolve the orthogonal edges so a push into
        # adjoining geometry cuts instead of burying faces inside the mesh.
        if event.type == 'D':
            self.dissolve = not self.dissolve
            if self.locked:
                self._refresh_preview()
            return True
        return False

    def _tool_chips(self):
        return [("C", "Copy", self.copy), ("D", "Manifold", self.dissolve),
                ("R", "Repeat"), ("X", "Snap", self.snap)]

    def _cursor_label(self):
        return "%.3f m" % self.distance

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
            note = ("  [%s]" % self._manifold_note) if self._manifold_note else ""
            top = ("Distance:  %.3f m%s%s%s%s"
                   % (self.distance, typed, copy, infer, note), accent)
        last = HARDFLOW_OT_push_pull._LAST_DISTANCE
        repeat = ("    R repeat %.3f m" % last) if abs(last) > 1e-6 else ""
        return [
            top,
            ("Click face = lock    drag / type number = distance    "
             "X snap %s    C copy %s    D manifold %s"
             % ('ON' if self.snap else 'OFF', 'ON' if self.copy else 'OFF',
                'ON' if self.dissolve else 'OFF'), dim),
            ("Enter / click apply%s    Esc cancel" % repeat, dim),
        ]

    # --- non-modal apply (F9 redo / scripting) ---------------------------

    def execute(self, context):
        """Re-apply the extrude from the stored face + distance, without the modal
        loop -- the "Adjust Last Operation" (F9) redo and the scripted entry point.
        Reproduces exactly what the drag committed (same world->local normal
        conversion), so tweaking the distance in the redo panel just re-extrudes."""
        obj = context.active_object
        if obj is None or obj.type != 'MESH' or abs(self.distance) <= 1e-6:
            return {'CANCELLED'}
        mw = obj.matrix_world
        if context.mode == 'EDIT_MESH':
            basis = geometry.selected_face_basis(obj)
            if basis is None:
                return {'CANCELLED'}
            _center, normal = basis
            world = (mw.to_3x3() @ normal).normalized() * self.distance
            disp = mw.inverted_safe().to_3x3() @ world
            geometry.flush_edit_mesh(obj)
            geometry.edit_extrude_faces(obj, disp, keep_original=self.copy)
            return {'FINISHED'}
        if not (0 <= self.face_index < len(obj.data.polygons)):
            return {'CANCELLED'}
        poly = obj.data.polygons[self.face_index]
        world = (mw.to_3x3() @ poly.normal).normalized() * self.distance
        disp = mw.inverted_safe().to_3x3() @ world
        self._ctx = context
        self._final = True
        self.edit = False
        if not self._manifold_push(obj, disp):
            geometry.extrude_faces(obj, [self.face_index], disp,
                                   keep_original=self.copy)
        return {'FINISHED'}

    def draw(self, context):
        """Compact redo panel: adjust the extrude distance / copy after the fact."""
        col = self.layout.column()
        col.prop(self, "distance")
        col.prop(self, "copy")
        col.prop(self, "dissolve")
