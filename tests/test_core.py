# Saf cekirdek mantigin Blender'siz birim testleri.
#
# core/grid.py ve core/snap.py bilincli olarak bpy/mathutils icermez; bu yuzden
# normal CPython ile kosabilirler. (raycast/geometry/boolean bpy'ye baglidir ve
# burada test edilmez -- onlar Blender icinde headless kosulur.)
#
# Kosum:
#   python tests/test_core.py          # bagimsiz, pytest gerekmez
#   pytest tests/                       # pytest varsa otomatik bulur
import importlib.util
import math
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    """core/<name>.py'yi paketi (ve bpy'yi) import etmeden dosyadan yukle."""
    path = os.path.join(_ROOT, "core", name + ".py")
    spec = importlib.util.spec_from_file_location("hf_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


grid = _load("grid")
snap = _load("snap")


# --- grid: dunya-olcekli snap ------------------------------------------------

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
    # grid'e hizali sinirlara disari dogru genisler
    segs = grid.world_grid_segments(0.05, 0.95, 0.05, 0.95, 0.5)
    us = sorted({s[0][0] for s in segs if s[0][0] == s[1][0]})
    assert us == [0.0, 0.5, 1.0]


def test_world_grid_segments_guards():
    assert grid.world_grid_segments(0, 1000, 0, 1000, 0.001) == []  # patlama korumasi
    assert grid.world_grid_segments(1, 0, 0, 1, 0.1) == []          # dejenere sinir


# --- grid: aci kilidi --------------------------------------------------------

def test_snap_angle_locks_to_step():
    # 40 derecelik yon 15-kademede 45'e yuvarlanir; mesafe korunur
    a = (0.0, 0.0)
    p = (math.cos(math.radians(40)), math.sin(math.radians(40)))
    sx, sy = grid.snap_angle(a, p, 15, True)
    assert math.isclose(math.degrees(math.atan2(sy, sx)), 45.0, abs_tol=1e-6)
    assert math.isclose(math.hypot(sx, sy), 1.0, abs_tol=1e-9)


def test_snap_angle_disabled_and_degenerate():
    assert grid.snap_angle((0, 0), (3, 4), 15, False) == (3, 4)
    assert grid.snap_angle((2, 2), (2, 2), 15, True) == (2, 2)  # sifir uzaklik


# --- grid: kendiyle kesisme (bozuk poly tespiti) -----------------------------

def test_segments_intersect():
    assert grid.segments_intersect((0, 0), (10, 10), (0, 10), (10, 0))   # X
    assert not grid.segments_intersect((0, 0), (10, 0), (0, 5), (10, 5))  # paralel
    assert grid.segments_intersect((0, 0), (10, 0), (5, 0), (5, 5))       # T-dokunma


def test_is_self_intersecting():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert not grid.is_self_intersecting(square)
    bowtie = [(0, 0), (10, 0), (0, 10), (10, 10)]   # papyon (kendiyle kesisir)
    assert grid.is_self_intersecting(bowtie)
    assert not grid.is_self_intersecting([(0, 0), (1, 0), (0, 1)])  # ucgen
    # konkav ama temiz (ok/L sekli) kesismez
    arrow = [(0, 0), (4, 0), (4, 4), (2, 2), (0, 4)]
    assert not grid.is_self_intersecting(arrow)


# --- snap: vertex / edge -----------------------------------------------------

def test_nearest_point():
    pts = [(0, 0), (10, 0), (3, 4)]
    assert snap.nearest_point((4, 4), pts, 5)[0] == 2
    assert snap.nearest_point((100, 100), pts, 5) is None
    assert snap.nearest_point((0, 0), [None, (1, 0), None], 5)[0] == 1  # None atlanir


def test_closest_point_on_segment():
    s = snap.closest_point_on_segment
    assert s((5, 5), (0, 0), (10, 0)) == (5.0, 0.0)    # dik ayak
    assert s((-5, 0), (0, 0), (10, 0)) == (0.0, 0.0)   # a'ya clamp
    assert s((15, 0), (0, 0), (10, 0)) == (10.0, 0.0)  # b'ye clamp
    assert s((1, 1), (2, 2), (2, 2)) == (2.0, 2.0)     # dejenere kenar


def test_nearest_on_segments():
    segs = [((0, 0), (10, 0)), ((0, 20), (10, 20))]
    hit = snap.nearest_on_segments((5, 3), segs, 5)
    assert hit[0] == 0 and hit[1] == (5.0, 0.0)
    assert snap.nearest_on_segments((5, 10), segs, 5) is None
    # ucu None olan kenar atlanir
    segs2 = [(None, (1, 1)), ((0, 0), (10, 0))]
    assert snap.nearest_on_segments((5, 3), segs2, 5)[0] == 1


def _run_all():
    """Bagimsiz kosum: test_* fonksiyonlarini bul, calistir, ozet bas."""
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
    print("\n%d/%d gecti" % (len(fns) - failed, len(fns)))
    return failed


if __name__ == "__main__":
    raise SystemExit(_run_all())
