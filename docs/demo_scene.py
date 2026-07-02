"""Hardflow demo-scene setup — a camera-ready starting point for recording GIFs.

Run it inside Blender (Text Editor ▸ Open ▸ this file ▸ Run Script, or F3 ▸
"Run Script"). It is *additive and non-destructive*: it never deletes your
existing objects. It drops a small set of clean demo meshes into a fresh
"HF Demo" collection and frames + shades the 3D viewport so every recording
starts from an identical, hard-surface-readable state.

Re-running it clears only the "HF Demo" collection it owns, so you can reset
between takes with a single Run Script.

Tested against Blender 4.2 LTS+ (matches the add-on target).
"""

import bpy
import math

try:
    import mathutils
except Exception:  # pragma: no cover - only ever runs inside Blender
    mathutils = None

DEMO_COLLECTION = "HF Demo"


# --------------------------------------------------------------------------- #
# Scene contents
# --------------------------------------------------------------------------- #
def _demo_collection():
    """Return the (re-created) HF Demo collection, cleared of prior contents."""
    existing = bpy.data.collections.get(DEMO_COLLECTION)
    if existing is not None:
        for obj in list(existing.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        return existing
    coll = bpy.data.collections.new(DEMO_COLLECTION)
    bpy.context.scene.collection.children.link(coll)
    return coll


def _add_plate(coll, name, location, size=(2.0, 2.0, 0.35), bevel=0.04):
    """A beveled 'panel' block — the main surface to cut / push-pull / decal."""
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)

    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.to_mesh(mesh)
    bm.free()

    obj.location = location
    obj.scale = (size[0] / 2.0, size[1] / 2.0, size[2] / 2.0)

    if bevel > 0.0:
        mod = obj.modifiers.new("Bevel", 'BEVEL')
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = 'ANGLE'

    for poly in mesh.polygons:
        poly.use_smooth = False
    return obj


def _add_cylinder(coll, name, location, radius=0.7, depth=1.4):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)

    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=32,
        radius1=radius, radius2=radius, depth=depth,
    )
    bm.to_mesh(mesh)
    bm.free()

    obj.location = location
    return obj


def build_scene():
    coll = _demo_collection()
    plate = _add_plate(coll, "HF_Plate", (0.0, 0.0, 0.0))
    _add_plate(coll, "HF_Plate_Small", (3.2, 0.0, 0.0),
               size=(1.4, 1.4, 0.3))
    _add_cylinder(coll, "HF_Cylinder", (-3.0, 0.0, 0.7))

    # Make the main plate the active/selected object so the tools poll True.
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    plate.select_set(True)
    bpy.context.view_layer.objects.active = plate
    return plate


# --------------------------------------------------------------------------- #
# Viewport framing + shading
# --------------------------------------------------------------------------- #
def _iter_view3d_spaces():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                yield area.spaces.active


def frame_viewport():
    for space in _iter_view3d_spaces():
        r3d = space.region_3d
        try:
            r3d.view_perspective = 'PERSP'
            if mathutils is not None:
                r3d.view_rotation = mathutils.Euler(
                    (math.radians(62.0), 0.0, math.radians(46.0)), 'XYZ'
                ).to_quaternion()
            r3d.view_location = (0.0, 0.0, 0.0)
            r3d.view_distance = 8.0
        except Exception as exc:
            print("Hardflow demo: view framing skipped:", exc)

        shading = space.shading
        try:
            shading.type = 'SOLID'
            shading.light = 'MATCAP'
            shading.show_cavity = True
            shading.cavity_type = 'BOTH'
        except Exception as exc:
            print("Hardflow demo: shading skipped:", exc)

        overlay = space.overlay
        try:
            # Keep the floor grid + axes (nice for scale), drop the clutter.
            overlay.show_cursor = False
            overlay.show_relationship_lines = False
            overlay.show_text = True  # keep the HUD / header text visible
        except Exception as exc:
            print("Hardflow demo: overlay skipped:", exc)


def main():
    plate = build_scene()
    frame_viewport()
    print("Hardflow demo scene ready. Active object:", plate.name)
    print("  N-panel ▸ Hardflow, then record. Ctrl+Shift+D to draw a cut.")


if __name__ == "__main__":
    main()
