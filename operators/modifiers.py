# Hard Ops tarzi yardimci operatorler: akilli bevel ve mirror.
import bpy
from bpy.types import Operator
from bpy.props import FloatProperty, IntProperty, EnumProperty, BoolProperty


class HARDFLOW_OT_bevel(Operator):
    bl_idname = "object.hardflow_bevel"
    bl_label = "Hardflow Bevel"
    bl_options = {'REGISTER', 'UNDO'}

    width: FloatProperty(name="Width", default=0.02, min=0.0, soft_max=0.5)
    segments: IntProperty(name="Segments", default=2, min=1, max=24)
    harden: BoolProperty(name="Harden Normals", default=True)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        if self.harden:
            obj.data.use_auto_smooth = getattr(obj.data, "use_auto_smooth", False)
        mod = obj.modifiers.new("HF_Bevel", 'BEVEL')
        mod.width = self.width
        mod.segments = self.segments
        mod.limit_method = 'ANGLE'
        mod.angle_limit = 0.523599  # 30 derece
        mod.use_clamp_overlap = True
        mod.harden_normals = self.harden
        mod.miter_outer = 'MITER_ARC'
        return {'FINISHED'}


class HARDFLOW_OT_mirror(Operator):
    bl_idname = "object.hardflow_mirror"
    bl_label = "Hardflow Mirror"
    bl_options = {'REGISTER', 'UNDO'}

    axis: EnumProperty(
        name="Axis",
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='X',
    )
    bisect: BoolProperty(name="Bisect", default=True)
    flip: BoolProperty(name="Flip", default=False)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        mod = obj.modifiers.new("HF_Mirror", 'MIRROR')
        idx = {'X': 0, 'Y': 1, 'Z': 2}[self.axis]
        mod.use_axis = (idx == 0, idx == 1, idx == 2)
        mod.use_bisect_axis = (idx == 0, idx == 1, idx == 2)
        if self.flip:
            mod.use_bisect_flip_axis = (idx == 0, idx == 1, idx == 2)
        mod.use_clip = True
        return {'FINISHED'}
