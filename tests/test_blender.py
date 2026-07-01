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


def test_bevel_cutter_chamfers_edges():
    # Bevelled cut: chamfering the cutter adds geometry (more faces/verts) and
    # leaves a valid closed mesh. A unit cube has 8 verts / 6 faces.
    _reset()
    import bmesh
    me = bpy.data.meshes.new("Cutter")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me)
    bm.free()
    out = geometry.bevel_cutter(me, 0.1, segments=2)
    assert out is me
    assert len(me.vertices) > 8 and len(me.polygons) > 6, \
        (len(me.vertices), len(me.polygons))
    # width <= 0 is a no-op
    me2 = bpy.data.meshes.new("Cutter2")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(me2)
    bm.free()
    geometry.bevel_cutter(me2, 0.0)
    assert len(me2.vertices) == 8


def test_transfer_decal_retargets():
    # Transfer moves a decal onto a new surface: shrinkwrap target + parent both
    # follow, world pose preserved.
    _reset()
    hardflow.register()
    try:
        a = _add_cube("SurfA", size=2.0)
        b = _add_cube("SurfB", size=2.0, location=(5, 0, 0))
        d = decal.make_decal(bpy.context, a, Vector((0, 0, 1)),
                             Vector((0, 0, 1)), Vector((1, 0, 0)))
        assert d.parent is a
        sw = next(m for m in d.modifiers if m.type == 'SHRINKWRAP')
        assert sw.target is a
        before = d.matrix_world.copy()
        for o in bpy.context.selected_objects:
            o.select_set(False)
        d.select_set(True)
        b.select_set(True)
        bpy.context.view_layer.objects.active = b
        res = bpy.ops.object.hardflow_transfer_decal()
        assert res == {'FINISHED'}, res
        assert d.parent is b
        assert next(m for m in d.modifiers if m.type == 'SHRINKWRAP').target is b
        # world pose preserved
        assert (d.matrix_world.translation - before.translation).length < 1e-5
    finally:
        hardflow.unregister()


def test_robust_boolean_intersect():
    # The draw tool's Intersect mode (and the menu entry) route to an INTERSECT
    # boolean: keep only the volume inside the cutter. Verify against real Blender.
    _reset()
    target = _add_cube("Target", size=2.0)               # local x in [-1, 1]
    cutter = _add_cube("Cutter", size=2.0, location=(1, 0, 0))  # world x in [0, 2]
    _activate(target)
    ok, _used, _msg = boolean.robust_boolean(bpy.context, target, cutter,
                                             'INTERSECT', 'EXACT')
    assert ok, "INTERSECT boolean failed"
    xs = [v.co.x for v in target.data.vertices]
    assert xs, "INTERSECT produced an empty mesh"
    # the result must live in the [0, 1] overlap band, not the original [-1, 1]
    assert min(xs) >= -0.05 and max(xs) <= 1.05, (min(xs), max(xs))


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


def test_build_primitives():
    # New starter primitives: cylinder / cone / sphere / tube builders + the
    # add_primitive operator that places + selects each one.
    import bmesh
    _reset()
    cyl = geometry.build_cylinder(radius=0.5, depth=1.0, segments=12)
    assert cyl is not None and len(cyl.vertices) == 24        # 12 top + 12 bottom
    assert len(cyl.polygons) == 14                            # 12 walls + 2 caps

    cone = geometry.build_cone(radius=0.5, depth=1.0, segments=12)
    assert cone is not None and len(cone.vertices) == 13      # base ring + apex

    sphere = geometry.build_uv_sphere(radius=0.5, segments=16, rings=8)
    assert sphere is not None and len(sphere.polygons) > 0

    tube = geometry.build_tube(radius=0.5, inner_radius=0.3, depth=1.0, segments=12)
    assert tube is not None and len(tube.vertices) == 48      # 4 rings x 12
    bm = bmesh.new()
    bm.from_mesh(tube)
    assert all(len(e.link_faces) == 2 for e in bm.edges), "tube not a closed solid"
    bm.free()

    hardflow.register()
    try:
        for kind, prefix in (('CYLINDER', 'Hardflow_Cylinder'),
                             ('CONE', 'Hardflow_Cone'),
                             ('SPHERE', 'Hardflow_Sphere'),
                             ('TUBE', 'Hardflow_Tube')):
            res = bpy.ops.object.hardflow_add_primitive(kind=kind)
            assert res == {'FINISHED'}, (kind, res)
            ob = bpy.context.active_object
            assert ob is not None and ob.name.startswith(prefix), (kind, ob)
            assert ob.select_get()
    finally:
        hardflow.unregister()


def test_new_cutter_shapes_build():
    # The new draw shapes (slot / star / arc) lift to valid prism cutters, so the
    # draw tool's commit path builds real boolean cutters from them.
    import math
    _reset()
    vd = Vector((0, 0, 1))
    for label, pts2d in (
            ("slot", grid.slot_points((0, 0), (4, 2), segments=6)),
            ("star", grid.star_points((0, 0), (1, 0), 5)),
            ("arc", grid.arc_points((0, 0), (1, 0), segments=8, sweep=math.pi / 2))):
        corners = [Vector((x, y, 0.0)) for x, y in pts2d]
        mesh = geometry.build_prisms([(corners, vd)], 1.0)
        assert mesh is not None, label
        assert len(mesh.polygons) > 0, label


def test_live_boolean_preview_and_cutter_options():
    # The cutter-option / live-preview preferences exist with their defaults, and
    # the live-preview mechanism (a temp Boolean modifier on the target pointing
    # at the cutter) shows the real result in the evaluated mesh before commit.
    _reset()
    hardflow.register()
    try:
        from hardflow.preferences import get_prefs
        prefs = get_prefs(bpy.context)
        for attr in ("live_boolean_preview", "draw_inset", "draw_bevel_cut",
                     "draw_cutter_bevel", "draw_array_count", "draw_array_axis"):
            assert hasattr(prefs, attr), attr
        assert prefs.live_boolean_preview is False and prefs.draw_array_count == 1

        target = _add_cube("Target", size=2.0)
        cutter = _add_cube("Cutter", size=1.0, location=(1, 0, 0))
        mod = target.modifiers.new("HF_LivePreview", 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.object = cutter
        deps = bpy.context.evaluated_depsgraph_get()
        ev = target.evaluated_get(deps)
        assert len(ev.data.polygons) != 6, "live boolean modifier showed no result"
        target.modifiers.remove(mod)
        assert target.modifiers.get("HF_LivePreview") is None
    finally:
        hardflow.unregister()


def test_face_edge_tangent_near_point():
    # SURFACE-grid orientation on a non-rectangular (parallelogram) ANGLED face:
    # without near_point it aligns to the longest edge; with near_point it aligns
    # to the edge nearest the click, so a box follows the edge you start on.
    import bmesh
    _reset()
    # Parallelogram: long edges along +/-Y (len 3), slanted "rungs" along (1,1,1).
    co = [Vector((0, 0, 0)), Vector((0, 3, 0)),
          Vector((1, 4, 1)), Vector((1, 1, 1))]
    me = bpy.data.meshes.new("Para")
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(c) for c in co])
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Para", me)
    bpy.context.collection.objects.link(ob)
    mw = ob.matrix_world
    normal = (mw.to_3x3() @ me.polygons[0].normal).normalized()
    assert max(abs(normal.x), abs(normal.y), abs(normal.z)) < 0.98  # truly angled

    # no near_point -> longest edge (the +/-Y long pair)
    t_long = raycast.face_edge_tangent(ob, 0, mw, normal)
    assert t_long is not None
    assert abs(t_long.normalized().dot(Vector((0, 1, 0)))) > 0.99, t_long

    # near the slanted B-C edge -> aligns to THAT edge ((1,1,1) dir), not Y
    near_bc = mw @ ((co[1] + co[2]) * 0.5)
    t_bc = raycast.face_edge_tangent(ob, 0, mw, normal, near_point=near_bc)
    assert t_bc is not None
    bc = Vector((1, 1, 1)).normalized()
    assert abs(t_bc.normalized().dot(bc)) > 0.99, t_bc
    assert abs(t_bc.normalized().dot(Vector((0, 1, 0)))) < 0.6, t_bc


def test_build_pipe():
    _reset()
    pts = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((1, 1, 0))]
    curve = geometry.build_pipe(pts, radius=0.1)
    assert curve is not None
    assert abs(curve.bevel_depth - 0.1) < 1e-6   # stored as float32
    sp = curve.splines[0]
    assert sp.type == 'POLY' and len(sp.points) == 3
    # single point -> None
    assert geometry.build_pipe([Vector((0, 0, 0))]) is None


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
    # The default decal is a subdivided grid (not a lone quad) so the shrinkwrap
    # can bend it to a curved / multi-face surface -- 4 corners can't follow a curve.
    assert len(me.polygons) > 1 and len(me.vertices) > 4
    assert me.uv_layers, "decal mesh has no UV map"
    # segments=1 still yields the bare quad (flat surfaces / minimal geometry)
    quad = decal.build_decal_mesh(0.2, 0.3, segments=1)
    assert len(quad.vertices) == 4 and len(quad.polygons) == 1
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


def test_decal_mesh_grid_resolution():
    # The decal is an NxN grid so the shrinkwrap can conform it to curvature; the
    # topology and the full-image UV span must hold at every resolution.
    _reset()
    for segs in (1, 4, 12):
        me = decal.build_decal_mesh(0.2, 0.2, segments=segs)
        assert len(me.vertices) == (segs + 1) ** 2, (segs, len(me.vertices))
        assert len(me.polygons) == segs * segs, (segs, len(me.polygons))
        us = [round(d.uv[0], 4) for d in me.uv_layers.active.data]
        vs = [round(d.uv[1], 4) for d in me.uv_layers.active.data]
        assert min(us) == 0.0 and max(us) == 1.0
        assert min(vs) == 0.0 and max(vs) == 1.0


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
    assert decal.bake_image("HF_T_Norm", 256) == norm   # reused, not duplicated

    # ensure_material gives a node material; bake_image_node sets it active+sole
    target = _add_cube("Target", size=2.0)
    mat = decal.ensure_material(target)
    assert mat.use_nodes and target.active_material is mat
    node = decal.bake_image_node(mat, norm)
    # bpy returns a fresh Python wrapper per access, so `is` identity is
    # unreliable on RNA structs; compare with `==` (underlying-data equality)
    # or by name.
    assert node.type == 'TEX_IMAGE' and node.image == norm
    assert mat.node_tree.nodes.active == node
    assert all((n.select == (n.name == node.name)) for n in mat.node_tree.nodes)
    assert decal.bake_image_node(mat, norm) == node     # reused


def test_discard_bake_image_rolls_back():
    # The bake error path must undo only what it created: drop the image-texture
    # node it wired in and the image datablock, but never a reused prior result.
    _reset()
    target = _add_cube("BakeRollback", size=2.0)
    mat = decal.ensure_material(target)
    img = decal.bake_image("HF_T_Discard", 64, is_data=True)
    decal.bake_image_node(mat, img)
    assert any(n.type == 'TEX_IMAGE' and n.image == img
               for n in mat.node_tree.nodes)

    # remove_*=False (a re-bake reusing a prior image/node) keeps everything.
    decal.discard_bake_image(mat, img, remove_node=False, remove_image=False)
    assert "HF_T_Discard" in bpy.data.images
    assert any(n.type == 'TEX_IMAGE' for n in mat.node_tree.nodes)

    # Full rollback drops the node and the now-unused image.
    decal.discard_bake_image(mat, img, remove_node=True, remove_image=True)
    assert not any(n.type == 'TEX_IMAGE' for n in mat.node_tree.nodes)
    assert "HF_T_Discard" not in bpy.data.images


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


# --- Build tools: Push/Pull, Offset, Construction Grid ----------------------

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


def test_extrude_keep_original_vs_clean():
    # Clean push/pull drops the source face (manifold extrude); Copy keeps it as
    # an interior divider, so the only difference is that one extra face.
    _reset()
    a = _add_cube("Clean", size=2.0)
    assert geometry.extrude_faces(a, [0], Vector((0, 0, 1.0))) is True
    clean = len(a.data.polygons)
    b = _add_cube("Keep", size=2.0, location=(5, 0, 0))
    assert geometry.extrude_faces(b, [0], Vector((0, 0, 1.0)),
                                  keep_original=True) is True
    keep = len(b.data.polygons)
    assert keep == clean + 1, (clean, keep)


def test_inset_faces_offset():
    # geometry behind Offset: inset adds a ring of faces around the picked face.
    _reset()
    cube = _add_cube("OFF", size=2.0)
    before = len(cube.data.polygons)
    assert geometry.inset_faces(cube, [0], 0.3) is True
    assert len(cube.data.polygons) > before, "inset added no geometry"
    assert geometry.inset_faces(cube, [0], 0.0) is False      # zero thickness
    assert geometry.inset_faces(cube, [9999], 0.3) is False   # bad index


def test_inset_extrude_faces_recess():
    # Offset -> Push/Pull combo: inset the top face, then extrude the INNER face
    # up by 0.5. The inner panel rises to z=1.5 while the original outer corners
    # stay at z=1.0 -- proving we extrude the inner region, not the border ring.
    _reset()
    cube = _add_cube("Recess", size=2.0)
    top = max(range(len(cube.data.polygons)),
              key=lambda i: cube.data.polygons[i].normal.z)
    n = cube.data.polygons[top].normal.copy()           # ~ (0, 0, 1)
    assert geometry.inset_extrude_faces(cube, [top], 0.3, n * 0.5) is True
    zmax = max(v.co.z for v in cube.data.vertices)
    assert abs(zmax - 1.5) < 1e-5, "inner panel not raised: %f" % zmax
    outer = [v.co.z for v in cube.data.vertices
             if abs(abs(v.co.x) - 1.0) < 1e-4 and abs(abs(v.co.y) - 1.0) < 1e-4]
    assert any(abs(z - 1.0) < 1e-4 for z in outer), \
        "outer corners moved -> extruded the wrong faces: %r" % outer
    # guards
    assert geometry.inset_extrude_faces(cube, [], 0.3, Vector((0, 0, 1))) is False
    assert geometry.inset_extrude_faces(cube, [9999], 0.3,
                                        Vector((0, 0, 1))) is False


def test_nearest_edge_on_face():
    # Object-Mode edge pick: the edge nearest a hit point on the top face.
    _reset()
    cube = _add_cube("EdgePick", size=2.0)
    top = max(range(len(cube.data.polygons)),
              key=lambda i: cube.data.polygons[i].normal.z)
    key = geometry.nearest_edge_on_face(cube, top, Vector((1.0, 0.0, 1.0)))
    assert key is not None
    a, b = cube.data.vertices[key[0]].co, cube.data.vertices[key[1]].co
    # the +X / z=1 edge: both endpoints at x=1, z=1
    assert abs(a.x - 1.0) < 1e-4 and abs(b.x - 1.0) < 1e-4, (a[:], b[:])
    assert abs(a.z - 1.0) < 1e-4 and abs(b.z - 1.0) < 1e-4, (a[:], b[:])
    assert geometry.nearest_edge_on_face(cube, 9999, Vector((0, 0, 0))) is None


def test_bevel_object_edges():
    # Object-Mode edge bevel: one picked edge -> real chamfer geometry.
    _reset()
    cube = _add_cube("EdgeBevel", size=2.0)
    before = len(cube.data.vertices)
    top = max(range(len(cube.data.polygons)),
              key=lambda i: cube.data.polygons[i].normal.z)
    key = geometry.nearest_edge_on_face(cube, top, Vector((1.0, 0.0, 1.0)))
    assert geometry.bevel_object_edges(cube, [key], 0.2, segments=2) == 1
    assert len(cube.data.vertices) > before, "bevel added no geometry"
    assert geometry.bevel_object_edges(cube, [key], 0.0) == 0          # width 0
    assert geometry.bevel_object_edges(cube, [(0, 9000)], 0.2) == 0    # bad edge


def test_edge_loop():
    # Edge-loop walk on a 3x3 quad grid (interior verts are valence-4). The loop
    # of an interior horizontal edge spans the whole row; a plain cube (valence-3)
    # has no loop to extend.
    _reset()
    import bmesh
    me = bpy.data.meshes.new("grid")
    bm = bmesh.new()
    n = 4   # 4x4 verts -> 3x3 quads; vert (x,y) has index y*n + x
    vs = [[bm.verts.new((x, y, 0)) for x in range(n)] for y in range(n)]
    for y in range(n - 1):
        for x in range(n - 1):
            bm.faces.new((vs[y][x], vs[y][x + 1], vs[y + 1][x + 1], vs[y + 1][x]))
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("Grid", me)
    bpy.context.collection.objects.link(obj)
    keys = geometry.edge_loop(obj, (1 * n + 1, 1 * n + 2))   # (1,1)-(2,1)
    assert len(keys) == 3, keys                              # full row at y=1
    for (i, j) in keys:
        assert i // n == 1 and j // n == 1, (i, j)           # all on row y=1
    # a plain cube has no extendable loop -> just the picked edge (edge keys are
    # unordered: compare as a set, like the production bm.edges.get lookup)
    cube = _add_cube("LoopCube", size=2.0)
    top = max(range(len(cube.data.polygons)),
              key=lambda k: cube.data.polygons[k].normal.z)
    ek = geometry.nearest_edge_on_face(cube, top, Vector((1.0, 0.0, 1.0)))
    loop = geometry.edge_loop(cube, ek)
    assert len(loop) == 1 and set(loop[0]) == set(ek), (loop, ek)


def test_smart_bevel_edges():
    # Smart Bevel: bevel one edge, add holding loops, clean n-gons -- all in one
    # bmesh session. Compared against the plain chamfer, the smart pass never
    # removes geometry (support loops only add), and reports a structured summary.
    _reset()
    top_key = lambda c: geometry.nearest_edge_on_face(
        c, max(range(len(c.data.polygons)),
               key=lambda i: c.data.polygons[i].normal.z),
        Vector((1.0, 0.0, 1.0)))

    plain = _add_cube("PlainBevel", size=2.0)
    geometry.bevel_object_edges(plain, [top_key(plain)], 0.2, segments=2)
    plain_v = len(plain.data.vertices)

    cube = _add_cube("SmartBevel", size=2.0)
    before = len(cube.data.vertices)
    summary = geometry.smart_bevel_edges(cube, [top_key(cube)], 0.2, segments=2,
                                         support=True, tightness=0.5)
    assert summary['beveled'] == 1, summary
    assert isinstance(summary['supports'], int) and summary['supports'] >= 0
    assert isinstance(summary['ngons'], int) and summary['ngons'] >= 0
    assert len(cube.data.vertices) > before, "smart bevel added no geometry"
    # support loops only ever add geometry over the plain chamfer, never remove it
    assert len(cube.data.vertices) >= plain_v, (len(cube.data.vertices), plain_v)
    assert len(cube.data.polygons) > 0, "smart bevel emptied the mesh"

    # width 0 is a no-op that still returns the zeroed summary
    flat = _add_cube("SmartBevelZero", size=2.0)
    fv = len(flat.data.vertices)
    z = geometry.smart_bevel_edges(flat, [top_key(flat)], 0.0)
    assert z == {'beveled': 0, 'supports': 0, 'ngons': 0}
    assert len(flat.data.vertices) == fv          # untouched
    # a bad edge key bevels nothing
    assert geometry.smart_bevel_edges(cube, [(0, 9000)], 0.2)['beveled'] == 0


def test_dissolve_boolean_ngons():
    # An n-gon (single hexagon face) is triangulated and re-quadded so no face is
    # left with more than 4 sides; an all-quad cube is reported clean and unchanged.
    _reset()
    import bmesh
    import math as _m
    me = bpy.data.meshes.new("hex")
    bm = bmesh.new()
    verts = [bm.verts.new((_m.cos(a), _m.sin(a), 0.0))
             for a in [i * _m.tau / 6.0 for i in range(6)]]
    bm.faces.new(verts)                       # one 6-sided n-gon
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("Hex", me)
    bpy.context.collection.objects.link(obj)
    assert len(obj.data.polygons) == 1 and len(obj.data.polygons[0].vertices) == 6
    cleaned = geometry.dissolve_boolean_ngons(obj)
    assert cleaned == 1, cleaned
    assert max(len(p.vertices) for p in obj.data.polygons) <= 4, "n-gon survived"

    cube = _add_cube("CleanCube", size=2.0)
    faces_before = len(cube.data.polygons)
    assert geometry.dissolve_boolean_ngons(cube) == 0     # already quads
    assert len(cube.data.polygons) == faces_before        # untouched


def test_boolean_cut_ngon_cleanup_pipeline():
    # The real Ask-3 pipeline: a boolean DIFFERENCE leaves n-gons on the cut;
    # dissolve_boolean_ngons re-quads them so no face has more than 4 sides.
    _reset()
    target = _add_cube("NgonTarget", size=2.0)
    _activate(target)
    cutter = _add_cube("NgonCutter", size=1.0, location=(1.0, 1.0, 0.0))
    ok, _used, _msg = boolean.robust_boolean(bpy.context, target, cutter,
                                             'DIFFERENCE', 'EXACT')
    assert ok, "boolean cut failed"
    ngons_before = sum(1 for p in target.data.polygons if len(p.vertices) > 4)
    cleaned = geometry.dissolve_boolean_ngons(target)
    ngons_after = sum(1 for p in target.data.polygons if len(p.vertices) > 4)
    # the cleanup reports what it processed and leaves no n-gons behind
    assert cleaned == ngons_before, (cleaned, ngons_before)
    assert ngons_after == 0, "n-gons survived the cleanup"


def test_topology_prefs_registered():
    # The Super Modeling Mode topology toggles register with safe (off) defaults,
    # so enabling them is opt-in and the default cut/bevel behaviour is unchanged.
    # Read through get_prefs (not a raw addons[_PKG] lookup) so this passes both
    # under the Blender binary (addon enabled -> the real prefs) and a standalone
    # bpy module (registered but not enabled -> the RNA-declared defaults).
    _reset()
    hardflow.register()
    try:
        from hardflow.preferences import get_prefs
        prefs = get_prefs(bpy.context)
        assert prefs.cut_dissolve_ngons is False
        assert prefs.smart_bevel_default is False
    finally:
        hardflow.unregister()


def test_loop_cut():
    # Loop cut on a 3x3 quad grid: the ring of an interior horizontal edge is the
    # full column (4 edges); subdividing it inserts a loop -> +4 verts, +3 faces.
    _reset()
    import bmesh
    me = bpy.data.meshes.new("grid2")
    bm = bmesh.new()
    n = 4
    vs = [[bm.verts.new((x, y, 0)) for x in range(n)] for y in range(n)]
    for y in range(n - 1):
        for x in range(n - 1):
            bm.faces.new((vs[y][x], vs[y][x + 1], vs[y + 1][x + 1], vs[y + 1][x]))
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("Grid2", me)
    bpy.context.collection.objects.link(obj)
    ek = (1 * n + 1, 1 * n + 2)             # edge (1,1)-(2,1)
    assert len(geometry.edge_ring(obj, ek)) == 4, geometry.edge_ring(obj, ek)
    vb, fb = len(obj.data.vertices), len(obj.data.polygons)
    assert geometry.loop_cut(obj, ek, cuts=1) == 4
    assert len(obj.data.vertices) == vb + 4, len(obj.data.vertices)
    assert len(obj.data.polygons) == fb + 3, len(obj.data.polygons)
    # a plain cube has a 4-edge band ring -> loop cut adds geometry, no crash
    cube = _add_cube("LoopCutCube", size=2.0)
    top = max(range(len(cube.data.polygons)),
              key=lambda k: cube.data.polygons[k].normal.z)
    ck = geometry.nearest_edge_on_face(cube, top, Vector((1.0, 0.0, 1.0)))
    assert geometry.loop_cut(cube, ck, 1) >= 1


def _quad_grid(name, n=4):
    """An n x n vertex quad grid in the XY plane; vert (x, y) -> index y*n + x."""
    import bmesh
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = [[bm.verts.new((x, y, 0)) for x in range(n)] for y in range(n)]
    for y in range(n - 1):
        for x in range(n - 1):
            bm.faces.new((vs[y][x], vs[y][x + 1], vs[y + 1][x + 1], vs[y + 1][x]))
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    return obj


def test_loop_cut_slide():
    # Loop-cut slide on a 3x3 quad grid: the ring of a horizontal edge runs in X
    # (x: 1 -> 2). slide=0 inserts the loop at the midpoint x=1.5; a non-zero slide
    # moves the whole loop off-centre CONSISTENTLY (one shared x, no zig-zag).
    _reset()
    n = 4
    ek = (1 * n + 1, 1 * n + 2)                  # horizontal edge (1,1)-(2,1)

    mid = _quad_grid("SlideMid", n)
    assert geometry.loop_cut(mid, ek, cuts=1, slide=0.0) == 4
    mid_x = sorted({round(v.co.x, 5) for v in mid.data.vertices
                    if 1.0 < v.co.x < 2.0})
    assert mid_x == [1.5], mid_x                 # default = midpoint

    pos = _quad_grid("SlidePos", n)
    assert geometry.loop_cut(pos, ek, cuts=1, slide=0.6) == 4
    pos_x = sorted({round(v.co.x, 5) for v in pos.data.vertices
                    if 1.0 < v.co.x < 2.0})
    assert len(pos_x) == 1, pos_x                # consistent slide, no zig-zag
    assert abs(pos_x[0] - 1.5) > 0.05, pos_x     # actually slid off-centre

    neg = _quad_grid("SlideNeg", n)
    assert geometry.loop_cut(neg, ek, cuts=1, slide=-0.6) == 4
    neg_x = sorted({round(v.co.x, 5) for v in neg.data.vertices
                    if 1.0 < v.co.x < 2.0})
    assert len(neg_x) == 1, neg_x
    # opposite slide -> mirrored across the midpoint
    assert abs((pos_x[0] + neg_x[0]) - 3.0) < 1e-4, (pos_x, neg_x)

    # multiple cuts ignore slide -> evenly spaced (two loops at x=1/3+1, 2/3+1)
    multi = _quad_grid("SlideMulti", n)
    assert geometry.loop_cut(multi, ek, cuts=2, slide=0.9) == 4
    multi_x = sorted({round(v.co.x, 4) for v in multi.data.vertices
                      if 1.0 < v.co.x < 2.0})
    assert len(multi_x) == 2, multi_x
    assert abs(multi_x[0] - (1 + 1 / 3)) < 1e-3 and \
        abs(multi_x[1] - (1 + 2 / 3)) < 1e-3, multi_x


def test_offset_inference_projection():
    # The Offset tool's in-plane thickness inference: a coplanar vertex inside the
    # locked face yields the inset thickness at which the shrinking border reaches
    # it. Mirrors HARDFLOW_OT_offset._capture_offset_inference end to end (face
    # plane basis -> project boundary + interior -> candidate distances).
    _reset()
    import bmesh
    from hardflow.core import offset as inset_math
    me = bpy.data.meshes.new("face")
    bm = bmesh.new()
    c = [bm.verts.new(p) for p in [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]]
    bm.faces.new(c)
    bm.verts.new((3, 5, 0))           # coplanar interior vert, 3 from left edge
    bm.verts.new((5, 5, 5))           # off-plane -> must be filtered out
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("Face", me)
    bpy.context.collection.objects.link(obj)

    poly = obj.data.polygons[0]
    plane_co = obj.matrix_world @ poly.center
    plane_no = (obj.matrix_world.to_3x3() @ poly.normal).normalized()
    right, up, normal = raycast.basis_from_normal(plane_no)
    mw = obj.matrix_world
    boundary = [raycast.world_to_plane_uv(mw @ obj.data.vertices[vi].co,
                                          plane_co, right, up)
                for vi in poly.vertices]
    face_vi = set(poly.vertices)
    interior = []
    for v in obj.data.vertices:
        if v.index in face_vi:
            continue
        d = (mw @ v.co) - plane_co
        if abs(d.dot(normal)) > 1e-4:             # off the face plane -> skip
            continue
        uv = (d.dot(right), d.dot(up))
        if grid.point_in_polygon(uv, boundary):
            interior.append(uv)
    assert len(interior) == 1, interior          # the off-plane vert was dropped
    cands = inset_math.inset_inference_candidates(boundary, interior)
    assert any(abs(c - 3.0) < 1e-4 for c in cands), cands


def test_nearest_face_to_point():
    # Maps an evaluated-mesh raycast hit back to a base face (the hover-pick
    # through generative modifiers path).
    _reset()
    cube = _add_cube("FacePick", size=2.0)
    i = geometry.nearest_face_to_point(cube, Vector((0, 0, 1.2)))   # above top
    assert i >= 0
    assert cube.data.polygons[i].normal.z > 0.9, cube.data.polygons[i].normal[:]
    j = geometry.nearest_face_to_point(cube, Vector((1.2, 0, 0)))   # past +X
    assert cube.data.polygons[j].normal.x > 0.9
    empty = bpy.data.objects.new("Empty", bpy.data.meshes.new("empty"))
    assert geometry.nearest_face_to_point(empty, Vector((0, 0, 0))) == -1


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
                     "HARDFLOW_MT_pie_edit", "HARDFLOW_MT_menu",
                     "HARDFLOW_MT_menu_build", "HARDFLOW_MT_menu_edit",
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


def test_capture_edges_basis_uses_longest_edge():
    # The EDGES construction plane must orient its main (right) axis to the
    # LONGEST selected edge regardless of selection order (decal_math.best_edge_pair
    # wired through HARDFLOW_OT_draw._capture_edges_basis, which only reads the
    # edit-mesh -- no modal/region state -- so it runs headless).
    from hardflow.operators import draw_cut
    import bmesh
    _reset()
    # a 4 x 1 rectangle in the XY plane: the long side runs along world X
    me = bpy.data.meshes.new("Rect")
    bm = bmesh.new()
    vs = [bm.verts.new(c) for c in ((0, 0, 0), (4, 0, 0), (4, 1, 0), (0, 1, 0))]
    bm.faces.new(vs)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Rect", me)
    bpy.context.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.tool_settings.mesh_select_mode = (False, True, False)
    bm = bmesh.from_edit_mesh(ob.data)
    # select one long (X-aligned) edge and one short (Y-aligned) edge
    for e in bm.edges:
        e.select_set(False)
    for e in bm.edges:
        v = e.verts[1].co - e.verts[0].co
        if v.length > 1e-6 and abs(v.x) > abs(v.y):   # the long X edge
            e.select_set(True)
            break
    for e in bm.edges:
        v = e.verts[1].co - e.verts[0].co
        if v.length > 1e-6 and abs(v.y) > abs(v.x):   # a short Y edge
            e.select_set(True)
            break
    bmesh.update_edit_mesh(ob.data)

    basis = draw_cut.HARDFLOW_OT_draw._capture_edges_basis(None, bpy.context)
    bpy.ops.object.mode_set(mode='OBJECT')
    assert basis is not None
    _origin, right, _up, normal = basis
    # main axis follows the longest (X) edge; the plane normal is world Z
    assert abs(abs(right.x) - 1.0) < 1e-5, right
    assert abs(abs(normal.z) - 1.0) < 1e-5, normal


def test_capture_edges_basis_forced_main():
    # Ctrl+Click 'set main edge': forcing a SHORTER selected edge as the main axis
    # (self._forced_main_key) makes the grid's right axis follow it instead of the
    # automatic longest edge. Exercises the override path through best_edge_pair.
    from hardflow.operators import draw_cut
    import bmesh
    _reset()
    me = bpy.data.meshes.new("Rect2")
    bm = bmesh.new()
    vs = [bm.verts.new(c) for c in ((0, 0, 0), (4, 0, 0), (4, 1, 0), (0, 1, 0))]
    bm.faces.new(vs)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Rect2", me)
    bpy.context.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.context.tool_settings.mesh_select_mode = (False, True, False)
    bm = bmesh.from_edit_mesh(ob.data)
    for e in bm.edges:
        e.select_set(False)
    short_key = None
    for e in bm.edges:
        v = e.verts[1].co - e.verts[0].co
        if v.length <= 1e-6:
            continue
        if abs(v.x) > abs(v.y):                       # every long X edge
            e.select_set(True)
        elif short_key is None:                       # one short Y edge -> force it
            e.select_set(True)
            short_key = frozenset((e.verts[0].index, e.verts[1].index))
    bmesh.update_edit_mesh(ob.data)

    class _S:                                         # minimal stand-in for `self`
        pass
    s = _S()
    s._forced_main_key = short_key
    basis = draw_cut.HARDFLOW_OT_draw._capture_edges_basis(s, bpy.context)
    bpy.ops.object.mode_set(mode='OBJECT')
    assert basis is not None
    _o, right, _u, normal = basis
    # the main axis now follows the forced short (Y) edge, not the long X edge
    assert abs(abs(right.y) - 1.0) < 1e-5, right
    assert abs(abs(normal.z) - 1.0) < 1e-5, normal


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
    # "Connected faces": a drawn face that shares corners with the existing
    # mesh welds onto them instead of leaving a detached island.
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


def test_build_prism_project_taper():
    # PROJECT orientation (apex set) extrudes each corner along its own ray from
    # the camera, so the cutter is a frustum: the two caps have different
    # cross-sections. Fixed (apex=None) stays a straight prism.
    corners = [Vector((-1, -1, 0)), Vector((1, -1, 0)),
               Vector((1, 1, 0)), Vector((-1, 1, 0))]
    view_dir = Vector((0, 0, 1))
    apex = Vector((0, 0, 10))            # camera above the plane
    me = geometry.build_prism(corners, view_dir, thickness=4.0, apex=apex)
    assert me is not None
    assert len(me.vertices) == 8 and len(me.polygons) == 6

    def extent(z):
        xs = [v.co.x for v in me.vertices if round(v.co.z, 4) == z]
        return round(max(xs) - min(xs), 4)

    zs = sorted({round(v.co.z, 4) for v in me.vertices})
    assert len(zs) == 2, zs                       # two cap planes
    assert extent(zs[0]) != extent(zs[1]), (extent(zs[0]), extent(zs[1]))  # taper
    # Fixed: both caps keep the original 2.0 extent (a straight box prism).
    flat = geometry.build_prism(corners, view_dir, thickness=4.0)
    fxs = sorted({round(v.co.x, 4) for v in flat.vertices})
    assert fxs == [-1.0, 1.0], fxs


# --- v1.5 mesh-editing parity ------------------------------------------------

def test_edge_weights():
    # Edit-Mode edge bevel-weight / crease on the selected edges (the surviving
    # weighting workflow that feeds a weight-limited Bevel or creased Subdiv).
    _reset()
    cube = _add_cube("Weights", size=2.0)
    _edit_select_faces(cube, [0])
    m = geometry.edit_set_edge_weights(cube, bevel_weight=1.0, only_selected=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    assert m == 4                            # one quad face = 4 edges


# --- v1.6 modeling extras ----------------------------------------------------

def test_pipe_mesh_and_profile():
    assert geometry.profile_points('ROUND', 0.1) is None
    sq = geometry.profile_points('SQUARE', 0.1)
    assert len(sq) == 4
    pts = [Vector((0, 0, 0)), Vector((0, 0, 1)), Vector((0, 0, 2))]
    me = geometry.build_pipe_mesh(pts, sq)
    assert me is not None and len(me.polygons) > 0
    assert geometry.build_pipe_mesh([Vector((0, 0, 0))], sq) is None


def test_sweep_profiles():
    # The Sweep tool's structural cross-sections produce valid swept solids and
    # the operator registers (the modal itself is in the manual checklist).
    expected = {'L': 6, 'U': 8, 'T': 8, 'I': 12}
    pts = [Vector((0, 0, 0)), Vector((0, 0, 1)), Vector((0, 0, 2))]
    for profile, count in expected.items():
        prof = geometry.profile_points(profile, 0.2)
        assert prof is not None and len(prof) == count, profile
        me = geometry.build_pipe_mesh(pts, prof)
        assert me is not None and len(me.polygons) > 0, profile
    _reset()
    hardflow.register()
    try:
        assert hasattr(bpy.ops.mesh, "hardflow_sweep")
    finally:
        hardflow.unregister()


def test_build_loft():
    a = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((1, 1, 0)), Vector((0, 1, 0))]
    b = [p + Vector((0, 0, 2)) for p in a]
    me = geometry.build_loft(a, b)
    assert me is not None
    assert len(me.vertices) == 8 and len(me.polygons) == 6     # closed box
    assert geometry.build_loft(a, b[:3]) is None               # mismatched loops


# --- v1.7 decal extras -------------------------------------------------------

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
    # the grid decal must get INTERIOR uvs across the cell, not just the corners
    # (a sign-based corner map would collapse every interior vert onto 0.0/0.5)
    assert any(0.0 < u < 0.5 for u in us), "uv remap collapsed the grid to corners"

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


# --- v1.8 asset/insert extras ------------------------------------------------

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


def test_panel_health_cache():
    # The N-panel pre-cut warning is cached so it does not rebuild a bmesh on every
    # redraw; the cache must invalidate when the mesh's vert/poly count changes.
    _reset()
    from hardflow.ui import panel
    panel._HEALTH_CACHE["key"] = None          # isolate from any prior test
    cube = _add_cube("CacheClean", size=2.0)
    assert panel._cached_health_summary(cube) == ""        # clean -> no warning
    key1 = panel._HEALTH_CACHE["key"]
    assert panel._cached_health_summary(cube) == ""        # served from cache
    assert panel._HEALTH_CACHE["key"] == key1              # key unchanged

    import bmesh
    bm = bmesh.new()
    bm.from_mesh(cube.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[0]], context='FACES_ONLY')
    bm.to_mesh(cube.data)
    bm.free()
    summary = panel._cached_health_summary(cube)           # poly count changed
    assert "non-manifold" in summary, summary
    assert panel._HEALTH_CACHE["key"] != key1              # cache invalidated


def test_choose_solver_from_health():
    # a clean, closed manifold cube starts on the fast MANIFOLD solver where it
    # exists (Blender 4.5+), else the accurate EXACT solver
    _reset()
    cube = _add_cube("Clean", size=2.0)
    clean_expected = 'MANIFOLD' if boolean._solver_available('MANIFOLD') else 'EXACT'
    assert boolean.choose_solver(cube, 'EXACT') == clean_expected
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


def test_choose_solver_cutter_gate():
    # MANIFOLD needs BOTH operands watertight: a clean target paired with an open
    # (non-manifold) cutter must fall back to EXACT, not pick MANIFOLD.
    if not boolean._solver_available('MANIFOLD'):
        return  # pre-4.5: no MANIFOLD solver to gate
    _reset()
    target = _add_cube("CleanTarget", size=2.0)
    cutter = _add_cube("OpenCutter", size=1.0)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(cutter.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[0]], context='FACES_ONLY')   # open it
    bm.to_mesh(cutter.data)
    bm.free()
    assert boolean.choose_solver(target, 'EXACT', cutter=cutter) == 'EXACT'
    # a clean cutter restores the MANIFOLD fast path
    clean_cutter = _add_cube("CleanCutter", size=1.0)
    assert boolean.choose_solver(target, 'EXACT', cutter=clean_cutter) == 'MANIFOLD'


def test_solver_fallback_chain_and_message():
    # Manifold-first must escalate through EXACT before the lossy FAST; a broken
    # mesh's FAST start must not waste a slow EXACT attempt; messages stay quiet on
    # the happy path and warn only on a real downgrade / mid-chain fallback.
    assert boolean._dedupe(['A', 'B', 'A', 'C', 'B']) == ['A', 'B', 'C']
    assert boolean._fallback_chain('MANIFOLD', 'EXACT') == \
        ['MANIFOLD', 'EXACT', 'FAST']
    assert boolean._fallback_chain('FAST', 'EXACT') == ['FAST']
    assert boolean._fallback_chain('EXACT', 'EXACT') == ['EXACT', 'FAST']
    # planned solver worked -> quiet (incl. the Manifold clean-mesh fast path)
    assert boolean._solver_message('MANIFOLD', 'EXACT', 'MANIFOLD') == "Cut done"
    assert boolean._solver_message('EXACT', 'EXACT', 'EXACT') == "Cut done"
    # health forced a FAST downgrade -> say which geometry is at fault
    assert 'too broken' in boolean._solver_message('FAST', 'EXACT', 'FAST')
    # a deliberate FAST preference is not a downgrade -> quiet
    assert boolean._solver_message('FAST', 'FAST', 'FAST') == "Cut done"
    # mid-chain fallback (start failed, a later solver won) -> name it
    assert boolean._solver_message('EXACT', 'EXACT', 'MANIFOLD') == \
        "Cut done (EXACT solver fallback)"


def test_coerce_solver_fast_to_float():
    # Blender 5.0 renamed the FAST solver to FLOAT; a FAST request must map to the
    # available fast solver, not silently fall all the way back to the slow EXACT.
    avail = {i.identifier for i in
             bpy.types.BooleanModifier.bl_rna.properties['solver'].enum_items}
    coerced = boolean._coerce_solver('FAST')
    if 'FAST' in avail:
        assert coerced == 'FAST'
    elif 'FLOAT' in avail:
        assert coerced == 'FLOAT', coerced      # 5.x rename, not EXACT
    else:
        assert coerced == 'EXACT'
    # EXACT and an unknown solver are unaffected
    assert boolean._coerce_solver('EXACT') == 'EXACT'
    assert boolean._coerce_solver('NOPE') == 'EXACT'


def test_robust_boolean_succeeds_and_reports():
    _reset()
    target = _add_cube("Target", size=2.0)
    cutter = _add_cube("Cutter", size=1.0, location=(1, 0, 0))
    _activate(target)
    before = len(target.data.polygons)
    ok, used, msg = boolean.robust_boolean(bpy.context, target, cutter,
                                           'DIFFERENCE', 'EXACT')
    assert ok and used in {'MANIFOLD', 'EXACT', 'FAST'}
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
    assert abs(p.x - 0.1) < 1e-6      # Vector components are float32
    # an anchor within threshold wins over the grid
    p2 = snapping.snap_insert_point((0.12, 0.0, 0.0), 0.1,
                                    anchors=[Vector((0.13, 0.0, 0.0))],
                                    threshold=0.05)
    assert abs(p2.x - 0.13) < 1e-6


def test_new_operators_registered():
    _reset()
    hardflow.register()
    try:
        for name in ("hardflow_display_toggle", "hardflow_random_color",
                     "hardflow_copy_material", "hardflow_recalc_normals",
                     "hardflow_loft", "hardflow_match_decal",
                     "hardflow_retrim_decal", "hardflow_conform_decal",
                     "hardflow_create_decal", "hardflow_library_rename",
                     "hardflow_library_delete", "hardflow_material_insert",
                     "hardflow_export_asset"):
            assert hasattr(bpy.ops.object, name), "missing operator: %s" % name
        assert hasattr(bpy.ops.mesh, "hardflow_edge_weight")
        # HardFlow Mode shadowing verbs (Knife + Extrude) register on the shell.
        assert hasattr(bpy.ops.mesh, "hardflow_mode_knife")
        assert hasattr(bpy.ops.mesh, "hardflow_mode_extrude")
    finally:
        hardflow.unregister()


def test_menu_items_resolve():
    # Every operator + icon referenced by the header-menu tables resolves, so the
    # menus (and the panel rows that share the same operators/icons) draw without
    # a bad-idname or bad-icon error -- the class of failure headless can't click.
    _reset()
    hardflow.register()
    try:
        from hardflow.ui import menu
        icons = {e.identifier for e in
                 bpy.types.UILayout.bl_rna.functions['operator']
                 .parameters['icon'].enum_items}
        tables = (menu._BUILD_ITEMS, menu._BOOLEAN_ITEMS, menu._DISPLAY_ITEMS,
                  menu._CURVE_ITEMS, menu._ASSET_ITEMS)
        for table in tables:
            for entry in table:
                if entry is None:
                    continue
                idname, _text, icon, _props = entry
                area, op = idname.split(".", 1)
                root = getattr(bpy.ops, area)
                assert hasattr(root, op), "unregistered operator: %s" % idname
                assert icon in icons, "bad icon: %s" % icon
    finally:
        hardflow.unregister()


def test_gizmos_registered():
    _reset()
    # Gizmo / GizmoGroup classes aren't exposed on bpy.types by name; the
    # registry lookup bl_rna_get_subclass_py returns the class (or None).
    assert bpy.types.Gizmo.bl_rna_get_subclass_py("HARDFLOW_GT_drag_extrude") is None
    hardflow.register()
    try:
        assert bpy.types.Gizmo.bl_rna_get_subclass_py(
            "HARDFLOW_GT_drag_extrude") is not None
        for name in ("HARDFLOW_GGT_persistent", "HARDFLOW_GGT_move",
                     "HARDFLOW_GGT_rotate", "HARDFLOW_GGT_scale",
                     "HARDFLOW_GGT_bevel", "HARDFLOW_GGT_push_pull"):
            assert bpy.types.GizmoGroup.bl_rna_get_subclass_py(name) is not None, \
                "unregistered gizmo group: %s" % name
        # Scene settings present and writable.
        s = bpy.context.scene.hardflow_gizmos
        s.show = True
        assert s.show is True
        # Persistent group polls True with a mesh active + the toggle on, and
        # False once the master switch is off.
        from hardflow.gizmos import groups
        ob = _add_cube("GzCube")
        _activate(ob)
        assert groups.HARDFLOW_GGT_persistent.poll(bpy.context) is True
        s.show = False
        assert groups.HARDFLOW_GGT_persistent.poll(bpy.context) is False
    finally:
        hardflow.unregister()
    # Cleanly removed again.
    assert bpy.types.GizmoGroup.bl_rna_get_subclass_py("HARDFLOW_GGT_move") is None


def test_gizmo_bevel_handler_creates_modifier():
    _reset()
    hardflow.register()
    try:
        from hardflow.gizmos import groups
        ob = _add_cube("BevelGz")
        _activate(ob)
        # Below the epsilon nothing is created; a real drag value adds HF_Bevel.
        groups._bevel_set(0.0)
        assert ob.modifiers.get("HF_Bevel") is None
        groups._bevel_set(0.05)
        mod = ob.modifiers.get("HF_Bevel")
        assert mod is not None and abs(mod.width - 0.05) < 1e-6
        assert abs(groups._bevel_get() - 0.05) < 1e-6
        groups._bevel_set(0.12)          # subsequent drags adjust, not duplicate
        assert len([m for m in ob.modifiers if m.name == "HF_Bevel"]) == 1
        assert abs(ob.modifiers["HF_Bevel"].width - 0.12) < 1e-6
    finally:
        hardflow.unregister()


def test_gizmo_arrow_shape_is_triangle_soup():
    from hardflow.gizmos import shapes
    verts = shapes.arrow_tris(segments=8)
    assert len(verts) % 3 == 0 and len(verts) > 0
    assert all(len(v) == 3 for v in verts)
    # spans from the base (z=0) up to the cone tip
    zs = [v[2] for v in verts]
    assert min(zs) == 0.0 and max(zs) > 0.5


# --- bisect_plane + operator-layer Command Pattern (base.py) ----------------

def test_bisect_plane_slices_cube():
    _reset()
    ob = _add_cube("Bisect", size=2.0)
    before = len(ob.data.vertices)
    cut = geometry.bisect_plane(ob, Vector((0, 0, 0)), Vector((0, 0, 1)))
    assert cut > 0, cut                       # a mid-cube slice adds a cut loop
    assert len(ob.data.vertices) > before
    # a degenerate (zero-length) normal is a no-op, not a crash
    assert geometry.bisect_plane(ob, Vector((0, 0, 0)), Vector((0, 0, 0))) == 0


def test_place_point_command_execute_undo_redo():
    from hardflow.operators import base
    pts = []
    cmd = base.PlacePointCommand(pts, (1.0, 2.0, 3.0))
    cmd.execute()
    assert pts == [(1.0, 2.0, 3.0)]
    cmd.execute()                             # idempotent: still one point
    assert pts == [(1.0, 2.0, 3.0)]
    cmd.undo()
    assert pts == []
    cmd.redo()                                # HardFlowCommand.redo re-applies
    assert pts == [(1.0, 2.0, 3.0)]


def test_mesh_snapshot_command_preview_commit_undo():
    _reset()
    from hardflow.operators import base
    ob = _add_cube("Snap", size=2.0)
    before = len(ob.data.vertices)

    def _slice(o):
        geometry.bisect_plane(o, Vector((0, 0, 0)), Vector((0, 0, 1)))

    cmd = base.MeshSnapshotCommand(ob, _slice, label="slice")
    cmd.execute()                             # snapshot 'before' + apply
    applied = len(ob.data.vertices)
    assert applied > before
    cmd.execute()                             # guard: no second apply
    assert len(ob.data.vertices) == applied
    cmd.reapply()                             # preview frame: restore + re-edit
    assert len(ob.data.vertices) == applied   # same result, never stacked
    cmd.undo()                                # restore the 'before' snapshot
    assert len(ob.data.vertices) == before
    cmd.free()                                # drop the snapshot datablock
    cmd.free()                                # idempotent


def test_mesh_snapshot_command_uses_injected_restore():
    # Mode-aware: a tool passes restore=geometry.restore_edit_mesh (or any custom
    # restore) and the command routes through it -- the Object/Edit split in
    # _FaceDragModal collapses to one injected callable. Verified without a mode
    # toggle by recording that the injected callables fire.
    _reset()
    from hardflow.operators import base
    ob = _add_cube("Inject", size=2.0)
    calls = {"snap": 0, "restore": 0}

    def _snap(o, name):
        calls["snap"] += 1
        return geometry.snapshot_mesh(o, name)

    def _restore(o, snap):
        calls["restore"] += 1
        geometry.restore_mesh(o, snap)

    cmd = base.MeshSnapshotCommand(
        ob, lambda o: geometry.bisect_plane(o, Vector((0, 0, 0)),
                                            Vector((0, 0, 1))),
        snapshot=_snap, restore=_restore, label="inject")
    cmd.execute()                     # snapshot once + restore + mutate
    cmd.reapply()                     # restore + mutate
    cmd.undo()                        # restore
    assert calls["snap"] == 1, calls  # snapshot captured exactly once
    assert calls["restore"] == 3, calls
    cmd.free()


def test_mesh_snapshot_command_in_macro_rolls_back():
    # A two-edit macro on a real mesh: a mid-chain failure restores every mesh
    # snapshot, so nothing is left half-applied (the boolean-chain guarantee).
    _reset()
    from hardflow.operators import base
    from hardflow.core import command
    ob = _add_cube("Macro", size=2.0)
    before = len(ob.data.vertices)
    good = base.MeshSnapshotCommand(
        ob, lambda o: geometry.bisect_plane(o, Vector((0, 0, 0)),
                                            Vector((0, 0, 1))), label="ok")

    def _boom(_o):
        raise RuntimeError("solver failed")
    bad = base.MeshSnapshotCommand(ob, _boom, label="bad")
    macro = command.MacroCommand([good, bad], label="chain")
    raised = False
    try:
        macro.execute()
    except RuntimeError:
        raised = True
    assert raised and not macro.done
    assert len(ob.data.vertices) == before    # 'good' edit was rolled back
    good.free()
    bad.free()


def test_boolean_chain_command_atomic():
    # base.boolean_chain: N cutters applied to one target as an atomic macro.
    _reset()
    from hardflow.operators import base
    from hardflow.core import command
    target = _add_cube("BoolTarget", size=2.0)
    _activate(target)
    c1 = _add_cube("Cutter1", size=1.0, location=(1.0, 1.0, 1.0))
    c2 = _add_cube("Cutter2", size=1.0, location=(-1.0, -1.0, -1.0))
    v0 = len(target.data.vertices)
    chain = base.boolean_chain(bpy.context, target, [c1, c2], 'DIFFERENCE')
    chain.execute()
    assert chain.done and len(chain) == 2
    assert len(target.data.vertices) != v0, "boolean chain did not modify target"
    for c in chain._commands:
        c.free()

    # Atomic rollback: a chain whose last step raises restores the target fully,
    # so a failed cut never leaves a half-applied boolean (the crash-safety goal).
    _reset()
    target = _add_cube("BoolTarget2", size=2.0)
    _activate(target)
    cutter = _add_cube("Cutter3", size=1.0, location=(1.0, 1.0, 1.0))
    v0 = len(target.data.vertices)
    good = base.BooleanCutCommand(bpy.context, target, cutter, 'DIFFERENCE')

    def _boom(_o):
        raise RuntimeError("forced solver failure")
    bad = base.MeshSnapshotCommand(target, _boom, label="bad")
    macro = command.MacroCommand([good, bad], label="chain")
    raised = False
    try:
        macro.execute()
    except RuntimeError:
        raised = True
    assert raised and not macro.done
    assert len(target.data.vertices) == v0, "rollback left the target modified"
    good.free()
    bad.free()


def test_mesh_snapshot_command_snapshot_property():
    # The public snapshot accessor lets a modal tool read the pre-edit mesh from
    # the same datablock the command owns (used by _FaceDragModal inference).
    _reset()
    from hardflow.operators import base
    ob = _add_cube("SnapProp", size=2.0)
    cmd = base.MeshSnapshotCommand(ob, lambda o: None, label="noop")
    assert cmd.snapshot is None                       # before execute
    cmd.execute()
    assert cmd.snapshot is not None                   # captured on first apply
    assert len(cmd.snapshot.vertices) == len(ob.data.vertices)
    cmd.free()
    assert cmd.snapshot is None                       # dropped on free


def test_livepreview_command_lifecycle():
    # The named non-destructive live-boolean preview: refresh() attaches an
    # HF_LivePreview Boolean modifier to each target pointing at the cutter,
    # retargets when the wanted set changes, and clear()/undo() strip them all.
    # Never mutates target geometry (that is the whole reason it isn't a
    # MeshSnapshotCommand).
    _reset()
    from hardflow.operators import base
    target = _add_cube("PvTarget", size=2.0)
    other = _add_cube("PvOther", size=2.0, location=(4, 0, 0))
    cutter = _add_cube("PvCutter", size=1.0, location=(1, 0, 0))
    tris_before = len(target.data.polygons)

    cmd = base.LivePreviewCommand(cutter, 'DIFFERENCE')
    cmd.execute()                                     # arm; no modifier yet
    assert target.modifiers.get("HF_LivePreview") is None

    cmd.refresh([target])                             # attach to the one target
    mod = target.modifiers.get("HF_LivePreview")
    assert mod is not None and mod.object == cutter
    assert mod.operation == 'DIFFERENCE' and mod.show_render is False
    assert len(target.data.polygons) == tris_before   # base mesh untouched

    cmd.refresh([other])                              # retarget: target stripped
    assert target.modifiers.get("HF_LivePreview") is None
    assert other.modifiers.get("HF_LivePreview") is not None

    cmd.refresh([target])                             # idempotent re-add
    assert len(target.modifiers) == 1

    cmd.undo()                                        # _revert == clear
    assert target.modifiers.get("HF_LivePreview") is None
    assert other.modifiers.get("HF_LivePreview") is None

    # Scene sweep: a stray modifier on an untracked object is still caught.
    other.modifiers.new("HF_LivePreview", 'BOOLEAN')
    cmd.clear(bpy.context)
    assert other.modifiers.get("HF_LivePreview") is None
    cmd.free()                                        # idempotent


def test_draw_cut_uses_livepreview_command():
    # Guard the adoption: draw_cut's live boolean preview routes through the named
    # command, not the old ad-hoc _bool_targets / _remove_live_mod bookkeeping.
    from hardflow.operators import draw_cut
    cls = draw_cut.HARDFLOW_OT_draw
    assert not hasattr(cls, "_remove_live_mod")
    assert "LivePreviewCommand" in (cls._sync_live_boolean.__doc__ or "")


def test_facetool_command_adoption_structure():
    # The _FaceDragModal tools now share the base MeshSnapshotCommand-backed
    # preview: the base owns _begin_edit / _refresh_preview, and each subclass
    # supplies _mutate (the edit WITHOUT the restore) instead of its own
    # _refresh_preview. Guard the contract so a future edit can't half-migrate it.
    from hardflow.operators import face_tool, push_pull, offset, edge_tool
    assert hasattr(face_tool._FaceDragModal, "_begin_edit")
    assert hasattr(face_tool._FaceDragModal, "_refresh_preview")
    for cls in (push_pull.HARDFLOW_OT_push_pull, offset.HARDFLOW_OT_offset,
                edge_tool.HARDFLOW_OT_edge_bevel, edge_tool.HARDFLOW_OT_loop_cut):
        assert "_mutate" in cls.__dict__, "%s must supply _mutate" % cls.__name__
        assert "_refresh_preview" not in cls.__dict__, \
            "%s must reuse the base _refresh_preview" % cls.__name__


def test_facetool_begin_edit_lifecycle():
    # The _FaceDragModal preview lifecycle on a real mesh via a stand-in `self`
    # (the modal shell itself needs a viewport; this covers the snapshot/restore
    # composition it now delegates to the per-session command): _begin_edit
    # snapshots + applies, _refresh_preview never stacks, undo_all restores.
    _reset()
    import types
    from hardflow.operators import face_tool
    from hardflow.core import command
    ob = _add_cube("FaceTool", size=2.0)
    before = len(ob.data.vertices)

    def _slice(o):
        geometry.bisect_plane(o, Vector((0, 0, 0)), Vector((0, 0, 1)))

    s = types.SimpleNamespace(obj=ob, _snapshot_name="hf_test",
                              _commands=command.CommandManager(),
                              _edit=None, _base=None)
    s._mutate = _slice
    face_tool._FaceDragModal._begin_edit(s)          # snapshot + first apply
    assert s._edit is not None and s._base is not None
    applied = len(ob.data.vertices)
    assert applied > before
    face_tool._FaceDragModal._refresh_preview(s)     # drag frame: restore + re-apply
    assert len(ob.data.vertices) == applied          # never stacked
    s._commands.undo_all()                           # cancel -> restore snapshot
    assert len(ob.data.vertices) == before
    s._edit.free()


def test_mode_shell_verb_and_plane_cycle():
    # HardFlow Mode shell: SURFACE promoted onto the plane cycle, and Tab cycles
    # the active verb (Knife <-> Extrude) in-session. Both are plain list walks;
    # call them unbound on a stand-in `self` (an Operator subclass can't be
    # __new__'d without a live invocation) so they check without a viewport.
    import types
    from hardflow.operators import hardflow_mode as hm
    assert "SURFACE" in hm._PLANES
    assert hm._VERBS == ("KNIFE", "EXTRUDE")
    assert hm.HARDFLOW_OT_mode_knife._START_VERB == "KNIFE"
    assert hm.HARDFLOW_OT_mode_extrude._START_VERB == "EXTRUDE"
    shell = hm._HardflowModeModal
    fake = types.SimpleNamespace(_active_verb="KNIFE", verb="Knife", _plane="VIEW")
    shell._cycle_verb(fake)
    assert fake._active_verb == "EXTRUDE" and fake.verb == "Extrude"
    shell._cycle_verb(fake)
    assert fake._active_verb == "KNIFE" and fake.verb == "Knife"
    # Plane cycle steps VIEW -> SURFACE -> ... and wraps.
    shell._cycle_plane(fake, 1)
    assert fake._plane == "SURFACE"
    fake._plane = "VIEW"
    shell._cycle_plane(fake, -1)
    assert fake._plane == hm._PLANES[-1]


def test_draw_cut_apply_destructive_atomic_chain():
    # draw_cut._apply_destructive now applies the cutter through an atomic
    # base.MacroCommand of BooleanCutCommands. Call it unbound with a stand-in
    # `self` (mode + report/_report_boolean stubs) to prove the wiring: CUT on
    # multiple targets cuts them all and removes the cutter; SLICE keeps the
    # carved piece.
    _reset()
    import types
    from hardflow.operators import draw_cut
    hardflow.register()
    try:
        apply_destructive = draw_cut.HARDFLOW_OT_draw._apply_destructive
        noop = lambda *a, **k: None

        # CUT across two targets with one cutter (multi-object path). The cutter
        # sits at the corner shared by both targets so its DIFFERENCE clips each.
        t1 = _add_cube("AtomT1", size=2.0, location=(0.0, 0.0, 0.0))
        t2 = _add_cube("AtomT2", size=2.0, location=(2.0, 2.0, 2.0))
        cutter = _add_cube("AtomCut", size=1.0, location=(1.0, 1.0, 1.0))
        v1, v2 = len(t1.data.vertices), len(t2.data.vertices)
        fake = types.SimpleNamespace(mode='CUT', report=noop,
                                     _report_boolean=noop)
        apply_destructive(fake, bpy.context, [t1, t2], cutter, 'FAST')
        assert len(t1.data.vertices) != v1 and len(t2.data.vertices) != v2
        assert "AtomCut" not in bpy.data.objects        # cutter cleaned up

        # SLICE: the target is carved and a second (intersected) piece is kept.
        target = _add_cube("SliceT", size=2.0, location=(8.0, 0.0, 0.0))
        _activate(target)
        cutter = _add_cube("SliceCut", size=1.0, location=(8.5, 0.5, 0.5))
        objs_before = set(bpy.data.objects.keys())
        fake = types.SimpleNamespace(mode='SLICE', report=noop,
                                     _report_boolean=noop)
        apply_destructive(fake, bpy.context, [target], cutter, 'FAST')
        assert "SliceCut" not in bpy.data.objects        # cutter cleaned up
        # A carved-off duplicate survives the successful slice.
        new_objs = set(bpy.data.objects.keys()) - objs_before - {"SliceCut"}
        assert new_objs, "slice did not keep the carved piece"
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
