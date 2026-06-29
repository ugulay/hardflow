# Pure 2D polygon offset (the SketchUp "Offset" tool's math).
#
# Offsets a simple polygon inward (positive distance) or outward (negative) by
# sliding every edge along its inward normal and intersecting the offset edges
# at each vertex (a miter join). No bpy/mathutils -- testable with plain tuples.
# The operator does the in-plane (u, v) <-> world lifting; this module only sees
# 2D points.
import math


def signed_area(points):
    """Twice-the-signed-area sign tells winding: > 0 = counter-clockwise (CCW),
    < 0 = clockwise. Used to make a positive distance always mean 'inward'."""
    n = len(points)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x0, y0 = points[i]
        x1, y1 = points[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s * 0.5


def _line_intersection(p0, d0, p1, d1):
    """Intersection of two lines given as point+direction. Returns None when the
    directions are (near) parallel."""
    cross = d0[0] * d1[1] - d0[1] * d1[0]
    if abs(cross) < 1e-12:
        return None
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    t = (dx * d1[1] - dy * d1[0]) / cross
    return (p0[0] + d0[0] * t, p0[1] + d0[1] * t)


def offset_polygon(points, distance):
    """Offset a simple polygon by `distance` (positive = inward, negative =
    outward), independent of the polygon's winding. Returns the new list of
    points, or None if the polygon is degenerate or the offset edges become
    fully parallel/collapsed.

    Each edge is pushed along its inward normal; consecutive offset edges are
    intersected to find the new (mitred) vertex. Sharp spikes are not clamped --
    a distance larger than the local feature size can self-intersect, which the
    caller should treat as invalid (same contract as the draw tool's
    self-intersection guard)."""
    n = len(points)
    if n < 3 or distance == 0.0:
        return list(points) if n >= 3 else None

    # Normalize winding so the inward normal formula is consistent: work on a
    # CCW copy, where the left normal (-dy, dx) of each edge points inward.
    pts = list(points)
    if signed_area(pts) < 0.0:
        pts = list(reversed(pts))

    # Offset line for each edge, as (point-on-line, direction).
    lines = []
    for i in range(n):
        ax, ay = pts[i]
        bx, by = pts[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        length = math.hypot(ex, ey)
        if length < 1e-12:
            return None                     # zero-length edge -> degenerate
        nx, ny = -ey / length, ex / length  # inward (left) unit normal, CCW
        off = (ax + nx * distance, ay + ny * distance)
        lines.append((off, (ex, ey)))

    out = []
    for i in range(n):
        prev = lines[i - 1]                 # edge ending at vertex i
        cur = lines[i]                      # edge starting at vertex i
        hit = _line_intersection(prev[0], prev[1], cur[0], cur[1])
        if hit is None:
            # Collinear edges: fall back to the offset point itself.
            hit = cur[0]
        out.append(hit)

    # If we reversed for winding, restore the caller's original orientation.
    if signed_area(points) < 0.0:
        out = list(reversed(out))
    return out
