# Pure poly-line / freehand-stroke path math, stdlib arithmetic only: stroke
# simplification (Ramer-Douglas-Peucker), corner-cut smoothing (Chaikin),
# an interpolating spline through anchors (centripetal Catmull-Rom) and even
# arc-length re-sampling. Points are (x, y, z) tuples (any dimension >= 2
# actually works). No bpy / mathutils here, so everything is unit-tested
# without Blender (mirrors core/grid.py and core/transform.py); the curve
# objects are built in operators/pipe.py.
import math


def _dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(len(a))))


def _lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a)))


def path_length(points):
    """Total arc length of a poly-line (0.0 for fewer than 2 points). Pure
    arithmetic, unit-tested."""
    return sum(_dist(a, b) for a, b in zip(points[:-1], points[1:]))


def dedup_points(points, tol=1e-9):
    """Drop near-duplicate CONSECUTIVE points (keeps input order, returns new
    tuples). Guards the spline / resample math against zero-length spans."""
    out = []
    for p in points:
        q = tuple(p)
        if not out or _dist(out[-1], q) > tol:
            out.append(q)
    return out


def _segment_distance(p, a, b):
    """Distance from point `p` to the SEGMENT a-b (not the infinite line), so a
    stroke that doubles back is still simplified sanely."""
    ab2 = sum((b[i] - a[i]) ** 2 for i in range(len(a)))
    if ab2 <= 0.0:
        return _dist(p, a)
    t = sum((p[i] - a[i]) * (b[i] - a[i]) for i in range(len(a))) / ab2
    t = max(0.0, min(1.0, t))
    return _dist(p, _lerp(a, b, t))


def rdp_simplify(points, epsilon):
    """Ramer-Douglas-Peucker: reduce a dense poly-line (a freehand stroke) to
    the fewest points that stay within `epsilon` of the original. Endpoints are
    always kept; `epsilon` <= 0 or fewer than 3 points return a plain copy.
    Iterative (no recursion limit on long strokes). Pure arithmetic."""
    pts = [tuple(p) for p in points]
    if len(pts) < 3 or epsilon <= 0.0:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i0, i1 = stack.pop()
        if i1 <= i0 + 1:
            continue
        d_max, i_max = -1.0, i0
        for i in range(i0 + 1, i1):
            d = _segment_distance(pts[i], pts[i0], pts[i1])
            if d > d_max:
                d_max, i_max = d, i
        if d_max > epsilon:
            keep[i_max] = True
            stack.append((i0, i_max))
            stack.append((i_max, i1))
    return [p for p, k in zip(pts, keep) if k]


def chaikin_smooth(points, iterations=1, closed=False):
    """Chaikin corner cutting: each pass replaces every edge with its 1/4 and
    3/4 points, rounding corners while shrinking toward the control polygon.
    Open paths keep their exact endpoints; `closed` cuts around the wrap too.
    Pure arithmetic."""
    pts = [tuple(p) for p in points]
    for _ in range(max(0, int(iterations))):
        if len(pts) < 3:
            break
        edges = list(zip(pts, pts[1:] + [pts[0]])) if closed else \
            list(zip(pts[:-1], pts[1:]))
        cut = []
        for a, b in edges:
            cut.append(_lerp(a, b, 0.25))
            cut.append(_lerp(a, b, 0.75))
        pts = cut if closed else [pts[0]] + cut + [pts[-1]]
    return pts


def catmull_rom(points, samples=6, closed=False, alpha=0.5):
    """Interpolating spline THROUGH the anchor points: centripetal Catmull-Rom
    (`alpha` 0.5; 0 = uniform), evaluated `samples` steps per span. The returned
    dense poly-line contains every anchor exactly (open paths keep both
    endpoints; closed paths wrap without repeating the seam). Centripetal
    parameterization avoids the loops/overshoots uniform CR develops on the
    uneven spacing click-placed anchors have. Fewer than 3 distinct points come
    back as a plain copy. Pure arithmetic."""
    pts = dedup_points(points)
    if closed and len(pts) > 2 and _dist(pts[0], pts[-1]) <= 1e-9:
        pts = pts[:-1]
    if len(pts) < 3:
        return pts
    samples = max(1, int(samples))
    dim = len(pts[0])

    def knot(t, a, b):
        return t + max(_dist(a, b) ** alpha, 1e-9)

    def span(p0, p1, p2, p3):
        """Barry-Goldman evaluation of one p1->p2 span; returns `samples`
        points from p1 inclusive to p2 exclusive."""
        t0 = 0.0
        t1 = knot(t0, p0, p1)
        t2 = knot(t1, p1, p2)
        t3 = knot(t2, p2, p3)
        out = []
        for s in range(samples):
            t = t1 + (t2 - t1) * (s / samples)

            def mix(pa, pb, ta, tb):
                if tb - ta <= 1e-12:
                    return pa
                w = (t - ta) / (tb - ta)
                return tuple(pa[i] + (pb[i] - pa[i]) * w for i in range(dim))

            a1 = mix(p0, p1, t0, t1)
            a2 = mix(p1, p2, t1, t2)
            a3 = mix(p2, p3, t2, t3)
            b1 = mix(a1, a2, t0, t2)
            b2 = mix(a2, a3, t1, t3)
            out.append(mix(b1, b2, t1, t2))
        return out

    n = len(pts)
    out = []
    if closed:
        for i in range(n):
            out.extend(span(pts[(i - 1) % n], pts[i],
                            pts[(i + 1) % n], pts[(i + 2) % n]))
    else:
        # Ghost endpoints by reflection so the curve starts/ends at the anchors
        # with a natural tangent.
        first = tuple(2 * pts[0][i] - pts[1][i] for i in range(dim))
        last = tuple(2 * pts[-1][i] - pts[-2][i] for i in range(dim))
        ext = [first] + pts + [last]
        for i in range(1, n):
            out.extend(span(ext[i - 1], ext[i], ext[i + 1], ext[i + 2]))
        out.append(pts[-1])
    return out


def resample_path(points, step, closed=False):
    """Re-sample a poly-line at even `step` arc-length spacing. Open paths keep
    both exact endpoints (the last span may be shorter); closed paths wrap and
    do not repeat the seam point. `step` <= 0 or fewer than 2 distinct points
    return a plain copy. Pure arithmetic."""
    pts = dedup_points(points)
    if closed and len(pts) > 2:
        pts = pts + [pts[0]]
    if len(pts) < 2 or step <= 0.0:
        return pts
    out = [pts[0]]
    carry = 0.0                 # distance already walked into the current span
    for a, b in zip(pts[:-1], pts[1:]):
        span = _dist(a, b)
        d = step - carry        # distance to the next emitted sample
        while d <= span:
            out.append(_lerp(a, b, d / span))
            d += step
        carry = span - (d - step)
    tail = pts[-1]
    if closed:
        if _dist(out[-1], tail) <= 1e-9:
            out.pop()           # landed exactly on the seam
    elif _dist(out[-1], tail) > 1e-9:
        out.append(tail)        # open paths always keep the true endpoint
    return out
