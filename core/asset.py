# Asset / kitbash logic: append a ready-made part (an "INSERT")
# from a .blend library, orient it to a surface, optionally bind it as a boolean
# cutter or conform it to the surface, and gather it in a "Hardflow Assets"
# collection.
#
# This module uses bpy.data / mathutils but NEVER bpy.ops / gpu / blf, keeping
# with the core layer rule (it reuses the deliberate modifier_apply concession in
# core/boolean.py). The pure orientation math lives in core/decal_math.py and the
# pure library scan in core/asset_lib.py, so both are tested without Blender.
import bpy
from mathutils import Matrix

from . import decal_math, boolean


ASSET_COLLECTION = "Hardflow Assets"


def asset_collection(context):
    """Get/create the collection that gathers placed assets (mirrors
    core/boolean.py cutter_collection and core/decal.py decal_collection)."""
    coll = bpy.data.collections.get(ASSET_COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(ASSET_COLLECTION)
        context.scene.collection.children.link(coll)
    return coll


def load_blend_objects(filepath, link=False):
    """Append (link=False) or link (link=True) every object from a .blend library
    and return the new object data-blocks. They are NOT yet in any scene
    collection -- the caller links them where it wants. Returns [] if the file
    has no objects."""
    with bpy.data.libraries.load(filepath, link=link) as (data_from, data_to):
        data_to.objects = list(data_from.objects)
    return [o for o in data_to.objects if o is not None]


def asset_matrix(location, normal, tangent, scale=1.0):
    """World matrix placing an INSERT at location with local +Z along the surface
    normal and local +Y along tangent (uniform scale). Reuses the shared pure
    basis (core/decal_math.orientation_basis), so a part sits on a surface the
    same way a decal does."""
    x, y, z = decal_math.orientation_basis(tuple(normal), tuple(tangent))
    return Matrix((
        (x[0] * scale, y[0] * scale, z[0] * scale, location[0]),
        (x[1] * scale, y[1] * scale, z[1] * scale, location[1]),
        (x[2] * scale, y[2] * scale, z[2] * scale, location[2]),
        (0.0, 0.0, 0.0, 1.0),
    ))


def place_asset(context, objects, location, normal, tangent, scale=1.0,
                name="HF_Insert"):
    """Place a group of appended objects as one INSERT: parent them under a new
    Empty oriented to the surface, so the part keeps its authored layout but sits
    where the cursor hit. Returns the root Empty. Objects with an existing parent
    (sub-parts of the kit) keep their hierarchy and only follow the root."""
    coll = asset_collection(context)
    root = bpy.data.objects.new(name, None)
    root.empty_display_size = 0.1
    root.empty_display_type = 'ARROWS'
    coll.objects.link(root)
    root.matrix_world = asset_matrix(location, normal, tangent, scale)
    root["hf_asset_root"] = name

    for o in objects:
        coll.objects.link(o)
        if o.parent is None:
            # the appended object's matrix_world is its authored local pose;
            # parenting with an identity inverse makes world = root @ that pose.
            o.parent = root
            o.matrix_parent_inverse = Matrix()
        o["hf_asset"] = name
    return root


def bind_cutters(context, meshes, target, operation='DIFFERENCE', solver='EXACT',
                 non_destructive=True, failures=None):
    """Make each (already surface-placed) mesh a boolean cutter on the target. In
    non-destructive mode the live modifier stays and the cutter is stashed
    (non-destructive); otherwise the boolean is applied and the cutter deleted.
    Shared by make_asset_cutter and the live-preview commit. Returns `meshes`.

    In destructive mode each cut goes through `robust_boolean` (solver fallback +
    cutter normal repair + diagnosis); if a `failures` list is given, the
    human-readable message for any cut that still fails is appended to it (the
    caller -- an operator -- reports it; core stays free of bpy.ops/report)."""
    for m in meshes:
        if non_destructive:
            boolean.add_boolean(target, m, operation, solver)
            boolean.stash_cutter(context, m, target)
        else:
            ok, _used, msg = boolean.robust_boolean(context, target, m,
                                                    operation, solver)
            if not ok and failures is not None:
                failures.append(msg)
    if not non_destructive:
        for m in meshes:
            if m.name in bpy.data.objects:
                bpy.data.objects.remove(m, do_unlink=True)
    return meshes


def flatten_objects(objects):
    """Drop parenting while preserving each object's world pose, so a previewed
    INSERT (parented under an oriented root) can be re-bound as independent
    cutters. World matrices are captured first, so inter-object parenting is safe."""
    worlds = {o: o.matrix_world.copy() for o in objects}
    for o in objects:
        o.parent = None
        o.matrix_world = worlds[o]


def make_asset_cutter(context, objects, target, location, normal, tangent,
                      scale=1.0, operation='DIFFERENCE', solver='EXACT',
                      non_destructive=True, failures=None):
    """Bind a kit part to the target as a boolean: orient every mesh object of the
    INSERT to the surface and make each a cutter (CUT/MAKE/INTERSECT) via
    bind_cutters. Returns the list of mesh cutters acted on. A `failures` list, if
    given, collects diagnosis messages for cuts that fail (see bind_cutters)."""
    mat = asset_matrix(location, normal, tangent, scale)
    coll = asset_collection(context)
    meshes = [o for o in objects if o.type == 'MESH']
    for o in objects:
        coll.objects.link(o)
        o.matrix_world = mat @ o.matrix_world      # authored pose -> placed pose

    bind_cutters(context, meshes, target, operation, solver, non_destructive,
                 failures)
    # non-mesh helpers (empties/curves) of a cutter kit are dropped destructively
    if not non_destructive:
        for o in objects:
            if o.type != 'MESH' and o.name in bpy.data.objects:
                bpy.data.objects.remove(o, do_unlink=True)
    return meshes


def conform_asset(objects, target, offset=0.0):
    """Wrap/Conform an INSERT onto a curved surface: add a SHRINKWRAP
    (NEAREST_SURFACEPOINT) modifier toward the target on each mesh object, so the
    part hugs the surface (wrap/conform). Returns the modifiers added."""
    mods = []
    for o in objects:
        if o.type != 'MESH':
            continue
        mod = o.modifiers.new("HF_Conform", 'SHRINKWRAP')
        mod.wrap_method = 'NEAREST_SURFACEPOINT'
        mod.target = target
        mod.offset = offset
        mods.append(mod)
    return mods


# --- Asset/insert extras (v1.8) -----------------------------------------


def bound_size(objects):
    """Largest world-space bounding extent across the mesh objects of an INSERT
    (a proxy for the part's overall size). Used by the auto/smart-scale fit.
    Returns 0.0 when there is no mesh."""
    best = 0.0
    for o in objects:
        if o.type == 'MESH':
            best = max(best, max(o.dimensions))
    return best


def surface_feature_size(obj):
    """A proxy for the target's local feature size: its smallest non-zero
    world dimension. The INSERT is scaled to a fraction of this on placement."""
    dims = [d for d in obj.dimensions if d > 1e-6]
    return min(dims) if dims else 0.0


def load_blend_materials(filepath, link=False):
    """Append (or link) every material from a .blend library -- a material-only
    INSERT (material insert). Returns the new material data-blocks."""
    with bpy.data.libraries.load(filepath, link=link) as (data_from, data_to):
        data_to.materials = list(data_from.materials)
    return [m for m in data_to.materials if m is not None]


def apply_material(obj, mat):
    """Give a mesh object `mat` as its sole material (material INSERT). Returns
    True on success."""
    if obj.type != 'MESH' or mat is None:
        return False
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return True


def write_objects_blend(filepath, objects):
    """Write the given objects (and their mesh/curve data + materials) to a .blend
    library -- .blend pack INSERT export into the asset library. Returns the
    filepath, or None when there is nothing to write."""
    blocks = set()
    for o in objects:
        blocks.add(o)
        if o.data is not None:
            blocks.add(o.data)
        for slot in getattr(o, "material_slots", []):
            if slot.material is not None:
                blocks.add(slot.material)
    if not blocks:
        return None
    bpy.data.libraries.write(filepath, blocks, fake_user=True, compress=True)
    return filepath


def transfer_shading(target, objects):
    """Apply the target's active material and smooth-shading state to the placed
    part (material/auto-smooth transfer). Does nothing for the material if
    the target has none."""
    if target is None or target.type != 'MESH':
        return
    mat = target.active_material
    smooth = bool(target.data.polygons) and target.data.polygons[0].use_smooth
    for o in objects:
        if o.type != 'MESH':
            continue
        if mat is not None:
            o.data.materials.clear()
            o.data.materials.append(mat)
        for poly in o.data.polygons:
            poly.use_smooth = smooth
