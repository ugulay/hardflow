# Pure topology-cleanup predicates -- stdlib only, no bpy.
#
# Module 4 (MeshMachine parity) hardens the post-boolean cleanup so a cut mesh
# survives a Subdivision surface without shading artifacts. A boolean scatters two
# kinds of garbage a SubD hates: near-zero-area *sliver* faces, and redundant
# valence-2 vertices sitting mid-edge along an otherwise straight run. The bmesh
# surgery lives in core/geometry (dissolve_boolean_ngons + _clean_boolean_slivers);
# the geometric *decisions* -- is this face a sliver? is this vertex redundant? --
# are pure and live here so tests/test_core.py can pin them without a live Blender.


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _length(v):
    return (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5


def triangle_area(a, b, c):
    """Area of the 3D triangle (a, b, c): ``0.5 * |(b - a) x (c - a)|``. Zero for
    a degenerate (collinear) triangle. Pure float."""
    return 0.5 * _length(_cross(_sub(b, a), _sub(c, a)))


def polygon_area(points):
    """Area of a planar 3D polygon via Newell's cross sum:
    ``0.5 * |Σ_i v_i x v_{i+1}|`` (indices wrap). The cross sum is the polygon's
    *area vector*; it is translation-invariant for a closed loop, so it is robust
    for convex or concave planar faces and returns ~0 for a degenerate/sliver
    face. Fewer than 3 points -> 0. Pure float."""
    n = len(points)
    if n < 3:
        return 0.0
    sx = sy = sz = 0.0
    for i in range(n):
        c = _cross(points[i], points[(i + 1) % n])
        sx += c[0]
        sy += c[1]
        sz += c[2]
    return 0.5 * _length((sx, sy, sz))


def is_sliver(points, area_eps=1e-7):
    """True when a face is a near-zero-area sliver -- its area is at or under
    `area_eps` (or it has fewer than 3 verts). These are exactly the degenerate
    off-cuts a boolean leaves that pinch a Subdivision surface. Pure."""
    if len(points) < 3:
        return True
    return polygon_area(points) <= area_eps


def collinear(a, b, c, eps=1e-6):
    """True when `b` lies on (within `eps` of) the straight segment a->c -- i.e.
    the triangle (a, b, c) is degenerate. Measured as twice the triangle area
    (``|(b-a) x (c-a)|``) so it scales with the arm lengths; the cleanup uses it to
    spot a vertex that adds nothing to a straight edge. Pure."""
    return _length(_cross(_sub(b, a), _sub(c, a))) <= eps


def redundant_vertex(prev, v, nxt, eps=1e-6):
    """A mid-edge (valence-2) vertex `v` between neighbors `prev` and `nxt` is
    redundant when the three are collinear: dissolving it removes an unnecessary
    vertex without changing the silhouette, which is the SubD-stabilizing win on a
    boolean cut line. Named alias of `collinear` for the caller's intent. Pure."""
    return collinear(prev, v, nxt, eps)
