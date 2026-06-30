# Mesh-editing parity operators (v1.5): edge bevel-weight/crease, viewport
# display toggles, material/color helpers, and the boolean-health normal recalc.
# All thin
# wrappers over pure-ish core helpers in core/geometry.py + core/boolean.py; the
# modifier stack manager lives in ui/panel.py (it only drives Blender's built-in
# modifier operators).
import random

import bpy
from bpy.types import Operator
from bpy.props import FloatProperty, EnumProperty, BoolProperty

from ..core import geometry, boolean


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


class HARDFLOW_OT_recalc_normals(Operator):
    bl_idname = "object.hardflow_recalc_normals"
    bl_label = "Recalculate Normals"
    bl_description = ("Make the active mesh's normals point consistently outward "
                      "(the common fix for booleans that won't cut)")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        obj = context.active_object
        boolean.recalc_normals(obj)
        h = boolean.mesh_health(obj)
        if h['non_manifold'] or h['degenerate']:
            self.report({'WARNING'},
                        "Normals recalculated, but %s remain"
                        % (boolean._health_summary(obj),))
        else:
            self.report({'INFO'}, "Normals recalculated; mesh looks boolean-ready")
        return {'FINISHED'}
