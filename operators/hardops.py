# Hard Ops parity operators (v1.5): dice/panel, edge bevel-weight/crease,
# viewport display toggles, material/color helpers, and parametric greeble
# generators (step / taper / knurl). All thin wrappers over pure-ish core builders
# in core/geometry.py; the modifier stack manager lives in ui/panel.py (it only
# drives Blender's built-in modifier operators).
import random

import bpy
from bpy.types import Operator
from bpy.props import (IntProperty, FloatProperty, EnumProperty, BoolProperty,
                       FloatVectorProperty)
from mathutils import Matrix

from ..core import geometry, boolean


def _place_at_cursor(context, obj):
    """Link a freshly built object, drop it at the 3D cursor, make it the
    active selection (shared by the greeble generators)."""
    context.collection.objects.link(obj)
    obj.matrix_world = Matrix.Translation(context.scene.cursor.location)
    for o in list(context.selected_objects):
        o.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


class HARDFLOW_OT_dice(Operator):
    bl_idname = "object.hardflow_dice"
    bl_label = "Hardflow Dice"
    bl_description = ("Grid-slice the mesh into panels along its local axes "
                      "(Hard Ops dice / panel break)")
    bl_options = {'REGISTER', 'UNDO'}

    count_x: IntProperty(name="X", default=2, min=1, max=64)
    count_y: IntProperty(name="Y", default=2, min=1, max=64)
    count_z: IntProperty(name="Z", default=1, min=1, max=64)
    mark_sharp: BoolProperty(name="Mark Cuts Sharp", default=True)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')

    def execute(self, context):
        passes = geometry.dice_mesh(
            context.active_object,
            (self.count_x, self.count_y, self.count_z),
            mark_sharp=self.mark_sharp)
        self.report({'INFO'}, "Dice: %d cut plane(s)" % passes)
        return {'FINISHED'}


class HARDFLOW_OT_edge_weight(Operator):
    bl_idname = "mesh.hardflow_edge_weight"
    bl_label = "Hardflow Edge Weight"
    bl_description = ("Set bevel weight / crease on the selected edges so a "
                      "weight-limited Bevel or creased Subdivision can act on "
                      "them (Edit Mode)")
    bl_options = {'REGISTER', 'UNDO'}

    bevel_weight: FloatProperty(name="Bevel Weight", default=1.0, min=0.0, max=1.0)
    crease: FloatProperty(name="Crease", default=0.0, min=0.0, max=1.0)
    set_bevel: BoolProperty(name="Set Bevel Weight", default=True)
    set_crease: BoolProperty(name="Set Crease", default=False)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'EDIT_MESH')

    def execute(self, context):
        bw = self.bevel_weight if self.set_bevel else None
        cr = self.crease if self.set_crease else None
        if bw is None and cr is None:
            self.report({'WARNING'}, "Nothing to set")
            return {'CANCELLED'}
        n = geometry.edit_set_edge_weights(context.active_object, bw, cr)
        self.report({'INFO'}, "Weighted %d edge(s)" % n)
        return {'FINISHED'}


class HARDFLOW_OT_display_toggle(Operator):
    bl_idname = "object.hardflow_display_toggle"
    bl_label = "Hardflow Display Toggle"
    bl_description = "Quick viewport toggles: wireframe / sharp edges / cutters"
    bl_options = {'REGISTER'}

    mode: EnumProperty(
        name="Toggle",
        items=[
            ('WIRE', "Wireframe", "Show the active object as wireframe overlay"),
            ('SHARP', "Sharp Edges", "Show sharp edges in the viewport overlay"),
            ('CUTTERS', "Cutters", "Show/hide the Hardflow Cutters collection"),
        ],
        default='WIRE',
    )

    def execute(self, context):
        if self.mode == 'WIRE':
            obj = context.active_object
            if obj is None:
                return {'CANCELLED'}
            obj.show_wire = not obj.show_wire
            obj.show_all_edges = obj.show_wire
        elif self.mode == 'SHARP':
            ov = getattr(context.space_data, "overlay", None)
            if ov is None or not hasattr(ov, "show_edge_sharp"):
                self.report({'INFO'}, "Sharp-edge overlay not available here")
                return {'CANCELLED'}
            ov.show_edge_sharp = not ov.show_edge_sharp
        elif self.mode == 'CUTTERS':
            coll = bpy.data.collections.get(boolean.CUTTER_COLLECTION)
            if coll is None:
                self.report({'INFO'}, "No cutter collection")
                return {'CANCELLED'}
            coll.hide_viewport = not coll.hide_viewport
        return {'FINISHED'}


class HARDFLOW_OT_random_color(Operator):
    bl_idname = "object.hardflow_random_color"
    bl_label = "Hardflow Random Colors"
    bl_description = ("Assign a random viewport color to each selected object for "
                      "fast block-out readability (sets shading to Object color)")
    bl_options = {'REGISTER', 'UNDO'}

    saturation: FloatProperty(name="Saturation", default=0.5, min=0.0, max=1.0)
    value: FloatProperty(name="Value", default=0.9, min=0.0, max=1.0)

    def execute(self, context):
        from colorsys import hsv_to_rgb
        sel = [o for o in context.selected_objects]
        for o in sel:
            r, g, b = hsv_to_rgb(random.random(), self.saturation, self.value)
            o.color = (r, g, b, 1.0)
        # Make the colors visible: switch solid shading to per-object color.
        space = context.space_data
        if space is not None and space.type == 'VIEW_3D':
            space.shading.color_type = 'OBJECT'
        self.report({'INFO'}, "Colored %d object(s)" % len(sel))
        return {'FINISHED'}


class HARDFLOW_OT_copy_material(Operator):
    bl_idname = "object.hardflow_copy_material"
    bl_label = "Hardflow Copy Material"
    bl_description = "Copy the active object's active material to all selected meshes"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.active_material is not None

    def execute(self, context):
        mat = context.active_object.active_material
        n = 0
        for o in context.selected_objects:
            if o.type != 'MESH' or o is context.active_object:
                continue
            o.data.materials.clear()
            o.data.materials.append(mat)
            n += 1
        self.report({'INFO'}, "Copied material to %d mesh(es)" % n)
        return {'FINISHED'}


class _GreebleBase(Operator):
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'


class HARDFLOW_OT_add_step(_GreebleBase):
    bl_idname = "object.hardflow_add_step"
    bl_label = "Add Steps"
    bl_description = "Add a stepped block (staircase greeble) at the 3D cursor"

    count: IntProperty(name="Steps", default=5, min=1, max=128)
    rise: FloatProperty(name="Rise", default=0.1, min=0.001, soft_max=2.0)
    run: FloatProperty(name="Run", default=0.1, min=0.001, soft_max=2.0)
    width: FloatProperty(name="Width", default=1.0, min=0.001, soft_max=10.0)

    def execute(self, context):
        mesh = geometry.build_steps(self.count, self.rise, self.run, self.width)
        _place_at_cursor(context, bpy.data.objects.new("Hardflow_Steps", mesh))
        return {'FINISHED'}


class HARDFLOW_OT_add_taper(_GreebleBase):
    bl_idname = "object.hardflow_add_taper"
    bl_label = "Add Taper"
    bl_description = "Add a tapered box / frustum at the 3D cursor (top=0 = pyramid)"

    bottom: FloatProperty(name="Bottom", default=1.0, min=0.001, soft_max=10.0)
    top: FloatProperty(name="Top", default=0.5, min=0.0, soft_max=10.0)
    height: FloatProperty(name="Height", default=1.0, min=0.001, soft_max=10.0)

    def execute(self, context):
        mesh = geometry.build_taper(self.bottom, self.top, self.height)
        _place_at_cursor(context, bpy.data.objects.new("Hardflow_Taper", mesh))
        return {'FINISHED'}


class HARDFLOW_OT_add_knurl(_GreebleBase):
    bl_idname = "object.hardflow_add_knurl"
    bl_label = "Add Knurl"
    bl_description = "Add a knurled cylinder at the 3D cursor"

    radius: FloatProperty(name="Radius", default=0.5, min=0.001, soft_max=10.0)
    height: FloatProperty(name="Height", default=1.0, min=0.001, soft_max=10.0)
    teeth: IntProperty(name="Teeth", default=16, min=3, max=128)
    depth: FloatProperty(name="Tooth Depth", default=0.05, min=0.001, soft_max=1.0)

    def execute(self, context):
        mesh = geometry.build_knurl(self.radius, self.height, self.teeth,
                                    self.depth)
        _place_at_cursor(context, bpy.data.objects.new("Hardflow_Knurl", mesh))
        return {'FINISHED'}
