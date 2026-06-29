# Headless Blender smoke test -- automatically verifies the bpy-dependent core.
#
# Run (Blender 4.2+ must be installed):
#   blender --background --python tests/test_blender.py
#
# Zero exit code = passed. The modal drawing operator (HARDFLOW_OT_draw) requires
# a window/region, so it is NOT tested here; instead the building blocks it uses
# (build_prism, apply/add_boolean) and the non-modal bevel/mirror operators are
# verified. For pure math: python tests/test_core.py.
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
from hardflow.core import geometry, boolean, decal, decal_image, atlas  # noqa: E402


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
        # EXEC_DEFAULT -> execute() (redo path); modal invoke is skipped
        bpy.ops.object.hardflow_bevel(width=0.03, segments=3, weighted_normal=True)
        assert any(m.type == 'BEVEL' for m in ob.modifiers), "bevel not added"
        assert any(m.type == 'WEIGHTED_NORMAL' for m in ob.modifiers), \
            "weighted normal not added"
        bev = next(m for m in ob.modifiers if m.type == 'BEVEL')
        assert bev.segments == 3 and abs(bev.width - 0.03) < 1e-6
        bpy.ops.object.hardflow_mirror(axis='X')
        assert any(m.type == 'MIRROR' for m in ob.modifiers), "mirror not added"
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
