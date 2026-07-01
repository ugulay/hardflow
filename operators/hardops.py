# Mesh-editing parity operators (v1.5): edge bevel-weight/crease, viewport
# display toggles, material/color helpers, and the boolean-health normal recalc.
# All thin
# wrappers over pure-ish core helpers in core/geometry.py + core/boolean.py; the
# modifier stack manager lives in ui/panel.py (it only drives Blender's built-in
# modifier operators).
import math
import random

import bpy
from bpy.types import Operator
from bpy.props import FloatProperty, IntProperty, EnumProperty, BoolProperty

from ..core import geometry, boolean, hardsurface


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


class HARDFLOW_OT_smart_sharpen(Operator):
    bl_idname = "object.hardflow_smart_sharpen"
    bl_label = "Smart Sharpen / Init HardSurface"
    bl_description = ("One-shot hard-surface init on the selected mesh(es): mark "
                      "the hard edges sharp + weighted by dihedral angle, add an "
                      "angle-driven non-destructive Bevel, and cap the stack with "
                      "a Weighted Normal so the shading reads clean. Re-runs / F9 "
                      "update the same modifiers in place (never stacks copies)")
    bl_options = {'REGISTER', 'UNDO'}

    # The two managed modifiers, matched by name so a re-run updates in place.
    BEVEL_NAME = "HF_Bevel"
    WN_NAME = "HF_WeightedNormal"

    angle: FloatProperty(
        name="Sharp Angle", subtype='ANGLE',
        description="Edges whose dihedral face angle reaches this become hard "
                    "(marked sharp + bevel-weighted)",
        default=math.radians(30.0), min=math.radians(1.0), max=math.radians(180.0),
    )
    auto_width: BoolProperty(
        name="Auto Width", default=True,
        description="Scale the bevel width to the object's smallest dimension "
                    "instead of using a fixed width",
    )
    width: FloatProperty(
        name="Bevel Width", subtype='DISTANCE',
        description="Bevel width at full edge weight (used when Auto Width is off)",
        default=0.02, min=0.0, soft_max=1.0,
    )
    segments: IntProperty(name="Segments", default=2, min=1, max=12)
    profile: FloatProperty(name="Profile", default=0.7, min=0.0, max=1.0)
    use_weighted_normal: BoolProperty(
        name="Weighted Normal", default=True,
        description="Add a Weighted Normal modifier at the bottom of the stack so "
                    "the beveled shading stays crisp",
    )
    set_crease: BoolProperty(
        name="Also Crease", default=False,
        description="Also crease the hard edges (for a creased Subdivision)",
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')

    def _targets(self, context):
        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        if meshes:
            return meshes
        obj = context.active_object
        return [obj] if obj is not None and obj.type == 'MESH' else []

    def _bevel_mod(self, obj, width):
        """Get/create the managed Bevel modifier and tune it. Weight-limited so it
        acts only on the edges mark_sharp_edges weighted."""
        mod = obj.modifiers.get(self.BEVEL_NAME)
        if mod is None or mod.type != 'BEVEL':
            if mod is not None:
                obj.modifiers.remove(mod)
            mod = obj.modifiers.new(self.BEVEL_NAME, 'BEVEL')
        mod.width = width
        mod.segments = self.segments
        mod.profile = self.profile
        mod.limit_method = 'WEIGHT'
        return mod

    def _weighted_normal_mod(self, obj):
        """Get/create the Weighted Normal modifier and force it to the very bottom
        of the stack (it must run after the bevel to fix the shading)."""
        mod = obj.modifiers.get(self.WN_NAME)
        if mod is None or mod.type != 'WEIGHTED_NORMAL':
            if mod is not None:
                obj.modifiers.remove(mod)
            mod = obj.modifiers.new(self.WN_NAME, 'WEIGHTED_NORMAL')
        mod.keep_sharp = True
        mod.weight = 50
        mod.mode = 'FACE_AREA'
        try:
            idx = list(obj.modifiers).index(mod)
            last = len(obj.modifiers) - 1
            if idx != last:
                obj.modifiers.move(idx, last)
        except (ValueError, RuntimeError):
            pass
        return mod

    def _process(self, obj):
        crease = 1.0 if self.set_crease else None
        n = geometry.mark_sharp_edges(
            obj, self.angle, set_sharp=True, set_bevel_weight=True,
            crease=crease, shade_smooth=True)
        # Pre-4.1 needs auto-smooth on for sharp edges to affect shading; 4.1+
        # dropped the flag (sharp edges are always live).
        if hasattr(obj.data, "use_auto_smooth"):
            obj.data.use_auto_smooth = True
        width = (hardsurface.adaptive_bevel_width(tuple(obj.dimensions))
                 if self.auto_width else self.width)
        self._bevel_mod(obj, width)
        if self.use_weighted_normal:
            self._weighted_normal_mod(obj)
        else:
            old = obj.modifiers.get(self.WN_NAME)
            if old is not None:
                obj.modifiers.remove(old)
        return n

    def execute(self, context):
        done, marked = 0, 0
        for obj in self._targets(context):
            try:
                marked += self._process(obj)
                done += 1
            except Exception as ex:  # noqa: BLE001 -- one bad mesh can't abort all
                self.report({'WARNING'},
                            "Smart Sharpen failed on %s: %s" % (obj.name, ex))
        if not done:
            self.report({'ERROR'}, "Smart Sharpen: no mesh processed")
            return {'CANCELLED'}
        self.report({'INFO'},
                    "Smart Sharpen: %d object(s), %d hard edge(s)" % (done, marked))
        return {'FINISHED'}

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "angle")
        col.prop(self, "auto_width")
        row = col.row()
        row.enabled = not self.auto_width
        row.prop(self, "width")
        col.prop(self, "segments")
        col.prop(self, "profile")
        col.prop(self, "use_weighted_normal")
        col.prop(self, "set_crease")


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
