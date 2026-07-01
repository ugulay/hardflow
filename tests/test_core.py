# Blender-free unit tests for the pure core logic.
#
# core/grid.py and core/snap.py deliberately contain no bpy/mathutils; so they
# can run on plain CPython. (raycast/geometry/boolean depend on bpy and are not
# tested here -- they run headless inside Blender.)
#
# Run:
#   python tests/test_core.py          # standalone, no pytest needed
#   pytest tests/                       # pytest finds it automatically if present
import importlib.util
import math
import os
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    """Load core/<name>.py from file without importing the package (or bpy)."""
    path = os.path.join(_ROOT, "core", name + ".py")
    spec = importlib.util.spec_from_file_location("hf_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


grid = _load("grid")
offset = _load("offset")
snap = _load("snap")
decal_math = _load("decal_math")
decal_image = _load("decal_image")
atlas = _load("atlas")
transform = _load("transform")
asset_lib = _load("asset_lib")
command = _load("command")


# --- grid: world-scale snap --------------------------------------------------

def test_snap_world_rounds_to_grid():
    assert grid.snap_world(0.123, -0.077, 0.1, True) == (0.1, -0.1)
    assert grid.snap_world(0.04, 0.06, 0.1, True) == (0.0, 0.1)


def test_snap_world_disabled_or_zero_is_noop():
    assert grid.snap_world(0.123, -0.077, 0.1, False) == (0.123, -0.077)
    assert grid.snap_world(5.0, 5.0, 0.0, True) == (5.0, 5.0)


def test_snap_world_3d_rounds_each_axis():
    # every axis is rounded independently to the nearest grid line
    assert grid.snap_world_3d(0.123, -0.077, 0.249, 0.1, True) == (0.1, -0.1, 0.2)
    assert grid.snap_world_3d(0.04, 0.06, -0.04, 0.1, True) == (0.0, 0.1, 0.0)


def test_snap_world_3d_disabled_or_zero_is_noop():
    assert grid.snap_world_3d(0.123, -0.077, 0.5, 0.1, False) == (0.123, -0.077, 0.5)
    assert grid.snap_world_3d(5.0, 5.0, 5.0, 0.0, True) == (5.0, 5.0, 5.0)


def test_world_grid_segments_basic_and_expand():
    segs = grid.world_grid_segments(0.0, 1.0, 0.0, 1.0, 0.5)
    assert len(segs) == 6
    assert ((0.0, 0.0), (0.0, 1.0)) in segs
    assert ((0.0, 0.0), (1.0, 0.0)) in segs
    # expands outward to grid-aligned bounds
    segs = grid.world_grid_segments(0.05, 0.95, 0.05, 0.95, 0.5)
    us = sorted({s[0][0] for s in segs if s[0][0] == s[1][0]})
    assert us == [0.0, 0.5, 1.0]


def test_world_grid_segments_guards():
    assert grid.world_grid_segments(0, 1000, 0, 1000, 0.001) == []  # blow-up guard
    assert grid.world_grid_segments(1, 0, 0, 1, 0.1) == []          # degenerate bound


# --- grid: scalar snap + construction grid (Build tools) --------------------

def test_snap_scalar():
    assert grid.snap_scalar(0.123, 0.1, True) == 0.1
    assert grid.snap_scalar(0.16, 0.1, True) == 0.2
    assert grid.snap_scalar(-0.04, 0.1, True) == 0.0  # rounds toward nearest
    # disabled or non-positive size is a no-op
    assert grid.snap_scalar(0.123, 0.1, False) == 0.123
    assert grid.snap_scalar(0.123, 0.0, True) == 0.123


def test_snap_to_candidates():
    cands = [0.0, 1.0, 2.5]
    assert snap.snap_to_candidates(0.95, cands, 0.2) == 1.0   # within tol -> snap
    assert snap.snap_to_candidates(0.5, cands, 0.2) == 0.5    # outside tol -> free
    assert snap.snap_to_candidates(2.46, cands, 0.1) == 2.5
    assert snap.snap_to_candidates(5.0, [], 0.2) == 5.0       # no candidates
    assert snap.snap_to_candidates(-1.9, [-2.0, 0.0], 0.2) == -2.0  # negative side
    # exact tie -> the FIRST candidate within tol wins (deterministic: strict <)
    assert snap.snap_to_candidates(1.0, [0.5, 1.5], 0.6) == 0.5
    assert snap.snap_to_candidates(1.0, [1.5, 0.5], 0.6) == 1.5


def test_centered_grid_segments():
    segs = grid.centered_grid_segments(1.0, 0.5)
    # lines at -1, -0.5, 0, 0.5, 1 on each axis -> 5 verticals + 5 horizontals
    assert len(segs) == 10
    assert ((0.0, -1.0), (0.0, 1.0)) in segs       # center vertical
    assert ((-1.0, 0.0), (1.0, 0.0)) in segs       # center horizontal
    # symmetric extent: every line spans the full [-1, 1]
    for (x1, y1), (x2, y2) in segs:
        span = {abs(x1), abs(x2), abs(y1), abs(y2)}
        assert max(span) == 1.0
    # degenerate / blow-up guards
    assert grid.centered_grid_segments(0.0, 0.5) == []
    assert grid.centered_grid_segments(1.0, 0.0) == []
    assert grid.centered_grid_segments(100.0, 0.001) == []  # too dense


# --- grid: in-plane rotation handle (v1.4) -----------------------------------

def test_centroid():
    assert grid.centroid([(0, 0), (2, 0), (2, 2), (0, 2)]) == (1.0, 1.0)
    assert grid.centroid([]) == (0.0, 0.0)


def test_rotate_2d_quarter_turn_about_centroid():
    sq = [(0, 0), (2, 0), (2, 2), (0, 2)]
    out = grid.rotate_2d(sq, math.pi / 2)        # 90 deg about (1, 1)
    # a 90 deg rotation of a centred square maps it back onto itself (as a set)
    got = set((round(x, 6), round(y, 6)) for x, y in out)
    assert got == set((round(x, 6), round(y, 6)) for x, y in sq)
    # explicit center: rotating (1,0) by 180 about origin -> (-1, 0)
    r = grid.rotate_2d([(1, 0)], math.pi, center=(0, 0))[0]
    assert math.isclose(r[0], -1.0, abs_tol=1e-9)
    assert math.isclose(r[1], 0.0, abs_tol=1e-9)


# --- transform: dice planes + fit scale (v1.5 / v1.8) ------------------------

def test_dice_coordinates():
    # 3 pieces over [0, 9] -> interior cuts at 3 and 6
    assert transform.dice_coordinates(0.0, 9.0, 3) == [3.0, 6.0]
    assert transform.dice_coordinates(0.0, 1.0, 1) == []     # one piece, no cut
    assert transform.dice_coordinates(0.0, 1.0, 0) == []     # clamps to 1
    assert transform.dice_coordinates(5.0, 5.0, 4) == []     # zero span


def test_fit_scale():
    # insert size 2, target feature 4, fraction 0.5 -> scale 1.0
    assert transform.fit_scale(2.0, 4.0, 0.5) == 1.0
    # default 0.25 fraction: 1m insert into a 4m feature -> 1.0
    assert transform.fit_scale(1.0, 4.0) == 1.0
    # degenerate inputs fall back to the default
    assert transform.fit_scale(0.0, 4.0) == 1.0
    assert transform.fit_scale(2.0, 0.0, default=3.0) == 3.0


def test_adaptive_dimension():
    # 2% of the largest dimension, within the clamp band
    assert abs(transform.adaptive_dimension(1.0, 0.02) - 0.02) < 1e-9
    assert abs(transform.adaptive_dimension(10.0, 0.02) - 0.2) < 1e-9
    # clamps: huge object capped at max, tiny object floored at min
    assert transform.adaptive_dimension(1000.0, 0.02, max_value=0.5) == 0.5
    assert transform.adaptive_dimension(0.01, 0.02, min_value=0.001) == 0.001
    # unknown size -> min_value
    assert transform.adaptive_dimension(0.0, min_value=0.002) == 0.002


# --- offset: 2D polygon inset (Offset) --------------------------------------

def test_signed_area_winding():
    ccw = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert offset.signed_area(ccw) > 0
    assert offset.signed_area(list(reversed(ccw))) < 0
    assert offset.signed_area([(0, 0), (1, 1)]) == 0.0  # too few points


def test_offset_polygon_inward_square():
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]          # CCW
    out = offset.offset_polygon(sq, 2.0)               # inward by 2
    expect = [(2, 2), (8, 2), (8, 8), (2, 8)]
    for (ox, oy), (ex, ey) in zip(out, expect):
        assert math.isclose(ox, ex, abs_tol=1e-9)
        assert math.isclose(oy, ey, abs_tol=1e-9)
    # winding independence: a CW square insets to the same shrunk box
    cw = list(reversed(sq))
    out_cw = offset.offset_polygon(cw, 2.0)
    assert set((round(x, 6), round(y, 6)) for x, y in out_cw) == \
        set((round(x, 6), round(y, 6)) for x, y in expect)


def test_offset_polygon_outward_and_guards():
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
    out = offset.offset_polygon(sq, -1.0)              # negative = outward
    assert (-1.0, -1.0) in [(round(x, 6), round(y, 6)) for x, y in out]
    assert offset.offset_polygon(sq, 0.0) == sq        # zero distance no-op
    assert offset.offset_polygon([(0, 0), (1, 0)], 1.0) is None  # < 3 points
    # a zero-length edge is degenerate
    assert offset.offset_polygon([(0, 0), (0, 0), (1, 1)], 0.5) is None


def test_inset_inference_candidates():
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
    # a point 3 in from the left edge -> the inset border reaches it at t = 3
    cands = offset.inset_inference_candidates(sq, [(3, 5)])
    assert any(math.isclose(c, 3.0, abs_tol=1e-9) for c in cands)
    # the centre is 5 from every edge -> the border collapses there at t = 5
    cands2 = offset.inset_inference_candidates(sq, [(5, 5)])
    assert any(math.isclose(c, 5.0, abs_tol=1e-9) for c in cands2)
    # a coplanar edge (two verts at x=2) aligns the whole border at t = 2
    edge = offset.inset_inference_candidates(sq, [(2, 3), (2, 7)])
    assert sum(1 for c in edge if math.isclose(c, 2.0, abs_tol=1e-9)) == 2
    assert edge == sorted(edge)
    # points on / outside the boundary are dropped; a degenerate poly -> []
    assert offset.inset_inference_candidates(sq, [(0, 0)]) == []
    assert offset.inset_inference_candidates([(0, 0), (1, 1)], [(0.5, 0.5)]) == []


# --- grid: shape points ------------------------------------------------------

def test_lock_distance():
    # locks the point to an exact distance along the a->b direction
    assert grid.lock_distance((0, 0), (10, 0), 2.5) == (2.5, 0.0)
    x, y = grid.lock_distance((0, 0), (3, 4), 10.0)   # dir (0.6,0.8) * 10
    assert abs(x - 6.0) < 1e-9 and abs(y - 8.0) < 1e-9
    # shrinks as well as extends
    assert grid.lock_distance((1, 1), (5, 1), 2.0) == (3.0, 1.0)
    # degenerate direction (b == a) returns a unchanged
    assert grid.lock_distance((2, 2), (2, 2), 5.0) == (2.0, 2.0)


def test_ngon_points():
    # a square (4 sides) around the origin with the first vertex on +x
    pts = grid.ngon_points((0.0, 0.0), (1.0, 0.0), 4)
    assert len(pts) == 4
    # every corner sits on the circumradius defined by the edge point
    for x, y in pts:
        assert math.isclose(math.hypot(x, y), 1.0, abs_tol=1e-9)
    # first vertex points toward the edge point
    assert math.isclose(pts[0][0], 1.0, abs_tol=1e-9)
    assert math.isclose(pts[0][1], 0.0, abs_tol=1e-9)
    # sides < 3 is clamped to a triangle; sides count is respected otherwise
    assert len(grid.ngon_points((0, 0), (2, 0), 1)) == 3
    assert len(grid.ngon_points((0, 0), (2, 0), 6)) == 6
    # a zero-radius drag (edge == center) yields no shape, not a coincident cluster
    assert grid.ngon_points((1.0, 1.0), (1.0, 1.0), 6) == []


def test_slot_points():
    # a wide stadium: caps on the short (vertical) ends, straight long sides.
    pts = grid.slot_points((0.0, 0.0), (4.0, 2.0), segments=8)
    assert len(pts) == 2 * (8 + 1)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    # the outline stays inside the bounding box defined by the two corners
    assert math.isclose(min(xs), 0.0, abs_tol=1e-9)
    assert math.isclose(max(xs), 4.0, abs_tol=1e-9)
    assert min(ys) >= -1e-9 and max(ys) <= 2.0 + 1e-9
    # a tall slot rotates the caps onto the top / bottom
    tall = grid.slot_points((0.0, 0.0), (2.0, 6.0), segments=4)
    assert len(tall) == 2 * (4 + 1)


def test_star_points():
    # a 5-point star -> 10 vertices alternating outer / inner radius.
    pts = grid.star_points((0.0, 0.0), (1.0, 0.0), 5, inner_ratio=0.5)
    assert len(pts) == 10
    radii = [math.hypot(x, y) for x, y in pts]
    assert math.isclose(radii[0], 1.0, abs_tol=1e-9)          # outer spike
    assert math.isclose(radii[1], 0.5, abs_tol=1e-9)          # inner valley
    # first spike aims at the edge point
    assert math.isclose(pts[0][0], 1.0, abs_tol=1e-9)
    assert math.isclose(pts[0][1], 0.0, abs_tol=1e-9)
    # spikes < 2 clamp to 2 (4 verts); ratio is clamped into (0, 1)
    assert len(grid.star_points((0, 0), (1, 0), 1)) == 4
    # zero-radius drag -> no shape
    assert grid.star_points((0, 0), (0, 0), 5) == []


def test_arc_points():
    # a quarter sector: center + (segments + 1) arc samples, all on the radius.
    pts = grid.arc_points((0.0, 0.0), (1.0, 0.0), segments=8, sweep=math.pi / 2)
    assert len(pts) == 1 + (8 + 1)
    assert pts[0] == (0.0, 0.0)                               # the wedge apex
    for x, y in pts[1:]:
        assert math.isclose(math.hypot(x, y), 1.0, abs_tol=1e-9)
    # arc spans from the edge angle (0) through the sweep (90 deg)
    assert math.isclose(pts[1][0], 1.0, abs_tol=1e-9)        # start on +x
    assert math.isclose(pts[-1][1], 1.0, abs_tol=1e-9)       # end on +y
    # zero-radius drag -> no shape
    assert grid.arc_points((2, 2), (2, 2), segments=8) == []


# --- grid: angle lock --------------------------------------------------------

def test_snap_angle_locks_to_step():
    # a 40-degree direction rounds to 45 on a 15-step; distance is preserved
    a = (0.0, 0.0)
    p = (math.cos(math.radians(40)), math.sin(math.radians(40)))
    sx, sy = grid.snap_angle(a, p, 15, True)
    assert math.isclose(math.degrees(math.atan2(sy, sx)), 45.0, abs_tol=1e-6)
    assert math.isclose(math.hypot(sx, sy), 1.0, abs_tol=1e-9)


def test_snap_angle_disabled_and_degenerate():
    assert grid.snap_angle((0, 0), (3, 4), 15, False) == (3, 4)
    assert grid.snap_angle((2, 2), (2, 2), 15, True) == (2, 2)  # zero distance


# --- grid: self-intersection (broken poly detection) -------------------------

def test_segments_intersect():
    assert grid.segments_intersect((0, 0), (10, 10), (0, 10), (10, 0))   # X
    assert not grid.segments_intersect((0, 0), (10, 0), (0, 5), (10, 5))  # parallel
    assert grid.segments_intersect((0, 0), (10, 0), (5, 0), (5, 5))       # T-touch


def test_is_self_intersecting():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert not grid.is_self_intersecting(square)
    bowtie = [(0, 0), (10, 0), (0, 10), (10, 10)]   # bowtie (self-intersects)
    assert grid.is_self_intersecting(bowtie)
    assert not grid.is_self_intersecting([(0, 0), (1, 0), (0, 1)])  # triangle
    # concave but clean (arrow/L shape) does not intersect
    arrow = [(0, 0), (4, 0), (4, 4), (2, 2), (0, 4)]
    assert not grid.is_self_intersecting(arrow)


def test_point_in_polygon():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert grid.point_in_polygon((5, 5), square)
    assert not grid.point_in_polygon((15, 5), square)      # right of the square
    assert not grid.point_in_polygon((-1, 5), square)      # left of the square
    assert not grid.point_in_polygon((5, 20), square)      # above
    # concave L: a point in the notch is outside
    el = [(0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10)]
    assert grid.point_in_polygon((2, 8), el)               # in the tall arm
    assert not grid.point_in_polygon((8, 8), el)           # in the cut-out notch
    assert not grid.point_in_polygon((0, 0), [(0, 0), (1, 1)])  # degenerate


def test_polygons_overlap():
    sq = [(0, 0), (4, 0), (4, 4), (0, 4)]
    # shared area (a corner of one inside the other)
    assert grid.polygons_overlap(sq, [(2, 2), (6, 2), (6, 6), (2, 6)])
    # a thin strip crossing the square with NO vertex of either inside the
    # other -> caught only by the edge-crossing test (the old center/corner
    # footprint test missed this and fell back to slicing every face)
    strip = [(0.5, -1.0), (1.0, -1.0), (1.0, 5.0), (0.5, 5.0)]
    assert grid.polygons_overlap(sq, strip)
    assert grid.polygons_overlap(strip, sq)        # symmetric
    # disjoint polygons do not overlap
    assert not grid.polygons_overlap(sq, [(10, 10), (12, 10), (11, 12)])
    # degenerate inputs (fewer than 3 points) never overlap
    assert not grid.polygons_overlap(sq, [(1, 1), (2, 2)])


# --- snap: vertex / edge -----------------------------------------------------

def test_nearest_point():
    pts = [(0, 0), (10, 0), (3, 4)]
    assert snap.nearest_point((4, 4), pts, 5)[0] == 2
    assert snap.nearest_point((100, 100), pts, 5) is None
    assert snap.nearest_point((0, 0), [None, (1, 0), None], 5)[0] == 1  # None skipped


def test_closest_point_on_segment():
    s = snap.closest_point_on_segment
    assert s((5, 5), (0, 0), (10, 0)) == (5.0, 0.0)    # foot of perpendicular
    assert s((-5, 0), (0, 0), (10, 0)) == (0.0, 0.0)   # clamp to a
    assert s((15, 0), (0, 0), (10, 0)) == (10.0, 0.0)  # clamp to b
    assert s((1, 1), (2, 2), (2, 2)) == (2.0, 2.0)     # degenerate edge


def test_nearest_on_segments():
    segs = [((0, 0), (10, 0)), ((0, 20), (10, 20))]
    hit = snap.nearest_on_segments((5, 3), segs, 5)
    assert hit[0] == 0 and hit[1] == (5.0, 0.0)
    assert snap.nearest_on_segments((5, 10), segs, 5) is None
    # an edge with a None endpoint is skipped
    segs2 = [(None, (1, 1)), ((0, 0), (10, 0))]
    assert snap.nearest_on_segments((5, 3), segs2, 5)[0] == 1


def test_resolve_snap_disambiguates():
    # hit tuples: (index, point, dist)
    vert = (0, (0, 0), 3.0)
    mid = (1, (1, 0), 3.0)
    edge = (2, (2, 0), 1.0)
    # nothing -> None
    assert snap.resolve_snap([('VERT', None), ('EDGE', None)]) is None
    # only an edge available -> that edge
    assert snap.resolve_snap([('VERT', None), ('EDGE', edge)]) == ('EDGE', edge)
    # a clearly-closer edge (dist 1) beats a far vertex (dist 3) when the gap
    # exceeds tie_px -- the old strict-priority order got this wrong
    assert snap.resolve_snap([('VERT', vert), ('EDGE', edge)],
                             tie_px=1.0) == ('EDGE', edge)
    # within tie_px, the more precise kind wins (vertex over equal-distance mid)
    assert snap.resolve_snap([('MID', mid), ('VERT', vert)]) == ('VERT', vert)
    # a near-tie (vertex 3.0 vs edge 1.0) inside a generous tie_px -> vertex wins
    assert snap.resolve_snap([('VERT', vert), ('EDGE', edge)],
                             tie_px=5.0) == ('VERT', vert)


# --- decal_math: orientation basis -------------------------------------------

def _is_unit(v):
    return math.isclose(math.sqrt(sum(c * c for c in v)), 1.0, abs_tol=1e-9)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_best_edge_pair():
    # longest edge is the 'main'; the most-perpendicular edge is the partner,
    # a nearly-parallel edge is rejected in its favour
    assert decal_math.best_edge_pair([(10, 0, 0), (2, 0.1, 0), (0, 3, 0)]) == (0, 2)
    # order independence: same edges shuffled -> same chosen vectors
    assert decal_math.best_edge_pair([(0, 3, 0), (10, 0, 0), (2, 0.1, 0)]) == (1, 0)
    # all parallel -> no valid partner, the longest is the lone main edge
    assert decal_math.best_edge_pair([(1, 0, 0), (2, 0, 0)]) == (1, None)
    # single edge / empty are well-defined
    assert decal_math.best_edge_pair([(5, 0, 0)]) == (0, None)
    assert decal_math.best_edge_pair([]) == (0, None)
    # forced_main (Ctrl+Click 'set main edge') overrides the longest-edge pick;
    # the partner is still the most-perpendicular of the rest
    vecs = [(10, 0, 0), (2, 0.1, 0), (0, 3, 0)]
    assert decal_math.best_edge_pair(vecs, forced_main=2) == (2, 0)
    assert decal_math.best_edge_pair(vecs, forced_main=1) == (1, 2)
    # an out-of-range forced index falls back to the automatic longest edge
    assert decal_math.best_edge_pair(vecs, forced_main=9) == (0, 2)


def test_orientation_basis_identity():
    x, y, z = decal_math.orientation_basis((0, 0, 1), (1, 0, 0))
    assert math.isclose(z[2], 1.0, abs_tol=1e-9)      # z follows the normal
    assert math.isclose(y[0], 1.0, abs_tol=1e-9)      # tangent preserved as +y
    assert _is_unit(x) and _is_unit(y) and _is_unit(z)


def test_orientation_basis_orthonormal_and_right_handed():
    # an arbitrary tilted normal with a tangent not on the surface
    x, y, z = decal_math.orientation_basis((0.3, 0.4, 0.866), (1, 0, 0))
    for v in (x, y, z):
        assert _is_unit(v)
    assert math.isclose(_dot(x, y), 0.0, abs_tol=1e-9)
    assert math.isclose(_dot(y, z), 0.0, abs_tol=1e-9)
    assert math.isclose(_dot(x, z), 0.0, abs_tol=1e-9)
    # right-handed: x cross y == z
    cx = decal_math._cross(x, y)
    assert all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(cx, z))


def test_orientation_basis_degenerate_tangent():
    # tangent parallel to the normal -> falls back to a valid surface tangent
    x, y, z = decal_math.orientation_basis((0, 0, 1), (0, 0, 1))
    assert _is_unit(x) and _is_unit(y) and _is_unit(z)
    assert math.isclose(_dot(x, z), 0.0, abs_tol=1e-9)


def test_orientation_basis_near_parallel_is_stable():
    # a tangent *almost* parallel to the normal must resolve to the SAME stable
    # frame as an exactly-parallel one -- no "pop" on curved surfaces. Previously
    # the near-parallel case slipped past the zero-length guard and produced a
    # near-random tangent.
    n = (0.0, 0.0, 1.0)
    exact = decal_math.orientation_basis(n, (0.0, 0.0, 1.0))
    near = decal_math.orientation_basis(n, (0.02, 0.0, 1.0))   # ~1.1 deg off
    for a, b in zip(near[1], exact[1]):          # y axes should match
        assert math.isclose(a, b, abs_tol=1e-6), (near, exact)


def test_dominant_tangent_picks_longest_edge():
    # a 4x1 rectangle on the XY plane: the long edges run along X -> tangent ~ +X
    rect_edges = [(4, 0, 0), (0, 1, 0), (-4, 0, 0), (0, -1, 0)]
    t = decal_math.dominant_tangent(rect_edges, (0, 0, 1))
    assert t is not None
    assert math.isclose(abs(t[0]), 1.0, abs_tol=1e-9)        # aligned to X
    assert math.isclose(t[2], 0.0, abs_tol=1e-9)             # in the surface plane
    # the out-of-plane part of an edge is dropped before measuring length
    tilted = [(0, 0.5, 5), (3, 0, 0)]   # first is mostly along normal -> short in-plane
    t2 = decal_math.dominant_tangent(tilted, (0, 0, 1))
    assert math.isclose(abs(t2[0]), 1.0, abs_tol=1e-9)       # the 3-along-X edge wins
    # no usable edge -> None
    assert decal_math.dominant_tangent([(0, 0, 2)], (0, 0, 1)) is None


def test_basis_from_edge():
    # an edge along X on a Z-up surface -> right = X, up = Y, z = Z
    r, u, z = decal_math.basis_from_edge((3, 0, 0), (0, 0, 1))
    assert _is_unit(r) and _is_unit(u) and _is_unit(z)
    assert math.isclose(abs(r[0]), 1.0, abs_tol=1e-9)
    assert math.isclose(z[2], 1.0, abs_tol=1e-9)
    assert math.isclose(_dot(r, z), 0.0, abs_tol=1e-9)
    # edge parallel to the normal -> still a valid (non-zero) frame
    r2, u2, z2 = decal_math.basis_from_edge((0, 0, 5), (0, 0, 1))
    assert _is_unit(r2) and _is_unit(u2) and _is_unit(z2)


def test_basis_from_two_edges():
    # X edge + Y edge -> the XY plane, normal +Z
    r, u, z = decal_math.basis_from_two_edges((2, 0, 0), (0, 3, 0))
    assert _is_unit(r) and _is_unit(u) and _is_unit(z)
    assert math.isclose(abs(z[2]), 1.0, abs_tol=1e-9)
    assert math.isclose(_dot(r, u), 0.0, abs_tol=1e-9)
    assert math.isclose(_dot(r, z), 0.0, abs_tol=1e-9)
    # parallel edges -> no unique plane -> falls back to a valid single-edge frame
    r2, u2, z2 = decal_math.basis_from_two_edges((1, 0, 0), (2, 0, 0))
    assert _is_unit(r2) and _is_unit(u2) and _is_unit(z2)


def test_base_tangent_on_floor_falls_back():
    # a horizontal surface (normal == world up) cannot use world up as tangent
    t = decal_math.base_tangent((0, 0, 1))
    assert _is_unit(t)
    assert math.isclose(_dot(t, (0, 0, 1)), 0.0, abs_tol=1e-9)


def test_rotate_about_axis_quarter_turn():
    r = decal_math.rotate_about_axis((1, 0, 0), (0, 0, 1), math.pi / 2)
    assert math.isclose(r[0], 0.0, abs_tol=1e-9)
    assert math.isclose(r[1], 1.0, abs_tol=1e-9)
    assert math.isclose(r[2], 0.0, abs_tol=1e-9)


# --- decal_image: library scan + aspect fit (v0.9) ---------------------------

def test_is_image_file():
    assert decal_image.is_image_file("logo.png")
    assert decal_image.is_image_file("WARN.JPG")           # case-insensitive
    assert decal_image.is_image_file("/a/b/c.tga")         # full path ok
    assert not decal_image.is_image_file("notes.txt")
    assert not decal_image.is_image_file("noext")


def test_scan_library():
    assert decal_image.scan_library("") == []
    assert decal_image.scan_library("/no/such/folder/here") == []
    with tempfile.TemporaryDirectory() as d:
        for fn in ("b.png", "a.jpg", "readme.txt", "c.TGA"):
            with open(os.path.join(d, fn), "w") as f:
                f.write("x")
        os.mkdir(os.path.join(d, "sub.png"))   # a dir named like an image: skip
        items = decal_image.scan_library(d)
        names = [n for n, _p in items]
        assert names == ["a", "b", "c"]         # sorted, stems, txt+dir excluded
        assert all(os.path.isfile(p) for _n, p in items)


def test_aspect_size():
    # wide image: width is the longest side, height shrinks
    assert decal_image.aspect_size(200, 100, 1.0) == (1.0, 0.5)
    # tall image: height is the longest side
    assert decal_image.aspect_size(100, 200, 1.0) == (0.5, 1.0)
    # square stays square
    assert decal_image.aspect_size(256, 256, 0.4) == (0.4, 0.4)
    # degenerate dimensions fall back to a square (never zero-area)
    assert decal_image.aspect_size(0, 100, 2.0) == (2.0, 2.0)
    assert decal_image.aspect_size(100, 100, 0.0) == (0.0, 0.0)


def test_safe_filename():
    # ordinary names pass through, internal spaces are kept (collapsed)
    assert decal_image.safe_filename("Bolt M3") == "Bolt M3"
    assert decal_image.safe_filename("Bolt   M3") == "Bolt M3"
    # path separators and illegal chars are stripped (can't escape the folder);
    # leading/trailing dots are also trimmed (no "../" or hidden-file stems)
    assert decal_image.safe_filename("../../etc/passwd") == "etcpasswd"
    assert decal_image.safe_filename("a/b\\c:d*e?f") == "abcdef"
    assert decal_image.safe_filename('na"me') == "name"
    # spaces between kept characters survive an illegal-char strip
    assert decal_image.safe_filename("na me|x") == "na mex"
    # control whitespace becomes a space, leading/trailing dots + space trimmed
    assert decal_image.safe_filename("  .name.\t") == "name"
    # nothing usable -> default
    assert decal_image.safe_filename("///") == "untitled"
    assert decal_image.safe_filename("") == "untitled"
    assert decal_image.safe_filename("   ", default="x") == "x"


# --- atlas: trim-sheet slicing + bin packing (v0.9) --------------------------

def test_slice_grid():
    cells = atlas.slice_grid(2, 2)
    assert len(cells) == 4
    # reading order: first cell is the TOP-LEFT (low u, high v)
    assert cells[0] == (0.0, 0.5, 0.5, 1.0)
    assert cells[1] == (0.5, 0.5, 1.0, 1.0)
    assert cells[2] == (0.0, 0.0, 0.5, 0.5)
    assert cells[3] == (0.5, 0.0, 1.0, 0.5)
    # every cell is a quarter of the unit square; areas sum to 1
    area = sum((u1 - u0) * (v1 - v0) for u0, v0, u1, v1 in cells)
    assert math.isclose(area, 1.0, abs_tol=1e-9)
    # degenerate counts clamp to at least 1 row/col
    assert atlas.slice_grid(0, 0) == [(0.0, 0.0, 1.0, 1.0)]


def test_cell_rect_wraps():
    assert atlas.cell_rect(2, 2, 0) == (0.0, 0.5, 0.5, 1.0)
    assert atlas.cell_rect(2, 2, 4) == atlas.cell_rect(2, 2, 0)   # wraps forward
    assert atlas.cell_rect(2, 2, -1) == atlas.cell_rect(2, 2, 3)  # and backward


def test_rect_pixels_and_next_pow2():
    assert atlas.rect_pixels((0.0, 0.0, 0.5, 0.25), 1024, 1024) == (512.0, 256.0)
    assert atlas.next_pow2(1) == 1
    assert atlas.next_pow2(513) == 1024
    assert atlas.next_pow2(1024) == 1024


def test_pack_shelves_no_overlap_and_in_bounds():
    sizes = [(100, 50), (40, 80), (60, 60), (30, 30)]
    places, aw, ah = atlas.pack_shelves(sizes, max_width=128)
    assert len(places) == len(sizes)
    assert aw == 128 and ah > 0
    # everything stays inside the atlas
    for x, y, w, h in places:
        assert 0 <= x and x + w <= aw
        assert 0 <= y and y + h <= ah
    # no two rects overlap
    for i in range(len(places)):
        for j in range(i + 1, len(places)):
            ax, ay, aw_, ah_ = places[i]
            bx, by, bw, bh = places[j]
            separate = (ax + aw_ <= bx or bx + bw <= ax
                        or ay + ah_ <= by or by + bh <= ay)
            assert separate, "rect %d overlaps rect %d" % (i, j)


def test_pack_shelves_widens_for_oversized_item():
    # an item wider than max_width forces the atlas to grow to fit it
    places, aw, ah = atlas.pack_shelves([(200, 30)], max_width=128)
    assert aw == 200 and places[0] == (0, 0, 200, 30)
    assert atlas.pack_shelves([], 128) == ([], 0, 0)


def test_rect_to_uv_flips_y():
    # top-left pixel rect -> UV with v=1 at the top of the image
    assert atlas.rect_to_uv(0, 0, 64, 64, 128, 128) == (0.0, 0.5, 0.5, 1.0)
    assert atlas.rect_to_uv(64, 64, 64, 64, 128, 128) == (0.5, 0.0, 1.0, 0.5)
    assert atlas.rect_to_uv(0, 0, 1, 1, 0, 0) == (0.0, 0.0, 1.0, 1.0)  # guard


def test_remap_uv_composes_into_slot():
    slot = (0.5, 0.0, 1.0, 0.5)                       # bottom-right quadrant
    assert atlas.remap_uv(0.0, 0.0, slot) == (0.5, 0.0)   # min corner -> slot min
    assert atlas.remap_uv(1.0, 1.0, slot) == (1.0, 0.5)   # max corner -> slot max
    assert atlas.remap_uv(0.5, 0.5, slot) == (0.75, 0.25)  # center -> slot center


def _rgba(px, w, x, y):
    i = (y * w + x) * 4
    return px[i:i + 4]


def test_blit_pixels_places_block():
    # 4x4 transparent atlas; blit a 2x2 source at bottom-left (1, 1)
    dst = [0.0] * (4 * 4 * 4)
    src = [float(n) for n in range(2 * 2 * 4)]    # 16 distinct values
    atlas.blit_pixels(dst, 4, 4, src, 2, 2, 1, 1)
    assert _rgba(dst, 4, 1, 1) == src[0:4]        # src row 0 -> dst row 1
    assert _rgba(dst, 4, 2, 2) == src[12:16]      # src (1,1) -> dst (2,2)
    assert _rgba(dst, 4, 0, 0) == [0.0, 0.0, 0.0, 0.0]   # untouched stays clear


def test_blit_pixels_clips_out_of_bounds():
    dst = [0.0] * (2 * 2 * 4)
    src = [1.0] * (2 * 2 * 4)
    # place so only the bottom-left pixel lands inside (x0=-1, y0=-1)
    atlas.blit_pixels(dst, 2, 2, src, 2, 2, -1, -1)
    assert _rgba(dst, 2, 0, 0) == [1.0, 1.0, 1.0, 1.0]   # the one in-bounds pixel
    assert _rgba(dst, 2, 1, 1) == [0.0, 0.0, 0.0, 0.0]   # the rest clipped away


# --- transform: cable / rope sag math (v1.1) --------------------------------

def test_cable_points_straight_and_sag():
    # straight line: endpoints exact, midpoint interpolated, no droop
    pts = transform.cable_points((0, 0, 0), (2, 0, 0), segments=2, sag=0.0)
    assert pts[0] == (0.0, 0.0, 0.0)
    assert pts[-1] == (2.0, 0.0, 0.0)
    assert pts[1] == (1.0, 0.0, 0.0)
    # with sag the mid-span droops by `sag` along -Z; endpoints unchanged
    pts = transform.cable_points((0, 0, 0), (2, 0, 0), segments=2, sag=0.5)
    assert pts[0] == (0.0, 0.0, 0.0) and pts[-1] == (2.0, 0.0, 0.0)
    assert math.isclose(pts[1][2], -0.5, abs_tol=1e-9)
    # sag pulls along an arbitrary axis index
    pts = transform.cable_points((0, 0, 0), (0, 2, 0), segments=2, sag=0.3, axis=0)
    assert math.isclose(pts[1][0], -0.3, abs_tol=1e-9)
    # segments clamps to at least 1 (just the two endpoints)
    assert len(transform.cable_points((0, 0, 0), (1, 0, 0), segments=0)) == 2


def test_cable_chain_joins_without_duplicates():
    anchors = [(0, 0, 0), (2, 0, 0), (4, 0, 0)]
    chain = transform.cable_chain(anchors, segments=2, sag=0.0)
    # 2 spans * 2 segments + 1 = 5 points, the shared anchor is not duplicated
    assert len(chain) == 5
    assert chain[0] == (0.0, 0.0, 0.0)
    assert chain[-1] == (4.0, 0.0, 0.0)
    assert chain[2] == (2.0, 0.0, 0.0)   # join anchor appears exactly once
    # fewer than two anchors returned unchanged
    assert transform.cable_chain([(1, 2, 3)]) == [(1, 2, 3)]
    assert transform.cable_chain([]) == []


# --- asset_lib: kit (.blend) library scan (v1.0) -----------------------------

def test_is_asset_file():
    assert asset_lib.is_asset_file("part.blend")
    assert asset_lib.is_asset_file("/a/b/KIT.BLEND")        # case-insensitive
    assert not asset_lib.is_asset_file("texture.png")
    assert not asset_lib.is_asset_file("noext")


def test_scan_assets():
    assert asset_lib.scan_assets("") == []
    assert asset_lib.scan_assets("/no/such/folder/here") == []
    with tempfile.TemporaryDirectory() as d:
        for fn in ("b.blend", "a.blend", "notes.txt", "tex.png"):
            with open(os.path.join(d, fn), "w") as f:
                f.write("x")
        os.mkdir(os.path.join(d, "sub.blend"))   # a dir named like a blend: skip
        items = asset_lib.scan_assets(d)
        names = [n for n, _p in items]
        assert names == ["a", "b"]               # sorted, stems, non-blend excluded
        assert all(os.path.isfile(p) for _n, p in items)


# --- command: reversible-operation journal (HardFlow Mode undo) -------------

class _Journal:
    """A tiny do/undo probe: applies a token to a shared list, reverts by
    removing it, and records how many times each hook fired."""

    def __init__(self, log, token):
        self.log = log
        self.token = token
        self.applies = 0
        self.reverts = 0

    def make(self):
        def do():
            self.applies += 1
            self.log.append(self.token)

        def undo():
            self.reverts += 1
            self.log.remove(self.token)
        return command.CallbackCommand(do, undo, label="j%s" % self.token)


def test_command_execute_undo_are_idempotent():
    log = []
    j = _Journal(log, 1)
    cmd = j.make()
    cmd.execute()
    cmd.execute()                 # second execute is a no-op (already done)
    assert log == [1] and j.applies == 1
    cmd.undo()
    cmd.undo()                    # second undo is a no-op (already reverted)
    assert log == [] and j.reverts == 1


def test_command_manager_do_undo_redo():
    log = []
    mgr = command.CommandManager()
    mgr.do(_Journal(log, "a").make())
    mgr.do(_Journal(log, "b").make())
    assert log == ["a", "b"] and len(mgr) == 2 and mgr.labels() == ["ja", "jb"]
    mgr.undo()
    assert log == ["a"] and mgr.can_redo()
    mgr.redo()
    assert log == ["a", "b"] and not mgr.can_redo()


def test_command_manager_new_do_clears_redo():
    log = []
    mgr = command.CommandManager()
    mgr.do(_Journal(log, "a").make())
    mgr.undo()
    assert mgr.can_redo()
    mgr.do(_Journal(log, "c").make())     # a fresh action forks history
    assert not mgr.can_redo()
    assert log == ["c"]


def test_command_manager_undo_all():
    log = []
    mgr = command.CommandManager()
    for t in ("a", "b", "c"):
        mgr.do(_Journal(log, t).make())
    mgr.undo_all()
    assert log == [] and len(mgr) == 0 and not mgr.can_undo()


def test_macro_command_reverses_children_in_order():
    log = []
    macro = command.MacroCommand(label="chain")
    macro.add(_Journal(log, 1).make())
    macro.add(_Journal(log, 2).make())
    macro.add(_Journal(log, 3).make())
    macro.execute()
    assert log == [1, 2, 3]
    macro.undo()
    assert log == []              # undone 3 -> 2 -> 1, list emptied cleanly


def test_macro_command_rolls_back_on_failing_child():
    log = []
    macro = command.MacroCommand(label="chain")
    macro.add(_Journal(log, 1).make())
    macro.add(_Journal(log, 2).make())

    def boom():
        raise RuntimeError("solver failed")
    macro.add(command.CallbackCommand(boom, lambda: None, label="bad"))

    raised = False
    try:
        macro.execute()
    except RuntimeError:
        raised = True
    # all-or-nothing: the two applied children were rolled back, none linger
    assert raised and log == [] and not macro.done


def _run_all():
    """Standalone run: find test_* functions, run them, print a summary."""
    fns = sorted((n, f) for n, f in globals().items()
                 if n.startswith("test_") and callable(f))
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print("ok   ", name)
        except AssertionError as ex:
            failed += 1
            print("FAIL ", name, "->", ex)
    print("\n%d/%d passed" % (len(fns) - failed, len(fns)))
    return failed


if __name__ == "__main__":
    raise SystemExit(_run_all())
