# Pure transform helpers for the array / radial-array tools.
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


def fit_scale(insert_size, target_feature, fraction=0.25, default=1.0):
    """Uniform scale that fits an INSERT of size `insert_size` to `fraction` of a
    target's local feature size -- smart scale on placement. Returns
    `default` when either size is non-positive. Pure arithmetic, unit-tested; the
    bbox measurement lives in core/asset.py."""
    if insert_size <= 0.0 or target_feature <= 0.0:
        return default
    return (target_feature * fraction) / insert_size


def adaptive_dimension(max_dimension, fraction=0.02, min_value=0.001,
                       max_value=1.0):
    """A length that scales with an object's size: `fraction` of its largest
    dimension, clamped to [min_value, max_value]. Lets a bevel width / cut
    chamfer read the same on a 5 cm bracket and a 50 m hull instead of a fixed
    value that's invisible on one and huge on the other. Returns `min_value` when
    the dimension is unknown (<= 0). Pure arithmetic, unit-tested."""
    if max_dimension <= 0.0:
        return min_value
    return max(min_value, min(max_value, max_dimension * fraction))


def dice_coordinates(lo, hi, count):
    """Interior cut positions that slice the span [lo, hi] into `count` equal
    pieces. Returns the `count - 1` evenly spaced interior coordinates (empty for
    count <= 1). Pure arithmetic, unit-tested."""
    count = max(1, int(count))
    if count == 1 or hi <= lo:
        return []
    step = (hi - lo) / count
    return [lo + step * i for i in range(1, count)]


def cable_points(p0, p1, segments=12, sag=0.0, axis=2):
    """Points along one hanging-cable span from p0 to p1 (both endpoints
    included). The span is linearly interpolated, then drooped with a parabolic
    sag: 0 at the ends, `sag` metres at mid-span, pulling along -`axis` (gravity;
    axis 2 = world Z). sag=0 yields a straight segment. `segments` >= 1
    sub-divisions. Pure arithmetic -- no bpy/mathutils -- so the cable shape is
    unit-tested without Blender (the curve build lives in operators/pipe.py)."""
    segments = max(1, int(segments))
    out = []
    for i in range(segments + 1):
        t = i / segments
        p = [p0[k] + (p1[k] - p0[k]) * t for k in range(3)]
        p[axis] -= 4.0 * sag * t * (1.0 - t)
        out.append((p[0], p[1], p[2]))
    return out


def cable_chain(points, segments=12, sag=0.0, axis=2):
    """A sagging cable through a list of >=2 anchor points: each consecutive span
    is drooped with `cable_points` and the spans are joined without duplicating
    the shared anchors. Fewer than 2 points are returned unchanged. Pure
    arithmetic, no bpy."""
    if len(points) < 2:
        return [tuple(p) for p in points]
    out = [tuple(points[0])]
    for a, b in zip(points[:-1], points[1:]):
        out.extend(cable_points(a, b, segments, sag, axis)[1:])
    return out
