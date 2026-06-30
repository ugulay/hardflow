# Decal logic: build a thin plane, orient it to a surface,
# stick it down with a SHRINKWRAP (PROJECT) modifier + parent, assign a
# type-specific material, and gather it in a "Hardflow Decals" collection.
#
# This module uses bpy.data / bmesh / mathutils but NEVER bpy.ops / gpu / blf,
# keeping with the core layer rule. The pure orientation math lives in
# core/decal_math.py so it can be tested without Blender.
import bpy
import bmesh
from mathutils import Matrix, Vector

from . import decal_math


DECAL_COLLECTION = "Hardflow Decals"

# (id, label, description) -- shared by the operator enum and the panel.
DECAL_TYPES = (
    ('INFO', "Info", "Logo / text / warning mark (emissive accent)"),
    ('PANEL', "Panel", "Panel line / seam (dark recessed look)"),
    ('SUBSET', "Subset", "Masked sub-material patch"),
)


def decal_collection(context):
    """Get/create the collection that gathers decals (mirrors
    core/boolean.py cutter_collection)."""
    coll = bpy.data.collections.get(DECAL_COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(DECAL_COLLECTION)
        context.scene.collection.children.link(coll)
    return coll


def build_decal_mesh(width, height, name="hf_decal", uv_rect=(0.0, 0.0, 1.0, 1.0)):
    """A single UV-mapped quad centred on the local origin, lying in the local
    XY plane (so local +Z is the decal's facing/projection axis). uv_rect
    (u0,v0,u1,v1) maps the quad to a sub-region of the image -- (0,0,1,1) is the
    whole image; a trim-sheet cell (see core/atlas.py) is a sub-rect."""
    hw, hh = width * 0.5, height * 0.5
    u0, v0, u1, v1 = uv_rect
    bm = bmesh.new()
    v00 = bm.verts.new((-hw, -hh, 0.0))
    v10 = bm.verts.new((hw, -hh, 0.0))
    v11 = bm.verts.new((hw, hh, 0.0))
    v01 = bm.verts.new((-hw, hh, 0.0))
    face = bm.faces.new((v00, v10, v11, v01))
    uv = bm.loops.layers.uv.new("UVMap")
    coords = {v00: (u0, v0), v10: (u1, v0), v11: (u1, v1), v01: (u0, v1)}
    for loop in face.loops:
        loop[uv].uv = coords[loop.vert]
    bmesh.ops.recalc_face_normals(bm, faces=[face])
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def decal_matrix(location, normal, tangent, scale=1.0):
    """Build a world matrix that places a decal at location, with local +Z along
    the surface normal and local +Y along tangent (re-orthogonalized). Uses the
    pure core basis."""
    x, y, z = decal_math.orientation_basis(tuple(normal), tuple(tangent))
    basis = Matrix((
        (x[0] * scale, y[0] * scale, z[0] * scale, location[0]),
        (x[1] * scale, y[1] * scale, z[1] * scale, location[1]),
        (x[2] * scale, y[2] * scale, z[2] * scale, location[2]),
        (0.0, 0.0, 0.0, 1.0),
    ))
    return basis


def adaptive_decal_offset(target):
    """A surface hover gap scaled to the target's size: ~0.05% of its average
    dimension, floored at 0.1 mm. A fixed 1 mm z-fights on a large mesh and looks
    like a thick gap on a small one; scaling keeps the decal flush at any scale."""
    dims = [d for d in target.dimensions if d > 1e-6]
    size = (sum(dims) / len(dims)) if dims else 0.1
    return max(1e-4, size * 0.0005)


def add_shrinkwrap(decal, target, offset=None):
    """Stick the decal to the target surface: PROJECT the plane down its local
    -Z onto the target, hovering just above the surface to avoid z-fighting.
    `offset=None` picks a size-proportional gap (adaptive_decal_offset)."""
    if offset is None:
        offset = adaptive_decal_offset(target)
    mod = decal.modifiers.new("HF_Shrinkwrap", 'SHRINKWRAP')
    mod.wrap_method = 'PROJECT'
    mod.wrap_mode = 'ABOVE_SURFACE'
    mod.use_negative_direction = True
    mod.use_positive_direction = False
    mod.use_project_z = True
    mod.target = target
    mod.offset = offset
    return mod


DECAL_NODE_GROUP = "HF_DecalShader"

# Per-type tuning of the shared node group's inputs. v0.9's image library will
# plug textures into the same group sockets; here we just set flat defaults.
_DECAL_PRESETS = {
    'INFO': {"Base Color": (0.9, 0.9, 0.9, 1.0),
             "Emission Color": (0.1, 0.8, 1.0, 1.0),
             "Emission Strength": 1.5},
    'PANEL': {"Base Color": (0.02, 0.02, 0.02, 1.0),
              "Metallic": 0.8, "Roughness": 0.35, "Depth": 1.0},
    'SUBSET': {"Base Color": (0.8, 0.25, 0.1, 1.0),
               "Roughness": 0.5},
}


def _color_io(node):
    """The RGBA input/output sockets of a node, found by socket type rather than
    index. ShaderNodeMix exposes Float, Vector and Color variants of the same
    A/B/Result names, so name- or index-based access is fragile; type is stable."""
    ins = [s for s in node.inputs if s.type == 'RGBA']
    out = next((s for s in node.outputs if s.type == 'RGBA'), None)
    return ins, out


def _link_if_present(links, source, node, input_name):
    """Link source into node.inputs[input_name] only if it exists (Blender 4.0
    renamed the Principled 'Emission' socket to 'Emission Color')."""
    if input_name in node.inputs:
        links.new(source, node.inputs[input_name])


def _decal_node_group():
    """Get/create the shared decal PBR shader node group. It exposes the standard
    decal channels (base color, metallic, roughness, AO, normal, emission, alpha)
    on a Group Input and wires them into a Principled BSDF, so per-type materials
    -- and the v0.9 image library -- just feed one shared graph. Plain Principled
    + a Mix node keeps it Eevee + Cycles compatible."""
    ng = bpy.data.node_groups.get(DECAL_NODE_GROUP)
    if ng is not None:
        return ng

    ng = bpy.data.node_groups.new(DECAL_NODE_GROUP, 'ShaderNodeTree')
    iface = ng.interface

    def _in(name, socket_type, default=None):
        sock = iface.new_socket(name=name, in_out='INPUT', socket_type=socket_type)
        if default is not None:
            sock.default_value = default
        return sock

    _in("Base Color", 'NodeSocketColor', (0.8, 0.8, 0.8, 1.0))
    _in("Metallic", 'NodeSocketFloat', 0.0)
    _in("Roughness", 'NodeSocketFloat', 0.5)
    _in("AO", 'NodeSocketFloat', 1.0)
    _in("Normal", 'NodeSocketVector')
    _in("Height", 'NodeSocketFloat', 0.0)
    _in("Depth", 'NodeSocketFloat', 0.0)
    _in("Emission Color", 'NodeSocketColor', (0.0, 0.0, 0.0, 1.0))
    _in("Emission Strength", 'NodeSocketFloat', 0.0)
    _in("Alpha", 'NodeSocketFloat', 1.0)
    iface.new_socket(name="BSDF", in_out='OUTPUT', socket_type='NodeSocketShader')

    nodes, links = ng.nodes, ng.links
    g_in = nodes.new('NodeGroupInput')
    g_in.location = (-600, 0)
    g_out = nodes.new('NodeGroupOutput')
    g_out.location = (300, 0)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)

    # AO * Base Color. A float AO auto-converts to greyscale on the color socket.
    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.location = (-300, 120)
    mix.inputs[0].default_value = 1.0           # Factor (index 0) = full multiply
    color_ins, color_out = _color_io(mix)
    links.new(g_in.outputs["Base Color"], color_ins[0])
    links.new(g_in.outputs["AO"], color_ins[1])

    links.new(color_out, bsdf.inputs["Base Color"])
    links.new(g_in.outputs["Metallic"], bsdf.inputs["Metallic"])
    links.new(g_in.outputs["Roughness"], bsdf.inputs["Roughness"])
    links.new(g_in.outputs["Alpha"], bsdf.inputs["Alpha"])

    # Fake depth (v0.8 "parallax"): a Height channel drives a Bump node that
    # perturbs the normal, recessing panel lines. Depth = bump strength; with the
    # default Depth=0 (or a flat Height) the bump passes the base normal through,
    # so this is a no-op until a height map is plugged in (v0.9 image library).
    # View-dependent parallax-occlusion UV offset also lands there (needs a UV-
    # sampled height texture to act on).
    bump = nodes.new('ShaderNodeBump')
    bump.location = (-300, -220)
    links.new(g_in.outputs["Height"], bump.inputs["Height"])
    links.new(g_in.outputs["Depth"], bump.inputs["Strength"])
    links.new(g_in.outputs["Normal"], bump.inputs["Normal"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    _link_if_present(links, g_in.outputs["Emission Color"], bsdf, "Emission Color")
    _link_if_present(links, g_in.outputs["Emission Strength"], bsdf,
                     "Emission Strength")
    links.new(bsdf.outputs["BSDF"], g_out.inputs["BSDF"])
    return ng


def _new_decal_material(name):
    """Create a node-based material wired around the shared HF_DecalShader group,
    returning (material, group_node, node_tree). The stock Principled BSDF is
    replaced by an instance of our group, and alpha blending is enabled. Shared
    by the per-type templates and the v0.9 image decals; callers just feed the
    group's inputs."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    # Alpha blending: EEVEE Next (Blender 4.2+) replaced `blend_method` with
    # `surface_render_method`; the legacy attribute was removed. Set whichever
    # the running build exposes.
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = 'BLENDED'
    elif hasattr(mat, "blend_method"):
        mat.blend_method = 'BLEND'

    tree = mat.node_tree
    # Replace the stock Principled BSDF with our shared decal node group.
    out = next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL'), None)
    for node in list(tree.nodes):
        if node.type == 'BSDF_PRINCIPLED':
            tree.nodes.remove(node)
    if out is None:
        out = tree.nodes.new('ShaderNodeOutputMaterial')
    out.location = (300, 0)

    group = tree.nodes.new('ShaderNodeGroup')
    group.node_tree = _decal_node_group()
    group.location = (0, 0)
    tree.links.new(group.outputs["BSDF"], out.inputs["Surface"])
    return mat, group, tree


def decal_material(decal_type):
    """Get/create a shared material template per decal type. Each material
    instances the shared HF_DecalShader node group (v0.8 PBR graph) and tunes its
    inputs, so the graph reads well in both Eevee and Cycles. v0.9 image decals
    plug textures into the very same group sockets (see image_decal_material)."""
    name = "HF_Decal_%s" % decal_type.capitalize()
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat

    mat, group, _tree = _new_decal_material(name)
    for key, value in _DECAL_PRESETS.get(decal_type, {}).items():
        if key in group.inputs:
            group.inputs[key].default_value = value
    return mat


def image_decal_material(image):
    """Get/create a material that drives the shared HF_DecalShader group from an
    image: the image's Color feeds Base Color and its Alpha feeds Alpha, so a PNG
    cut-out (logo, warning mark) reads as a transparent decal on the surface. One
    material is cached per image data-block."""
    name = "HF_Decal_Img_%s" % image.name
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat

    mat, group, tree = _new_decal_material(name)
    tex = tree.nodes.new('ShaderNodeTexImage')
    tex.image = image
    tex.location = (-320, 0)
    tree.links.new(tex.outputs["Color"], group.inputs["Base Color"])
    tree.links.new(tex.outputs["Alpha"], group.inputs["Alpha"])
    return mat


def ensure_material(obj, name_hint="HF_Baked"):
    """Return obj's active node-based material, creating one if it has none. The
    bake target needs a material to host the destination image node."""
    mat = obj.active_material
    if mat is None:
        mat = bpy.data.materials.new("%s_%s" % (name_hint, obj.name))
        mat.use_nodes = True
        obj.data.materials.append(mat)
    elif not mat.use_nodes:
        mat.use_nodes = True
    return mat


def bake_image(name, size, is_data=False):
    """Get/create a square image to bake into. Normal/data maps use the Non-Color
    space so values are not gamma-twisted."""
    img = bpy.data.images.get(name)
    if img is None:
        img = bpy.data.images.new(name, width=size, height=size, alpha=False)
    img.colorspace_settings.name = 'Non-Color' if is_data else 'sRGB'
    return img


def atlas_image(name, w, h):
    """Get/create a transparent RGBA image of exactly (w x h) to assemble a decal
    atlas into. If an image of that name exists at a different size it is replaced
    so a re-atlas never blits into a stale buffer."""
    img = bpy.data.images.get(name)
    if img is not None and tuple(img.size) != (w, h):
        bpy.data.images.remove(img)
        img = None
    if img is None:
        img = bpy.data.images.new(name, width=w, height=h, alpha=True)
    img.colorspace_settings.name = 'sRGB'
    return img


def bake_image_node(material, image):
    """Add (or reuse) an Image Texture node holding image and make it the sole
    active+selected node of the material -- Cycles writes the bake there."""
    tree = material.node_tree
    node = next((n for n in tree.nodes
                 if n.type == 'TEX_IMAGE' and n.image == image), None)
    if node is None:
        node = tree.nodes.new('ShaderNodeTexImage')
        node.image = image
        node.location = (-500, -350)
    tree.nodes.active = node
    # Compare by name, not `is`: bpy hands out a fresh Python wrapper per access,
    # so `other is node` can be False even for the same node -- which would leave
    # the bake-target node unselected and misdirect the Cycles bake. Node names
    # are unique within a node tree.
    for other in tree.nodes:
        other.select = (other.name == node.name)
    return node


def discard_bake_image(material, image, remove_node=True, remove_image=True):
    """Roll back bake_image_node after a *failed* bake so the failure does not
    leave an orphan image plus a dangling Image Texture node wired into the
    target material. Pass the flags that say what THIS bake call newly created
    (remove_node / remove_image) so a re-bake never deletes a prior good result.
    Safe to call when the datablocks are already gone."""
    if remove_node and material is not None and material.use_nodes:
        tree = material.node_tree
        for node in [n for n in tree.nodes
                     if n.type == 'TEX_IMAGE' and n.image == image]:
            tree.nodes.remove(node)
    if remove_image and image is not None and image.users == 0:
        bpy.data.images.remove(image)


def _assemble_decal(context, target, mesh, location, normal, tangent,
                    material, offset, tag):
    """Shared decal assembly: orient the quad to the surface, link it into the
    decal collection, give it the material, stick it down with a shrinkwrap, and
    parent it to the target so it follows the object. Returns the new object."""
    decal = bpy.data.objects.new("Hardflow_Decal", mesh)
    decal.matrix_world = decal_matrix(location, normal, tangent)

    decal_collection(context).objects.link(decal)
    decal.data.materials.append(material)
    add_shrinkwrap(decal, target, offset=offset)

    # follow the target when it moves, keeping the placed world pose
    decal.parent = target
    decal.matrix_parent_inverse = target.matrix_world.inverted_safe()

    decal.show_wire = False
    decal.hide_render = False
    decal["hf_decal_type"] = tag
    return decal


def make_decal(context, target, location, normal, tangent,
               width=0.2, height=0.2, decal_type='INFO', offset=None):
    """Create a type-template decal (Info/Panel/Subset) on the target surface and
    return it. The caller supplies the surface hit (location, normal) and a
    tangent (roll direction)."""
    mesh = build_decal_mesh(width, height)
    return _assemble_decal(context, target, mesh, location, normal, tangent,
                           decal_material(decal_type), offset, decal_type)


def make_image_decal(context, target, location, normal, tangent, image,
                     width=0.2, height=0.2, offset=None,
                     uv_rect=(0.0, 0.0, 1.0, 1.0)):
    """Create an image-driven decal (v0.9 library / 'decal from image') on the
    target surface and return it. The quad carries the image's color+alpha via
    image_decal_material; the caller usually sizes width/height to the image's
    aspect (see core/decal_image.aspect_size). uv_rect selects a sub-region of
    the image -- pass a trim-sheet cell (core/atlas.cell_rect) for a trim decal."""
    mesh = build_decal_mesh(width, height, uv_rect=uv_rect)
    decal = _assemble_decal(context, target, mesh, location, normal, tangent,
                            image_decal_material(image), offset, 'IMAGE')
    decal["hf_decal_image"] = image.name
    return decal


# --- Decal extras (v1.7) ------------------------------------------------


def _decal_group_node(decal_obj):
    """The HF_DecalShader group node of a decal's active material, or None."""
    mat = decal_obj.active_material
    if mat is None or not mat.use_nodes:
        return None
    return next((n for n in mat.node_tree.nodes
                 if n.type == 'GROUP' and n.node_tree
                 and n.node_tree.name == DECAL_NODE_GROUP), None)


def sample_material(obj):
    """Sample base color / metallic / roughness from obj's active material so a
    placed decal can be matched to the surface it sits on (v1.7 material match).
    Reads a Principled BSDF, falling back to an HF_DecalShader group. Returns a
    dict or None when there is nothing to sample."""
    mat = obj.active_material if obj is not None else None
    if mat is None or not mat.use_nodes:
        return None
    nodes = mat.node_tree.nodes
    bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    src = bsdf
    if src is None:
        src = next((n for n in nodes if n.type == 'GROUP' and n.node_tree
                    and n.node_tree.name == DECAL_NODE_GROUP), None)
    if src is None:
        return None
    return {
        'base_color': tuple(src.inputs['Base Color'].default_value),
        'metallic': src.inputs['Metallic'].default_value,
        'roughness': src.inputs['Roughness'].default_value,
    }


def match_decal_to_material(decal_obj, sample):
    """Tune a decal's HF_DecalShader inputs to a sampled material (from
    sample_material) so it reads as the same surface. The decal's material is made
    single-user first so shared templates are never clobbered. Base Color is only
    set when it is not texture-driven (an image decal keeps its texture). Returns
    True on success."""
    if sample is None:
        return False
    grp = _decal_group_node(decal_obj)
    if grp is None:
        return False
    # Copy the material so tuning one decal does not affect every sibling, and
    # replace it in the ACTIVE slot (the decal's material may not be slot 0).
    old = decal_obj.active_material
    mat = old.copy()
    decal_obj.active_material = mat
    # Re-matching the same decal would otherwise leave the previous single-user
    # copy as an orphan (HF_Decal_*.001/.002...). Drop it once it hits 0 users;
    # shared templates keep other users, so they are never removed here.
    if old is not None and old.users == 0:
        bpy.data.materials.remove(old)
    grp = _decal_group_node(decal_obj)
    if not grp.inputs['Base Color'].is_linked:
        grp.inputs['Base Color'].default_value = sample['base_color']
    grp.inputs['Metallic'].default_value = sample['metallic']
    grp.inputs['Roughness'].default_value = sample['roughness']
    return True


def set_decal_uv_rect(decal_obj, uv_rect):
    """Rewrite a decal quad's UVs to a new sub-rect (a different trim cell) after
    placement -- the interactive trim-UV editor (v1.7). Maps each loop to a corner
    by its vertex's local position sign (the build_decal_mesh layout). Returns
    True on success."""
    me = decal_obj.data
    uvl = me.uv_layers.active
    if uvl is None:
        return False
    u0, v0, u1, v1 = uv_rect
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uvl.data[li].uv = (u1 if co.x > 0 else u0, v1 if co.y > 0 else v0)
    me.update()
    return True


def conform_trim_decal(context, decal_obj, target, subdivisions=8, max_gap=0.05):
    """Auto-cut a decal to the surface (v1.7): subdivide its quad, then delete any
    face whose center projects farther than `max_gap` from `target`'s nearest
    surface -- i.e. faces floating over a boolean cut or off an edge. The decal's
    shrinkwrap keeps wrapping the rest. Returns the face count removed."""
    subdivisions = max(0, int(subdivisions))
    me = decal_obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    if subdivisions > 0:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=subdivisions,
                                  use_grid_fill=True)
    mw = decal_obj.matrix_world
    depsgraph = context.evaluated_depsgraph_get()
    eval_t = target.evaluated_get(depsgraph)
    t_inv = eval_t.matrix_world.inverted_safe()
    t_mw = eval_t.matrix_world
    doomed = []
    for f in bm.faces:
        world_c = mw @ f.calc_center_median()
        ok, loc, _n, _i = eval_t.closest_point_on_mesh(t_inv @ world_c)
        if not ok:
            doomed.append(f)
            continue
        if (t_mw @ loc - world_c).length > max_gap:
            doomed.append(f)
    removed = len(doomed)
    if doomed:
        bmesh.ops.delete(bm, geom=doomed, context='FACES')
    bm.to_mesh(me)
    me.update()
    bm.free()
    return removed


def retarget_decal(decal_obj, new_target):
    """Move a placed decal onto a different surface object (decal transfer):
    re-point its shrinkwrap at `new_target` and re-parent to it while
    keeping the decal's current world pose. Returns True when a shrinkwrap was
    retargeted (False if the decal had none -- it is still re-parented)."""
    world = decal_obj.matrix_world.copy()
    shrink = next((m for m in decal_obj.modifiers if m.type == 'SHRINKWRAP'), None)
    if shrink is not None:
        shrink.target = new_target
    decal_obj.parent = new_target
    decal_obj.matrix_parent_inverse = new_target.matrix_world.inverted_safe()
    decal_obj.matrix_world = world          # back-solve basis -> world preserved
    return shrink is not None


def save_image(image, filepath, file_format='PNG'):
    """Write an image datablock to disk (used by the decal-creation pipeline to
    drop a baked decal into the library folder). Returns the saved filepath."""
    image.filepath_raw = filepath
    image.file_format = file_format
    image.save()
    return filepath
