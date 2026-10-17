#!/usr/bin/env python
# Generator for Hardflow's bundled starter library.
#
# Run it to (re)generate `library/decals`, `library/trims` and `library/assets`:
#
#     python tools/make_library.py                 # images only
#     blender -b -P tools/make_library.py -- all   # images + INSERT .blend kit
#
# Everything here is drawn/modelled procedurally in-house, so the shipped
# library is unambiguously the project's own work under the same GPLv3 licence
# as the code -- no third-party asset provenance to audit. The decals are clean
# geometric hard-surface graphics (seams, vents, fasteners, hazard markings):
# exactly what procedural generation is good at, and exactly what the decal /
# trim-sheet / POM / atlas features need in order to be reachable out of the box.
#
# Images are written with a tiny built-in PNG encoder (zlib + struct), so the
# image half needs no Blender and no third-party packages. Shapes are rasterised
# at SS x resolution and box-filtered down, which is what keeps the edges clean.
#
# This file is a development tool: it is excluded from the released extension
# zip (see .github/workflows/release.yml), and the generated PNG/.blend files
# are what actually ship.
import math
import os
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "library")
SS = 4                      # supersampling factor for anti-aliased edges


# --------------------------------------------------------------------------
# PNG output
# --------------------------------------------------------------------------

def write_png(path, width, height, rgba):
    """Write an 8-bit RGBA PNG. `rgba` is a flat bytearray of w*h*4, top row
    first. Pure stdlib: PNG is just zlib-compressed scanlines with a 1-byte
    filter prefix each, wrapped in length/type/CRC chunks."""
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)                               # filter type 0 (None)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))

    header = struct.pack(">2I5B", width, height, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", header)
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)
    return path


# --------------------------------------------------------------------------
# Canvas: a supersampled coverage/colour buffer
# --------------------------------------------------------------------------

class Canvas:
    """A supersampled grayscale-with-alpha canvas.

    Decals are drawn as luminance + alpha on purpose: the colour carries the
    graphic, and its luminance doubles as the height map that drives Hardflow's
    parallax / bump depth (core/parallax.surface_depth reads 1 - luminance), so
    one file works as both albedo and depth source."""

    def __init__(self, size):
        self.size = size
        self.n = size * SS
        # value, alpha per supersample
        self.val = bytearray([255]) * (self.n * self.n)
        self.alpha = bytearray(self.n * self.n)

    # -- primitives (all in 0..1 unit space, y down) --

    def _px(self, x, y, v, a):
        i = y * self.n + x
        if a >= self.alpha[i]:
            self.alpha[i] = a
            self.val[i] = v
        elif a:
            self.val[i] = (self.val[i] * (255 - a) + v * a) // 255

    def rect(self, x0, y0, x1, y1, v=0, a=255, radius=0.0):
        n = self.n
        px0, py0 = max(0, int(x0 * n)), max(0, int(y0 * n))
        px1, py1 = min(n, int(math.ceil(x1 * n))), min(n, int(math.ceil(y1 * n)))
        r = radius * n
        for y in range(py0, py1):
            for x in range(px0, px1):
                if r > 0.0:
                    # rounded corners: distance to the inner rect
                    cx = min(max(x + 0.5, px0 + r), px1 - r)
                    cy = min(max(y + 0.5, py0 + r), py1 - r)
                    if (x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2 > r * r:
                        continue
                self._px(x, y, v, a)

    def ring(self, cx, cy, r_out, r_in=0.0, v=0, a=255):
        n = self.n
        cxp, cyp, ro, ri = cx * n, cy * n, r_out * n, r_in * n
        for y in range(max(0, int(cyp - ro - 1)), min(n, int(cyp + ro + 2))):
            for x in range(max(0, int(cxp - ro - 1)), min(n, int(cxp + ro + 2))):
                d2 = (x + 0.5 - cxp) ** 2 + (y + 0.5 - cyp) ** 2
                if ri * ri <= d2 <= ro * ro:
                    self._px(x, y, v, a)

    def poly(self, pts, v=0, a=255):
        """Fill a convex-or-concave polygon by even-odd scanline crossing."""
        n = self.n
        p = [(x * n, y * n) for x, y in pts]
        ys = [q[1] for q in p]
        for y in range(max(0, int(min(ys))), min(n, int(math.ceil(max(ys))) + 1)):
            yc = y + 0.5
            xs = []
            for i in range(len(p)):
                x0, y0 = p[i]
                x1, y1 = p[(i + 1) % len(p)]
                if (y0 <= yc < y1) or (y1 <= yc < y0):
                    xs.append(x0 + (yc - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                for x in range(max(0, int(xs[k])), min(n, int(xs[k + 1]) + 1)):
                    self._px(x, y, v, a)

    def line(self, x0, y0, x1, y1, width, v=0, a=255):
        """A thick line as a quad (round caps are not needed for these graphics)."""
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy)
        if ln <= 0.0:
            return
        ox, oy = -dy / ln * width / 2.0, dx / ln * width / 2.0
        self.poly([(x0 + ox, y0 + oy), (x1 + ox, y1 + oy),
                   (x1 - ox, y1 - oy), (x0 - ox, y0 - oy)], v, a)

    # -- output --

    def rgba(self):
        """Box-filter the supersampled buffer down to `size` and interleave."""
        size, n = self.size, self.n
        out = bytearray(size * size * 4)
        f2 = SS * SS
        for y in range(size):
            for x in range(size):
                vs = a_s = 0
                for sy in range(y * SS, y * SS + SS):
                    base = sy * n
                    for sx in range(x * SS, x * SS + SS):
                        i = base + sx
                        a = self.alpha[i]
                        a_s += a
                        vs += self.val[i] * a       # alpha-weighted colour
                a = a_s // f2
                v = (vs // a_s) if a_s else 255
                o = (y * size + x) * 4
                out[o] = out[o + 1] = out[o + 2] = v
                out[o + 3] = a
        return out


# --------------------------------------------------------------------------
# The decals
# --------------------------------------------------------------------------

def d_panel_seam(c):
    """A straight recessed seam with a lighter lip -- the POM showcase."""
    c.rect(0.02, 0.46, 0.98, 0.54, v=20)
    c.rect(0.02, 0.44, 0.98, 0.46, v=190, a=200)      # upper lip
    c.rect(0.02, 0.54, 0.98, 0.56, v=90, a=200)       # lower shadow


def d_panel_corner(c):
    """An L-shaped seam, for where two panels meet at a corner. The arms run
    from the junction outward -- a seam crossing the middle would be a T."""
    c.rect(0.46, 0.46, 0.92, 0.54, v=20)          # arm to the right
    c.rect(0.46, 0.08, 0.54, 0.54, v=20)          # arm upward
    c.rect(0.46, 0.44, 0.92, 0.46, v=190, a=200)  # lip along the horizontal
    c.rect(0.44, 0.08, 0.46, 0.46, v=190, a=200)  # lip along the vertical


def d_panel_double(c):
    """Twin parallel seams, the staple for breaking up a large flat."""
    for y in (0.34, 0.60):
        c.rect(0.04, y, 0.96, y + 0.06, v=24)
        c.rect(0.04, y - 0.02, 0.96, y, v=185, a=190)


def d_vent_slots(c):
    """Five louvre slots with equal ribs -- matches the VENT draw shape."""
    n, top, bot = 5, 0.16, 0.84
    pitch = (bot - top) / (2 * n - 1)
    for i in range(n):
        y = top + i * 2 * pitch
        c.rect(0.14, y, 0.86, y + pitch, v=16, radius=pitch * 0.35)
        c.rect(0.14, y - pitch * 0.18, 0.86, y, v=200, a=170)


def d_vent_round(c):
    """A circular grate: concentric rings plus radial spokes."""
    c.ring(0.5, 0.5, 0.47, 0.43, v=120)
    for r in (0.38, 0.29, 0.20, 0.11):
        c.ring(0.5, 0.5, r, r - 0.045, v=18)
    for k in range(6):
        a = k * math.pi / 3.0
        c.line(0.5, 0.5, 0.5 + 0.42 * math.cos(a), 0.5 + 0.42 * math.sin(a),
               0.035, v=150)


def d_hex_grill(c):
    """A hexagonal mesh grill, for intakes and speaker ports."""
    r, rows, cols = 0.075, 7, 7
    dx, dy = r * 1.8, r * 1.56
    for row in range(rows):
        for col in range(cols):
            cx = 0.12 + col * dx + (dx / 2.0 if row % 2 else 0.0)
            cy = 0.12 + row * dy
            if cx > 0.95 or cy > 0.95:
                continue
            pts = [(cx + r * 0.78 * math.cos(math.pi / 6 + k * math.pi / 3),
                    cy + r * 0.78 * math.sin(math.pi / 6 + k * math.pi / 3))
                   for k in range(6)]
            c.poly(pts, v=22)


def _hex_head(c, cx, cy, r, v=40):
    pts = [(cx + r * math.cos(k * math.pi / 3), cy + r * math.sin(k * math.pi / 3))
           for k in range(6)]
    c.poly(pts, v=160)
    pts = [(cx + r * 0.62 * math.cos(k * math.pi / 3),
            cy + r * 0.62 * math.sin(k * math.pi / 3)) for k in range(6)]
    c.poly(pts, v=v)


def d_bolt_hex(c):
    """One hex bolt head with a washer."""
    c.ring(0.5, 0.5, 0.46, 0.38, v=120)
    _hex_head(c, 0.5, 0.5, 0.33)


def d_bolt_row(c):
    """A row of four hex bolts -- fastener strips along a seam."""
    for i in range(4):
        _hex_head(c, 0.155 + i * 0.23, 0.5, 0.095)


def d_rivet_row(c):
    """Small domed rivets: two staggered rows."""
    for row, y in ((0, 0.33), (1, 0.67)):
        for i in range(7):
            cx = 0.09 + i * 0.137 + (0.068 if row else 0.0)
            if cx > 0.95:
                continue
            c.ring(cx, y, 0.045, 0.0, v=150)
            c.ring(cx, y, 0.022, 0.0, v=60)


def d_screw_phillips(c):
    """A phillips screw head."""
    c.ring(0.5, 0.5, 0.44, 0.0, v=165)
    c.ring(0.5, 0.5, 0.44, 0.37, v=90)
    c.rect(0.44, 0.17, 0.56, 0.83, v=25, radius=0.03)
    c.rect(0.17, 0.44, 0.83, 0.56, v=25, radius=0.03)


def d_access_hatch(c):
    """A rounded access hatch: recessed plate, lip and four corner bolts."""
    c.rect(0.06, 0.18, 0.94, 0.82, v=120, radius=0.08)
    c.rect(0.09, 0.21, 0.91, 0.79, v=40, radius=0.06)
    c.rect(0.14, 0.26, 0.86, 0.74, v=150, radius=0.05)
    for x in (0.20, 0.80):
        for y in (0.32, 0.68):
            _hex_head(c, x, y, 0.05)


def d_data_plate(c):
    """A blank data plate: border, header band and hatch lines where text would
    go. Text-free on purpose -- no language, no fake branding, reusable."""
    c.rect(0.08, 0.26, 0.92, 0.74, v=175, radius=0.02)
    c.rect(0.10, 0.28, 0.90, 0.72, v=60, radius=0.015)
    c.rect(0.10, 0.28, 0.90, 0.40, v=150)             # header band
    for i in range(4):
        y = 0.455 + i * 0.065
        c.rect(0.14, y, 0.62 - i * 0.07, y + 0.028, v=170)
    for x in (0.12, 0.88):
        c.ring(x, 0.5, 0.022, 0.0, v=200)


def d_hazard_stripes(c):
    """Diagonal hazard stripes, clipped to a band."""
    for i in range(-6, 14):
        x = i * 0.13
        c.poly([(x, 0.28), (x + 0.065, 0.28), (x + 0.065 + 0.44, 0.72),
                (x + 0.44, 0.72)], v=30)
    # knock the band edges straight
    c.rect(0.0, 0.0, 1.0, 0.28, v=255, a=0)
    c.rect(0.0, 0.72, 1.0, 1.0, v=255, a=0)
    c.rect(0.0, 0.255, 1.0, 0.285, v=90)
    c.rect(0.0, 0.715, 1.0, 0.745, v=90)


def d_arrow(c):
    """A directional flow arrow."""
    c.poly([(0.08, 0.42), (0.58, 0.42), (0.58, 0.28), (0.94, 0.5),
            (0.58, 0.72), (0.58, 0.58), (0.08, 0.58)], v=30)


def d_grate_slot(c):
    """A rectangular slotted grate (four wide slots, rounded ends)."""
    c.rect(0.06, 0.1, 0.94, 0.9, v=130, radius=0.04)
    for i in range(4):
        y = 0.19 + i * 0.175
        c.rect(0.13, y, 0.87, y + 0.105, v=18, radius=0.05)


def d_tread_plate(c):
    """Anti-slip tread pattern, tiles seamlessly as a surface detail."""
    for row in range(4):
        for col in range(4):
            cx, cy = 0.125 + col * 0.25, 0.125 + row * 0.25
            a = math.pi / 4 if (row + col) % 2 else -math.pi / 4
            dx, dy = 0.085 * math.cos(a), 0.085 * math.sin(a)
            c.line(cx - dx, cy - dy, cx + dx, cy + dy, 0.045, v=40)


DECALS = (
    ("panel_seam", 512, d_panel_seam),
    ("panel_corner", 512, d_panel_corner),
    ("panel_double", 512, d_panel_double),
    ("vent_slots", 512, d_vent_slots),
    ("vent_round", 512, d_vent_round),
    ("hex_grill", 512, d_hex_grill),
    ("bolt_hex", 256, d_bolt_hex),
    ("bolt_row", 512, d_bolt_row),
    ("rivet_row", 512, d_rivet_row),
    ("screw_phillips", 256, d_screw_phillips),
    ("access_hatch", 512, d_access_hatch),
    ("data_plate", 512, d_data_plate),
    ("hazard_stripes", 512, d_hazard_stripes),
    ("arrow_flow", 512, d_arrow),
    ("grate_slot", 512, d_grate_slot),
    ("tread_plate", 512, d_tread_plate),
)


def build_decals(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    made = []
    for name, size, fn in DECALS:
        c = Canvas(size)
        fn(c)
        made.append(write_png(os.path.join(out_dir, name + ".png"),
                              size, size, c.rgba()))
        print("  decal", name)
    return made


# --------------------------------------------------------------------------
# The trim sheet: a 4x4 grid, so Seed Grid Regions (4, 4) carves it exactly
# --------------------------------------------------------------------------

TRIM_CELLS = (
    d_panel_seam, d_panel_double, d_vent_slots, d_bolt_row,
    d_hex_grill, d_access_hatch, d_rivet_row, d_hazard_stripes,
    d_vent_round, d_data_plate, d_arrow, d_grate_slot,
    d_panel_corner, d_screw_phillips, d_tread_plate, d_bolt_hex,
)


def build_trim_sheet(out_dir, cell=256):
    """One 4x4 sheet. Each cell is drawn on its own canvas and blitted in, so
    the cell graphics are identical to the standalone decals -- which makes the
    sheet a real teaching aid for the trim editor rather than filler."""
    os.makedirs(out_dir, exist_ok=True)
    size = cell * 4
    sheet = bytearray(size * size * 4)
    for idx, fn in enumerate(TRIM_CELLS):
        c = Canvas(cell)
        fn(c)
        src = c.rgba()
        cx, cy = (idx % 4) * cell, (idx // 4) * cell
        for y in range(cell):
            so = y * cell * 4
            do = ((cy + y) * size + cx) * 4
            sheet[do:do + cell * 4] = src[so:so + cell * 4]
    path = write_png(os.path.join(out_dir, "trim_sheet_4x4.png"),
                     size, size, sheet)
    print("  trim sheet 4x4 (%dpx)" % size)
    return [path]


# --------------------------------------------------------------------------
# The INSERT kit (needs Blender)
# --------------------------------------------------------------------------

def build_assets(out_dir):
    """Write one .blend per kit part. Only runs inside Blender."""
    try:
        import bpy
        import bmesh
    except ImportError:
        print("  (skipped INSERT kit: run inside Blender for .blend output)")
        return []
    from mathutils import Matrix, Vector

    os.makedirs(out_dir, exist_ok=True)

    def new_bm():
        return bmesh.new()

    def finish(bm, name):
        me = bpy.data.meshes.new(name)
        bm.normal_update()
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(name, me)
        return ob

    def cyl(bm, r, depth, segs=16, matrix=None, cap=True):
        bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segs,
                              radius1=r, radius2=r, depth=depth,
                              matrix=matrix or Matrix())

    def cone(bm, r1, r2, depth, segs=16, matrix=None):
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs,
                              radius1=r1, radius2=r2, depth=depth,
                              matrix=matrix or Matrix())

    def box(bm, sx, sy, sz, loc=(0, 0, 0)):
        m = (Matrix.Translation(Vector(loc))
             @ Matrix.Diagonal(Vector((sx, sy, sz, 1.0))))
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)

    def bolt_m8():
        bm = new_bm()
        cyl(bm, 0.008, 0.005, 6,
            Matrix.Translation((0, 0, 0.0025)))          # hex head
        cyl(bm, 0.0055, 0.018, 12,
            Matrix.Translation((0, 0, -0.009)))          # shank
        return [finish(bm, "HF_Bolt_M8")]

    def washer_nut():
        bm = new_bm()
        cyl(bm, 0.009, 0.0035, 6, Matrix.Translation((0, 0, 0.00175)))
        return [finish(bm, "HF_Nut_M8")]

    def vent_louvre():
        bm = new_bm()
        box(bm, 0.12, 0.08, 0.006, (0, 0, -0.003))
        for i in range(5):
            y = -0.028 + i * 0.014
            box(bm, 0.104, 0.007, 0.012, (0, y, 0.004))
        return [finish(bm, "HF_Vent_Louvre")]

    def hatch_round():
        bm = new_bm()
        cyl(bm, 0.05, 0.004, 32, Matrix.Translation((0, 0, 0.002)))
        cyl(bm, 0.042, 0.006, 32, Matrix.Translation((0, 0, 0.005)))
        for k in range(6):
            a = k * math.pi / 3.0
            cyl(bm, 0.004, 0.004, 6,
                Matrix.Translation((0.046 * math.cos(a), 0.046 * math.sin(a),
                                    0.005)))
        return [finish(bm, "HF_Hatch_Round")]

    def socket_port():
        # A recessed port: made to be used as a boolean cutter INSERT.
        bm = new_bm()
        box(bm, 0.045, 0.03, 0.02, (0, 0, -0.008))
        box(bm, 0.052, 0.037, 0.004, (0, 0, 0.002))
        return [finish(bm, "HF_Socket_Port")]

    def pipe_clamp():
        bm = new_bm()
        for sign in (-1, 1):
            box(bm, 0.008, 0.03, 0.022, (sign * 0.026, 0, 0))
        cyl(bm, 0.026, 0.016, 24,
            Matrix.Rotation(math.pi / 2.0, 4, 'X'))
        cyl(bm, 0.021, 0.02, 24,
            Matrix.Rotation(math.pi / 2.0, 4, 'X'))
        return [finish(bm, "HF_Pipe_Clamp")]

    def heatsink():
        bm = new_bm()
        box(bm, 0.09, 0.06, 0.006, (0, 0, -0.003))
        for i in range(9):
            x = -0.04 + i * 0.01
            box(bm, 0.004, 0.056, 0.028, (x, 0, 0.014))
        return [finish(bm, "HF_Heatsink")]

    def greeble_cluster():
        bm = new_bm()
        box(bm, 0.07, 0.05, 0.008, (0, 0, 0.004))
        box(bm, 0.03, 0.022, 0.014, (-0.016, 0.01, 0.015))
        box(bm, 0.018, 0.03, 0.02, (0.018, -0.006, 0.018))
        cyl(bm, 0.008, 0.016, 12, Matrix.Translation((0.016, 0.016, 0.016)))
        cone(bm, 0.009, 0.004, 0.012,
             12, Matrix.Translation((-0.02, -0.014, 0.014)))
        return [finish(bm, "HF_Greeble_Cluster")]

    parts = (
        ("bolt_m8", bolt_m8),
        ("nut_m8", washer_nut),
        ("vent_louvre", vent_louvre),
        ("hatch_round", hatch_round),
        ("socket_port", socket_port),
        ("pipe_clamp", pipe_clamp),
        ("heatsink", heatsink),
        ("greeble_cluster", greeble_cluster),
    )
    made = []
    for fname, fn in parts:
        objects = fn()
        path = os.path.join(out_dir, fname + ".blend")
        # Link to the scene so the written .blend opens with the part visible,
        # then write just these datablocks (fake_user so they survive the load).
        for ob in objects:
            bpy.context.collection.objects.link(ob)
        blocks = set(objects) | {ob.data for ob in objects}
        bpy.data.libraries.write(path, blocks, fake_user=True, compress=True)
        for ob in objects:
            bpy.data.objects.remove(ob, do_unlink=True)
        made.append(path)
        print("  insert", fname)
    return made


# --------------------------------------------------------------------------

def main(argv):
    want_assets = "all" in argv or "assets" in argv
    print("Hardflow starter library ->", LIB)
    made = []
    made += build_decals(os.path.join(LIB, "decals"))
    made += build_trim_sheet(os.path.join(LIB, "trims"))
    if want_assets:
        made += build_assets(os.path.join(LIB, "assets"))
    total = sum(os.path.getsize(p) for p in made if os.path.isfile(p))
    print("%d file(s), %.1f KB total" % (len(made), total / 1024.0))


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    main(args)
