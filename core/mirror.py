# Pure mirror / symmetry decision math -- stdlib only, no bpy / bmesh / mathutils.
#
# The hard-surface mirror is not "add a Mirror modifier" (Blender has that
# button): it is deciding, from where the user is looking and what they have
# selected, WHICH axis to mirror on, WHICH half to keep, and which side of the
# bisect plane to throw away -- then doing all of it in one keystroke. That
# decision layer is pure arithmetic, so it lives here where tests/test_core.py
# can cover every case without a viewport.
#
# Operator glue (modifier wiring, bmesh bisect/symmetrize) is operators/mirror.py.
import math

AXES = ('X', 'Y', 'Z')


def axis_index(axis):
    """0/1/2 for 'X'/'Y'/'Z'. Raises ValueError on anything else, so a typo in a
    caller surfaces at once instead of silently mirroring on X."""
    return AXES.index(axis)


def axis_from_direction(direction):
    """The world axis a view `direction` (3-vector) most points along: the
    dominant component by magnitude.

    This is what makes the mirror feel like one key: looking roughly down -Y at
    the front of a model and pressing mirror should mirror across X, the axis
    you see left-right... which is NOT this axis. Callers pass the axis they
    want resolved -- `axis_from_direction(view)` gives the axis you are looking
    ALONG (use `screen_axis` for the left-right one). Ties break X > Y > Z so
    the result is deterministic on a perfect 45 deg view."""
    best, best_mag = 'X', -1.0
    for i, axis in enumerate(AXES):
        mag = abs(direction[i])
        if mag > best_mag + 1e-12:
            best, best_mag = axis, mag
    return best


def screen_axis(direction):
    """The axis to mirror across for a view pointing along `direction`: the
    largest axis that is NOT the one you are looking along.

    Mirroring across the view axis is almost never what a modeler wants (it
    would fold the model toward/away from the camera); mirroring left-right is.
    With the depth axis removed, the remaining dominant axis is that one. Ties
    break X > Y > Z."""
    depth = axis_from_direction(direction)
    best, best_mag = None, -1.0
    for i, axis in enumerate(AXES):
        if axis == depth:
            continue
        mag = abs(direction[i])
        if mag > best_mag + 1e-12:
            best, best_mag = axis, mag
    # A perfectly axis-aligned view leaves two zero components: pick the first
    # remaining axis rather than returning None.
    if best is None:
        best = next(a for a in AXES if a != depth)
    return best


def use_axis_flags(axis):
    """(x, y, z) booleans for a Mirror modifier's `use_axis` from one axis."""
    i = axis_index(axis)
    return tuple(j == i for j in range(3))


def keep_positive_side(direction, axis):
    """When bisecting, whether to keep the +`axis` half.

    Keep the half the user is looking at: if the view direction (camera ->
    scene) runs along -axis, the camera sits on the + side, so the + half is the
    visible one. A view exactly edge-on to the axis keeps + as the tie-break, so
    the result is never undefined."""
    return direction[axis_index(axis)] <= 0.0


def bisect_normal(axis, keep_positive):
    """Plane normal (a 3-tuple) for a bisect that discards the unwanted half.

    bmesh's bisect_plane clears the geometry on the side the normal points to
    when `clear_outer` is used, so the normal points at the half being thrown
    away: +axis when we are keeping the negative half, and vice versa."""
    i = axis_index(axis)
    sign = -1.0 if keep_positive else 1.0
    return tuple(sign if j == i else 0.0 for j in range(3))


def symmetrize_direction(axis, keep_positive):
    """The **bmesh op** `symmetrize` direction for keeping one half: ('X', True)
    -> 'X', meaning the +X half is copied onto -X; ('X', False) -> '-X'.

    Verified against Blender 5.2.2: `bmesh.ops.symmetrize` takes
    ['-X', '-Y', '-Z', 'X', 'Y', 'Z'] and rejects the 'POSITIVE_X' spelling --
    that one belongs to the `bpy.ops.mesh.symmetrize` operator, which is what
    `symmetrize_enum` below returns. Mixing them up raises ValueError at the
    call, so the two are kept apart deliberately."""
    return axis if keep_positive else "-" + axis


def symmetrize_enum(axis, keep_positive):
    """The **operator** spelling of the same choice, for
    `bpy.ops.mesh.symmetrize(direction=...)`: 'POSITIVE_X' / 'NEGATIVE_X'."""
    return "%s_%s" % ('POSITIVE' if keep_positive else 'NEGATIVE', axis)


def mirror_point(point, axis, pivot=(0.0, 0.0, 0.0)):
    """Reflect `point` across the plane through `pivot` perpendicular to `axis`.
    The reference the bmesh/modifier paths are checked against in tests."""
    i = axis_index(axis)
    out = list(point)
    out[i] = 2.0 * pivot[i] - point[i]
    return tuple(out)


def is_symmetric(points, axis, pivot=(0.0, 0.0, 0.0), tol=1e-6):
    """Whether `points` is already mirror-symmetric about the plane: every point
    has a partner at its reflection (within `tol`). On-plane points pair with
    themselves. O(n^2), so it is for test-sized sets and small meshes, not a
    per-frame check."""
    pts = [tuple(p) for p in points]
    for p in pts:
        want = mirror_point(p, axis, pivot)
        if not any(_close(want, q, tol) for q in pts):
            return False
    return True


def _close(a, b, tol):
    return all(abs(a[i] - b[i]) <= tol for i in range(3))


def pivot_offset(pivot_world, object_origin_world):
    """How far the mirror plane sits from the object's own origin, per axis.

    A Mirror modifier always mirrors about its object's origin (or a mirror
    object's). Mirroring about the 3D cursor therefore needs a helper at the
    cursor -- this is the offset the operator gives that helper, and 0 on every
    axis means the cursor is already on the origin, so no helper is needed."""
    return tuple(pivot_world[i] - object_origin_world[i] for i in range(3))


def needs_pivot_helper(pivot_world, object_origin_world, tol=1e-6):
    """True when the requested pivot is far enough from the object origin that a
    Mirror modifier needs a mirror-object helper to reach it."""
    return any(abs(d) > tol
               for d in pivot_offset(pivot_world, object_origin_world))


def bisect_angle_ok(axis, normal, tol_deg=1.0):
    """Whether a face `normal` lies in the bisect plane (i.e. the face is
    parallel to the mirror plane, within `tol_deg`).

    Used to warn before a bisect that would shave a wall flat on the seam: a
    face whose normal is perpendicular to the mirror axis is safe, one pointing
    along the axis is not."""
    i = axis_index(axis)
    mag = math.sqrt(sum(c * c for c in normal))
    if mag <= 1e-12:
        return True
    cos_to_axis = abs(normal[i]) / mag
    return cos_to_axis <= math.sin(math.radians(tol_deg))
