# Grid snapping.
#   snap_point / grid_lines : v0.1 screen-space (legacy, no longer used by the
#       operator)
#   snap_world / world_grid_segments : v0.2 world-scale, meter-based snap on the
#       projection plane's local (u, v) axes (Grid Modeler "absolute size").
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
    pts = []
    for i in range(segments):
        a = (i / segments) * math.tau
        pts.append((center[0] + math.cos(a) * r,
                    center[1] + math.sin(a) * r))
    return pts


def box_points(a, b):
    """The 4 corners of a rectangle from two diagonal points."""
    return [(a[0], a[1]), (b[0], a[1]), (b[0], b[1]), (a[0], b[1])]


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
