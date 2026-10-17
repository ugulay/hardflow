# Cut-aware seams + hard-surface unwrap.
#
# The idea: on a boolean model the seams belong on the cut boundaries, and
# Hardflow already knows where those are. Smart Sharpen marks every hard edge
# a cut produced as sharp and bevel-weighted (core/geometry.mark_sharp_edges),
# so reading those marks back is not inference from geometry -- it is the
# modelling history, written into the mesh by the tool that did the cutting.
# Edges with no mark fall back to the dihedral-angle rule, so this also works
# on a mesh that never went through Smart Sharpen.
#
# Layer split: every per-edge decision is pure in core/unwrap.py; this file
# measures the angle with bmesh (the same edge.calc_face_angle that
# mark_sharp_edges uses, so shading and UVs agree by construction), writes the
# seam flags, and drives Blender's own unwrap/pack -- which are far better than
# anything worth reimplementing here.
import bmesh
import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from math import radians

from ..core import unwrap as unwrap_core
from ..preferences import get_prefs


def edge_data(bm):
    """Per-edge measurements for the pure seam rule, read off a bmesh.

    `calc_face_angle` raises on an edge that is not between exactly two faces,
    which is precisely the boundary / non-manifold case the rule handles
    separately -- so those are flagged rather than measured."""
    layer = bm.edges.layers.bevel_weight.verify() \
        if hasattr(bm.edges.layers, "bevel_weight") else None
    out = []
    for e in bm.edges:
        faces = len(e.link_faces)
        angle = 0.0
        if faces == 2:
            try:
                angle = e.calc_face_angle()
            except (ValueError, RuntimeError):
                angle = 0.0
        out.append({
            'key': e.index,
            'angle': angle,
            'sharp': not e.smooth,
            'bevel_weight': (e[layer] if layer is not None else 0.0),
            'boundary': faces == 1,
            'non_manifold': faces > 2,
        })
    return out


def mark_seams(obj, clear=True, **rules):
    """Mark UV seams on `obj` from the pure rule. Returns ``(keys, counts)``.

    Object Mode, bmesh only -- no bpy.ops, so it is safe inside a batch."""
    me = obj.data
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bm.edges.ensure_lookup_table()
        edges = edge_data(bm)
        keys, counts = unwrap_core.seam_edges(edges, **rules)
        wanted = set(keys)
        for e in bm.edges:
            if clear or e.index in wanted:
                e.seam = e.index in wanted
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    return keys, counts


class _SeamRules:
    """The seam-rule properties, shared by both operators so Mark Seams and
    Unwrap cannot drift apart."""

    angle_limit: FloatProperty(
        name="Angle", subtype='ANGLE',
        description="Unmarked edges this sharp become seams too, so the rule "
                    "still works on a mesh that never went through Smart "
                    "Sharpen",
        default=radians(60.0), min=radians(1.0), max=radians(180.0),
    )
    use_sharp: BoolProperty(
        name="From Sharp Edges", default=True,
        description="Seam along edges marked sharp -- on a Hardflow model "
                    "that is every boolean cut, because Smart Sharpen marked "
                    "them while cutting")
    use_bevel_weight: BoolProperty(
        name="From Bevel Weight", default=True,
        description="Seam along bevel-weighted edges (also set by Smart "
                    "Sharpen on a cut)")
    use_angle: BoolProperty(
        name="From Angle", default=True,
        description="Fall back to the dihedral angle on unmarked edges. Turn "
                    "off for a purely cut-aware unwrap: only edges Hardflow "
                    "marked become seams")
    clear_existing: BoolProperty(
        name="Replace Seams", default=True,
        description="Clear the existing seams first. Turn off to add to them")

    def _rules(self):
        return dict(angle_limit=self.angle_limit, use_sharp=self.use_sharp,
                    use_bevel_weight=self.use_bevel_weight,
                    use_angle=self.use_angle)

    def _targets(self, context):
        return [o for o in context.selected_objects if o.type == 'MESH']


class HARDFLOW_OT_mark_seams(_SeamRules, Operator):
    bl_idname = "mesh.hardflow_mark_seams"
    bl_label = "Mark Cut Seams"
    bl_description = ("Mark UV seams along the hard edges -- on a Hardflow "
                      "model that means along the boolean cuts, because Smart "
                      "Sharpen marked them while cutting. Unmarked edges fall "
                      "back to the dihedral angle")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'OBJECT'
                and any(o.type == 'MESH' for o in context.selected_objects))

    def execute(self, context):
        total = {}
        done = 0
        for obj in self._targets(context):
            try:
                _keys, counts = mark_seams(obj, clear=self.clear_existing,
                                           **self._rules())
            except Exception as ex:  # noqa: BLE001 -- one bad mesh can't abort
                self.report({'WARNING'},
                            "Seams failed on %s: %s" % (obj.name, ex))
                continue
            for k, v in counts.items():
                total[k] = total.get(k, 0) + v
            done += 1
        if not done:
            self.report({'ERROR'}, "Mark Seams: no mesh processed")
            return {'CANCELLED'}
        self.report({'INFO'}, unwrap_core.describe(total))
        return {'FINISHED'}

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "use_sharp")
        col.prop(self, "use_bevel_weight")
        col.prop(self, "use_angle")
        sub = col.row()
        sub.enabled = self.use_angle
        sub.prop(self, "angle_limit")
        col.prop(self, "clear_existing")


class HARDFLOW_OT_unwrap(_SeamRules, Operator):
    bl_idname = "mesh.hardflow_unwrap"
    bl_label = "Hard-Surface Unwrap"
    bl_description = ("Mark seams along the cuts, unwrap, and pack the islands "
                      "with a pixel-accurate margin -- the whole hard-surface "
                      "UV pass in one step")
    bl_options = {'REGISTER', 'UNDO'}

    method: EnumProperty(
        name="Method",
        items=(('ANGLE_BASED', "Angle Based",
                "Blender's angle-based unwrap: fewer, cleaner islands -- the "
                "right default for panelled hard-surface forms"),
               ('CONFORMAL', "Conformal",
                "Less distortion on organic shapes, more stretch on flats")),
        default='ANGLE_BASED',
    )
    seams: BoolProperty(
        name="Mark Seams First", default=True,
        description="Re-mark the cut seams before unwrapping. Turn off to "
                    "unwrap along the seams already on the mesh")
    pack: BoolProperty(
        name="Pack Islands", default=True,
        description="Pack the islands into 0-1 after unwrapping")
    average_scale: BoolProperty(
        name="Average Island Scale", default=True,
        description="Even out texel density across islands before packing, so "
                    "one face is not twice the resolution of its neighbour")
    padding_px: IntProperty(
        name="Padding (px)", default=4, min=0, soft_max=64,
        description="Island padding in PIXELS of the target texture -- what "
                    "actually stops bleeding in a bake. Converted to Blender's "
                    "UV-space margin using the texture size below")

    @classmethod
    def poll(cls, context):
        return (context.mode == 'OBJECT'
                and any(o.type == 'MESH' for o in context.selected_objects))

    def execute(self, context):
        prefs = get_prefs(context)
        targets = self._targets(context)
        if not targets:
            self.report({'ERROR'}, "Unwrap: select a mesh")
            return {'CANCELLED'}

        total = {}
        if self.seams:
            for obj in targets:
                try:
                    _k, counts = mark_seams(obj, clear=self.clear_existing,
                                            **self._rules())
                except Exception as ex:  # noqa: BLE001
                    self.report({'WARNING'},
                                "Seams failed on %s: %s" % (obj.name, ex))
                    continue
                for k, v in counts.items():
                    total[k] = total.get(k, 0) + v

        margin = unwrap_core.pack_margin(self.padding_px,
                                         prefs.gameready_texture_size)
        active = context.view_layer.objects.active
        try:
            self._unwrap(context, targets, margin)
        except Exception as ex:  # noqa: BLE001
            self.report({'ERROR'}, "Unwrap failed: %s" % ex)
            return {'CANCELLED'}
        finally:
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            context.view_layer.objects.active = active

        self.report({'INFO'}, "Unwrapped %d object(s) -- %s, %d px padding"
                    % (len(targets), unwrap_core.describe(total),
                       self.padding_px))
        return {'FINISHED'}

    def _unwrap(self, context, targets, margin):
        """Blender's own unwrap/pack, driven over the selection in one Edit
        session. Everything here is a bpy.ops call on purpose: the unwrapper
        and the packer are far better than anything worth reimplementing."""
        for obj in targets:
            if not obj.data.uv_layers:
                obj.data.uv_layers.new(name="UVMap")
        context.view_layer.objects.active = targets[0]
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.unwrap(method=self.method, margin=margin)
        if self.average_scale:
            bpy.ops.uv.select_all(action='SELECT')
            bpy.ops.uv.average_islands_scale()
        if self.pack:
            bpy.ops.uv.select_all(action='SELECT')
            bpy.ops.uv.pack_islands(margin=margin)
        bpy.ops.object.mode_set(mode='OBJECT')

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "method")
        col.prop(self, "seams")
        if self.seams:
            box = col.box().column()
            box.prop(self, "use_sharp")
            box.prop(self, "use_bevel_weight")
            box.prop(self, "use_angle")
            sub = box.row()
            sub.enabled = self.use_angle
            sub.prop(self, "angle_limit")
            box.prop(self, "clear_existing")
        col.prop(self, "average_scale")
        col.prop(self, "pack")
        col.prop(self, "padding_px")
