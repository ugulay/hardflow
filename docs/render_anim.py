"""Render the frames for the README hero GIF (docs/img/hardflow-demo.gif).

Run it INSIDE Blender with the Hardflow add-on enabled (Text Editor ▸ Open ▸
this file ▸ Run Script). It builds a greeble panel with the add-on's real
booleans and renders, in an isolated temp scene:

  * a build-up sequence  — the detail groups appearing one at a time, and
  * a 360° turntable      — of the finished part,

as PNG frames into a temp folder (printed at the end). It is non-destructive:
the temp scene + camera are deleted and your original scene restored; nothing
is saved.

Blender's bundled Python has no Pillow, so stitch the frames into the GIF from
an OUTSIDE Python that does (`pip install pillow`):

    import os
    from PIL import Image
    FR = r"<the folder printed below>"
    order = ["b%02d" % i for i in range(6)] + ["t%02d" % i for i in range(30)]
    dur = [550, 420, 420, 420, 420, 650] + [70] * 30
    imgs = [Image.open(os.path.join(FR, n + ".png")).convert("RGB") for n in order]
    W = 640
    if imgs[0].width > W:
        h = round(imgs[0].height * W / imgs[0].width)
        imgs = [im.resize((W, h), Image.LANCZOS) for im in imgs]
    pal = imgs[5].quantize(colors=256, method=Image.MEDIANCUT)
    fr = [im.quantize(palette=pal, dither=Image.FLOYDSTEINBERG) for im in imgs]
    fr[0].save("docs/img/hardflow-demo.gif", save_all=True, append_images=fr[1:],
               duration=dur, loop=0, optimize=True, disposal=1)
"""
import os
import math
import bmesh
import bpy
from mathutils import Vector


def _hardflow():
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


C_bool = _hardflow().core.boolean

FRAMES = os.path.join(bpy.app.tempdir, "hardflow_frames")
os.makedirs(FRAMES, exist_ok=True)

report = {"frames": [], "errors": []}
win = bpy.context.window_manager.windows[0]
orig_scene = win.scene
scene = bpy.data.scenes.new("HF_Anim")
TOP = 0.2
N_GROUPS = 5
BASE_ANGLE = -45.0


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


def plate(name, sx=3.4, sy=3.4, sz=0.4, bevel=0.03):
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


def boss(name, w, d, cx, cy, h=0.12):
    return cube(name, w, d, h + 0.04, loc=(cx, cy, TOP + (h + 0.04) / 2.0 - 0.04))


def apply_group(p, gi):
    if gi == 0:
        cut(p, boss("g_bay", 1.7, 1.05, -0.15, 0.55, h=0.14), 'UNION')
    elif gi == 1:
        for i, (bx, by) in enumerate([(-0.85, 0.3), (0.5, 0.3),
                                      (-0.85, 0.82), (0.5, 0.82)]):
            cut(p, cyl("g_bolt%d" % i, 0.07, 2.0, loc=(bx, by, 0)))
    elif gi == 2:
        for i, vy in enumerate([-0.35, -0.58, -0.81]):
            cut(p, cube("g_vent%d" % i, 1.5, 0.11, 2.0, loc=(-0.35, vy, 0)))
    elif gi == 3:
        cut(p, cyl("g_port", 0.3, 2.0, loc=(1.0, -0.55, 0)))
    elif gi == 4:
        for i, (qx, qy) in enumerate([(0.92, 0.72), (0.92, 0.32)]):
            cut(p, boss("g_pad%d" % i, 0.32, 0.32, qx, qy, h=0.1), 'UNION')


def build_greeble(name, n_groups):
    p = plate(name)
    for gi in range(n_groups):
        apply_group(p, gi)
    return p


def setup_render():
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.resolution_x = 720
    scene.render.resolution_y = 540
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
        sh.cavity_type = 'BOTH'
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
    cam = bpy.data.objects.new("HF_Cam", bpy.data.cameras.new("HF_Cam"))
    cam.data.type = 'ORTHO'
    _link(cam)
    scene.camera = cam
    return cam


def place_cam(cam, angle_deg, elev=5.2, radius=9.0, oscale=5.5):
    a = math.radians(angle_deg)
    cam.location = (radius * math.cos(a), radius * math.sin(a), elev)
    d = Vector((0.0, 0.0, -0.05)) - Vector(cam.location)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.data.ortho_scale = oscale
    cam.data.shift_x = 0.0
    cam.data.shift_y = 0.0


def render_frame(fname):
    scene.render.filepath = os.path.join(FRAMES, fname)
    area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    with bpy.context.temp_override(window=win, area=area, region=region,
                                   scene=scene):
        bpy.ops.render.opengl(write_still=True, view_context=False)
    report["frames"].append(fname)


def clear_scene():
    cam = scene.camera
    for o in list(scene.collection.objects):
        if o is cam:
            continue
        bpy.data.objects.remove(o, do_unlink=True)


try:
    win.scene = scene
    cam = setup_render()
    place_cam(cam, BASE_ANGLE)
    for stage in range(N_GROUPS + 1):
        try:
            build_greeble("Greeble", stage)
            render_frame("b%02d.png" % stage)
            clear_scene()
        except Exception:
            import traceback
            report["errors"].append("build %d: %s" % (stage,
                                     traceback.format_exc()))
            clear_scene()
    try:
        build_greeble("GreebleFull", N_GROUPS)
        turns = 30
        for i in range(turns):
            place_cam(cam, BASE_ANGLE + (360.0 * i / turns))
            render_frame("t%02d.png" % i)
        clear_scene()
    except Exception:
        import traceback
        report["errors"].append("turntable: " + traceback.format_exc())
        clear_scene()
finally:
    try:
        win.scene = orig_scene
    except Exception as exc:
        report["errors"].append("restore: " + str(exc))
    try:
        c = scene.camera
        if c:
            data = c.data
            bpy.data.objects.remove(c, do_unlink=True)
            if data.users == 0:
                bpy.data.cameras.remove(data)
        clear_scene()
        bpy.data.scenes.remove(scene)
    except Exception as exc:
        report["errors"].append("cleanup: " + str(exc))

print("Hardflow anim frames ->", FRAMES)
print("frames:", len(report["frames"]), "(stitch with Pillow — see docstring)")
if report["errors"]:
    print("errors:", report["errors"])
