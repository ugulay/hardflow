# Pure decal orientation math -- no bpy, no mathutils, plain 3-tuples.
#
# A decal is a thin plane that lies *on* a surface. Given the surface normal at
# the hit point and a desired tangent (the decal's "up" direction along the
# surface, set by the user's roll), we need an orthonormal right-handed basis:
#
#   z_axis  = surface normal       (decal's local +Z, points away from surface)
#   y_axis  = tangent on surface   (decal's local +Y, the roll direction)
#   x_axis  = y_axis x z_axis      (decal's local +X)
#
# Keeping this bpy/mathutils-free means it runs under plain CPython and is
# covered by tests/test_core.py. core/decal.py turns the basis into a
# mathutils.Matrix at the (Blender-only) call site.


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _length(a):
    return _dot(a, a) ** 0.5


def _normalize(a, fallback=(0.0, 0.0, 1.0)):
    n = _length(a)
    if n < 1e-9:
        return fallback
    return (a[0] / n, a[1] / n, a[2] / n)


def base_tangent(normal, world_up=(0.0, 0.0, 1.0)):
    """A stable default tangent on the surface: the world up vector projected
    onto the surface plane. Falls back to world +X when the surface faces
    (anti)parallel to world up (a floor/ceiling), so the result is never zero."""
    z = _normalize(normal)
    # remove the component of world_up along the normal
    proj = _sub(world_up, _scale(z, _dot(world_up, z)))
    if _length(proj) < 1e-6:
        alt = (1.0, 0.0, 0.0)
        proj = _sub(alt, _scale(z, _dot(alt, z)))
    return _normalize(proj)


def rotate_about_axis(vec, axis, angle):
    """Rotate vec around the unit-ish axis by angle radians (Rodrigues'
    rotation). axis is normalized internally."""
    import math
    k = _normalize(axis)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    term1 = _scale(vec, cos_a)
    term2 = _scale(_cross(k, vec), sin_a)
    term3 = _scale(k, _dot(k, vec) * (1.0 - cos_a))
    return _add(_add(term1, term2), term3)


def orientation_basis(normal, tangent):
    """Return an orthonormal right-handed (x, y, z) basis for a decal sitting on
    a surface. z follows the normal; y is the tangent re-orthogonalized onto the
    surface plane; x completes the frame. All three are returned as unit
    3-tuples. Degenerate inputs fall back to the world axes."""
    z = _normalize(normal)
    # re-orthogonalize the tangent against z (Gram-Schmidt)
    y = _sub(tangent, _scale(z, _dot(tangent, z)))
    if _length(y) < 1e-6:
        y = base_tangent(z)
    y = _normalize(y)
    x = _normalize(_cross(y, z))
    # recompute y to guarantee exact orthogonality after the cross
    y = _cross(z, x)
    return x, y, z
