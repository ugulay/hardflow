# Non-destructive cutter management: apply (bake), select, delete.
# The "Cutters" list in the N-panel delegates to these operators.
import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, StringProperty

from ..core import boolean


def _still_used(cutter, ignore=None):
    """Is any object still using this cutter in a boolean modifier?"""
    for ob in bpy.data.objects:
        if ob is ignore:
            continue
        for m in ob.modifiers:
            if getattr(m, "object", None) is cutter:
                return True
    return False


class HARDFLOW_OT_apply_cutters(Operator):
    bl_idname = "object.hardflow_apply_cutters"
    bl_label = "Apply Cutters"
    bl_description = ("Apply all live Hardflow booleans on the active object "
                      "(bake); delete cutters no longer used")
    bl_options = {'REGISTER', 'UNDO'}

    delete_cutters: BoolProperty(
        name="Delete Cutters",
        description="After applying, delete cutters not used anywhere else",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj) and any(m.name.startswith("HF_Bool")
                                 for m in obj.modifiers)

    def execute(self, context):
        obj = context.active_object
        used = []
        for mod in list(obj.modifiers):
            if not mod.name.startswith("HF_Bool"):
                continue
            if mod.type == 'BOOLEAN' and mod.object is not None:
                used.append(mod.object)
            with context.temp_override(active_object=obj, object=obj):
                bpy.ops.object.modifier_apply(modifier=mod.name)

        removed = 0
        if self.delete_cutters:
            for cutter in set(used):
                if not _still_used(cutter):
                    bpy.data.objects.remove(cutter, do_unlink=True)
                    removed += 1
        self.report({'INFO'}, "Cutters applied (%d deleted)" % removed)
        return {'FINISHED'}


class HARDFLOW_OT_select_cutter(Operator):
    bl_idname = "object.hardflow_select_cutter"
    bl_label = "Select Cutter"
    bl_description = "Make the cutter visible, select and activate it (to edit)"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        cutter = bpy.data.objects.get(self.name)
        if cutter is None:
            self.report({'WARNING'}, "Cutter not found")
            return {'CANCELLED'}
        for o in list(context.selected_objects):
            o.select_set(False)
        cutter.hide_viewport = False
        cutter.hide_set(False)
        cutter.select_set(True)
        context.view_layer.objects.active = cutter
        return {'FINISHED'}


class HARDFLOW_OT_remove_cutter(Operator):
    bl_idname = "object.hardflow_remove_cutter"
    bl_label = "Delete Cutter"
    bl_description = ("Delete the cutter from the scene; boolean modifiers using "
                      "it become ineffective (reversible with undo)")
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        cutter = bpy.data.objects.get(self.name)
        if cutter is None:
            return {'CANCELLED'}
        bpy.data.objects.remove(cutter, do_unlink=True)
        return {'FINISHED'}
