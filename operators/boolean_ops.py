# Boolean from selected objects: use one already-existing object as the cutter
# against the other selected meshes -- no drawing. The
# active object is the cutter; every other selected mesh is a target. Honours the
# non-destructive preference (leave a live modifier + stash the cutter).
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty

from ..core import boolean, geometry
from ..preferences import get_prefs


_BOOL_MODES = [
    ('DIFFERENCE', "Difference", "Cut the cutter out of the targets (CUT)"),
    ('UNION', "Union", "Merge the cutter into the targets (MAKE)"),
    ('INTERSECT', "Intersect", "Keep only the overlap"),
    ('SLICE', "Slice", "Split each target in two along the cutter"),
]


class HARDFLOW_OT_boolean(Operator):
    bl_idname = "object.hardflow_boolean"
    bl_label = "Boolean (Selected)"
    bl_description = ("Boolean the selected meshes using the active object as the "
                      "cutter (Difference / Union / Intersect / Slice)")
    bl_options = {'REGISTER', 'UNDO'}

    operation: EnumProperty(name="Operation", items=_BOOL_MODES,
                            default='DIFFERENCE')

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        sel = [o for o in context.selected_objects if o.type == 'MESH']
        return (context.mode == 'OBJECT' and obj is not None
                and obj.type == 'MESH' and len(sel) >= 2)

    def execute(self, context):
        prefs = get_prefs(context)
        solver = prefs.default_solver
        nd = prefs.non_destructive
        cleanup = prefs.cleanup_after_cut
        cutter = context.active_object
        targets = [o for o in context.selected_objects
                   if o.type == 'MESH' and o is not cutter]
        if not targets:
            self.report({'WARNING'}, "Select target meshes plus an active cutter")
            return {'CANCELLED'}

        op = (self.operation if self.operation != 'SLICE' else None)
        self._failures = []
        try:
            if self.operation == 'SLICE':
                self._slice(context, targets, cutter, solver, nd, cleanup)
            elif nd:
                for t in targets:
                    boolean.add_boolean(t, cutter, op, solver)
                boolean.stash_cutter(context, cutter, targets[0])
            else:
                for t in targets:
                    self._cut(context, t, cutter, op, solver, cleanup)
                bpy.data.objects.remove(cutter, do_unlink=True)
        except Exception as ex:  # noqa: BLE001
            self.report({'ERROR'}, "Hardflow Boolean: %s" % ex)
            return {'CANCELLED'}

        if self._failures:
            self.report({'WARNING'}, self._failures[0])
        else:
            self.report({'INFO'}, "Boolean %s on %d target(s)"
                        % (self.operation.capitalize(), len(targets)))
        return {'FINISHED'}

    def _cut(self, context, target, cutter, op, solver, cleanup):
        """Destructive cut with solver fallback + diagnosis. The cutter is deleted
        right after, so the normal-repair retry inside robust_boolean is safe."""
        ok, _used, msg = boolean.robust_boolean(context, target, cutter, op, solver)
        if not ok:
            self._failures.append(msg)
        elif cleanup:
            geometry.cleanup_mesh(target)

    def _slice(self, context, targets, cutter, solver, nd, cleanup):
        """Split each target in two: a DIFFERENCE half and an INTERSECT half (the
        carved-out piece), mirroring the draw tool's SLICE."""
        for t in targets:
            other = boolean.duplicate_object(context, t)
            if nd:
                boolean.add_boolean(t, cutter, 'DIFFERENCE', solver)
                boolean.add_boolean(other, cutter, 'INTERSECT', solver)
            else:
                self._cut(context, t, cutter, 'DIFFERENCE', solver, cleanup)
                self._cut(context, other, cutter, 'INTERSECT', solver, cleanup)
        if nd:
            boolean.stash_cutter(context, cutter, targets[0])
        else:
            bpy.data.objects.remove(cutter, do_unlink=True)
