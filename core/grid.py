# Grid snapping. v0.1 ekran-uzayinda snap yapar (basit ve ongorulebilir).
# YOL HARITASI: bunu projeksiyon duzleminin yerel 2D ekseninde snap'e cevir
# (Grid Modeler'in "absolute size" modu gibi tutarli dunya-olcekli grid icin).
import math


def snap_point(coord, grid_px, enabled):
    if not enabled or grid_px <= 1:
        return (coord[0], coord[1])
    return (round(coord[0] / grid_px) * grid_px,
            round(coord[1] / grid_px) * grid_px)


def grid_lines(region, grid_px, enabled):
    """Viewport'a cizilecek grid cizgilerinin uc nokta listesi (LINES icin)."""
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
    """Merkez ve kenar noktasindan ekran-uzayi cember koseleri."""
    r = math.hypot(edge[0] - center[0], edge[1] - center[1])
    pts = []
    for i in range(segments):
        a = (i / segments) * math.tau
        pts.append((center[0] + math.cos(a) * r,
                    center[1] + math.sin(a) * r))
    return pts


def box_points(a, b):
    """Iki kosegen noktasindan dikdortgenin 4 kosesi."""
    return [(a[0], a[1]), (b[0], a[1]), (b[0], b[1]), (a[0], b[1])]
