"""Regenerate the README gallery renders (docs/img/shot*.png).

Run it INSIDE Blender with the Hardflow add-on enabled (Text Editor ▸ Open ▸
this file ▸ Run Script, or F3 ▸ "Run Script"). Every image is genuine Hardflow
output: the boolean (`core.boolean.robust_boolean`), the shape footprints
(`core.grid.*_points` + `core.geometry.build_prism`) and the pipe
(`core.geometry.build_pipe`) are the add-on's own code.

It is *non-destructive*: all geometry is built in an isolated temporary scene,
rendered with Blender's Workbench engine (a clean studio-lit look), and then the
scene + camera are deleted and your original scene is restored. Your file is
never modified — nothing is saved.

Output goes to `docs/img/` next to this script (falls back to a folder beside
the .blend, then the temp dir).
"""
import os
import bmesh
import bpy
from mathutils import Vector


def _hardflow():
    """Resolve the enabled Hardflow add-on module, however it was installed."""
    import importlib
    import sys
    for name in ("bl_ext.user_default.hardflow", "hardflow"):
        try:
            return importlib.import_module(name)
        except Exception:
            pass
    for name, mod in list(sys.modules.items()):
        if name.endswith(".hardflow") and hasattr(mod, "core"):
            return mod
    raise ImportError("Hardflow add-on not found — enable it first.")


_hf = _hardflow()
C_bool = _hf.core.boolean
C_geo = _hf.core.geometry
C_grid = _hf.core.grid


def _out_dir():
    try:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")
    except NameError:
        pass
    if bpy.data.filepath:
        return os.path.join(os.path.dirname(bpy.data.filepath),
                            "hardflow_gallery")
    return os.path.join(bpy.app.tempdir, "hardflow_gallery")


OUT = _out_dir()
os.makedirs(OUT, exist_ok=True)

report = {"rendered": [], "errors": []}
win = bpy.context.window_manager.windows[0]
orig_scene = win.scene
scene = bpy.data.scenes.new("HF_Shots")


def _link(ob):
    scene.collection.objects.link(ob)
    return ob


def _mesh_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return _link(bpy.data.objects.new(name, me))


def cube(name, sx, sy, sz, loc=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= sx / 2.0
        v.co.y *= sy / 2.0
        v.co.z *= sz / 2.0
    ob = _mesh_obj(name, bm)
    ob.location = loc
    return ob


def cyl(name, r, d, loc=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=48,
                          radius1=r, radius2=r, depth=d)
    ob = _mesh_obj(name, bm)
    ob.location = loc
    return ob


def plate(name, sx=2.4, sy=2.4, sz=0.4, bevel=0.03):
    ob = cube(name, sx, sy, sz)
    if bevel > 0:
        m = ob.modifiers.new("Bevel", 'BEVEL')
        m.width = bevel
        m.segments = 2
        m.limit_method = 'ANGLE'
    return ob


def cut(target, cutter, op='DIFFERENCE'):
    if cutter is None:
        return
    bpy.context.view_layer.objects.active = target
    for o in bpy.context.selected_objects:
        o.select_set(False)
    target.select_set(True)
    C_bool.robust_boolean(bpy.context, target, cutter, op)
    if cutter.name in bpy.data.objects:
        bpy.data.objects.remove(cutter, do_unlink=True)


def shape_pillar(name, pts2d, base_top, height=0.6):
    """Extrude a 2D footprint UP into a solid pillar standing on the base."""
    if not pts2d or len(pts2d) < 3:
        return None
    corners = [Vector((x, y, base_top - 0.06)) for (x, y) in pts2d]
    me = C_geo.build_prism(corners, Vector((0, 0, 1)), height + 0.06, name=name)
    if me is None:
        return None
    return _link(bpy.data.objects.new(name, me))


def setup_render():
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 960
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    sh = scene.display.shading
    sh.light = 'STUDIO'
    try:
        sh.color_type = 'SINGLE'
        sh.single_color = (0.62, 0.64, 0.68)
    except Exception:
        pass
    sh.show_cavity = True
    sh.show_shadows = True
    try:
        sh.shadow_intensity = 0.45
    except Exception:
        pass
    try:
        sh.cavity_type = 'BOTH'
        sh.curvature_ridge_factor = 1.0
        sh.curvature_valley_factor = 2.0
    except Exception:
        pass
    sh.show_object_outline = True
    sh.background_type = 'VIEWPORT'
    sh.background_color = (0.17, 0.18, 0.20)
    try:
        scene.display.render_aa = '8'
    except Exception:
        pass
    cam_data = bpy.data.cameras.new("HF_Cam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 4.6
    cam = bpy.data.objects.new("HF_Cam", cam_data)
    _link(cam)
    scene.camera = cam
    cam.location = (6.5, -6.5, 5.2)
    direction = Vector((0, 0, -0.1)) - cam.location
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


def frame_camera():
    """Auto-fit the ortho camera so the subject fills the frame."""
    cam = scene.camera
    if cam is None:
        return
    m = cam.matrix_world.inverted()
    xs, ys = [], []
    for ob in scene.collection.objects:
        if ob is cam or ob.type not in {'MESH', 'CURVE'}:
            continue
        for c in ob.bound_box:
            v = m @ (ob.matrix_world @ Vector(c[:]))
            xs.append(v.x)
            ys.append(v.y)
    if not xs:
        return
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    aspect = scene.render.resolution_x / float(scene.render.resolution_y)
    cam.data.ortho_scale = max(w, h * aspect) * 1.10
    cam.data.shift_x = ((max(xs) + min(xs)) / 2.0) / cam.data.ortho_scale
    cam.data.shift_y = ((max(ys) + min(ys)) / 2.0) / cam.data.ortho_scale


def render_to(filename):
    frame_camera()
    path = os.path.join(OUT, filename)
    scene.render.filepath = path
    area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    with bpy.context.temp_override(window=win, area=area, region=region,
                                   scene=scene):
        # view_context=False -> clean CAMERA render (no grid/axes/cursor).
        bpy.ops.render.opengl(write_still=True, view_context=False)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    report["rendered"].append({"file": filename, "bytes": size})


def clear_scene():
    cam = scene.camera
    for o in list(scene.collection.objects):
        if o is cam:
            continue  # keep the camera across shots
        bpy.data.objects.remove(o, do_unlink=True)


# --------------------------------------------------------------------------- #
try:
    win.scene = scene
    setup_render()

    # Shot 1 — Boolean cut (hero): round hole + a slot + a notch through a panel.
    try:
        p = plate("Panel")
        cut(p, cyl("cutR", 0.42, 2.0, loc=(0.55, 0.4, 0)))
        cut(p, cube("cutSlot", 1.4, 0.4, 2.0, loc=(-0.35, -0.4, 0)))
        cut(p, cube("cutStep", 0.55, 0.55, 0.5, loc=(0.6, -0.55, 0.15)))
        render_to("shot1-boolean-cut.png")
        clear_scene()
    except Exception:
        import traceback
        report["errors"].append("shot1: " + traceback.format_exc())
        clear_scene()

    # Shot 2 — Shape library: star / hexagon / circle / slot footprints
    # extruded into solid pillars (core.grid generators + build_prism).
    try:
        plate("ShapeBase", sx=4.6, sy=2.6, sz=0.22, bevel=0.02)
        bt = 0.11
        shape_pillar("pStar",
                     C_grid.star_points((-1.55, 0.0), (-1.18, 0.0), 5, 0.45), bt)
        shape_pillar("pHex",
                     C_grid.ngon_points((-0.5, 0.0), (-0.12, 0.0), 6), bt)
        shape_pillar("pCircle",
                     C_grid.circle_points((0.5, 0.0), (0.85, 0.0), 44), bt)
        shape_pillar("pSlot",
                     C_grid.slot_points((1.02, -0.2), (1.98, 0.2), 14), bt)
        render_to("shot2-shapes.png")
        clear_scene()
    except Exception:
        import traceback
        report["errors"].append("shot2: " + traceback.format_exc())
        clear_scene()

    # Shot 3 — Greeble / detail panel: raised bay + bolt holes + vent slots +
    # round port + pads (rapid boolean detailing, DIFFERENCE + UNION).
    try:
        top = 0.2

        def boss(name, w, d, cx, cy, h=0.12):
            # Embed 0.04 into the panel so the UNION isn't a coplanar-face case.
            return cube(name, w, d, h + 0.04,
                        loc=(cx, cy, top + (h + 0.04) / 2.0 - 0.04))

        p = plate("Greeble", sx=3.4, sy=3.4, sz=0.4)
        cut(p, boss("g_bay", 1.7, 1.05, -0.15, 0.55, h=0.14), 'UNION')
        for i, (bx, by) in enumerate([(-0.85, 0.3), (0.5, 0.3),
                                      (-0.85, 0.82), (0.5, 0.82)]):
            cut(p, cyl("g_bolt%d" % i, 0.07, 2.0, loc=(bx, by, 0)))
        for i, vy in enumerate([-0.35, -0.58, -0.81]):
            cut(p, cube("g_vent%d" % i, 1.5, 0.11, 2.0, loc=(-0.35, vy, 0)))
        cut(p, cyl("g_port", 0.3, 2.0, loc=(1.0, -0.55, 0)))
        for i, (qx, qy) in enumerate([(0.92, 0.72), (0.92, 0.32)]):
            cut(p, boss("g_pad%d" % i, 0.32, 0.32, qx, qy, h=0.1), 'UNION')
        render_to("shot3-greeble.png")
        clear_scene()
    except Exception:
        import traceback
        report["errors"].append("shot3: " + traceback.format_exc())
        clear_scene()

    # Shot 4 — Pipe draped flat across a panel (build_pipe returns CURVE data).
    try:
        plate("PipePanel", sx=3.4, sy=3.4, sz=0.5)
        z = 0.33  # just above the top face (0.25) so it rides the surface
        pts = [Vector((-1.4, -0.85, z)), Vector((0.35, -0.85, z)),
               Vector((0.35, 1.15, z))]
        curve = C_geo.build_pipe(pts, radius=0.1, bevel_res=12)
        if curve is not None:
            _link(bpy.data.objects.new("HF_Pipe", curve))
        render_to("shot4-pipe.png")
        clear_scene()
    except Exception:
        import traceback
        report["errors"].append("shot4: " + traceback.format_exc())
        clear_scene()

finally:
    # Restore the user's scene and delete everything this script created.
    try:
        win.scene = orig_scene
    except Exception as exc:
        report["errors"].append("restore: " + str(exc))
    try:
        cam = scene.camera
        if cam:
            data = cam.data
            bpy.data.objects.remove(cam, do_unlink=True)
            if data.users == 0:
                bpy.data.cameras.remove(data)
        clear_scene()
        bpy.data.scenes.remove(scene)
    except Exception as exc:
        report["errors"].append("cleanup: " + str(exc))

print("Hardflow gallery ->", OUT)
print("rendered:", [r["file"] for r in report["rendered"]])
if report["errors"]:
    print("errors:", report["errors"])
