# Pure transform helpers for the array / radial-array tools (Hard Ops spirit).
#
# No bpy / mathutils here -- only arithmetic -- so it is unit-tested without
# Blender (mirrors core/grid.py and core/atlas.py). The bpy side (creating the
# Array modifier + offset empty) lives in operators/array.py.
import math


def radial_step_radians(count, full_turn_deg=360.0):
    """Angle (radians) between successive copies of a radial array. An Array
    modifier driven by an offset empty rotated by this step sweeps `count` copies
    evenly around the pivot. `count` is clamped to at least 1 (a single copy =
    no rotation)."""
    count = max(1, int(count))
    return math.radians(full_turn_deg) / count


def radial_angles_deg(count, full_turn_deg=360.0):
    """The absolute angle (degrees) of each copy in a radial array, copy 0 at 0.
    Useful for previews / labelling; `count` clamped to at least 1."""
    count = max(1, int(count))
    step = full_turn_deg / count
    return [i * step for i in range(count)]


def array_offset_vector(axis, distance, relative_size=0.0):
    """Constant offset vector for a linear Array along a world axis ('X'/'Y'/'Z').
    `distance` is metres; `relative_size` adds a fraction of the object's own size
    along that axis (the caller multiplies it in). Returns a 3-tuple."""
    idx = {'X': 0, 'Y': 1, 'Z': 2}.get(axis, 0)
    out = [0.0, 0.0, 0.0]
    out[idx] = distance + relative_size
    return (out[0], out[1], out[2])


def mirror_axis_flags(axis):
    """(x, y, z) booleans selecting a single world axis from 'X'/'Y'/'Z'. Shared
    by the mirror and symmetrize tools so the axis mapping lives in one place."""
    return (axis == 'X', axis == 'Y', axis == 'Z')
