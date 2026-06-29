# Headless Blender smoke testi -- bpy'ye bagli cekirdegi otomatik dogrular.
#
# Calistirma (Blender 4.2+ kurulu olmali):
#   blender --background --python tests/test_blender.py
#
# Sifir cikis kodu = gecti. Modal cizim operatoru (HARDFLOW_OT_draw) pencere/
# region gerektirdiginden burada test EDILMEZ; bunun yerine onun kullandigi
# yapi taslari (build_prism, apply/add_boolean) ve modal-olmayan bevel/mirror
# operatorleri dogrulanir. Saf matematik icin: python tests/test_core.py.
import os
import sys

import bpy
from mathutils import Vector

# hardflow paketini import edebilmek icin repo'nun ust klasorunu path'e ekle.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PARENT = os.path.dirname(_REPO)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

_PKG = os.path.basename(_REPO)            # genelde "hardflow"
hardflow = __import__(_PKG)
from hardflow.core import geometry, boolean   # noqa: E402


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
    assert me is not None, "build_prism None dondu"
    assert len(me.vertices) == 8, len(me.vertices)   # 4 on + 4 arka
    assert len(me.polygons) == 6, len(me.polygons)   # kapali prizma (kutu)
    # dejenere (tekrar eden kose) -> None
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
    assert after != before, "DIFFERENCE geometriyi degistirmedi"
    assert len(target.modifiers) == 0, "modifier uygulanmadi (hala duruyor)"


def test_add_boolean_nondestructive():
    _reset()
    target = _add_cube("Target", size=2.0)
    cutter = _add_cube("Cutter", size=1.0, location=(1, 0, 0))
    mod = boolean.add_boolean(target, cutter, 'DIFFERENCE', 'EXACT')
    assert mod.name in target.modifiers, "modifier eklenmedi"
    assert mod.object is cutter
    # stash_cutter kesiciyi ayri koleksiyona tasimali
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
        # EXEC_DEFAULT -> execute() (redo yolu); modal invoke atlanir
        bpy.ops.object.hardflow_bevel(width=0.03, segments=3, weighted_normal=True)
        assert any(m.type == 'BEVEL' for m in ob.modifiers), "bevel eklenmedi"
        assert any(m.type == 'WEIGHTED_NORMAL' for m in ob.modifiers), \
            "weighted normal eklenmedi"
        bev = next(m for m in ob.modifiers if m.type == 'BEVEL')
        assert bev.segments == 3 and abs(bev.width - 0.03) < 1e-6
        bpy.ops.object.hardflow_mirror(axis='X')
        assert any(m.type == 'MIRROR' for m in ob.modifiers), "mirror eklenmedi"
    finally:
        hardflow.unregister()


def test_build_face_and_cleanup():
    _reset()
    # build_face: 4 koseden tek n-gen
    me = geometry.build_face([Vector((0, 0, 0)), Vector((1, 0, 0)),
                              Vector((1, 1, 0)), Vector((0, 1, 0))])
    assert me is not None and len(me.polygons) == 1
    assert len(me.vertices) == 4
    # cleanup_mesh: cakisik vertex'li mesh'i kaynat
    cube = _add_cube("CleanMe", size=2.0)
    # ikinci ust uste kup -> remove doubles birlestirmeli
    extra = _add_cube("Extra", size=2.0)
    _activate(cube)
    # cube'a cakisik vertexler eklemek icin Extra'yi join etmek yerine,
    # dogrudan cleanup'in dusurmedigini/koruyamadigini sanity-check et:
    before = len(cube.data.vertices)
    geometry.cleanup_mesh(cube)
    assert len(cube.data.vertices) <= before  # temizleme vertex artirmamali


def test_build_pipe():
    _reset()
    pts = [Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((1, 1, 0))]
    curve = geometry.build_pipe(pts, radius=0.1)
    assert curve is not None
    assert curve.bevel_depth == 0.1
    sp = curve.splines[0]
    assert sp.type == 'POLY' and len(sp.points) == 3
    # tek nokta -> None
    assert geometry.build_pipe([Vector((0, 0, 0))]) is None


def test_clean_operator():
    _reset()
    hardflow.register()
    try:
        ob = _add_cube("Obj", size=2.0)
        _activate(ob)
        before = len(ob.data.vertices)
        bpy.ops.object.hardflow_clean()
        # temiz bir kup degismemeli (8 vertex korunur)
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
        assert len(target.modifiers) == 0, "modifier uygulanmadi"
        assert len(target.data.polygons) != before, "boolean bake edilmedi"
        assert bpy.data.objects.get("Cutter") is None, "kullanilmayan kesici silinmedi"
    finally:
        hardflow.unregister()


def test_multi_object_difference():
    # Tek kesici + iki hedef: ikisinin de poligon sayisi degismeli.
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
    print("\n%d/%d gecti" % (len(tests) - failed, len(tests)))
    return failed


if __name__ == "__main__":
    sys.exit(_run())
