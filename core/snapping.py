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


def _obj_world_geo(obj):
    """(world verts, world edge index pairs) for one object. When the object is
    in Edit Mode its LIVE edit-mesh (bmesh.from_edit_mesh, unapplied) is read so
    vertex/edge snap tracks geometry mid-edit; otherwise the object data is used."""
    mw = obj.matrix_world
    if obj.mode == 'EDIT':
        import bmesh
        bm = bmesh.from_edit_mesh(obj.data)
        wverts = [mw @ v.co for v in bm.verts]
        edges = [(e.verts[0].index, e.verts[1].index) for e in bm.edges]
        return wverts, edges
    me = obj.data
    wverts = [mw @ v.co for v in me.vertices]
    edges = [tuple(e.vertices) for e in me.edges]
    return wverts, edges


def collect_geo(context, target='ACTIVE', max_verts=GEO_MAX_VERTS):
    """Gather world-space vertices, edge midpoints and edge segments from the
    candidate objects. Returns a Geo; geo.enabled is False (and the lists empty)
    when the total vertex count exceeds max_verts. Edit-Mode objects expose their
    live (unapplied) edit-mesh so snap works mid-edit (v1.3)."""
    geo = Geo()
    objects = _mesh_objects(context, target)

    def _count(o):
        if o.mode == 'EDIT':
            import bmesh
            return len(bmesh.from_edit_mesh(o.data).verts)
        return len(o.data.vertices)

    total = sum(_count(o) for o in objects)
    if total == 0 or total > max_verts:
        return geo
    geo.enabled = True
    for obj in objects:
        wverts, edges = _obj_world_geo(obj)
        geo.verts.extend(wverts)
        for i, j in edges:
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
    within threshold_px. Picks the geometrically nearest target (snap.resolve_snap
    disambiguates), with vertex precedence only breaking near-ties -- so a close
    edge isn't hijacked by a far vertex."""
    if geo is None or not geo.enabled:
        return None

    vscr = _to_screen(region, rv3d, geo.verts)
    mscr = _to_screen(region, rv3d, geo.mids)
    segs = []
    for (a3, b3) in geo.edges:
        a2 = raycast.world_to_screen(region, rv3d, a3)
        b2 = raycast.world_to_screen(region, rv3d, b3)
        segs.append((None if a2 is None else (a2[0], a2[1]),
                     None if b2 is None else (b2[0], b2[1])))

    best = snap.resolve_snap([
        ('VERT', snap.nearest_point(coord, vscr, threshold_px)),
        ('MID', snap.nearest_point(coord, mscr, threshold_px)),
        ('EDGE', snap.nearest_on_segments(coord, segs, threshold_px)),
    ])
    if best is None:
        return None
    kind, hit = best
    if kind == 'VERT':
        return (geo.verts[hit[0]], 'VERT')
    if kind == 'MID':
        return (geo.mids[hit[0]], 'MID')
    idx = hit[0]
    a2, b2 = segs[idx]
    a3, b3 = geo.edges[idx]
    t = _segment_t(hit[1], a2, b2)
    return (a3.lerp(b3, t), 'EDGE')


def snap_insert_point(point, spacing, anchors=(), threshold=0.0):
    """Snap an INSERT placement point to existing insert anchors or a regular
    world grid (KitOps insert grid / factory snapping, v1.8). Priority: the
    nearest anchor within `threshold`, else the world grid of `spacing`, else the
    raw point. `anchors` are world Vectors. Returns a Vector."""
    p = Vector(point)
    best = None
    for a in anchors:
        d = (Vector(a) - p).length
        if d <= threshold and (best is None or d < best[0]):
            best = (d, Vector(a))
    if best is not None:
        return best[1]
    if spacing > 0.0:
        return grid_snap_3d(p, spacing, True)
    return p


def grid_snap_3d(point, size, enabled):
    """Round a free 3D world point onto the world grid. Thin Vector wrapper over
    the pure grid.snap_world_3d so the rounding stays unit-tested."""
    x, y, z = grid.snap_world_3d(point[0], point[1], point[2], size, enabled)
    return Vector((x, y, z))


# --- surface drape (pipe routing) ---------------------------------------

def nearest_surface_point(context, world_co, target='VISIBLE'):
    """Closest point on the candidate meshes to `world_co`, as (location,
    normal) in world space (the surface evaluated with modifiers), or None when
    there is no mesh. Uses Object.closest_point_on_mesh, so -- unlike a raycast
    -- it needs no ray direction and always finds the nearest surface, which is
    what lets a draped pipe wrap around an edge it crosses in mid-air."""
    depsgraph = context.evaluated_depsgraph_get()
    best = None
    for obj in _mesh_objects(context, target):
        eval_obj = obj.evaluated_get(depsgraph)
        mw = eval_obj.matrix_world
        local = mw.inverted_safe() @ Vector(world_co)
        ok, loc, nrm, _idx = eval_obj.closest_point_on_mesh(local)
        if not ok:
            continue
        wloc = mw @ loc
        d = (wloc - Vector(world_co)).length_squared
        if best is None or d < best[0]:
            wnrm = (mw.to_3x3() @ nrm).normalized()
            best = (d, wloc, wnrm)
    if best is None:
        return None
    return best[1], best[2]


def drape_path(context, points, segments=8, lift=0.0, target='VISIBLE'):
    """Drape a poly-line over the model surface: every span between consecutive
    `points` is sub-divided into `segments` steps and each sample (anchors
    included) is snapped onto the nearest surface, then lifted `lift` metres
    along that surface's normal so the tube rests on top instead of sinking in.
    Samples that find no surface keep their straight-line position (lifted along
    world +Z as a harmless fallback). Returns a list of Vectors >= len(points).
    bpy data + mathutils only -- no bpy.ops -- so it sits in the logic layer."""
    pts = [Vector(p) for p in points]
    if len(pts) < 2:
        return pts
    segments = max(1, int(segments))

    def place(world_co):
        near = nearest_surface_point(context, world_co, target)
        if near is None:
            return Vector(world_co) + Vector((0.0, 0.0, lift))
        loc, nrm = near
        return loc + nrm * lift

    out = [place(pts[0])]
    for a, b in zip(pts[:-1], pts[1:]):
        for i in range(1, segments + 1):
            t = i / segments
            out.append(place(a.lerp(b, t)))
    return out
