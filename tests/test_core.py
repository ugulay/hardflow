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
snap = _load("snap")
decal_math = _load("decal_math")
decal_image = _load("decal_image")
atlas = _load("atlas")
transform = _load("transform")
asset_lib = _load("asset_lib")


# --- grid: world-scale snap --------------------------------------------------

def test_snap_world_rounds_to_grid():
    assert grid.snap_world(0.123, -0.077, 0.1, True) == (0.1, -0.1)
    assert grid.snap_world(0.04, 0.06, 0.1, True) == (0.0, 0.1)


def test_snap_world_disabled_or_zero_is_noop():
    assert grid.snap_world(0.123, -0.077, 0.1, False) == (0.123, -0.077)
    assert grid.snap_world(5.0, 5.0, 0.0, True) == (5.0, 5.0)


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


# --- grid: shape points ------------------------------------------------------

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


# --- decal_math: orientation basis -------------------------------------------

def _is_unit(v):
    return math.isclose(math.sqrt(sum(c * c for c in v)), 1.0, abs_tol=1e-9)


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


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


# --- transform: array / radial-array math (v1.0) ----------------------------

def test_radial_step_radians():
    assert math.isclose(transform.radial_step_radians(4), math.pi / 2, abs_tol=1e-9)
    assert math.isclose(transform.radial_step_radians(6, 180.0),
                        math.radians(30), abs_tol=1e-9)
    # count clamps to at least 1 (a single copy = no rotation)
    assert math.isclose(transform.radial_step_radians(0), math.radians(360),
                        abs_tol=1e-9)


def test_radial_angles_deg():
    assert transform.radial_angles_deg(4) == [0.0, 90.0, 180.0, 270.0]
    assert transform.radial_angles_deg(3, 180.0) == [0.0, 60.0, 120.0]
    assert transform.radial_angles_deg(0) == [0.0]   # clamped to one copy


def test_array_offset_vector():
    assert transform.array_offset_vector('X', 2.0) == (2.0, 0.0, 0.0)
    assert transform.array_offset_vector('Y', 1.5) == (0.0, 1.5, 0.0)
    assert transform.array_offset_vector('Z', 0.5, 0.5) == (0.0, 0.0, 1.0)


def test_mirror_axis_flags():
    assert transform.mirror_axis_flags('X') == (True, False, False)
    assert transform.mirror_axis_flags('Y') == (False, True, False)
    assert transform.mirror_axis_flags('Z') == (False, False, True)


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
