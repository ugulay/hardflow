# Pure hard-surface "sharpen / initialize" math -- stdlib only, no bpy.
#
# Module 3 (HardOps parity) adds a one-shot "Smart Sharpen / Initialize
# HardSurface" operator: mark the hard edges, drop an angle/weight-limited Bevel
# modifier, and cap the stack with a Weighted Normal so the shading reads clean.
# The bmesh edge-marking lives in core/geometry.mark_sharp_edges; the pure
# decisions -- which edges count as "hard" and how wide the auto bevel should be
# -- live here so tests/test_core.py can pin them without a live Blender.
#
# "Dihedral angle" convention (matches bmesh edge.calc_face_angle): the angle
# between the two adjacent FACE NORMALS. Two coplanar faces -> 0; a 90-degree
# fold -> pi/2; a fully back-folded edge -> pi. An edge is "hard" (mark it sharp /
# give it a bevel weight) when that angle reaches the threshold.
import math


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    n = (a[0] * a[0] + a[1] * a[1] + a[2] * a[2]) ** 0.5
    if n < 1e-12:
        return (0.0, 0.0, 0.0)
    return (a[0] / n, a[1] / n, a[2] / n)


def dihedral_angle(normal_a, normal_b):
    """Angle in radians between two face normals -- the edge's dihedral fold.

    ``acos(clamp(dot(unit_a, unit_b), -1, 1))``: 0 for coplanar faces, pi/2 for a
    right-angle fold, pi for a fully reversed edge. Degenerate (zero-length)
    normals return 0 (treated as flat). Pure float."""
    a, b = _norm(normal_a), _norm(normal_b)
    if a == (0.0, 0.0, 0.0) or b == (0.0, 0.0, 0.0):
        return 0.0                       # degenerate normal -> treat as flat
    d = _dot(a, b)
    d = -1.0 if d < -1.0 else 1.0 if d > 1.0 else d
    return math.acos(d)


def should_sharpen(angle, threshold):
    """True when a dihedral `angle` (radians) reaches the `threshold` -- the single
    predicate the sharpen pass applies per edge. Pure."""
    return angle >= threshold


def sharp_edges(edge_normals, threshold):
    """Filter (key, normal_a, normal_b) triples down to the keys whose dihedral
    angle reaches `threshold` (radians) -- the set of hard edges to mark sharp /
    weight. Mirrors what core/geometry.mark_sharp_edges does on the real mesh
    (which uses bmesh's own calc_face_angle), kept pure so the decision is
    unit-tested. Returns the list of qualifying keys, order preserved."""
    out = []
    for key, na, nb in edge_normals:
        if should_sharpen(dihedral_angle(na, nb), threshold):
            out.append(key)
    return out


def adaptive_bevel_width(dimensions, fraction=0.01, floor=1e-4):
    """A bevel width scaled to the object's size: `fraction` of its smallest
    non-zero dimension, floored at `floor`. Keyed to the SMALLEST side because a
    chamfer has to fit the thinnest wall without overlapping itself; a flat or
    degenerate object still gets the visible `floor` bevel. Pure float.

        >>> adaptive_bevel_width((2.0, 2.0, 2.0))   # 1% of 2.0
        0.02
        >>> adaptive_bevel_width((0.0, 0.0, 0.0))    # degenerate -> floor
        0.0001
    """
    dims = [d for d in dimensions if d > floor]
    if not dims:
        return floor
    return max(floor, min(dims) * fraction)
