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


def snap_to_candidates(value, candidates, tol):
    """Snap a scalar `value` to the nearest entry in `candidates` within `tol`;
    if none is close enough (or `candidates` is empty) return `value` unchanged.
    Used for direct-modeling inference: snapping a push/pull distance to a real
    vertex / feature height instead of the free-drag value."""
    best = value
    best_d = None
    for c in candidates:
        d = abs(c - value)
        # Within tol (inclusive); strict improvement keeps it deterministic --
        # on an exact tie the FIRST candidate wins regardless of iteration order.
        if d <= tol and (best_d is None or d < best_d):
            best_d = d
            best = c
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


# Lower number = more precise / preferred snap target when distances tie.
_SNAP_PRIORITY = {'VERT': 0, 'MID': 1, 'EDGE': 2}


def resolve_snap(candidates, tie_px=4.0):
    """Disambiguate competing geometry-snap hits. `candidates` is a list of
    (kind, hit) where hit is (index, (x, y), dist) or None. Returns the chosen
    (kind, hit), or None when nothing snapped.

    Picks the geometrically *nearest* hit, but when several land within `tie_px`
    of the closest one, the most precise kind wins (VERT > MID > EDGE). So a
    cursor sitting on an edge right next to a vertex snaps to the vertex, while a
    clearly-closer edge still beats a far vertex -- instead of the old strict
    VERT-then-MID-then-EDGE order that let a far vertex hijack a near edge."""
    real = [(k, h) for (k, h) in candidates if h is not None]
    if not real:
        return None
    nearest = min(d for _k, (_i, _p, d) in real)
    close = [kh for kh in real if kh[1][2] - nearest <= tie_px]
    return min(close, key=lambda kh: _SNAP_PRIORITY.get(kh[0], 99))
