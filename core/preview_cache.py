# Pure caching / culling math for the live boolean preview -- stdlib only.
#
# The `J` live preview (operators/draw_cut._sync_live_boolean) hangs a temporary
# Boolean modifier on every target and refreshes it on *every* mouse-move frame.
# On a 1M+ poly target that per-frame churn stutters the viewport even though the
# cutter usually only touches a small corner of the mesh. This module answers the
# two pure questions that make the preview cheap, with NO bpy dependency so they
# stay unit-testable on plain CPython (core-isolation rule):
#
#   1) "Did the cursor move enough to be worth recomputing?"  -> a distance gate,
#      so a still / barely-nudged mouse doesn't re-bake the boolean each frame.
#   2) "Does the cutter's bounding box actually reach this target?" -> AABB overlap,
#      so a heavy target the cut isn't near never carries the temp modifier at all
#      (the practical form of "only work the local intersecting region").
#
# operators/base.LivePreviewCommand / operators/draw_cut own the bpy side (reading
# world bounds, attaching modifiers); they call in here for the decision math.
# Layer rule: no bpy / bpy.ops / gpu / blf (same discipline as core/grid.py).


def moved_enough(last, current, threshold):
    """True when `current` is at least `threshold` away from `last` (squared
    Euclidean distance under the hood, so no sqrt). `last` None means "never
    computed yet" -> always True. A non-positive threshold disables the gate
    (always True). Points are any equal-length numeric sequences (2D screen px or
    3D world meters); mismatched lengths compare on the shorter one.

        >>> moved_enough(None, (0, 0), 5)
        True
        >>> moved_enough((0.0, 0.0), (1.0, 1.0), 5.0)   # dist ~1.41 < 5
        False
        >>> moved_enough((0.0, 0.0), (4.0, 4.0), 5.0)   # dist ~5.66 >= 5
        True
    """
    if last is None or threshold <= 0.0:
        return True
    n = min(len(last), len(current))
    d2 = sum((current[i] - last[i]) ** 2 for i in range(n))
    return d2 >= threshold * threshold


def aabb(points):
    """Axis-aligned bounding box (min_corner, max_corner) of an iterable of
    points (each an equal-length numeric sequence). Returns None for an empty
    input. Works in any dimension the points share.

        >>> aabb([(0, 0, 0), (1, 2, -1)])
        ((0, 0, 0), (1, 2, -1))
    """
    pts = list(points)
    if not pts:
        return None
    dim = len(pts[0])
    lo = [min(p[i] for p in pts) for i in range(dim)]
    hi = [max(p[i] for p in pts) for i in range(dim)]
    return (tuple(lo), tuple(hi))


def expand_aabb(box, margin):
    """Grow an (min, max) box outward by `margin` on every axis (a shrink for a
    negative margin, clamped so min never crosses max). Used to pad the cutter's
    box so a target just touching the cut still counts as overlapping despite
    float slop. Returns None for a None box."""
    if box is None:
        return None
    lo, hi = box
    dim = len(lo)
    nlo, nhi = [], []
    for i in range(dim):
        a, b = lo[i] - margin, hi[i] + margin
        if a > b:                       # over-shrunk: collapse to the midpoint
            a = b = 0.5 * (lo[i] + hi[i])
        nlo.append(a)
        nhi.append(b)
    return (tuple(nlo), tuple(nhi))


def boxes_overlap(a, b):
    """True when two AABBs (each (min, max)) intersect or touch on every shared
    axis (the separating-axis test for boxes). A None box overlaps nothing.

        >>> boxes_overlap(((0, 0), (1, 1)), ((0.5, 0.5), (2, 2)))
        True
        >>> boxes_overlap(((0, 0), (1, 1)), ((2, 2), (3, 3)))
        False
    """
    if a is None or b is None:
        return False
    (alo, ahi), (blo, bhi) = a, b
    for i in range(min(len(alo), len(blo))):
        if ahi[i] < blo[i] or bhi[i] < alo[i]:
            return False
    return True


def point_in_box(point, box):
    """True when `point` lies inside (or on) the AABD `box` ((min, max)) on every
    shared axis. None box contains nothing."""
    if box is None:
        return False
    lo, hi = box
    for i in range(min(len(point), len(lo))):
        if point[i] < lo[i] or point[i] > hi[i]:
            return False
    return True


class PreviewGate:
    """Tiny stateful distance gate for a live-preview loop: remembers the last
    position it accepted and answers `should_update(pos)` -- True the first time
    and whenever the cursor has since moved at least `threshold`, recording the
    new position on a True. Keeps the per-frame gating decision (and its one
    piece of state) out of the bpy operator so it can be tested directly.

        gate = PreviewGate(threshold=0.01)   # ~1 cm in world units
        if gate.should_update(cursor_world):
            resync_the_preview()
    """

    def __init__(self, threshold=0.0):
        self.threshold = threshold
        self._last = None

    def should_update(self, pos):
        if moved_enough(self._last, pos, self.threshold):
            self._last = tuple(pos)
            return True
        return False

    def reset(self):
        """Forget the last position so the next `should_update` always fires
        (call when the preview target set or shape mode changes)."""
        self._last = None
