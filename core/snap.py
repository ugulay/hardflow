# Geometri (vertex / edge) snap -- saf 2D ekran-uzayi matematigi.
# Operator, hedefin dunya koselerini ekrana projekte eder; bu modul yalnizca
# "imlece en yakin"i bulur. bpy/mathutils gerekmez, duz tuple ile test edilebilir.
import math


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def nearest_point(cursor, points, threshold):
    """points: [(x, y) | None, ...]. cursor'a en yakin nokta esik icindeyse
    (index, (x, y), dist) doner; yoksa None. None elemanlar atlanir (kamera
    arkasinda kalan projeksiyonlar)."""
    best = None
    for i, p in enumerate(points):
        if p is None:
            continue
        d = _dist(cursor, p)
        if d <= threshold and (best is None or d < best[2]):
            best = (i, p, d)
    return best


def closest_point_on_segment(p, a, b):
    """p noktasinin [a, b] dogru parcasi uzerindeki en yakin noktasi (2D)."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    if ll <= 1e-12:           # dejenere kenar (a == b)
        return (ax, ay)
    t = ((px - ax) * dx + (py - ay) * dy) / ll
    t = max(0.0, min(1.0, t))
    return (ax + t * dx, ay + t * dy)


def nearest_on_segments(cursor, segments, threshold):
    """segments: [((x1,y1),(x2,y2)) | uçları None olabilen, ...]. cursor'a en
    yakin kenar uzeri noktasi esik icindeyse (index, (x, y), dist) doner."""
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
