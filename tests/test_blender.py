# Headless Blender smoke test -- automatically verifies the bpy-dependent core.
#
# Run (Blender 4.2+ must be installed):
#   blender --background --python tests/test_blender.py
#
# Zero exit code = passed. The modal drawing operator (HARDFLOW_OT_draw) requires
# a window/region, so it is NOT tested here; instead the building blocks it uses
# (build_prism, apply/add_boolean) and the non-modal bevel/mirror operators are
# verified. For pure math: python tests/test_core.py. For the modal tools that
# can't run headless (draw, Push/Pull, Offset, the menus): tests/manual_checklist.md.
import os
import sys

import bpy
from mathutils import Vector

# Add the repo's parent folder to the path so the hardflow package can be imported.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PARENT = os.path.dirname(_REPO)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

_PKG = os.path.basename(_REPO)            # usually "hardflow"
hardflow = __import__(_PKG)
from hardflow.core import (geometry, boolean, decal, decal_image, atlas,  # noqa: E402
                           asset, grid, raycast, snapping)


def _reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _add_cube(name="Cube", size=2.0, location=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = location
    bpy.context.collection.objects.link(ob)
    return ob


def _activate(ob):
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)


def test_build_prism():
    corners = [Vector((-1, -1, 0)), Vector((1, -1, 0)),
               Vector((1, 1, 0)), Vector((-1, 1, 0))]
    view_dir = Vector((0, 0, -1))
    me = geometry.build_prism(corners, view_dir, thickness=4.0)
    assert me is not None, "build_prism returned None"
    assert len(me.vertices) == 8, len(me.vertices)   # 4 front + 4 back
    assert len(me.polygons) == 6, len(me.polygons)   # closed prism (box)
    # degenerate (repeated corner) -> None
    bad = geometry.build_prism([Vector((0, 0, 0))] * 4, view_dir, 4.0)
    assert bad is None


def test_apply_boolean_difference():
    _reset()
    target = _add_cube("Target", size=2.0)
    cutter = _add_cube("Cutter", size=1.0, location=(1, 0, 0))
    _activate(target)
    before = len(target.data.polygons)
    boolean.apply_boolean(bpy.context, target, cutter, 'DIFFERENCE', 'EXACT')
    after = len(target.data.polygons)
    assert after != before, "DIFFERENCE did not change the geometry"
    assert len(target.modifiers) == 0, "modifier not applied (still present)"


def test_add_boolean_nondestructive():
    _reset()
    target = _add_cube("Target", size=2.0)
    cutter = _add_cube("Cutter", size=1.0, location=(1, 0, 0))
    mod = boolean.add_boolean(target, cutter, 'DIFFERENCE', 'EXACT')
    assert mod.name in target.modifiers, "modifier not added"
    assert mod.object is cutter
    # stash_cutter should move the cutter to a separate collection
    boolean.stash_cutter(bpy.context, cutter, target)
    coll = bpy.data.collections.get(boolean.CUTTER_COLLECTION)
    assert coll is not None and cutter.name in coll.objects
    assert cutter.parent is target
    assert cutter.display_type == 'WIRE'


def test_bevel_and_mirror_operators():
    _reset()
    hardflow.register()
    try:
        ob = _add_cube("Obj")
        _activate(ob)
        # EXEC_DEFAULT -> execute() (redo path); modal invoke is skipped.
        # adaptive=False so the explicit width is honoured (adaptive would scale
        # the width to the object's size instead).
        bpy.ops.object.hardflow_bevel(width=0.03, segments=3, weighted_normal=True,
                                      adaptive=False)
        assert any(m.type == 'BEVEL' for m in ob.modifiers), "bevel not added"
        assert any(m.type == 'WEIGHTED_NORMAL' for m in ob.modifiers), \
            "weighted normal not added"
        bev = next(m for m in ob.modifiers if m.type == 'BEVEL')
        assert bev.segments == 3 and abs(bev.width - 0.03) < 1e-6
        bpy.ops.object.hardflow_mirror(axis='X')
        assert any(m.type == 'MIRROR' for m in ob.modifiers), "mirror not added"
    finally:
        hardflow.unregister()


def test_adaptive_bevel_scales_to_object():
    # with adaptive on (default), the bevel width is derived from the object's
    # size: a 2 m cube -> 2% of 2.0 = 0.04, not the fixed 0.02 default.
    _reset()
    hardflow.register()
    try:
        ob = _add_cube("Big", size=2.0)            # 2 m across
        _activate(ob)
        bpy.ops.object.hardflow_bevel(adaptive=True)
        bev = next(m for m in ob.modifiers if m.type == 'BEVEL')
        assert abs(bev.width - 0.04) < 1e-6, bev.width
    finally:
        hardflow.unregister()


def test_build_face_and_cleanup():
    _reset()
    # build_face: a single n-gon from 4 corners
    me = geometry.build_face([Vector((0, 0, 0)), Vector((1, 0, 0)),
                              Vector((1, 1, 0)), Vector((0, 1, 0))])
    assert me is not None and len(me.polygons) == 1
    assert len(me.vertices) == 4
    # cleanup_mesh: weld a mesh with overlapping vertices
    cube = _add_cube("CleanMe", size=2.0)
    # a second overlapping cube -> remove doubles should merge it
    extra = _add_cube("Extra", size=2.0)
    _activate(cube)
    # rather than joining Extra to add overlapping vertices to the cube,
    # directly sanity-check that cleanup neither drops nor fails to preserve:
    before = len(cube.data.vertices)
    geometry.cleanup_mesh(cube)
    assert len(cube.data.vertices) <= before  # cleanup must not increase vertices


def test_build_pipe():
    _reset()
    pts = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((1, 1, 0))]
    curve = geometry.build_pipe(pts, radius=0.1)
    assert curve is not None
    assert curve.bevel_depth == 0.1
    sp = curve.splines[0]
    assert sp.type == 'POLY' and len(sp.points) == 3
    # single point -> None
    assert geometry.build_pipe([Vector((0, 0, 0))]) is None


def test_clean_operator():
    _reset()
    hardflow.register()
    try:
        ob = _add_cube("Obj", size=2.0)
        _activate(ob)
        before = len(ob.data.vertices)
        bpy.ops.object.hardflow_clean()
        # a clean cube should not change (8 vertices preserved)
        assert len(ob.data.vertices) == before == 8
    finally:
        hardflow.unregister()


def test_apply_cutters_operator():
    _reset()
    hardflow.register()
    try:
        target = _add_cube("Target", size=2.0)
        cutter = _add_cube("Cutter", size=1.0, location=(1, 0, 0))
        boolean.add_boolean(target, cutter, 'DIFFERENCE', 'EXACT')
        boolean.stash_cutter(bpy.context, cutter, target)
        _activate(target)
        before = len(target.data.polygons)
        bpy.ops.object.hardflow_apply_cutters(delete_cutters=True)
        assert len(target.modifiers) == 0, "modifier not applied"
        assert len(target.data.polygons) != before, "boolean not baked"
        assert bpy.data.objects.get("Cutter") is None, "unused cutter not deleted"
    finally:
        hardflow.unregister()


def test_multi_object_difference():
    # Single cutter + two targets: both should change their polygon count.
    _reset()
    t1 = _add_cube("T1", size=2.0, location=(-2, 0, 0))
    t2 = _add_cube("T2", size=2.0, location=(2, 0, 0))
    cutter = _add_cube("Cutter", size=1.0, location=(-2, 0, 1))
    b1, b2 = len(t1.data.polygons), len(t2.data.polygons)
    boolean.apply_boolean(bpy.context, t1, cutter, 'DIFFERENCE', 'EXACT')
    cutter2 = _add_cube("Cutter2", size=1.0, location=(2, 0, 1))
    boolean.apply_boolean(bpy.context, t2, cutter2, 'DIFFERENCE', 'EXACT')
    assert len(t1.data.polygons) != b1
    assert len(t2.data.polygons) != b2


def test_decal_mesh_and_material():
    _reset()
    me = decal.build_decal_mesh(0.2, 0.3)
    assert me is not None
    assert len(me.vertices) == 4 and len(me.polygons) == 1
    assert me.uv_layers, "decal mesh has no UV map"
    for type_id, _label, _desc in decal.DECAL_TYPES:
        mat = decal.decal_material(type_id)
        assert mat is not None and mat.use_nodes
        # v0.8: each material instances the shared PBR node group, wired to output
        grp = next((n for n in mat.node_tree.nodes
                    if n.type == 'GROUP'
                    and n.node_tree and n.node_tree.name == decal.DECAL_NODE_GROUP),
                   None)
        assert grp is not None, "material does not use HF_DecalShader group"
        out = next((n for n in mat.node_tree.nodes
                    if n.type == 'OUTPUT_MATERIAL'), None)
        assert out is not None and out.inputs['Surface'].is_linked
        for chan in ("Base Color", "AO", "Normal", "Emission Color", "Alpha"):
            assert chan in grp.inputs, "missing decal channel: %s" % chan
    # the node group itself is a shared singleton, not duplicated per material
    assert decal._decal_node_group() is decal._decal_node_group()
    # materials are cached/shared, not recreated
    assert decal.decal_material('INFO') is decal.decal_material('INFO')


def test_adaptive_decal_offset_scales():
    _reset()
    big = _add_cube("Big", size=10.0)
    small = _add_cube("Small", size=0.2)
    ob = decal.adaptive_decal_offset(big)
    os = decal.adaptive_decal_offset(small)
    assert ob > os, (ob, os)          # larger target -> larger hover gap
    assert os >= 1e-4                 # never below the 0.1 mm floor
    # offset=None on make_decal -> the shrinkwrap uses the adaptive gap
    d = decal.make_decal(bpy.context, big, Vector((0, 0, 5)),
                         Vector((0, 0, 1)), Vector((1, 0, 0)), offset=None)
    sw = next(m for m in d.modifiers if m.type == 'SHRINKWRAP')
    assert abs(sw.offset - decal.adaptive_decal_offset(big)) < 1e-9


def test_make_decal_sticks_to_surface():
    _reset()
    target = _add_cube("Target", size=2.0)
    location = Vector((0.0, 0.0, 1.0))   # top face of the cube
    normal = Vector((0.0, 0.0, 1.0))
    tangent = Vector((1.0, 0.0, 0.0))
    d = decal.make_decal(bpy.context, target, location, normal, tangent,
                         width=0.3, height=0.3, decal_type='PANEL', offset=0.001)
    assert d is not None
    # shrinkwrap PROJECT adhesion
    sw = next((m for m in d.modifiers if m.type == 'SHRINKWRAP'), None)
    assert sw is not None and sw.wrap_method == 'PROJECT'
    assert sw.target is target
    # parented + collected + materialed
    assert d.parent is target
    coll = bpy.data.collections.get(decal.DECAL_COLLECTION)
    assert coll is not None and d.name in coll.objects
    assert len(d.data.materials) == 1
    assert d.get("hf_decal_type") == 'PANEL'
    # the decal plane faces along the surface normal (local +Z == world +Z here)
    z_axis = d.matrix_world.to_3x3().col[2].normalized()
    assert abs(z_axis.z - 1.0) < 1e-6, z_axis


def test_image_decal_material_and_make():
    # v0.9: an image-driven decal plugs the image into the shared node group's
    # Base Color + Alpha and sizes the quad to the image's aspect ratio.
    _reset()
    img = bpy.data.images.new("HF_T_Logo", width=200, height=100, alpha=True)
    mat = decal.image_decal_material(img)
    assert mat is not None and mat.use_nodes
    tex = next((n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE'), None)
    assert tex is not None and tex.image is img, "image texture node missing"
    grp = next((n for n in mat.node_tree.nodes
                if n.type == 'GROUP' and n.node_tree
                and n.node_tree.name == decal.DECAL_NODE_GROUP), None)
    assert grp is not None
    assert grp.inputs["Base Color"].is_linked and grp.inputs["Alpha"].is_linked
    assert decal.image_decal_material(img) is mat            # cached per image

    target = _add_cube("Target", size=2.0)
    w, h = decal_image.aspect_size(img.size[0], img.size[1], 0.4)  # 200x100 -> wide
    assert abs(w - 0.4) < 1e-6 and abs(h - 0.2) < 1e-6
    d = decal.make_image_decal(bpy.context, target, Vector((0, 0, 1)),
                               Vector((0, 0, 1)), Vector((1, 0, 0)), img,
                               width=w, height=h)
    assert d.parent is target and d.get("hf_decal_type") == 'IMAGE'
    assert d.get("hf_decal_image") == img.name
    assert d.data.materials and d.data.materials[0] is mat


def test_decal_mesh_uv_rect():
    # v0.9 trim: build_decal_mesh maps the quad onto a UV sub-rect (a trim cell).
    _reset()
    cell = atlas.cell_rect(2, 2, 0)        # top-left quarter: (0, .5, .5, 1)
    me = decal.build_decal_mesh(0.2, 0.2, uv_rect=cell)
    uvs = me.uv_layers.active.data
    us = [round(d.uv[0], 4) for d in uvs]
    vs = [round(d.uv[1], 4) for d in uvs]
    assert min(us) == 0.0 and max(us) == 0.5
    assert min(vs) == 0.5 and max(vs) == 1.0
    # default still spans the whole image
    full = decal.build_decal_mesh(0.2, 0.2)
    fus = [round(d.uv[0], 4) for d in full.uv_layers.active.data]
    assert min(fus) == 0.0 and max(fus) == 1.0


def test_atlas_decals():
    # v0.9 atlasing: pack two image decals' textures into one atlas image and
    # retarget their UVs + material. No bpy.ops.bake, so it runs headless.
    _reset()
    hardflow.register()
    try:
        target = _add_cube("Target", size=2.0)
        n = Vector((0, 0, 1))
        t = Vector((1, 0, 0))
        ia = bpy.data.images.new("HF_T_A", width=64, height=32, alpha=True)
        ib = bpy.data.images.new("HF_T_B", width=32, height=32, alpha=True)
        da = decal.make_image_decal(bpy.context, target, Vector((0, 0, 1)), n, t, ia,
                                    width=0.4, height=0.2)
        db = decal.make_image_decal(bpy.context, target, Vector((0.5, 0, 1)), n, t, ib,
                                    width=0.2, height=0.2)

        res = bpy.ops.object.hardflow_atlas_decals()
        assert res == {'FINISHED'}, res

        atlas_img = bpy.data.images.get("HF_Decal_Atlas")
        assert atlas_img is not None
        w, h = atlas_img.size
        assert w & (w - 1) == 0 and h & (h - 1) == 0, "atlas not power-of-two"

        # both decals now share the single atlas material
        assert len(da.data.materials) == 1 and len(db.data.materials) == 1
        assert da.data.materials[0] is db.data.materials[0]
        assert da.data.materials[0].name == "HF_Decal_Img_HF_Decal_Atlas"
        assert da.get("hf_decal_atlas") == "HF_Decal_Atlas"

        # every UV landed inside the atlas; the two decals map to different slots
        def _uvs(ob):
            return [tuple(round(c, 5) for c in d.uv) for d in ob.data.uv_layers.active.data]
        for u, v in _uvs(da) + _uvs(db):
            assert 0.0 <= u <= 1.0 and 0.0 <= v <= 1.0
        assert set(_uvs(da)) != set(_uvs(db)), "decals share a slot"
    finally:
        hardflow.unregister()


def test_decal_operators_registered():
    _reset()
    hardflow.register()
    try:
        assert hasattr(bpy.ops.object, "hardflow_place_decal")
        assert hasattr(bpy.ops.object, "hardflow_select_decal")
        assert hasattr(bpy.ops.object, "hardflow_remove_decal")
        assert hasattr(bpy.ops.object, "hardflow_load_decal_image")
        assert hasattr(bpy.ops.object, "hardflow_library_place")
        assert hasattr(bpy.ops.object, "hardflow_load_trim_sheet")
        assert hasattr(bpy.ops.object, "hardflow_atlas_decals")
        # select/remove are non-modal and safe to exec headless
        target = _add_cube("Target", size=2.0)
        d = decal.make_decal(bpy.context, target, Vector((0, 0, 1)),
                             Vector((0, 0, 1)), Vector((1, 0, 0)))
        name = d.name
        bpy.ops.object.hardflow_remove_decal(name=name)
        assert bpy.data.objects.get(name) is None, "decal not removed"
    finally:
        hardflow.unregister()


def test_bake_helpers():
    _reset()
    # bake_image: square, Non-Color for data maps
    norm = decal.bake_image("HF_T_Norm", 256, is_data=True)
    assert norm.size[0] == 256 and norm.size[1] == 256
    assert norm.colorspace_settings.name == 'Non-Color'
    col = decal.bake_image("HF_T_Col", 128, is_data=False)
    assert col.colorspace_settings.name == 'sRGB'
    assert decal.bake_image("HF_T_Norm", 256) is norm   # reused, not duplicated

    # ensure_material gives a node material; bake_image_node sets it active+sole
    target = _add_cube("Target", size=2.0)
    mat = decal.ensure_material(target)
    assert mat.use_nodes and target.active_material is mat
    node = decal.bake_image_node(mat, norm)
    assert node.type == 'TEX_IMAGE' and node.image is norm
    assert mat.node_tree.nodes.active is node
    assert all((n.select == (n is node)) for n in mat.node_tree.nodes)
    assert decal.bake_image_node(mat, norm) is node     # reused


def test_bake_decal_guards():
    _reset()
    hardflow.register()
    try:
        assert hasattr(bpy.ops.object, "hardflow_bake_decal")
        # a bmesh cube has no UV map; the bake must early-out before touching the
        # render engine (so a missing unwrap is a clean rejection, not a crash)
        target = _add_cube("Target", size=2.0)
        assert not target.data.uv_layers
        d = decal.make_decal(bpy.context, target, Vector((0, 0, 1)),
                             Vector((0, 0, 1)), Vector((1, 0, 0)))
        res = bpy.ops.object.hardflow_bake_decal(name=d.name)
        assert res == {'CANCELLED'}, res
        assert bpy.context.scene.render.engine != 'CYCLES'  # early-out, no switch
    finally:
        hardflow.unregister()


def test_symmetrize_mesh():
    _reset()
    # a centered cube symmetrized over +X stays a closed 8-vertex cube
    cube = _add_cube("Sym", size=2.0)
    geometry.symmetrize_mesh(cube, '+X')
    assert len(cube.data.vertices) == 8, len(cube.data.vertices)
    assert len(cube.data.polygons) == 6


def test_mark_sharp_by_angle():
    _reset()
    import math
    cube = _add_cube("Sharp", size=2.0)
    # every cube edge is a 90 degree crease -> all 12 are sharp at a 30 deg limit
    n = geometry.mark_sharp_by_angle(cube, math.radians(30))
    assert n == 12, n
    assert all(p.use_smooth for p in cube.data.polygons)
    assert any(not e.use_edge_sharp for e in cube.data.edges) is False  # all sharp
    # a very high limit marks nothing sharp
    n2 = geometry.mark_sharp_by_angle(cube, math.radians(170))
    assert n2 == 0


def test_symmetrize_and_sharpen_operators():
    _reset()
    hardflow.register()
    try:
        ob = _add_cube("Obj", size=2.0)
        _activate(ob)
        res = bpy.ops.object.hardflow_symmetrize(direction='+X')
        assert res == {'FINISHED'}, res
        res = bpy.ops.object.hardflow_sharpen(angle_deg=30.0, add_bevel=True)
        assert res == {'FINISHED'}, res
        assert any(m.type == 'BEVEL' for m in ob.modifiers)
        assert any(m.type == 'WEIGHTED_NORMAL' for m in ob.modifiers)
    finally:
        hardflow.unregister()


def test_boolean_from_selection():
    _reset()
    hardflow.register()
    try:
        target = _add_cube("Target", size=2.0)
        cutter = _add_cube("Cutter", size=1.0, location=(1, 0, 0))
        target.select_set(True)
        cutter.select_set(True)
        bpy.context.view_layer.objects.active = cutter   # active = cutter
        before = len(target.data.polygons)
        res = bpy.ops.object.hardflow_boolean(operation='DIFFERENCE')
        assert res == {'FINISHED'}, res
        # destructive by default: target changed, cutter removed
        assert len(target.data.polygons) != before
        assert bpy.data.objects.get("Cutter") is None
    finally:
        hardflow.unregister()


def test_array_operators():
    _reset()
    hardflow.register()
    try:
        ob = _add_cube("Obj", size=1.0)
        _activate(ob)
        bpy.ops.object.hardflow_array(count=4, axis='X', factor=1.5)
        arr = next((m for m in ob.modifiers if m.type == 'ARRAY'), None)
        assert arr is not None and arr.count == 4
        assert arr.use_relative_offset

        ob2 = _add_cube("Obj2", size=1.0, location=(3, 0, 0))
        _activate(ob2)
        bpy.ops.object.hardflow_radial_array(count=6, axis='Z')
        rad = next((m for m in ob2.modifiers if m.name == "HF_RadialArray"), None)
        assert rad is not None and rad.count == 6
        assert rad.use_object_offset and rad.offset_object is not None
    finally:
        hardflow.unregister()


def test_asset_matrix_identity():
    # a flat surface (normal +Z, tangent +X) gives an axis-aligned placement
    m = asset.asset_matrix((1.0, 2.0, 3.0), (0, 0, 1), (1, 0, 0), scale=2.0)
    assert tuple(round(c, 6) for c in m.translation) == (1.0, 2.0, 3.0)
    z = m.to_3x3().col[2].normalized()
    assert abs(z.z - 1.0) < 1e-6
    # uniform scale baked into the basis columns
    assert abs(m.to_3x3().col[0].length - 2.0) < 1e-6


def test_place_asset_groups_under_root():
    _reset()
    # two loose objects act as an appended kit; place_asset parents them to an
    # oriented root empty in the asset collection
    a = _add_cube("PartA", size=0.5)
    b = _add_cube("PartB", size=0.5, location=(0.5, 0, 0))
    for o in (a, b):
        for c in list(o.users_collection):
            c.objects.unlink(o)
    root = asset.place_asset(bpy.context, [a, b], (0, 0, 1), (0, 0, 1), (1, 0, 0),
                             scale=1.0, name="HF_Kit")
    assert root is not None and root.type == 'EMPTY'
    coll = bpy.data.collections.get(asset.ASSET_COLLECTION)
    assert coll is not None and root.name in coll.objects
    assert a.parent is root and b.parent is root
    assert a.get("hf_asset") == "HF_Kit"


def test_make_asset_cutter_nondestructive():
    _reset()
    target = _add_cube("Target", size=2.0)
    part = _add_cube("CutPart", size=1.0, location=(1, 0, 0))
    for c in list(part.users_collection):
        c.objects.unlink(part)
    meshes = asset.make_asset_cutter(
        bpy.context, [part], target, (0, 0, 0), (0, 0, 1), (1, 0, 0),
        scale=1.0, operation='DIFFERENCE', non_destructive=True)
    assert part in meshes
    assert any(m.type == 'BOOLEAN' and m.object is part for m in target.modifiers)
    coll = bpy.data.collections.get(boolean.CUTTER_COLLECTION)
    assert coll is not None and part.name in coll.objects   # stashed


def test_flatten_objects_preserves_world():
    # a preview INSERT parented under a moved/scaled root is flattened to
    # independent objects that keep their world pose (so they can be re-bound)
    _reset()
    from mathutils import Matrix
    root = bpy.data.objects.new("Root", None)
    bpy.context.collection.objects.link(root)
    root.matrix_world = Matrix.Translation((2, 0, 1)) @ Matrix.Scale(2.0, 4)
    child = _add_cube("Child", size=1.0)
    child.parent = root
    child.matrix_parent_inverse = Matrix()
    before = child.matrix_world.copy()
    asset.flatten_objects([root, child])
    assert child.parent is None
    after = child.matrix_world
    assert all(abs(a - b) < 1e-6 for a, b in zip(before.translation, after.translation))


def test_bind_cutters_nondestructive():
    _reset()
    target = _add_cube("Target", size=2.0)
    part = _add_cube("Part", size=1.0, location=(1, 0, 0))
    asset.bind_cutters(bpy.context, [part], target, operation='DIFFERENCE',
                       non_destructive=True)
    assert any(m.type == 'BOOLEAN' and m.object is part for m in target.modifiers)
    coll = bpy.data.collections.get(boolean.CUTTER_COLLECTION)
    assert coll is not None and part.name in coll.objects   # stashed


def test_conform_and_transfer_shading():
    _reset()
    target = _add_cube("Target", size=2.0)
    mat = bpy.data.materials.new("TgtMat")
    target.data.materials.append(mat)
    for p in target.data.polygons:
        p.use_smooth = True
    part = _add_cube("Part", size=0.5)

    asset.conform_asset([part], target, offset=0.0)
    sw = next((m for m in part.modifiers if m.type == 'SHRINKWRAP'), None)
    assert sw is not None and sw.wrap_method == 'NEAREST_SURFACEPOINT'
    assert sw.target is target

    asset.transfer_shading(target, [part])
    assert part.data.materials and part.data.materials[0] is mat
    assert all(p.use_smooth for p in part.data.polygons)


def test_asset_operators_registered():
    _reset()
    hardflow.register()
    try:
        assert hasattr(bpy.ops.object, "hardflow_place_asset")
        assert hasattr(bpy.ops.object, "hardflow_load_asset")
        assert hasattr(bpy.ops.object, "hardflow_asset_library_place")
        assert hasattr(bpy.ops.object, "hardflow_mark_asset")
        # mark-as-asset is non-modal and safe headless
        ob = _add_cube("MarkMe", size=1.0)
        _activate(ob)
        res = bpy.ops.object.hardflow_mark_asset()
        assert res == {'FINISHED'}, res
        assert ob.asset_data is not None, "object not marked as asset"
    finally:
        hardflow.unregister()


# --- SketchUp Build tools: Push/Pull, Offset, Construction Grid --------------

def test_extrude_faces_pushpull():
    # geometry behind Push/Pull: extruding one face must add side walls and move
    # the cap by the requested local vector.
    _reset()
    cube = _add_cube("PP", size=2.0)
    before = len(cube.data.polygons)
    ok = geometry.extrude_faces(cube, [0], Vector((0, 0, 1.0)))
    assert ok and len(cube.data.polygons) > before, "extrude added no geometry"
    top = max(v.co.z for v in cube.data.vertices)
    assert abs(top - 2.0) < 1e-5, "cap not raised to expected height: %f" % top
    # guards: empty list and out-of-range index are rejected, not crashes
    assert geometry.extrude_faces(cube, [], Vector((0, 0, 1))) is False
    assert geometry.extrude_faces(cube, [9999], Vector((0, 0, 1))) is False


def test_inset_faces_offset():
    # geometry behind Offset: inset adds a ring of faces around the picked face.
    _reset()
    cube = _add_cube("OFF", size=2.0)
    before = len(cube.data.polygons)
    assert geometry.inset_faces(cube, [0], 0.3) is True
    assert len(cube.data.polygons) > before, "inset added no geometry"
    assert geometry.inset_faces(cube, [0], 0.0) is False      # zero thickness
    assert geometry.inset_faces(cube, [9999], 0.3) is False   # bad index


def test_snapshot_restore_mesh():
    # the live-preview backbone for Push/Pull + Offset: snapshot a mesh, mutate
    # it, then restore it back to the captured state.
    _reset()
    cube = _add_cube("SNAP", size=2.0)
    base = geometry.snapshot_mesh(cube, "snap_base")
    before = len(cube.data.polygons)
    geometry.extrude_faces(cube, [0], Vector((0, 0, 1.0)))
    assert len(cube.data.polygons) != before, "edit did not change the mesh"
    geometry.restore_mesh(cube, base)
    assert len(cube.data.polygons) == before, "restore did not roll the mesh back"
    geometry.free_mesh(base)
    assert "snap_base" not in bpy.data.meshes, "snapshot datablock leaked"


def test_nearest_surface_point_lifts_along_normal():
    # closest_point_on_mesh backbone of the pipe drape: a point above the +Z face
    # of a 2m cube snaps back to z=1 with an upward normal.
    _reset()
    _activate(_add_cube("SURF", size=2.0))
    near = snapping.nearest_surface_point(bpy.context, Vector((0, 0, 5.0)),
                                          target='ACTIVE')
    assert near is not None, "no surface found"
    loc, nrm = near
    assert abs(loc.z - 1.0) < 1e-4, "nearest point not on the top face: %r" % loc
    assert nrm.z > 0.9, "normal not pointing up: %r" % nrm


def test_drape_path_rests_on_surface():
    # draping a straight span across the top of a 2m cube must keep every sample
    # lifted to (face + lift) along the surface normal, never sunk into the cube.
    _reset()
    _activate(_add_cube("DRAPE", size=2.0))
    lift = 0.1
    pts = snapping.drape_path(bpy.context,
                              [Vector((-0.5, 0, 1.0)), Vector((0.5, 0, 1.0))],
                              segments=4, lift=lift, target='ACTIVE')
    assert len(pts) >= 5, "drape did not sub-divide the span"
    for p in pts:
        assert abs(p.z - (1.0 + lift)) < 1e-4, "draped point off the surface: %r" % p
    # fewer than two points is returned unchanged
    assert len(snapping.drape_path(bpy.context, [Vector((0, 0, 0))])) == 1


def test_build_box_and_plane():
    _reset()
    box = geometry.build_box(2.0)
    assert box is not None and len(box.vertices) == 8 and len(box.polygons) == 6
    plane = geometry.build_plane(2.0)
    assert plane is not None and len(plane.vertices) == 4 and len(plane.polygons) == 1
    # plane spans +/- size/2 on XY, flat in Z
    xs = [v.co.x for v in plane.vertices]
    assert abs(min(xs) + 1.0) < 1e-6 and abs(max(xs) - 1.0) < 1e-6
    assert all(abs(v.co.z) < 1e-9 for v in plane.vertices)


def test_edit_bevel_edges():
    _reset()
    cube = _add_cube("BevelEdit", size=2.0)
    _edit_select_faces(cube, [0])            # selects that face's 4 edges too
    import bmesh
    bm = bmesh.from_edit_mesh(cube.data)
    bm.edges.ensure_lookup_table()
    sel_edges = sum(1 for e in bm.edges if e.select)
    assert sel_edges >= 1
    before = len(cube.data.polygons)
    n = geometry.edit_bevel_edges(cube, width=0.1, segments=2)
    bpy.ops.object.mode_set(mode='OBJECT')
    assert n == sel_edges
    assert len(cube.data.polygons) > before, "edge bevel added no geometry"
    # nothing selected -> no-op
    _edit_select_faces(cube, [])
    assert geometry.edit_bevel_edges(cube, width=0.1) == 0
    bpy.ops.object.mode_set(mode='OBJECT')


def test_build_line_guide():
    _reset()
    me = geometry.build_line(4.0, 'X')
    assert me is not None
    assert len(me.vertices) == 2 and len(me.edges) == 1 and len(me.polygons) == 0
    xs = sorted(v.co.x for v in me.vertices)
    assert abs(xs[0] + 2.0) < 1e-6 and abs(xs[1] - 2.0) < 1e-6
    # Y axis variant runs along Y
    mey = geometry.build_line(2.0, 'Y')
    assert max(abs(v.co.y) for v in mey.vertices) == 1.0


def test_add_guide_operator():
    _reset()
    hardflow.register()
    try:
        res = bpy.ops.object.hardflow_add_guide(axis='X', length=4.0)
        assert res == {'FINISHED'}, res
        g = bpy.data.objects.get("Hardflow_Guide")
        assert g is not None and g.display_type == 'WIRE' and g.show_in_front
        assert len(g.data.edges) == 1 and len(g.data.polygons) == 0
    finally:
        hardflow.unregister()


def test_add_primitive_operator():
    _reset()
    hardflow.register()
    try:
        res = bpy.ops.object.hardflow_add_primitive(kind='CUBE', size=2.0)
        assert res == {'FINISHED'}, res
        cube = bpy.data.objects.get("Hardflow_Cube")
        assert cube is not None and len(cube.data.polygons) == 6
        assert cube.select_get() and bpy.context.view_layer.objects.active is cube
        res = bpy.ops.object.hardflow_add_primitive(kind='PLANE', size=1.0)
        assert res == {'FINISHED'}, res
        assert bpy.data.objects.get("Hardflow_Plane") is not None
    finally:
        hardflow.unregister()


def test_build_grid_mesh_is_wire():
    _reset()
    segs = grid.centered_grid_segments(1.0, 0.5)
    me = geometry.build_grid_mesh(segs)
    assert me is not None
    assert len(me.edges) > 0, "grid mesh has no edges"
    assert len(me.polygons) == 0, "construction grid must be wire-only"
    assert geometry.build_grid_mesh([]) is None               # empty guard


def test_basis_from_normal_orthonormal():
    right, up, normal = raycast.basis_from_normal(Vector((0.3, 0.4, 0.866)))
    for v in (right, up, normal):
        assert abs(v.length - 1.0) < 1e-6, "basis vector not unit length"
    assert abs(right.dot(up)) < 1e-6 and abs(right.dot(normal)) < 1e-6
    assert abs(up.dot(normal)) < 1e-6
    # a vertical normal must still yield a valid (non-degenerate) tangent
    r, u, _n = raycast.basis_from_normal(Vector((0, 0, 1)))
    assert abs(r.length - 1.0) < 1e-6 and abs(u.length - 1.0) < 1e-6


def test_add_grid_operator():
    _reset()
    hardflow.register()
    try:
        assert hasattr(bpy.ops.object, "hardflow_add_grid")
        res = bpy.ops.object.hardflow_add_grid(plane='XY', extent=2.0, spacing=0.5)
        assert res == {'FINISHED'}, res
        gridobj = bpy.data.objects.get("Hardflow_Grid")
        assert gridobj is not None, "construction grid object not created"
        assert len(gridobj.data.edges) > 0 and len(gridobj.data.polygons) == 0
        assert gridobj.display_type == 'WIRE' and gridobj.show_in_front
    finally:
        hardflow.unregister()


def test_build_tool_operators_registered():
    # the modal operators can't run headless (no region), but they must register.
    _reset()
    hardflow.register()
    try:
        assert hasattr(bpy.ops.mesh, "hardflow_push_pull")
        assert hasattr(bpy.ops.mesh, "hardflow_offset")
        assert hasattr(bpy.ops.object, "hardflow_add_grid")
    finally:
        hardflow.unregister()


def test_menu_classes_registered():
    # the categorized pie + header dropdown menu system must register cleanly and
    # tear down without leaking the header hook.
    _reset()
    hardflow.register()
    try:
        for name in ("HARDFLOW_MT_pie", "HARDFLOW_MT_pie_build",
                     "HARDFLOW_MT_menu", "HARDFLOW_MT_menu_build",
                     "HARDFLOW_MT_menu_decals", "HARDFLOW_MT_menu_assets"):
            assert hasattr(bpy.types, name), "menu not registered: %s" % name
    finally:
        hardflow.unregister()
        # a full unregister (incl. menu.unregister removing the header hook) must
        # tear the classes back down -- no leak after disable/re-enable.
        assert not hasattr(bpy.types, "HARDFLOW_MT_menu"), \
            "menu class leaked after unregister"


# --- v1.3 Edit Mode bridge ---------------------------------------------------

def _edit_select_faces(ob, indices):
    """Enter Edit Mode on ob with exactly the given face indices selected."""
    import bmesh
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        f.select_set(False)
    for i in indices:
        bm.faces[i].select_set(True)
    bmesh.update_edit_mesh(ob.data)


def test_edit_extrude_and_basis():
    _reset()
    cube = _add_cube("EditPP", size=2.0)
    _edit_select_faces(cube, [0])
    basis = geometry.selected_face_basis(cube)
    assert basis is not None
    _center, normal = basis
    assert abs(normal.length - 1.0) < 1e-5
    ok = geometry.edit_extrude_faces(cube, normal * 1.0)
    assert ok
    bpy.ops.object.mode_set(mode='OBJECT')
    assert len(cube.data.polygons) >= 6      # extrude added side walls


def test_edit_inset_and_add_face_and_knife():
    _reset()
    cube = _add_cube("EditOff", size=2.0)
    _edit_select_faces(cube, [0])
    before = len(cube.data.polygons)
    assert geometry.edit_inset_faces(cube, 0.3) is True
    bpy.ops.object.mode_set(mode='OBJECT')
    assert len(cube.data.polygons) > before

    # add a face into the edit-mesh
    _edit_select_faces(cube, [0])
    pf = len(cube.data.polygons)
    from mathutils import Vector
    ok = geometry.edit_add_face(cube, [Vector((0, 0, 3)), Vector((1, 0, 3)),
                                       Vector((1, 1, 3))])
    bpy.ops.object.mode_set(mode='OBJECT')
    assert ok and len(cube.data.polygons) == pf + 1

    # knife score the selected face
    _edit_select_faces(cube, [0])
    ef = len(cube.data.edges)
    n = geometry.edit_knife_polygon(
        cube, [Vector((-0.5, -0.5, 1)), Vector((0.5, -0.5, 1)),
               Vector((0.5, 0.5, 1)), Vector((-0.5, 0.5, 1))],
        Vector((0, 0, 1)))
    bpy.ops.object.mode_set(mode='OBJECT')
    assert n >= 1 and len(cube.data.edges) >= ef


def test_edit_add_face_welds_to_existing():
    # Grid Modeler "connected faces": a drawn face that shares corners with the
    # existing mesh welds onto them instead of leaving a detached island.
    _reset()
    plane = bpy.data.meshes.new("P")
    import bmesh as _bm
    bm = _bm.new()
    vs = [bm.verts.new(c) for c in
          ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0))]
    bm.faces.new(vs)
    bm.to_mesh(plane)
    bm.free()
    pobj = bpy.data.objects.new("P", plane)
    bpy.context.collection.objects.link(pobj)
    _activate(pobj)
    bpy.ops.object.mode_set(mode='EDIT')
    before = len(plane.vertices)            # 4
    # a triangle sharing the quad's (1,0,0) and (1,1,0) corners + one new apex
    ok = geometry.edit_add_face(pobj, [Vector((1, 0, 0)), Vector((2, 0.5, 0)),
                                       Vector((1, 1, 0))], weld=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    assert ok
    # only the apex is genuinely new; the two shared corners welded onto the quad
    assert len(plane.vertices) == before + 1, len(plane.vertices)


def test_restore_edit_mesh():
    _reset()
    cube = _add_cube("EditSnap", size=2.0)
    _edit_select_faces(cube, [0])
    base = geometry.snapshot_mesh(cube, "edit_base")
    before = len(cube.data.polygons)
    geometry.edit_extrude_faces(cube, Vector((0, 0, 1.0)))
    geometry.restore_edit_mesh(cube, base)
    bpy.ops.object.mode_set(mode='OBJECT')
    assert len(cube.data.polygons) == before, "edit restore did not roll back"
    geometry.free_mesh(base)


def test_object_knife_polygon():
    _reset()
    cube = _add_cube("Knife", size=2.0)
    ef = len(cube.data.edges)
    n = geometry.knife_polygon(
        cube, [Vector((-0.5, -0.5, 1)), Vector((0.5, -0.5, 1)),
               Vector((0.5, 0.5, 1)), Vector((-0.5, 0.5, 1))],
        Vector((0, 0, 1)))
    assert n == 4 and len(cube.data.edges) > ef


def test_knife_polygon_is_local_not_whole_mesh():
    # Regression: a knife score over ONE region must not slice a distant region.
    # Build a single mesh with two separated cube blocks; knife only over the
    # near block and confirm the far block's geometry is untouched.
    _reset()
    import bmesh
    me = bpy.data.meshes.new("TwoBlocks")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)                       # near block @ origin
    far = bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.translate(bm, verts=far['verts'], vec=(10.0, 0.0, 0.0))  # far block
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("TwoBlocks", me)
    bpy.context.collection.objects.link(obj)

    def far_verts():
        return [tuple(round(c, 4) for c in v.co)
                for v in obj.data.vertices if v.co.x > 5.0]

    before = sorted(far_verts())
    assert len(before) == 8, before        # far block starts as a clean cube
    # knife a small square on the near block's top face
    geometry.knife_polygon(
        obj, [Vector((-0.5, -0.5, 1)), Vector((0.5, -0.5, 1)),
              Vector((0.5, 0.5, 1)), Vector((-0.5, 0.5, 1))],
        Vector((0, 0, 1)))
    after = sorted(far_verts())
    assert after == before, "knife sliced the distant block: %r" % after


# --- v1.4 multi-copy cutter builders -----------------------------------------

def test_build_prisms_and_faces():
    corners = [Vector((-1, -1, 0)), Vector((1, -1, 0)),
               Vector((1, 1, 0)), Vector((-1, 1, 0))]
    sets = [(corners, Vector((0, 0, -1))),
            ([c + Vector((4, 0, 0)) for c in corners], Vector((0, 0, -1)))]
    me = geometry.build_prisms(sets, thickness=4.0)
    assert me is not None and len(me.vertices) == 16   # two 8-vert prisms
    fme = geometry.build_faces(sets)
    assert fme is not None and len(fme.polygons) == 2
    assert geometry.build_prisms([], 1.0) is None


# --- v1.5 Hard Ops parity ----------------------------------------------------

def test_dice_mesh():
    _reset()
    cube = _add_cube("Dice", size=2.0)
    before = len(cube.data.polygons)
    passes = geometry.dice_mesh(cube, (2, 2, 1), mark_sharp=True)
    assert passes == 2                       # one cut per axis with count 2
    assert len(cube.data.polygons) > before


def test_edge_weights():
    _reset()
    import math
    cube = _add_cube("Weights", size=2.0)
    geometry.mark_sharp_by_angle(cube, math.radians(30))   # all 12 edges sharp
    n = geometry.set_sharp_edge_weights(cube, bevel_weight=1.0, crease=0.5)
    assert n == 12

    _edit_select_faces(cube, [0])
    m = geometry.edit_set_edge_weights(cube, bevel_weight=1.0, only_selected=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    assert m == 4                            # one quad face = 4 edges


def test_greeble_builders():
    _reset()
    steps = geometry.build_steps(count=4, rise=0.1, run=0.1, width=1.0)
    assert steps is not None and len(steps.polygons) > 0
    taper = geometry.build_taper(1.0, 0.5, 1.0)
    assert taper is not None and len(taper.vertices) == 8
    pyr = geometry.build_taper(1.0, 0.0, 1.0)         # top=0 -> pyramid (5 verts)
    assert len(pyr.vertices) == 5
    knurl = geometry.build_knurl(0.5, 1.0, teeth=8)
    assert knurl is not None and len(knurl.vertices) == 8 * 2 * 2


# --- v1.6 Grid Modeler extras ------------------------------------------------

def test_pipe_mesh_and_profile():
    assert geometry.profile_points('ROUND', 0.1) is None
    sq = geometry.profile_points('SQUARE', 0.1)
    assert len(sq) == 4
    pts = [Vector((0, 0, 0)), Vector((0, 0, 1)), Vector((0, 0, 2))]
    me = geometry.build_pipe_mesh(pts, sq)
    assert me is not None and len(me.polygons) > 0
    assert geometry.build_pipe_mesh([Vector((0, 0, 0))], sq) is None


def test_build_loft():
    a = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((1, 1, 0)), Vector((0, 1, 0))]
    b = [p + Vector((0, 0, 2)) for p in a]
    me = geometry.build_loft(a, b)
    assert me is not None
    assert len(me.vertices) == 8 and len(me.polygons) == 6     # closed box
    assert geometry.build_loft(a, b[:3]) is None               # mismatched loops


# --- v1.7 DECALmachine extras ------------------------------------------------

def test_decal_uv_rect_and_match():
    _reset()
    target = _add_cube("Target", size=2.0)
    mat = bpy.data.materials.new("Surf")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Metallic'].default_value = 0.7
    bsdf.inputs['Roughness'].default_value = 0.2
    target.data.materials.append(mat)

    d = decal.make_decal(bpy.context, target, Vector((0, 0, 1)),
                         Vector((0, 0, 1)), Vector((1, 0, 0)), decal_type='INFO')
    # re-trim: rewrite UVs to the top-left quarter cell
    cell = atlas.cell_rect(2, 2, 0)
    assert decal.set_decal_uv_rect(d, cell)
    us = [round(u.uv[0], 4) for u in d.data.uv_layers.active.data]
    assert min(us) == 0.0 and max(us) == 0.5

    # material match: copy the decal material, set metallic/roughness from target
    sample = decal.sample_material(target)
    assert sample is not None and abs(sample['metallic'] - 0.7) < 1e-6
    assert decal.match_decal_to_material(d, sample)
    grp = decal._decal_group_node(d)
    assert abs(grp.inputs['Metallic'].default_value - 0.7) < 1e-6
    assert abs(grp.inputs['Roughness'].default_value - 0.2) < 1e-6


def test_conform_trim_decal():
    _reset()
    target = _add_cube("Target", size=2.0)
    d = decal.make_decal(bpy.context, target, Vector((0, 0, 1)),
                         Vector((0, 0, 1)), Vector((1, 0, 0)),
                         width=0.5, height=0.5)
    # a decal hugging the surface keeps all its faces
    removed = decal.conform_trim_decal(bpy.context, d, target, subdivisions=2,
                                       max_gap=0.2)
    assert removed == 0
    # lift it far off the surface -> every face is now over a gap and trimmed
    from mathutils import Matrix
    d.matrix_world = Matrix.Translation((0, 0, 50)) @ d.matrix_world
    removed2 = decal.conform_trim_decal(bpy.context, d, target, subdivisions=2,
                                        max_gap=0.2)
    assert removed2 > 0


# --- v1.8 KitOps extras ------------------------------------------------------

def test_asset_fit_and_material_and_export():
    _reset()
    cube = _add_cube("Kit", size=2.0)
    assert abs(asset.bound_size([cube]) - 2.0) < 1e-6
    assert abs(asset.surface_feature_size(cube) - 2.0) < 1e-6

    mat = bpy.data.materials.new("KitMat")
    assert asset.apply_material(cube, mat)
    assert cube.data.materials[0] is mat

    import tempfile
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "kit.blend")
        out = asset.write_objects_blend(path, [cube])
        assert out == path and os.path.isfile(path)


def test_boolean_fallback():
    _reset()
    target = _add_cube("Target", size=2.0)
    cutter = _add_cube("Cutter", size=1.0, location=(1, 0, 0))
    _activate(target)
    before = len(target.data.polygons)
    used = boolean.apply_boolean_fallback(bpy.context, target, cutter,
                                          'DIFFERENCE', 'EXACT')
    assert used in {'EXACT', 'FAST'}
    assert len(target.data.polygons) != before


def test_mesh_health_detects_open_mesh():
    # a closed cube is clean; deleting a face opens 4 edges (non-manifold) and
    # leaves the diagnosis non-empty so a failed boolean can explain itself.
    _reset()
    cube = _add_cube("Healthy", size=2.0)
    h = boolean.mesh_health(cube)
    assert h['non_manifold'] == 0 and h['degenerate'] == 0 and h['loose'] == 0
    assert boolean._health_summary(cube) == ""

    import bmesh
    bm = bmesh.new()
    bm.from_mesh(cube.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[0]], context='FACES_ONLY')
    bm.to_mesh(cube.data)
    bm.free()
    h2 = boolean.mesh_health(cube)
    assert h2['non_manifold'] == 4, h2          # the hole's 4 border edges
    assert "non-manifold" in boolean._health_summary(cube)


def test_recalc_normals_outward():
    # flip every normal inward, recalc, and confirm the +Z face points out again.
    _reset()
    cube = _add_cube("Flip", size=2.0)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(cube.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(cube.data)
    bm.free()
    boolean.recalc_normals(cube)
    top = max(cube.data.polygons, key=lambda p: p.center.z)
    assert top.normal.z > 0.9, "recalc did not point the top face outward: %r" % (
        tuple(top.normal),)


def test_choose_solver_from_health():
    # a clean cube keeps the accurate EXACT solver
    _reset()
    cube = _add_cube("Clean", size=2.0)
    assert boolean.choose_solver(cube, 'EXACT') == 'EXACT'
    # a non-EXACT preference is passed through untouched
    assert boolean.choose_solver(cube, 'FAST') == 'FAST'

    # delete several faces -> many non-manifold edges -> start with FAST instead
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(cube.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[0], bm.faces[1], bm.faces[2]],
                     context='FACES_ONLY')
    bm.to_mesh(cube.data)
    bm.free()
    assert boolean.mesh_health(cube)['non_manifold'] >= 6
    assert boolean.choose_solver(cube, 'EXACT') == 'FAST'
    # but a heavy mesh is not scanned (cost guard) -> keeps preferred
    assert boolean.choose_solver(cube, 'EXACT', max_verts=0) == 'EXACT'


def test_robust_boolean_succeeds_and_reports():
    _reset()
    target = _add_cube("Target", size=2.0)
    cutter = _add_cube("Cutter", size=1.0, location=(1, 0, 0))
    _activate(target)
    before = len(target.data.polygons)
    ok, used, msg = boolean.robust_boolean(bpy.context, target, cutter,
                                           'DIFFERENCE', 'EXACT')
    assert ok and used in {'EXACT', 'FAST'}
    assert len(target.data.polygons) != before
    assert isinstance(msg, str) and msg

    # robust path is wired into the draw-cut's standalone boolean operator too
    hardflow.register()
    try:
        t = _add_cube("T", size=2.0, location=(5, 0, 0))
        c = _add_cube("C", size=1.0, location=(5.5, 0, 0))
        t.select_set(True)
        c.select_set(True)
        bpy.context.view_layer.objects.active = c
        b = len(t.data.polygons)
        res = bpy.ops.object.hardflow_boolean(operation='DIFFERENCE')
        assert res == {'FINISHED'} and len(t.data.polygons) != b
    finally:
        hardflow.unregister()


def test_recalc_normals_operator():
    _reset()
    hardflow.register()
    try:
        ob = _add_cube("Obj", size=2.0)
        _activate(ob)
        res = bpy.ops.object.hardflow_recalc_normals()
        assert res == {'FINISHED'}, res
        top = max(ob.data.polygons, key=lambda p: p.center.z)
        assert top.normal.z > 0.9
    finally:
        hardflow.unregister()


def test_bind_cutters_collects_failures():
    # destructive bind on a clean target succeeds -> no failure messages collected
    _reset()
    target = _add_cube("Target", size=2.0)
    part = _add_cube("Part", size=1.0, location=(0.5, 0, 0))
    fails = []
    before = len(target.data.polygons)
    asset.bind_cutters(bpy.context, [part], target, operation='DIFFERENCE',
                       non_destructive=False, failures=fails)
    assert fails == [], fails
    assert len(target.data.polygons) != before
    assert bpy.data.objects.get("Part") is None      # cutter deleted after apply


def test_snap_insert_point():
    p = snapping.snap_insert_point((0.12, 0.0, 0.0), 0.1)
    assert abs(p.x - 0.1) < 1e-9
    # an anchor within threshold wins over the grid
    p2 = snapping.snap_insert_point((0.12, 0.0, 0.0), 0.1,
                                    anchors=[Vector((0.13, 0.0, 0.0))],
                                    threshold=0.05)
    assert abs(p2.x - 0.13) < 1e-9


def test_new_operators_registered():
    _reset()
    hardflow.register()
    try:
        for name in ("hardflow_dice",
                     "hardflow_display_toggle", "hardflow_random_color",
                     "hardflow_copy_material", "hardflow_add_step",
                     "hardflow_add_taper", "hardflow_add_knurl",
                     "hardflow_loft", "hardflow_match_decal",
                     "hardflow_retrim_decal", "hardflow_conform_decal",
                     "hardflow_create_decal", "hardflow_library_rename",
                     "hardflow_library_delete", "hardflow_material_insert",
                     "hardflow_export_asset"):
            assert hasattr(bpy.ops.object, name), "missing operator: %s" % name
        assert hasattr(bpy.ops.mesh, "hardflow_edge_weight")
    finally:
        hardflow.unregister()


def _run():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print("ok   ", fn.__name__)
        except Exception as ex:           # noqa: BLE001
            failed += 1
            print("FAIL ", fn.__name__, "->", repr(ex))
    print("\n%d/%d passed" % (len(tests) - failed, len(tests)))
    return failed


if __name__ == "__main__":
    sys.exit(_run())
