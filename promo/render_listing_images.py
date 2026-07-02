# Renders the extensions.blender.org listing images for Hardflow, headless.
# The showcase geometry is built with Hardflow's OWN core functions (shape
# outlines, vent slats, radial sets, robust booleans, pipe sweeps, the cable
# gravity settle), so every image shows real production output.
#
# Run (from the repo root):
#   blender --background --factory-startup --python promo/render_listing_images.py
# Re-render a single image while tweaking:
#   blender -b --factory-startup -P promo/render_listing_images.py -- --only featured
#
# Outputs (promo/out/):
#   icon_256.png                  256 x 256 PNG, transparent   -> listing Icon
#   featured_1920x1080.png        1920 x 1080 PNG, 16:9        -> Featured image
#   preview_1_shapes.png          1920 x 1080 PNG              -> Preview slot 1
#   preview_2_radial_vent.png     1920 x 1080 PNG              -> Preview slot 2
#   preview_3_curves.png          1920 x 1080 PNG              -> Preview slot 3
#
# License: GPL-3.0-or-later (part of Hardflow).
import importlib
import math
import os
import sys
import traceback

import bpy
from mathutils import Vector

# Import the add-on package by folder name, like tests/test_blender.py does.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PARENT = os.path.dirname(_REPO)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)
_PKG = os.path.basename(_REPO)

geometry = importlib.import_module(_PKG + ".core.geometry")
boolean = importlib.import_module(_PKG + ".core.boolean")
grid = importlib.import_module(_PKG + ".core.grid")
path = importlib.import_module(_PKG + ".core.path")
physics = importlib.import_module(_PKG + ".core.physics")

OUT = os.path.join(_REPO, "promo", "out")
DOWN = Vector((0.0, 0.0, -1.0))

ACCENT = (0.05, 0.75, 1.0)          # Hardflow teal
PLATE_COL = (0.030, 0.034, 0.041)   # dark gunmetal
LIGHT_COL = (0.42, 0.44, 0.48)      # machined aluminium
COPPER_COL = (0.60, 0.23, 0.09)
FLOOR_COL = (0.012, 0.013, 0.016)


# --------------------------------------------------------------------------- #
# Studio helpers
# --------------------------------------------------------------------------- #

def enable_gpu():
    """Turn on any Cycles GPU backend that has devices; fall back to CPU."""
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except Exception:
        return 'CPU'
    for kind in ('OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL'):
        try:
            prefs.compute_device_type = kind
        except Exception:
            continue
        for refresh in ("refresh_devices", "get_devices"):
            try:
                getattr(prefs, refresh)()
                break
            except Exception:
                continue
        found = False
        for dev in prefs.devices:
            dev.use = dev.type in (kind, 'CPU')
            found = found or dev.type == kind
        if found:
            print("[promo] cycles device:", kind)
            return 'GPU'
    print("[promo] cycles device: CPU")
    return 'CPU'


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = enable_gpu()
    scene.cycles.use_denoising = True
    try:
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    return scene


def metal(name, color, rough, metallic=1.0):
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    return mat


def emission(name, color, strength):
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
    bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def add_obj(data, name, mat=None, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0)):
    obj = bpy.data.objects.new(name, data)
    obj.location = loc
    obj.rotation_euler = rot
    bpy.context.scene.collection.objects.link(obj)
    if mat is not None:
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
    return obj


def look_at(obj, target):
    aim = bpy.data.objects.new(obj.name + "_aim", None)
    aim.location = target
    bpy.context.scene.collection.objects.link(aim)
    con = obj.constraints.new('TRACK_TO')
    con.target = aim


def studio(cam_loc, cam_target, lens=50.0, key=2400, rim=3400, fill=600,
           floor=True, ortho_scale=None):
    scene = bpy.context.scene
    world = bpy.data.worlds.new("HF_World")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.008, 0.009, 0.011, 1.0)
    bg.inputs[1].default_value = 1.0
    scene.world = world

    if floor:
        add_obj(geometry.build_plane(60.0, name="HF_Floor"), "Floor",
                metal("HF_MatFloor", FLOOR_COL, 0.34, 0.9))

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = lens
    if ortho_scale is not None:
        cam_data.type = 'ORTHO'
        cam_data.ortho_scale = ortho_scale
    cam = add_obj(cam_data, "Cam", loc=cam_loc)
    look_at(cam, cam_target)
    scene.camera = cam

    def light(name, loc, power, size, color):
        ld = bpy.data.lights.new(name, 'AREA')
        ld.energy = power
        ld.size = size
        ld.color = color
        lo = add_obj(ld, name, loc=loc)
        look_at(lo, cam_target)

    light("Key", (4.5, -4.5, 6.0), key, 5.0, (1.0, 0.97, 0.92))
    light("Rim", (-4.0, 6.5, 4.5), rim, 6.0, (0.75, 0.87, 1.0))
    light("Fill", (-6.5, -3.5, 2.5), fill, 8.0, (0.9, 0.95, 1.0))


def render(filename, w=1920, h=1080, transparent=False, samples=160):
    scene = bpy.context.scene
    scene.render.resolution_x = w
    scene.render.resolution_y = h
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = transparent
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
    scene.cycles.samples = samples
    os.makedirs(OUT, exist_ok=True)
    scene.render.filepath = os.path.join(OUT, filename)
    bpy.ops.render.render(write_still=True)
    print("[promo] wrote", scene.render.filepath)


# --------------------------------------------------------------------------- #
# Geometry helpers (all cutting goes through the production boolean pipeline)
# --------------------------------------------------------------------------- #

def scaled_box(w, h, t, name):
    """A box mesh with the dimensions baked into the vertices (so later Bevel
    modifiers see true sizes, not unit-cube sizes under object scale)."""
    mesh = geometry.build_box(1.0, name=name)
    for v in mesh.vertices:
        v.co.x *= w
        v.co.y *= h
        v.co.z *= t
    return mesh


def _consume_cutter(target, cutter, mode):
    ok, _used, msg = boolean.robust_boolean(bpy.context, target, cutter,
                                            operation=mode)
    if not ok:
        print("[promo] boolean failed:", msg)
    data = cutter.data
    bpy.data.objects.remove(cutter)
    bpy.data.meshes.remove(data)


def cut(target, pts2d, depth, z_top, mode='DIFFERENCE', clearance=0.03):
    """Extrude a 2D outline into a prism cutter and boolean it downward.
    build_prism centers the prism on the corner plane, so put the corners at
    the mid-height of the intended span (z_top + clearance .. z_top - depth)."""
    zc = z_top + (clearance - depth) / 2.0
    corners = [Vector((x, y, zc)) for x, y in pts2d]
    mesh = geometry.build_prism(corners, DOWN, depth + clearance,
                                name="HF_Cutter")
    if mesh is None:
        return
    _consume_cutter(target, add_obj(mesh, "HF_Cutter"), mode)


def multi_cut(target, outlines, depth, z_top, mode='DIFFERENCE',
              clearance=0.03):
    """All outlines baked into ONE prism cutter -> one boolean (the in-draw
    array / vent path)."""
    zc = z_top + (clearance - depth) / 2.0
    sets = [([Vector((x, y, zc)) for x, y in pts], DOWN)
            for pts in outlines if pts]
    mesh = geometry.build_prisms(sets, depth + clearance, name="HF_Cutter")
    if mesh is None:
        return
    _consume_cutter(target, add_obj(mesh, "HF_Cutter"), mode)


def groove(target, pts2d, z_top, r=0.02, sink=0.6):
    """A panel-line groove: sweep a round profile along the path and subtract
    it (exactly what HARDFLOW_OT_panel_line does)."""
    lifted = [(x, y, z_top + r * (1.0 - sink)) for x, y in pts2d]
    dense = path.catmull_rom(lifted, samples=8)
    mesh = geometry.build_pipe_mesh(dense, geometry.round_profile(r, 16),
                                    name="HF_Groove")
    if mesh is None:
        return
    _consume_cutter(target, add_obj(mesh, "HF_Groove"), 'DIFFERENCE')


def harden(obj, width=0.01, segments=2, angle=30.0):
    """Machined edges: apply an angle-limited bevel (the Smart Sharpen look)."""
    mod = obj.modifiers.new("HF_EdgeBevel", 'BEVEL')
    mod.limit_method = 'ANGLE'
    mod.angle_limit = math.radians(angle)
    mod.width = width
    mod.segments = segments
    mod.use_clamp_overlap = True
    with bpy.context.temp_override(active_object=obj, object=obj):
        bpy.ops.object.modifier_apply(modifier=mod.name)


def bolt_ring(center, ring_r, count, bolt_r, z_top, proud=0.028, embed=0.012):
    """Hex bolt heads spun about the center with grid.radial_sets (the v1.20
    bolt-circle array)."""
    base = (center[0] + ring_r, center[1])
    outline = grid.ngon_points(base, (base[0] + bolt_r, base[1] + bolt_r * 0.3), 6)
    sets = grid.radial_sets(outline, count, center=center)
    zc = z_top + (proud - embed) / 2.0
    corner_sets = [([Vector((x, y, zc)) for x, y in pts], DOWN)
                   for pts in sets]
    mesh = geometry.build_prisms(corner_sets, proud + embed, name="HF_Bolts")
    obj = add_obj(mesh, "Bolts", metal("HF_MatLight", LIGHT_COL, 0.28))
    harden(obj, 0.006, 2)
    return obj


def ring_recesses(target, center, ring_r, count, hole_r, z_top, depth=0.02):
    base = (center[0] + ring_r, center[1])
    outline = grid.circle_points(base, (base[0] + hole_r, base[1]), 48)
    multi_cut(target, grid.radial_sets(outline, count, center=center),
              depth, z_top)


def glow_strip(w, h, loc, strength=5.0, name="Glow"):
    return add_obj(scaled_box(w, h, 0.012, name), name,
                   emission("HF_MatAccent%d" % int(strength * 10), ACCENT,
                            strength), loc=loc)


def add_text(body, size, loc, mat, extrude=0.045, bevel=0.007):
    tc = bpy.data.curves.new("HF_Text", 'FONT')
    tc.body = body
    tc.size = size
    tc.extrude = extrude
    tc.bevel_depth = bevel
    tc.align_x = 'CENTER'
    return add_obj(tc, "Text_" + body[:8], mat, loc=loc,
                   rot=(math.pi / 2.0, 0.0, 0.0))


def circle(center, r, segments=64):
    return grid.circle_points(center, (center[0] + r, center[1]), segments)


# --------------------------------------------------------------------------- #
# Scenes
# --------------------------------------------------------------------------- #

def scene_featured():
    reset_scene()
    studio(cam_loc=(0.0, -6.9, 4.3), cam_target=(0.0, 0.5, 0.55), lens=52)
    t = 0.14
    plate = add_obj(scaled_box(3.4, 2.0, t, "Plate"), "Plate",
                    metal("HF_MatPlate", PLATE_COL, 0.42))
    plate.location = (0.0, 0.0, t / 2.0)
    bpy.context.view_layer.update()

    # Left: circular boss recess + hub + bolt circle (radial array).
    boss = (-0.85, 0.1)
    cut(plate, circle(boss, 0.55, 96), 0.05, t)
    floor_z = t - 0.05                       # the recess floor seats the bolts
    hub = add_obj(geometry.build_cylinder(0.32, 0.12, 128, "Hub"), "Hub",
                  metal("HF_MatLight", LIGHT_COL, 0.28),
                  loc=(boss[0], boss[1], floor_z + 0.06))
    harden(hub, 0.012, 2)
    ring_recesses(plate, boss, 0.44, 8, 0.06, floor_z, depth=0.015)

    # Right top: vent grill (grid.vent_slats), cut through.
    slats = grid.vent_slats(grid.box_points((0.25, 0.35), (1.55, 0.95)), 5,
                            ratio=0.45)
    multi_cut(plate, slats, t + 0.02, t)

    # Right middle: slot recess with a glowing accent strip inside.
    cut(plate, grid.slot_points((0.25, -0.35), (1.55, -0.05), 12), 0.06, t)
    glow_strip(1.1, 0.12, (0.9, -0.2, t - 0.06 + 0.008), strength=6.0)

    # Right bottom: a smaller slot, cut through.
    cut(plate, grid.slot_points((0.25, -0.95), (0.95, -0.72), 12), t + 0.02, t)

    # Bottom left: panel-line grooves.
    groove(plate, [(-1.55, -0.45), (-0.5, -0.45), (-0.35, -0.62), (-0.35, -0.92)],
           t, r=0.02)
    groove(plate, [(-1.55, -0.72), (-0.8, -0.72), (-0.62, -0.9)], t, r=0.02)

    harden(plate, 0.009, 2)
    bolt_ring(boss, 0.44, 8, 0.042, floor_z)

    # Standing name + tagline behind the plate.
    add_text("HARDFLOW", 0.62, (0.0, 1.35, 0.55),
             emission("HF_MatName", ACCENT, 9.0))
    add_text("Hard-surface boolean modeling - free & open source", 0.155,
             (0.0, 1.35, 0.3),
             emission("HF_MatTag", (0.78, 0.81, 0.85), 2.4),
             extrude=0.0, bevel=0.0)

    render("featured_1920x1080.png")


def scene_shapes():
    reset_scene()
    studio(cam_loc=(0.0, -6.4, 4.6), cam_target=(0.0, 0.1, 0.15), lens=52)
    t = 0.14
    plate = add_obj(scaled_box(3.8, 2.1, t, "Plate"), "Plate",
                    metal("HF_MatPlate", PLATE_COL, 0.42))
    plate.location = (0.0, 0.0, t / 2.0)
    bpy.context.view_layer.update()

    through = t + 0.02
    # Row 1 (through cuts): box, circle, hexagon, slot.
    cut(plate, grid.box_points((-1.7, 0.25), (-1.15, 0.8)), through, t)
    cut(plate, circle((-0.62, 0.52), 0.29, 64), through, t)
    cut(plate, grid.ngon_points((0.28, 0.52), (0.28 + 0.31, 0.52 + 0.1), 6),
        through, t)
    cut(plate, grid.slot_points((0.95, 0.36), (1.7, 0.68), 12), through, t)

    # Row 2 (glowing recesses + a vent): star, arc, vent.
    star_c = (-1.3, -0.5)
    cut(plate, grid.star_points(star_c, (star_c[0] + 0.34, star_c[1] + 0.1),
                                5, inner_ratio=0.5), 0.07, t)
    glow_strip(0.68, 0.68, (star_c[0], star_c[1], t - 0.07 + 0.008),
               strength=5.0, name="GlowStar")

    arc_c = (-0.3, -0.62)
    cut(plate, grid.arc_points(arc_c, (arc_c[0] + 0.36, arc_c[1] + 0.05), 24,
                               sweep=math.radians(110)), 0.07, t)
    glow_strip(0.75, 0.55, (arc_c[0] + 0.15, arc_c[1] + 0.15,
                            t - 0.07 + 0.008), strength=5.0, name="GlowArc")

    slats = grid.vent_slats(grid.box_points((0.45, -0.85), (1.7, -0.3)), 4,
                            ratio=0.45)
    multi_cut(plate, slats, through, t)

    # Corner fastener bolts for the machined look.
    corners = [(-1.76, 0.9), (1.76, 0.9), (-1.76, -0.9), (1.76, -0.9)]
    outlines = [grid.ngon_points(c, (c[0] + 0.05, c[1] + 0.015), 6)
                for c in corners]
    zc = t + (0.03 - 0.012) / 2.0
    sets = [([Vector((x, y, zc)) for x, y in pts], DOWN) for pts in outlines]
    bolts = add_obj(geometry.build_prisms(sets, 0.042, "HF_Bolts"), "Bolts",
                    metal("HF_MatLight", LIGHT_COL, 0.28))
    harden(bolts, 0.005, 2)

    harden(plate, 0.009, 2)
    render("preview_1_shapes.png")


def scene_radial():
    reset_scene()
    studio(cam_loc=(0.3, -6.2, 4.4), cam_target=(0.0, 0.15, 0.2), lens=54)
    t = 0.15
    plate = add_obj(scaled_box(3.2, 2.0, t, "Plate"), "Plate",
                    metal("HF_MatPlate", PLATE_COL, 0.42))
    plate.location = (0.0, 0.0, t / 2.0)
    bpy.context.view_layer.update()

    # Center: turbine boss — recess + hub + 12-bolt circle + radial slots.
    boss = (-0.35, 0.1)
    cut(plate, circle(boss, 0.6, 96), 0.05, t)
    floor_z = t - 0.05
    hub = add_obj(geometry.build_cylinder(0.33, 0.14, 128, "Hub"), "Hub",
                  metal("HF_MatLight", LIGHT_COL, 0.28),
                  loc=(boss[0], boss[1], floor_z + 0.07))
    harden(hub, 0.012, 2)
    ring_recesses(plate, boss, 0.47, 12, 0.055, floor_z, depth=0.015)

    slot = grid.slot_points((boss[0] + 0.70, boss[1] - 0.05),
                            (boss[0] + 0.94, boss[1] + 0.05), 10)
    multi_cut(plate, grid.radial_sets(slot, 6, center=boss), t + 0.02, t)

    # Right: vent grill.
    slats = grid.vent_slats(grid.box_points((0.85, -0.75), (1.45, 0.55)), 6,
                            ratio=0.45)
    multi_cut(plate, slats, t + 0.02, t)

    # Panel-line grooves, and a glowing slot recess.
    groove(plate, [(-1.45, 0.82), (-0.9, 0.82), (-0.72, 0.66), (-0.72, 0.4)],
           t, r=0.02)
    groove(plate, [(1.45, 0.82), (0.9, 0.82), (0.72, 0.66)], t, r=0.02)
    cut(plate, grid.slot_points((-1.45, -0.88), (-0.55, -0.66), 12), 0.06, t)
    glow_strip(0.72, 0.1, (-1.0, -0.77, t - 0.06 + 0.008), strength=6.0)

    harden(plate, 0.009, 2)
    bolt_ring(boss, 0.47, 12, 0.038, floor_z)
    render("preview_2_radial_vent.png")


def scene_curves():
    reset_scene()
    studio(cam_loc=(0.2, -7.4, 3.6), cam_target=(0.0, 0.1, 0.55), lens=42)
    mat_plate = metal("HF_MatPlate", PLATE_COL, 0.42)
    mat_light = metal("HF_MatLight", LIGHT_COL, 0.28)

    block = add_obj(scaled_box(1.7, 1.3, 0.75, "Block"), "Block", mat_plate,
                    loc=(-0.7, 0.35, 0.375))
    slab = add_obj(scaled_box(1.3, 1.0, 0.34, "Slab"), "Slab", mat_plate,
                   loc=(0.9, -0.35, 0.17))
    post_a = add_obj(scaled_box(0.12, 0.12, 1.35, "PostA"), "PostA", mat_light,
                     loc=(-2.35, 1.05, 0.675))
    post_b = add_obj(scaled_box(0.12, 0.12, 0.55, "PostB"), "PostB", mat_light,
                     loc=(2.1, -0.7, 0.275))
    bpy.context.view_layer.update()

    # A vent on the slab top ties the boolean toolkit into the shot.
    slats = grid.vent_slats(grid.box_points((0.55, -0.65), (1.25, -0.05)), 4,
                            ratio=0.45)
    multi_cut(slab, slats, 0.36, 0.34)
    for obj in (block, slab, post_a, post_b):
        harden(obj, 0.014, 2)
    bpy.context.view_layer.update()

    # Cable: relax a particle chain with the production gravity settle, resting
    # on the scene through a nearest-surface collider (core/physics, v1.21).
    lift = 0.042
    colliders = [(o, o.matrix_world.copy(), o.matrix_world.inverted())
                 for o in (block, slab, post_a, post_b)]

    def collide(p):
        pt = Vector(p)
        moved = False
        if pt.z < lift:
            pt.z = lift
            moved = True
        for obj, mw, mi in colliders:
            ok, loc, nrm, _ = obj.closest_point_on_mesh(mi @ pt)
            if not ok:
                continue
            wloc = mw @ loc
            wn = (mw.to_3x3() @ nrm).normalized()
            delta = pt - wloc
            if delta.dot(wn) < 0.0 or delta.length < lift:
                pt = wloc + wn * lift
                moved = True
        return tuple(pt) if moved else None

    a = (-2.35, 1.05, 1.38)
    b = (2.1, -0.7, 0.58)
    n = 52
    start = [tuple(Vector(a).lerp(Vector(b), i / (n - 1))) for i in range(n)]
    settled = physics.settle_chain(start, pinned=(0, n - 1), slack=1.07,
                                   iterations=320, passes=6,
                                   collide=collide, collide_every=2)
    cable_data = geometry.build_pipe(settled, radius=0.04, bevel_res=6,
                                     name="Cable")
    if hasattr(cable_data, "use_fill_caps"):
        cable_data.use_fill_caps = True
    add_obj(cable_data, "Cable", metal("HF_MatRubber", (0.02, 0.02, 0.023),
                                       0.45, 0.0))

    # Pipes: Catmull-Rom smoothed runs (the Smooth Path spline).
    def pipe(points, radius, mat, name):
        dense = path.catmull_rom(points, samples=8)
        data = geometry.build_pipe(dense, radius=radius, bevel_res=6,
                                   name=name)
        if hasattr(data, "use_fill_caps"):
            data.use_fill_caps = True
        add_obj(data, name, mat)

    z = 0.085
    pipe([(-5.2, 2.0, z), (-0.6, 2.0, z), (0.1, 1.55, z), (5.2, 1.55, z)],
         0.07, mat_light, "Pipe1")
    pipe([(-5.2, 2.35, z), (-0.4, 2.35, z), (0.35, 1.9, z), (5.2, 1.9, z)],
         0.07, metal("HF_MatCopper", COPPER_COL, 0.32), "Pipe2")
    pipe([(-5.2, 2.7, z), (-0.2, 2.7, z), (0.6, 2.25, z), (5.2, 2.25, z)],
         0.055, mat_light, "Pipe3")

    # Glowing connector tips at the cable anchors.
    for loc in (a, b):
        tip = add_obj(geometry.build_cylinder(0.055, 0.1, 32, "Tip"), "Tip",
                      emission("HF_MatTip", ACCENT, 6.0), loc=loc)
        tip.rotation_euler = (math.pi / 2.0, 0.0, 0.0)

    render("preview_3_curves.png")


def scene_icon():
    reset_scene()
    studio(cam_loc=(4.0, -4.0, 3.1), cam_target=(0.0, 0.0, 0.68), lens=50,
           key=4200, rim=2600, fill=2000, floor=False, ortho_scale=2.9)
    block = add_obj(scaled_box(1.5, 1.5, 1.5, "Icon"), "Icon",
                    metal("HF_MatIconBody", (0.09, 0.10, 0.12), 0.4),
                    loc=(0.0, 0.0, 0.75))
    bpy.context.view_layer.update()

    # The boolean essence: a corner notch + a glowing bore.
    cut(block, grid.box_points((0.14, -0.95), (0.95, -0.14)), 1.6, 1.5)
    cut(block, circle((-0.22, 0.22), 0.36, 64), 1.6, 1.5)
    harden(block, 0.05, 3)
    add_obj(geometry.build_cylinder(0.31, 1.4, 48, "Core"), "Core",
            emission("HF_MatCore", ACCENT, 12.0), loc=(-0.22, 0.22, 0.72))
    # A thin teal slit inside the notch so the cut reads at tiny sizes.
    add_obj(scaled_box(0.016, 0.10, 1.38, "Strip"), "Strip",
            emission("HF_MatStrip", ACCENT, 7.0), loc=(0.155, -0.555, 0.72))

    render("icon_256.png", w=256, h=256, transparent=True, samples=200)


SCENES = {
    "icon": scene_icon,
    "featured": scene_featured,
    "shapes": scene_shapes,
    "radial": scene_radial,
    "curves": scene_curves,
}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    failures = []
    for name, fn in SCENES.items():
        if only and name != only:
            continue
        print("[promo] === scene:", name, "===")
        try:
            fn()
        except Exception:
            traceback.print_exc()
            failures.append(name)
    if failures:
        print("[promo] FAILED:", ", ".join(failures))
        sys.exit(1)
    print("[promo] DONE")


main()
