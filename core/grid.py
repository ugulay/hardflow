# Grid snapping.
#   snap_point / grid_lines : v0.1 screen-space (legacy, no longer used by the
#       operator)
#   snap_world / world_grid_segments : v0.2 world-scale, meter-based snap on the
#       projection plane's local (u, v) axes (world-scale / absolute size).
# All pure: no bpy/mathutils needed, testable with plain floats/tuples.
import math


def snap_point(coord, grid_px, enabled):
    if not enabled or grid_px <= 1:
        return (coord[0], coord[1])
    return (round(coord[0] / grid_px) * grid_px,
            round(coord[1] / grid_px) * grid_px)


def snap_angle(anchor, point, step_deg, enabled):
    """Lock point to step_deg increments around anchor; the distance to anchor
    is preserved (angle lock with Shift). Pure 2D."""
    if not enabled or step_deg <= 0:
        return (point[0], point[1])
    dx = point[0] - anchor[0]
    dy = point[1] - anchor[1]
    dist = math.hypot(dx, dy)
    if dist < 1e-9:
        return (point[0], point[1])
    step = math.radians(step_deg)
    ang = round(math.atan2(dy, dx) / step) * step
    return (anchor[0] + math.cos(ang) * dist, anchor[1] + math.sin(ang) * dist)


def snap_world(u, v, size, enabled):
    """Round the (u, v) meter coordinate on the projection plane to the grid."""
    if not enabled or size <= 0:
        return (u, v)
    return (round(u / size) * size, round(v / size) * size)


def snap_world_3d(x, y, z, size, enabled):
    """Round a 3D world point to the world grid, each axis independently.
    3-axis analogue of snap_world; used by the surface/curve tools (pipe, cable)
    to lock free 3D anchor points onto the grid. Pure: stdlib floats only."""
    if not enabled or size <= 0:
        return (x, y, z)
    return (round(x / size) * size,
            round(y / size) * size,
            round(z / size) * size)


def snap_scalar(value, size, enabled):
    """Round a single distance (push/pull amount, offset thickness) to the grid.
    1D analogue of snap_world; used by the direct-modeling Build tools."""
    if not enabled or size <= 0:
        return value
    return round(value / size) * size


def centered_grid_segments(half_extent, spacing, max_lines=400):
    """Grid line segments for a square reference grid centered on the origin,
    spanning [-half_extent, +half_extent] on both axes with `spacing` between
    lines (the construction-grid object). Each element is ((x1, y1), (x2, y2)).
    Returns empty if the parameters are degenerate or the line count would blow
    up. Pure 2D -- the operator lifts these onto the chosen plane."""
    if spacing <= 0 or half_extent <= 0:
        return []
    n = int(half_extent / spacing)          # lines on each side of the center
    if (2 * n + 1) * 2 > max_lines:
        return []
    lo, hi = -n * spacing, n * spacing
    segs = []
    for i in range(-n, n + 1):
        x = i * spacing
        segs.append(((x, lo), (x, hi)))     # vertical line
        segs.append(((lo, x), (hi, x)))     # horizontal line
    return segs


def world_grid_segments(umin, umax, vmin, vmax, size, max_lines=240):
    """Generate grid line segments within the visible (u, v) bounds; each
    element is ((u1, v1), (u2, v2)). Returns empty if the line count exceeds
    max_lines (very small grid or distant camera) -- prevents a blowup."""
    if size <= 0 or umax < umin or vmax < vmin:
        return []
    u0 = math.floor(umin / size) * size
    u1 = math.ceil(umax / size) * size
    v0 = math.floor(vmin / size) * size
    v1 = math.ceil(vmax / size) * size
    nu = int(round((u1 - u0) / size)) + 1
    nv = int(round((v1 - v0) / size)) + 1
    if nu < 0 or nv < 0 or nu + nv > max_lines:
        return []
    segs = []
    for i in range(nu):
        u = u0 + i * size
        segs.append(((u, v0), (u, v1)))
    for j in range(nv):
        v = v0 + j * size
        segs.append(((u0, v), (u1, v)))
    return segs


def grid_lines(region, grid_px, enabled):
    """List of endpoint vertices for the grid lines drawn in the viewport (for
    LINES)."""
    if not enabled or grid_px <= 1:
        return []
    w, h = region.width, region.height
    verts = []
    x = 0
    while x <= w:
        verts.append((x, 0)); verts.append((x, h))
        x += grid_px
    y = 0
    while y <= h:
        verts.append((0, y)); verts.append((w, y))
        y += grid_px
    return verts


def circle_points(center, edge, segments=32):
    """Screen-space circle corners from a center and an edge point."""
    r = math.hypot(edge[0] - center[0], edge[1] - center[1])
    if r < 1e-9:                     # zero-radius drag -> no shape (not a cluster
        return []                    # of coincident points)
    pts = []
    for i in range(segments):
        a = (i / segments) * math.tau
        pts.append((center[0] + math.cos(a) * r,
                    center[1] + math.sin(a) * r))
    return pts


def box_points(a, b):
    """The 4 corners of a rectangle from two diagonal points."""
    return [(a[0], a[1]), (b[0], a[1]), (b[0], b[1]), (a[0], b[1])]


def lock_distance(a, b, dist):
    """The point at exactly `dist` from `a` along the direction `a`->`b` (2D).
    Lets a drawn shape's size lock to a typed dimension (radius / extent /
    segment length) while keeping the cursor's direction. Returns `a` when the
    direction is degenerate (b == a). Pure 2D, unit-tested."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1e-12:
        return (a[0], a[1])
    s = dist / length
    return (a[0] + dx * s, a[1] + dy * s)


def ngon_points(center, edge, sides, rotation=0.0):
    """Screen-space regular-polygon corners from a center and an edge point.
    The edge point sets the circumradius and the orientation of the first
    vertex (so dragging rotates the n-gon); `rotation` adds an extra angular
    offset in radians. `sides` is clamped to at least 3."""
    sides = max(3, int(sides))
    dx = edge[0] - center[0]
    dy = edge[1] - center[1]
    r = math.hypot(dx, dy)
    if r < 1e-9:                      # zero-radius drag -> no shape
        return []
    base = math.atan2(dy, dx) + rotation
    pts = []
    for i in range(sides):
        a = base + (i / sides) * math.tau
        pts.append((center[0] + math.cos(a) * r,
                    center[1] + math.sin(a) * r))
    return pts


def slot_points(a, b, segments=8):
    """Stadium / slot outline (a rectangle with two semicircular caps) from two
    diagonal points a, b. The caps sit on the SHORTER pair of sides; the straight
    sides span the longer axis. `segments` points per cap. Returns the closed
    outline in whatever 2D space a and b live in (screen pixels or plane u, v
    meters), like box_points. A square (equal extents) degenerates to a circle."""
    segments = max(1, int(segments))
    x0, x1 = sorted((a[0], b[0]))
    y0, y1 = sorted((a[1], b[1]))
    w, h = x1 - x0, y1 - y0
    pts = []
    if w >= h:                       # horizontal slot -> caps on left / right
        r = h / 2.0
        cy = (y0 + y1) / 2.0
        cxr, cxl = x1 - r, x0 + r
        for i in range(segments + 1):           # right cap: +90deg down to -90deg
            ang = math.pi / 2 - math.pi * (i / segments)
            pts.append((cxr + math.cos(ang) * r, cy + math.sin(ang) * r))
        for i in range(segments + 1):           # left cap: -90deg round to +90deg
            ang = -math.pi / 2 - math.pi * (i / segments)
            pts.append((cxl + math.cos(ang) * r, cy + math.sin(ang) * r))
    else:                            # vertical slot -> caps on top / bottom
        r = w / 2.0
        cx = (x0 + x1) / 2.0
        cyt, cyb = y1 - r, y0 + r
        for i in range(segments + 1):           # top cap: 0deg round to 180deg
            ang = math.pi * (i / segments)
            pts.append((cx + math.cos(ang) * r, cyt + math.sin(ang) * r))
        for i in range(segments + 1):           # bottom cap: 180deg round to 360
            ang = math.pi + math.pi * (i / segments)
            pts.append((cx + math.cos(ang) * r, cyb + math.sin(ang) * r))
    return pts


def star_points(center, edge, points, inner_ratio=0.5, rotation=0.0):
    """Regular n-pointed star outline from a center and an edge point. The edge
    point sets the outer radius + the orientation of the first spike (so dragging
    rotates the star); inner vertices sit at `inner_ratio` of that radius.
    `points` is the spike count (clamped to >= 2), so the polygon has 2*points
    vertices. `rotation` adds an angular offset in radians. Pure 2D, like
    ngon_points."""
    points = max(2, int(points))
    dx = edge[0] - center[0]
    dy = edge[1] - center[1]
    r_out = math.hypot(dx, dy)
    if r_out < 1e-9:                  # zero-radius drag -> no shape
        return []
    r_in = r_out * max(0.01, min(0.99, inner_ratio))
    base = math.atan2(dy, dx) + rotation
    n = points * 2
    pts = []
    for i in range(n):
        ang = base + (i / n) * math.tau
        r = r_out if i % 2 == 0 else r_in
        pts.append((center[0] + math.cos(ang) * r, center[1] + math.sin(ang) * r))
    return pts


def arc_points(center, edge, segments=16, sweep=math.pi / 2, rotation=0.0):
    """Filled circular sector (pie wedge) outline: the `center`, then an arc of
    `segments` spans sampled from the edge point's angle through `sweep` radians.
    The edge point sets the radius + start angle (so dragging aims the wedge);
    `rotation` adds an offset. Returns a closed polygon (center + arc) in 2D, like
    ngon_points. A `sweep` of tau is a full disc."""
    segments = max(1, int(segments))
    dx = edge[0] - center[0]
    dy = edge[1] - center[1]
    r = math.hypot(dx, dy)
    if r < 1e-9:                      # zero-radius drag -> no shape
        return []
    base = math.atan2(dy, dx) + rotation
    pts = [(center[0], center[1])]
    for i in range(segments + 1):
        ang = base + sweep * (i / segments)
        pts.append((center[0] + math.cos(ang) * r, center[1] + math.sin(ang) * r))
    return pts


def centroid(points):
    """Average of a list of 2D points (the shape's in-plane center). Returns
    (0, 0) for an empty list. Pure 2D."""
    n = len(points)
    if n == 0:
        return (0.0, 0.0)
    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    return (sx / n, sy / n)


def rotate_2d(points, angle, center=None):
    """Rotate 2D `points` by `angle` radians about `center` (defaults to their
    centroid) -- the in-draw in-plane shape rotation handle (v1.4). Pure 2D, so
    it is unit-tested without Blender; the operator rotates the shape's plane
    (u, v) coordinates with this and lifts them back to world."""
    if center is None:
        center = centroid(points)
    cx, cy = center
    ca, sa = math.cos(angle), math.sin(angle)
    out = []
    for x, y in points:
        dx, dy = x - cx, y - cy
        out.append((cx + dx * ca - dy * sa, cy + dx * sa + dy * ca))
    return out


def radial_sets(points, count, center=(0.0, 0.0), sweep=None):
    """`count` copies of a 2D outline spun evenly about `center` -- the radial /
    bolt-circle array (v1.20). Copy i is the outline rotated by i * step, where
    step is `sweep` / count (default a full turn, so the copies close the
    circle). The original outline is returned first, unrotated. count < 2 is an
    identity. Pure 2D, like rotate_2d, so the operator spins the shape's plane
    (u, v) coordinates about the plane / grid origin (H) and lifts them back."""
    if count < 2:
        return [list(points)]
    total = math.tau if sweep is None else sweep
    step = total / count
    return [rotate_2d(points, step * i, center) if i else list(points)
            for i in range(count)]


def vent_slats(points, count, ratio=0.5):
    """Split the bounding rectangle of a drawn 2D outline into `count` parallel
    slot rectangles -- the vent / grill pattern (v1.20: draw one box, cut N
    louvre slots). Slats span the rect's LONGER axis and stack along the shorter
    one; each takes `ratio` (0..1) of its pitch, and the pitch is chosen so the
    border rib equals the interior ribs (pitch = span / (count + 1 - ratio)),
    the framed look a real vent has. The slat ends keep the same border. Returns
    a list of 4-corner rectangles (each like box_points), or [] when the rect
    degenerates. Pure 2D, unit-tested."""
    if count < 1 or not points:
        return []
    ratio = max(0.05, min(0.95, ratio))
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = x1 - x0, y1 - y0
    if w < 1e-9 or h < 1e-9:
        return []
    # Stack along the shorter axis so the slats span the longer one.
    along_x = w >= h
    stack = h if along_x else w         # pitch axis
    pitch = stack / (count + 1.0 - ratio)
    slot = pitch * ratio
    border = pitch * (1.0 - ratio)      # equals the rib between two slots
    end0 = (x0 if along_x else y0) + border
    end1 = (x1 if along_x else y1) - border
    if end1 - end0 < 1e-9 or slot < 1e-9:
        return []
    out = []
    for i in range(count):
        lo = (y0 if along_x else x0) + border + i * pitch
        hi = lo + slot
        if along_x:
            out.append(box_points((end0, lo), (end1, hi)))
        else:
            out.append(box_points((lo, end0), (hi, end1)))
    return out


def _orient(a, b, c):
    """Sign of the a->b->c turn (>0 CCW, <0 CW, 0 collinear)."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, c):
    """When c is collinear with a-b, is it on the a-b segment?"""
    return (min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and
            min(a[1], b[1]) <= c[1] <= max(a[1], b[1]))


def segments_intersect(a, b, c, d):
    """Do the segments [a,b] and [c,d] intersect? (touching included)."""
    o1, o2 = _orient(a, b, c), _orient(a, b, d)
    o3, o4 = _orient(c, d, a), _orient(c, d, b)
    if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0):
        return True
    if o1 == 0 and _on_segment(a, b, c):
        return True
    if o2 == 0 and _on_segment(a, b, d):
        return True
    if o3 == 0 and _on_segment(c, d, a):
        return True
    if o4 == 0 and _on_segment(c, d, b):
        return True
    return False


def is_self_intersecting(points):
    """Do the edges of a closed polygon intersect each other? Adjacent edges
    (sharing a vertex) are skipped. For warning before producing a broken
    cutter."""
    n = len(points)
    if n < 4:
        return False
    edges = [(points[i], points[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        a, b = edges[i]
        for j in range(i + 1, n):
            if j == (i + 1) % n or (j + 1) % n == i:
                continue  # adjacent edges (shared vertex) don't count
            c, d = edges[j]
            if segments_intersect(a, b, c, d):
                return True
    return False


def point_in_polygon(point, polygon):
    """Is the 2D `point` (x, y) inside the closed `polygon` (list of (x, y))?
    Ray-casting (even-odd) test, pure 2D. Used to limit the knife score to the
    faces actually under the drawn footprint instead of slicing the whole mesh.
    Points exactly on an edge may read either way -- callers use a margin."""
    n = len(polygon)
    if n < 3:
        return False
    x, y = point
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        # does the horizontal ray from (x, y) cross edge (i, j)?
        if (yi > y) != (yj > y):
            x_cross = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def polygons_overlap(a, b):
    """Do two simple 2D polygons share any area? True when any vertex of one
    lies inside the other, or any edge of one crosses an edge of the other.
    Used as the local-knife footprint test: a thin drawn polygon that merely
    *crosses* a big face (so neither a vertex-in test alone catches it) is still
    recognised, so the score follows the drawn outline instead of falling back
    to slicing the whole mesh. Pure 2D; lists of (x, y)."""
    na, nb = len(a), len(b)
    if na < 3 or nb < 3:
        return False
    if any(point_in_polygon(p, b) for p in a):
        return True
    if any(point_in_polygon(p, a) for p in b):
        return True
    for i in range(na):
        a1, a2 = a[i], a[(i + 1) % na]
        for j in range(nb):
            b1, b2 = b[j], b[(j + 1) % nb]
            if segments_intersect(a1, a2, b1, b2):
                return True
    return False
