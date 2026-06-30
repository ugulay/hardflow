# Array tools (Hard Ops spirit): a linear Array modifier and a radial array
# (Array modifier driven by a rotated offset Empty placed at the 3D cursor).
# Both are non-destructive -- the modifier stays editable -- and the angle math
# lives in core/transform.py (pure, tested).
import bpy
from bpy.types import Operator
from bpy.props import IntProperty, FloatProperty, EnumProperty, BoolProperty

from ..core import transform


class HARDFLOW_OT_array(Operator):
    bl_idname = "object.hardflow_array"
    bl_label = "Hardflow Array"
    bl_description = "Add a linear Array modifier along a world axis"
    bl_options = {'REGISTER', 'UNDO'}

    count: IntProperty(name="Count", default=3, min=1, max=512)
    axis: EnumProperty(
        name="Axis",
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='X',
    )
    use_relative: BoolProperty(
        name="Relative Offset", default=True,
        description="Offset by a factor of the object's own size (vs a constant "
                    "metre distance)")
    factor: FloatProperty(name="Offset", default=1.0, soft_min=-4.0, soft_max=4.0)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        mod = obj.modifiers.new("HF_Array", 'ARRAY')
        mod.count = self.count
        idx = {'X': 0, 'Y': 1, 'Z': 2}[self.axis]
        if self.use_relative:
            mod.use_relative_offset = True
            mod.use_constant_offset = False
            off = [0.0, 0.0, 0.0]
            off[idx] = self.factor
            mod.relative_offset_displace = off
        else:
            mod.use_relative_offset = False
            mod.use_constant_offset = True
            mod.constant_offset_displace = transform.array_offset_vector(
                self.axis, self.factor)
        return {'FINISHED'}


class HARDFLOW_OT_radial_array(Operator):
    bl_idname = "object.hardflow_radial_array"
    bl_label = "Hardflow Radial Array"
    bl_description = ("Radial array around the 3D cursor: an Array modifier driven "
                      "by a rotated offset Empty (count copies evenly around an axis)")
    bl_options = {'REGISTER', 'UNDO'}

    count: IntProperty(name="Count", default=6, min=1, max=512)
    axis: EnumProperty(
        name="Axis",
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='Z',
    )
    full_turn: FloatProperty(name="Sweep (deg)", default=360.0,
                             min=1.0, max=360.0)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        pivot = context.scene.cursor.location.copy()

        empty = bpy.data.objects.new("HF_RadialPivot", None)
        empty.empty_display_size = 0.2
        empty.location = pivot
        idx = {'X': 0, 'Y': 1, 'Z': 2}[self.axis]
        rot = [0.0, 0.0, 0.0]
        rot[idx] = transform.radial_step_radians(self.count, self.full_turn)
        empty.rotation_euler = rot
        context.collection.objects.link(empty)
        # the pivot follows the object so the array stays put if the object moves
        empty.parent = obj
        empty.matrix_parent_inverse = obj.matrix_world.inverted_safe()

        mod = obj.modifiers.new("HF_RadialArray", 'ARRAY')
        mod.count = self.count
        mod.use_relative_offset = False
        mod.use_object_offset = True
        mod.offset_object = empty

        self.report({'INFO'}, "Radial array x%d around %s (pivot at 3D cursor)"
                    % (self.count, self.axis))
        return {'FINISHED'}


class HARDFLOW_OT_curve_array(Operator):
    bl_idname = "object.hardflow_curve_array"
    bl_label = "Hardflow Array Along Curve"
    bl_description = ("Array the active mesh along a selected curve (Array "
                      "fit-curve + Curve deform), so copies follow the path")
    bl_options = {'REGISTER', 'UNDO'}

    count: IntProperty(
        name="Count", default=0, min=0, max=512,
        description="0 = fit the curve's length; otherwise a fixed copy count")
    axis: EnumProperty(
        name="Deform Axis",
        items=[('POS_X', "X", ""), ('POS_Y', "Y", ""), ('POS_Z', "Z", "")],
        default='POS_X',
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (context.mode == 'OBJECT' and obj is not None
                and obj.type == 'MESH'
                and any(o.type == 'CURVE' for o in context.selected_objects))

    def execute(self, context):
        obj = context.active_object
        curve = next((o for o in context.selected_objects
                      if o.type == 'CURVE'), None)
        if curve is None:
            self.report({'WARNING'}, "Select a curve to array along")
            return {'CANCELLED'}
        idx = {'POS_X': 0, 'POS_Y': 1, 'POS_Z': 2}[self.axis]
        arr = obj.modifiers.new("HF_CurveArray", 'ARRAY')
        if self.count > 0:
            arr.fit_type = 'FIXED_COUNT'
            arr.count = self.count
        else:
            arr.fit_type = 'FIT_CURVE'
            arr.curve = curve
        # one body-length offset along the deform axis -> copies sit end to end
        arr.use_relative_offset = True
        arr.use_constant_offset = False
        off = [0.0, 0.0, 0.0]
        off[idx] = 1.0
        arr.relative_offset_displace = off
        # Curve modifier AFTER the array bends the row of copies along the path
        deform = obj.modifiers.new("HF_CurveDeform", 'CURVE')
        deform.object = curve
        deform.deform_axis = self.axis
        self.report({'INFO'}, "Arrayed '%s' along '%s'" % (obj.name, curve.name))
        return {'FINISHED'}
