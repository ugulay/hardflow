# Hard Ops style helper operators: smart bevel, mirror, clean.
from math import radians

import bpy
from bpy.types import Operator
from bpy.props import FloatProperty, IntProperty, EnumProperty, BoolProperty

from ..core import geometry


class HARDFLOW_OT_bevel(Operator):
    bl_idname = "object.hardflow_bevel"
    bl_label = "Hardflow Bevel"
    bl_description = ("Smart bevel: interactive (drag=width, wheel="
                      "segments) + profile, angle limit, harden + weighted normal")
    bl_options = {'REGISTER', 'UNDO'}

    width: FloatProperty(name="Width", default=0.02, min=0.0, soft_max=0.5)
    segments: IntProperty(name="Segments", default=2, min=1, max=24)
    profile: FloatProperty(name="Profile", default=0.5, min=0.0, max=1.0)
    angle_deg: FloatProperty(name="Angle Limit", default=30.0, min=0.0, max=180.0)
    width_type: EnumProperty(
        name="Width Type",
        items=[('OFFSET', "Offset", ""), ('WIDTH', "Width", ""),
               ('DEPTH', "Depth", ""), ('PERCENT', "Percent", "")],
        default='OFFSET',
    )
    harden: BoolProperty(name="Harden Normals", default=True)
    weighted_normal: BoolProperty(
        name="Weighted Normal", default=True,
        description="Weighted Normal modifier for clean shading after bevel")

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    # --- modifier setup (execute = redo path; invoke sets up modal) ---------

    def _create(self, context):
        """Add HF_Bevel (+ optional Weighted Normal); store the added names.
        Since this is REGISTER|UNDO, on redo Blender first undoes, then calls
        this again -- so adding fresh each time is the correct pattern."""
        obj = context.active_object
        if self.harden:
            for poly in obj.data.polygons:
                poly.use_smooth = True
        bev = obj.modifiers.new("HF_Bevel", 'BEVEL')
        bev.width = self.width
        bev.segments = self.segments
        bev.profile = self.profile
        bev.limit_method = 'ANGLE'
        bev.angle_limit = radians(self.angle_deg)
        bev.offset_type = self.width_type
        bev.use_clamp_overlap = True
        bev.harden_normals = self.harden
        bev.miter_outer = 'MITER_ARC'
        self._added = [bev.name]
        if self.weighted_normal:
            wn = obj.modifiers.new("HF_WeightedNormal", 'WEIGHTED_NORMAL')
            wn.keep_sharp = True
            self._added.append(wn.name)
        return bev

    def _remove_added(self, context):
        obj = context.active_object
        for name in getattr(self, "_added", []):
            mod = obj.modifiers.get(name)
            if mod is not None:
                obj.modifiers.remove(mod)

    def execute(self, context):
        self._create(context)
        return {'FINISHED'}

    # --- interactive modal (HardOps style live adjustment) ------------------

    def invoke(self, context, event):
        self._start_x = event.mouse_x
        self._start_width = self.width
        self._bevel = self._create(context)
        self._status(context)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _status(self, context):
        context.workspace.status_text_set(
            "Bevel  |  drag: width %.3f  ·  wheel: segments %d  ·  "
            "Enter/Left confirm  ·  Esc cancel" % (self.width, self.segments))

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            delta = (event.mouse_x - self._start_x) * 0.0015
            self.width = max(0.0, self._start_width + delta)
            self._bevel.width = self.width
            self._status(context)

        elif event.type == 'WHEELUPMOUSE':
            self.segments = min(24, self.segments + 1)
            self._bevel.segments = self.segments
            self._status(context)
        elif event.type == 'WHEELDOWNMOUSE':
            self.segments = max(1, self.segments - 1)
            self._bevel.segments = self.segments
            self._status(context)

        elif event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'} and \
                event.value == 'PRESS':
            context.workspace.status_text_set(None)
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._remove_added(context)
            context.workspace.status_text_set(None)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}


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


class HARDFLOW_OT_clean(Operator):
    bl_idname = "object.hardflow_clean"
    bl_label = "Hardflow Clean"
    bl_description = ("Mesh cleanup: weld overlapping vertices, merge coplanar "
                      "faces, delete stray geometry (Hard Ops clean)")
    bl_options = {'REGISTER', 'UNDO'}

    merge_dist: FloatProperty(name="Merge Distance", default=0.0001,
                              min=0.0, soft_max=0.01, precision=5)
    dissolve_deg: FloatProperty(name="Dissolve Angle (deg)", default=5.0,
                                min=0.0, max=80.0)
    remove_loose: BoolProperty(name="Remove Loose", default=True)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH'

    def execute(self, context):
        from math import radians
        before = len(context.active_object.data.vertices)
        geometry.cleanup_mesh(
            context.active_object,
            merge_dist=self.merge_dist,
            dissolve_angle=radians(self.dissolve_deg),
            remove_loose=self.remove_loose,
        )
        after = len(context.active_object.data.vertices)
        self.report({'INFO'}, "Clean: %d -> %d vertex" % (before, after))
        return {'FINISHED'}


class HARDFLOW_OT_symmetrize(Operator):
    bl_idname = "object.hardflow_symmetrize"
    bl_label = "Hardflow Symmetrize"
    bl_description = ("Symmetrize the mesh: keep one side and mirror it onto the "
                      "other across the object-local axis (Hard Ops symmetrize)")
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        name="Direction",
        items=[('+X', "+X to -X", ""), ('-X', "-X to +X", ""),
               ('+Y', "+Y to -Y", ""), ('-Y', "-Y to +Y", ""),
               ('+Z', "+Z to -Z", ""), ('-Z', "-Z to +Z", "")],
        default='+X',
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')

    def execute(self, context):
        try:
            geometry.symmetrize_mesh(context.active_object, self.direction)
        except Exception as ex:  # noqa: BLE001
            self.report({'ERROR'}, "Symmetrize failed: %s" % ex)
            return {'CANCELLED'}
        return {'FINISHED'}


class HARDFLOW_OT_sharpen(Operator):
    bl_idname = "object.hardflow_sharpen"
    bl_label = "Hardflow Sharpen"
    bl_description = ("Mark sharp edges by angle and clean up shading with a "
                      "Weighted Normal modifier; optional angle-limited bevel "
                      "(Hard Ops SSharp)")
    bl_options = {'REGISTER', 'UNDO'}

    preset: EnumProperty(
        name="Preset",
        description="Hard Ops sharpen tier: how the sharp edges are weighted",
        items=[
            ('WN', "Weighted Normal", "Sharp + weighted normal only"),
            ('SSHARP', "SSharp", "Sharp + bevel weight + angle-limited bevel"),
            ('CSHARP', "CSharp", "Sharp + crease (for Subdivision)"),
            ('CUSTOM', "Custom", "Use the fields below directly"),
        ],
        default='WN',
    )
    angle_deg: FloatProperty(name="Sharp Angle", default=30.0, min=0.0, max=180.0)
    add_bevel: BoolProperty(
        name="Add Bevel", default=False,
        description="Also add a small angle-limited bevel on the sharp edges")
    bevel_width: FloatProperty(name="Bevel Width", default=0.01,
                               min=0.0, soft_max=0.2)
    weighted_normal: BoolProperty(name="Weighted Normal", default=True)
    bevel_weight: FloatProperty(name="Bevel Weight", default=0.0, min=0.0, max=1.0)
    crease: FloatProperty(name="Crease", default=0.0, min=0.0, max=1.0)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')

    def execute(self, context):
        obj = context.active_object
        # A named preset overrides the individual fields (CUSTOM keeps them).
        p = geometry.SHARPEN_PRESETS.get(self.preset)
        if p is not None:
            self.bevel_weight = p['bevel_weight']
            self.crease = p['crease']
            self.add_bevel = p['add_bevel']
            self.weighted_normal = p['weighted_normal']

        n = geometry.mark_sharp_by_angle(obj, radians(self.angle_deg))
        if self.bevel_weight != 0.0 or self.crease != 0.0:
            geometry.set_sharp_edge_weights(obj, self.bevel_weight, self.crease)

        if self.add_bevel and "HF_SharpenBevel" not in obj.modifiers:
            bev = obj.modifiers.new("HF_SharpenBevel", 'BEVEL')
            bev.width = self.bevel_width
            bev.segments = 2
            # A bevel weight tier limits the bevel to the weighted edges.
            if self.bevel_weight > 0.0:
                bev.limit_method = 'WEIGHT'
            else:
                bev.limit_method = 'ANGLE'
                bev.angle_limit = radians(self.angle_deg)
            bev.harden_normals = True
            bev.use_clamp_overlap = True
        if self.weighted_normal and "HF_WeightedNormal" not in obj.modifiers:
            wn = obj.modifiers.new("HF_WeightedNormal", 'WEIGHTED_NORMAL')
            wn.keep_sharp = True

        self.report({'INFO'}, "Sharpen (%s): %d sharp edge(s)" % (self.preset, n))
        return {'FINISHED'}
