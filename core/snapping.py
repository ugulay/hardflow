# Unified 3D snapping shared by every draw tool (ADD, Pipe, Cable/Rope).
#
# A single priority chain -- vertex/edge -> surface/face -> grid -> free -- so
# all tools stick/align the same way. This module is the "logic" layer: it may
# use bpy data + mathutils (core/raycast.py already does), but NOT bpy.ops /
# gpu / blf. The actual nearest-point picking is delegated to the pure 2D helpers
# in core/snap.py and the projection helpers in core/raycast.py, so the math stays
# testable.
from mathutils import Vector

from . import raycast, snap, grid


# On dense scenes, projecting every vertex on each mouse move is expensive; above
# this total vertex count geometry snap turns itself off.
GEO_MAX_VERTS = 20000


class Geo:
    """Pre-collected world-space snap geometry for one modal session. Built once
    in invoke() since the candidate objects do not move while drawing.

    verts : list[Vector]               -- world vertex positions
    mids  : list[Vector]               -- world edge midpoints
    edges : list[(Vector, Vector)]     -- world edge endpoint pairs
    enabled : bool                     -- False when the scene is too dense
    """

    __slots__ = ("verts", "mids", "edges", "enabled")

    def __init__(self):
        self.verts = []
        self.mids = []
        self.edges = []
        self.enabled = False


def _mesh_objects(context, target):
    """Candidate objects to snap against. target='ACTIVE' -> the active object
    only; 'VISIBLE' -> every visible mesh in the view layer."""
    if target == 'VISIBLE':
        return [o for o in context.visible_objects if o.type == 'MESH']
    obj = context.active_object
    return [obj] if obj is not None and obj.type == 'MESH' else []


def collect_geo(context, target='ACTIVE', max_verts=GEO_MAX_VERTS):
    """Gather world-space vertices, edge midpoints and edge segments from the
    candidate objects. Returns a Geo; geo.enabled is False (and the lists empty)
    when the total vertex count exceeds max_verts."""
    geo = Geo()
    objects = _mesh_objects(context, target)
    total = sum(len(o.data.vertices) for o in objects)
    if total == 0 or total > max_verts:
        return geo
    geo.enabled = True
    for obj in objects:
        me = obj.data
        mw = obj.matrix_world
        wverts = [mw @ v.co for v in me.vertices]
        geo.verts.extend(wverts)
        for e in me.edges:
            i, j = e.vertices
            a, b = wverts[i], wverts[j]
            geo.edges.append((a, b))
            geo.mids.append((a + b) * 0.5)
    return geo


def _to_screen(region, rv3d, world_pts):
    out = []
    for w in world_pts:
        s = raycast.world_to_screen(region, rv3d, w)
        out.append((s[0], s[1]) if s is not None else None)
    return out


def _segment_t(point, a, b):
    """Parameter t in [0, 1] of `point`'s projection onto segment [a, b] (2D)."""
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    ll = dx * dx + dy * dy
    if ll <= 1e-12:
        return 0.0
    t = ((point[0] - ax) * dx + (point[1] - ay) * dy) / ll
    return max(0.0, min(1.0, t))


def geo_snap_3d(region, rv3d, coord, geo, threshold_px):
    """Nearest vertex / edge-midpoint / on-edge point to the cursor, returned as
    (point3d, kind) with kind in {'VERT', 'MID', 'EDGE'}, or None if nothing is
    within threshold_px. Priority: exact vertex, then midpoint, then on-edge."""
    if geo is None or not geo.enabled:
        return None

    vscr = _to_screen(region, rv3d, geo.verts)
    hit = snap.nearest_point(coord, vscr, threshold_px)
    if hit is not None:
        return (geo.verts[hit[0]], 'VERT')

    mscr = _to_screen(region, rv3d, geo.mids)
    hit = snap.nearest_point(coord, mscr, threshold_px)
    if hit is not None:
        return (geo.mids[hit[0]], 'MID')

    segs = []
    ends = []
    for (a3, b3) in geo.edges:
        a2 = raycast.world_to_screen(region, rv3d, a3)
        b2 = raycast.world_to_screen(region, rv3d, b3)
        segs.append((None if a2 is None else (a2[0], a2[1]),
                     None if b2 is None else (b2[0], b2[1])))
        ends.append((a3, b3))
    hit = snap.nearest_on_segments(coord, segs, threshold_px)
    if hit is not None:
        idx = hit[0]
        a2, b2 = segs[idx]
        a3, b3 = ends[idx]
        t = _segment_t(hit[1], a2, b2)
        return (a3.lerp(b3, t), 'EDGE')
    return None


def grid_snap_3d(point, size, enabled):
    """Round a free 3D world point onto the world grid. Thin Vector wrapper over
    the pure grid.snap_world_3d so the rounding stays unit-tested."""
    x, y, z = grid.snap_world_3d(point[0], point[1], point[2], size, enabled)
    return Vector((x, y, z))
