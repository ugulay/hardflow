# Geometry (vertex / edge) snap -- pure 2D screen-space math.
# The operator projects the target's world vertices onto the screen; this module
# only finds the "nearest to the cursor". No bpy/mathutils needed, testable with
# plain tuples.
import math


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def nearest_point(cursor, points, threshold):
    """points: [(x, y) | None, ...]. If the nearest point to cursor is within
    the threshold, returns (index, (x, y), dist); otherwise None. None elements
    are skipped (projections that fall behind the camera)."""
    best = None
    for i, p in enumerate(points):
        if p is None:
            continue
        d = _dist(cursor, p)
        if d <= threshold and (best is None or d < best[2]):
            best = (i, p, d)
    return best


def closest_point_on_segment(p, a, b):
    """The nearest point on the segment [a, b] to point p (2D)."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    if ll <= 1e-12:           # degenerate edge (a == b)
        return (ax, ay)
    t = ((px - ax) * dx + (py - ay) * dy) / ll
    t = max(0.0, min(1.0, t))
    return (ax + t * dx, ay + t * dy)


def nearest_on_segments(cursor, segments, threshold):
    """segments: [((x1,y1),(x2,y2)) | endpoints may be None, ...]. If the nearest
    on-edge point to cursor is within the threshold, returns (index, (x, y),
    dist)."""
    best = None
    for i, seg in enumerate(segments):
        a, b = seg
        if a is None or b is None:
            continue
        c = closest_point_on_segment(cursor, a, b)
        d = _dist(cursor, c)
        if d <= threshold and (best is None or d < best[2]):
            best = (i, c, d)
    return best
