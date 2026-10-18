# Cage-based high-to-low baking.
#
# The cage is the point. Baking with a plain ray distance makes the rays fan
# out from the low poly's own normals, which on a hard-surface model means
# they diverge exactly at the bevelled corners where you most need them
# parallel -- that is where skewed, smeared normal maps come from. A cage is a
# copy of the low poly pushed outward, and the rays run from the cage inward
# along ITS interpolated normals, so they stay coherent across a corner.
#
# Hardflow's contribution is everything around the bake button: building a cage
# that actually encloses the high poly, pairing low with high by the naming
# convention every game pipeline already uses, naming the output after the
# asset rather than the object, and putting the render engine back afterwards.
# Those decisions are pure in core/bake.py; this file does the bmesh and bpy.
#
# Baking needs Cycles -- measured in Blender 5.2.2: EEVEE's baker is gone
# ("Current render engine does not support baking"), so the engine is switched
# for the bake and restored in a finally.
import bmesh
import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty

from ..core import bake as bake_core, boolean
from ..preferences import get_prefs

_BAKE_TYPE_ITEMS = (
    ('NORMAL', "Normal", "Tangent-space normal map -- the reason to bake"),
    ('AO', "Ambient Occlusion", "Contact shadow from the high poly"),
    ('ROUGHNESS', "Roughness", "Roughness from the high poly's materials"),
    ('COMBINED', "Combined", "Full shaded result"),
)


def object_size(obj):
    """World-space bounding-box size, which is what the cage standoff is
    reckoned from."""
    return tuple(obj.dimensions)


def fit_cage(context, low, highs, extrusion):
    """Build the cage and make sure it really encloses the high poly.

    The standoff is derived from a per-axis overhang, but the push runs along
    the vertex normal -- diagonal on a box corner -- so the cage grows by less
    than the standoff on each axis and can end up inside the high poly, which
    bakes holes. Measure what the first push achieved and, if it falls short,
    scale once and rebuild. Deterministic: at most two builds."""
    cage = build_cage(context, low, extrusion)
    if not highs:
        return cage, extrusion
    needed = (max(o.dimensions[0] for o in highs),
              max(o.dimensions[1] for o in highs),
              max(o.dimensions[2] for o in highs))
    fixed = bake_core.corrected_extrusion(extrusion, low.dimensions,
                                          cage.dimensions, needed)
    if fixed > extrusion:
        cage = build_cage(context, low, fixed)
        return cage, fixed
    return cage, extrusion


def build_cage(context, low, extrusion):
    """Create (or refresh) the cage for `low`: a copy pushed `extrusion` out
    along its vertex normals, shown as a wire and parked in Hardflow's hidden
    helper collection so it never clutters the outliner or renders.

    Pushing along the SMOOTH vertex normal on purpose -- a cage built on face
    normals splits at every hard edge, which is the very place the cage exists
    to keep rays coherent."""
    name = bake_core.cage_name(low.name)
    cage = bpy.data.objects.get(name)
    if cage is not None and cage.type != 'MESH':
        cage = None
    mesh = low.data.copy()
    mesh.name = name
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.normal_update()
        for v in bm.verts:
            v.co += v.normal * extrusion
        bm.to_mesh(mesh)
    finally:
        bm.free()
    if cage is None:
        cage = bpy.data.objects.new(name, mesh)
        boolean.helper_collection(context).objects.link(cage)
    else:
        old = cage.data
        cage.data = mesh
        if old.users == 0:
            bpy.data.meshes.remove(old)
    cage.matrix_world = low.matrix_world.copy()
    cage.display_type = 'WIRE'
    cage.hide_render = True
    return cage


class HARDFLOW_OT_make_cage(Operator):
    bl_idname = "object.hardflow_make_cage"
    bl_label = "Build Bake Cage"
    bl_description = ("Build a bake cage from the active low poly: a copy "
                      "pushed out along its normals, so the bake's rays stay "
                      "coherent across hard edges instead of fanning out")
    bl_options = {'REGISTER', 'UNDO'}

    extrusion: FloatProperty(
        name="Standoff", subtype='DISTANCE', default=0.0, min=0.0,
        soft_max=1.0,
        description="How far the cage stands off the low poly. 0 = work it "
                    "out from how far the high poly sticks out",
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (context.mode == 'OBJECT' and obj is not None
                and obj.type == 'MESH')

    def execute(self, context):
        low = context.active_object
        highs = [o for o in context.selected_objects
                 if o.type == 'MESH' and o is not low]
        extrusion = self.extrusion
        if extrusion <= 0.0:
            high_size = (max((o.dimensions[0] for o in highs), default=0.0),
                         max((o.dimensions[1] for o in highs), default=0.0),
                         max((o.dimensions[2] for o in highs), default=0.0))
            extrusion = bake_core.suggested_extrusion(object_size(low),
                                                      high_size)
        cage, extrusion = fit_cage(context, low, highs, extrusion)
        self.report({'INFO'}, "Cage '%s' at %.4f m standoff"
                    % (cage.name, extrusion))
        return {'FINISHED'}


class HARDFLOW_OT_bake_highlow(Operator):
    bl_idname = "object.hardflow_bake_highlow"
    bl_label = "Bake High to Low"
    bl_description = ("Bake the selected high poly onto the active low poly "
                      "through a cage. Needs the low poly unwrapped -- the "
                      "HF Output > Game-Ready panel's Unwrap does that)")
    bl_options = {'REGISTER', 'UNDO'}

    bake_type: EnumProperty(name="Type", items=_BAKE_TYPE_ITEMS,
                            default='NORMAL')
    size: IntProperty(name="Resolution", default=1024, min=16, max=8192)
    extrusion: FloatProperty(
        name="Cage Standoff", subtype='DISTANCE', default=0.0, min=0.0,
        soft_max=1.0,
        description="0 = work it out from how far the high poly sticks out")
    use_cage: BoolProperty(
        name="Use Cage", default=True,
        description="Bake through a cage. Turning this off falls back to a "
                    "plain ray distance, which skews the rays at hard edges")
    margin_px: IntProperty(
        name="Margin (px)", default=4, min=0, max=64,
        description="Bleed the result this far past each island, so mip-maps "
                    "do not pull the background in")
    samples: IntProperty(
        name="Samples", default=8, min=1, max=512,
        description="Cycles samples. A normal bake needs very few; AO wants "
                    "more")

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (context.mode == 'OBJECT' and obj is not None
                and obj.type == 'MESH'
                and any(o.type == 'MESH' and o is not obj
                        for o in context.selected_objects))

    def execute(self, context):
        low = context.active_object
        highs = [o for o in context.selected_objects
                 if o.type == 'MESH' and o is not low]
        if not highs:
            self.report({'ERROR'}, "Select the high poly, then the low poly "
                                   "last (it must be active)")
            return {'CANCELLED'}
        if not low.data.uv_layers:
            self.report({'ERROR'},
                        "'%s' has no UV map -- unwrap it first "
                        "(HF Output > Game-Ready > Hard-Surface Unwrap)"
                        % low.name)
            return {'CANCELLED'}

        image = self._target_image(low)
        try:
            self._ensure_material(low, image)
            for high in highs:
                self._ensure_any_material(high)
        except Exception as ex:  # noqa: BLE001
            self.report({'ERROR'}, "Could not prepare materials: %s" % ex)
            return {'CANCELLED'}

        extrusion = self.extrusion
        if extrusion <= 0.0:
            high_size = (max(o.dimensions[0] for o in highs),
                         max(o.dimensions[1] for o in highs),
                         max(o.dimensions[2] for o in highs))
            extrusion = bake_core.suggested_extrusion(object_size(low),
                                                      high_size)
        cage = None
        if self.use_cage:
            cage, extrusion = fit_cage(context, low, highs, extrusion)

        try:
            self._bake(context, low, highs, cage, extrusion)
        except RuntimeError as ex:
            self.report({'ERROR'}, "Bake failed: %s" % ex)
            return {'CANCELLED'}

        # Deliberately NOT packed. Packing freezes the image at its current
        # resolution -- the packed buffer is restored over any later scale --
        # so a re-bake at a different size would silently keep the old one.
        # Blender's own baker leaves the result in memory too; save it from
        # the Image editor, or save the .blend.
        self.report({'INFO'}, "Baked %s -> '%s' (%d px, %.4f m cage) -- "
                              "unsaved, save the image or the .blend"
                    % (self.bake_type, image.name, self.size, extrusion))
        return {'FINISHED'}

    # --- setup ------------------------------------------------------------

    def _target_image(self, low):
        """Get or create the output image, named after the ASSET. Reused and
        resized in place, so re-baking does not litter image.001, .002..."""
        name = bake_core.image_name(low.name, self.bake_type)
        data = bake_core.is_data(self.bake_type)
        img = bpy.data.images.get(name)
        if img is None:
            img = bpy.data.images.new(name, self.size, self.size,
                                      alpha=False, is_data=data)
        elif tuple(img.size) != (self.size, self.size):
            # A bpy.data.images.new() image is GENERATED, so its size is
            # governed by generated_width/height as well as the buffer.
            # (Setting those on a non-GENERATED image instead REVERTS the
            # size, hence the guard.)
            if img.source == 'GENERATED':
                img.generated_width = self.size
                img.generated_height = self.size
            img.scale(self.size, self.size)
        # A normal / AO / roughness map read through sRGB is silently wrong.
        img.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
        return img

    @staticmethod
    def _ensure_any_material(obj):
        """The high poly needs a material or there is nothing to read from."""
        if obj.data.materials:
            return
        mat = bpy.data.materials.new("%s_mat" % obj.name)
        mat.use_nodes = True
        obj.data.materials.append(mat)

    def _ensure_material(self, low, image):
        """The low poly needs a material whose ACTIVE node is the target image
        texture -- that is how Blender's baker chooses where to write."""
        if not low.data.materials:
            mat = bpy.data.materials.new("%s_mat" % low.name)
            mat.use_nodes = True
            low.data.materials.append(mat)
        for slot in low.material_slots:
            mat = slot.material
            if mat is None:
                continue
            if not mat.use_nodes:
                mat.use_nodes = True
            nodes = mat.node_tree.nodes
            node = next((n for n in nodes if n.type == 'TEX_IMAGE'
                         and n.image is image), None)
            if node is None:
                node = nodes.new('ShaderNodeTexImage')
                node.image = image
                node.location = (-400, 400)
            node.select = True
            nodes.active = node

    # --- the bake ---------------------------------------------------------

    def _bake(self, context, low, highs, cage, extrusion):
        """Drive Blender's baker, then put every setting back.

        The engine switch is not optional: measured on Blender 5.2.2, EEVEE
        answers "Current render engine does not support baking"."""
        scene = context.scene
        render = scene.render
        settings = render.bake
        saved = {
            'engine': render.engine,
            'selected_to_active': settings.use_selected_to_active,
            'use_cage': settings.use_cage,
            'cage_object': settings.cage_object,
            'cage_extrusion': settings.cage_extrusion,
            'margin': settings.margin,
            'use_clear': settings.use_clear,
        }
        samples = getattr(getattr(scene, "cycles", None), "samples", None)
        try:
            try:
                render.engine = 'CYCLES'
            except TypeError:
                raise RuntimeError(
                    "Cycles is not available, and baking needs it")
            if getattr(scene, "cycles", None) is not None:
                scene.cycles.samples = self.samples
            settings.use_selected_to_active = True
            settings.use_cage = bool(cage)
            settings.cage_object = cage
            settings.cage_extrusion = 0.0 if cage else extrusion
            settings.margin = self.margin_px
            settings.use_clear = True

            for obj in context.selected_objects:
                obj.select_set(False)
            for high in highs:
                high.select_set(True)
            low.select_set(True)
            context.view_layer.objects.active = low
            bpy.ops.object.bake(type=bake_core.blender_type(self.bake_type))
        finally:
            render.engine = saved['engine']
            settings.use_selected_to_active = saved['selected_to_active']
            settings.use_cage = saved['use_cage']
            settings.cage_object = saved['cage_object']
            settings.cage_extrusion = saved['cage_extrusion']
            settings.margin = saved['margin']
            settings.use_clear = saved['use_clear']
            if samples is not None:
                scene.cycles.samples = samples

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "bake_type")
        col.prop(self, "size")
        col.prop(self, "use_cage")
        sub = col.row()
        sub.enabled = True
        sub.prop(self, "extrusion")
        col.prop(self, "margin_px")
        col.prop(self, "samples")
