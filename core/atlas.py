# Pure UV-rectangle math for v0.9 decal trim sheets and atlasing. A trim sheet is
# one image sliced into a grid of cells; atlasing packs many images into one. No
# bpy here -- only arithmetic -- so it is unit-tested without Blender (mirrors
# core/decal_math.py and core/decal_image.py). The bpy side (building the UV'd
# quad, baking the atlas) lives in core/decal.py and the operators.
#
# UV convention: the unit square is [0,1]^2 with v=0 at the BOTTOM (Blender's UV
# space). Pixel rects, by contrast, count y downward from the top (image space);
# rect_to_uv flips between the two.


def slice_grid(cols, rows):
    """Slice the unit UV square into a cols x rows grid, returning each cell as a
    (u0, v0, u1, v1) rect in reading order: left-to-right, top-to-bottom. Because
    v grows upward, the first row sits at the top of the sheet (high v)."""
    cols = max(1, int(cols))
    rows = max(1, int(rows))
    dw = 1.0 / cols
    dh = 1.0 / rows
    out = []
    for r in range(rows):
        v1 = 1.0 - r * dh
        v0 = v1 - dh
        for c in range(cols):
            u0 = c * dw
            out.append((u0, v0, u0 + dw, v1))
    return out


def cell_rect(cols, rows, index):
    """The (u0,v0,u1,v1) of one grid cell by reading-order index. The index wraps
    (Python modulo, so negatives count back from the end), so callers can cycle
    freely without bounds-checking."""
    cells = slice_grid(cols, rows)
    return cells[index % len(cells)]


def rect_pixels(rect, sheet_w, sheet_h):
    """Pixel size (w, h) a UV rect covers on a sheet_w x sheet_h image. Feed this
    to core/decal_image.aspect_size so a trim slice is placed without stretching."""
    u0, v0, u1, v1 = rect
    return (abs(u1 - u0) * sheet_w, abs(v1 - v0) * sheet_h)


def next_pow2(n):
    """Smallest power of two >= n (and >= 1). Handy for GPU-friendly atlas sizes."""
    p = 1
    while p < n:
        p *= 2
    return p


def pack_shelves(sizes, max_width):
    """Shelf bin-packing. `sizes` is a list of (w, h) integer pixel sizes; pack
    them into rows ("shelves") no wider than max_width. Returns (placements,
    atlas_w, atlas_h) where placements aligns to the INPUT order, each entry the
    (x, y, w, h) top-left pixel rect of that item.

    Items are packed tallest-first (tighter shelves) but the result is restored
    to input order. If an item is wider than max_width the atlas widens to fit it,
    so packing never overflows."""
    if not sizes:
        return [], 0, 0
    max_width = max(1, int(max_width))
    atlas_w = max(max_width, max(w for w, _h in sizes))
    order = sorted(range(len(sizes)), key=lambda i: (-sizes[i][1], -sizes[i][0]))
    placements = [None] * len(sizes)
    x = y = shelf_h = 0
    for i in order:
        w, h = sizes[i]
        if x + w > atlas_w:          # current shelf is full -> start a new one
            y += shelf_h
            x = 0
            shelf_h = 0
        placements[i] = (x, y, w, h)
        x += w
        shelf_h = max(shelf_h, h)
    atlas_h = y + shelf_h
    return placements, atlas_w, atlas_h


# --- Free-rectangle trim editor (v1.16) --------------------------------------
# The grid helpers above slice the sheet into EQUAL cells. The editor lets the
# user carve arbitrary, unequal rectangles ("regions") anywhere on the sheet --
# UV-style cutting. These helpers are the pure math behind that: hit-testing,
# handle picking, resize/move/split, all in UV space ([0,1]^2, v up). The bpy
# side (the modal editor, the stored region list) lives in operators/trim_editor.

def _clamp01(x):
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def normalize_rect(rect):
    """Order and clamp a rect so u0<=u1, v0<=v1 and every edge sits in [0,1].
    A rect drawn right-to-left or bottom-to-top comes back canonical."""
    u0, v0, u1, v1 = rect
    if u1 < u0:
        u0, u1 = u1, u0
    if v1 < v0:
        v0, v1 = v1, v0
    return (_clamp01(u0), _clamp01(v0), _clamp01(u1), _clamp01(v1))


def rect_area(rect):
    u0, v0, u1, v1 = rect
    return abs(u1 - u0) * abs(v1 - v0)


def rect_contains(rect, u, v):
    """True when (u, v) is inside (or on the border of) a normalized rect."""
    u0, v0, u1, v1 = rect
    return u0 <= u <= u1 and v0 <= v <= v1


def rect_at_point(rects, u, v):
    """Index of the top-most region under a UV point, or -1 when none. Searches
    last-to-first so the most recently drawn (top) region wins overlaps -- the
    click-to-select rule for the editor."""
    for i in range(len(rects) - 1, -1, -1):
        if rect_contains(rects[i], u, v):
            return i
    return -1


def snap_value(x, step):
    """Snap a scalar to the nearest multiple of `step` (0/negative = no snap),
    clamped to [0,1]."""
    if step <= 0.0:
        return _clamp01(x)
    return _clamp01(round(x / step) * step)


def snap_rect(rect, step):
    """Snap all four edges of a rect to the `step` lattice, keeping it canonical."""
    u0, v0, u1, v1 = rect
    return normalize_rect((snap_value(u0, step), snap_value(v0, step),
                           snap_value(u1, step), snap_value(v1, step)))


# Handle codes: 4 corners + 4 edge mid-points. 'MOVE' is the interior (drag the
# whole rect). These name which part of a region a drag grabs.
_CORNERS = ('BL', 'BR', 'TL', 'TR')
_EDGES = ('L', 'R', 'B', 'T')


def rect_handle_points(rect):
    """The eight editor handles of a rect as a name -> (u, v) dict: four corners
    (BL/BR/TL/TR) and four edge mid-points (L/R/B/T)."""
    u0, v0, u1, v1 = rect
    mu, mv = (u0 + u1) * 0.5, (v0 + v1) * 0.5
    return {
        'BL': (u0, v0), 'BR': (u1, v0), 'TL': (u0, v1), 'TR': (u1, v1),
        'L': (u0, mv), 'R': (u1, mv), 'B': (mu, v0), 'T': (mu, v1),
    }


def nearest_handle(rect, u, v, tol):
    """Which handle a cursor grabs: the nearest corner/edge handle within `tol`
    (UV distance), else 'MOVE' when the cursor is inside the rect, else None.
    Corners and edges compete by plain nearest-distance, so the handle the cursor
    is closest to wins."""
    best, best_d = None, tol
    for name, (hu, hv) in rect_handle_points(rect).items():
        d = ((hu - u) ** 2 + (hv - v) ** 2) ** 0.5
        if d <= best_d:
            best, best_d = name, d
    if best is not None:
        return best
    return 'MOVE' if rect_contains(rect, u, v) else None


def resize_rect(rect, handle, u, v):
    """New rect after dragging one edge/corner handle to (u, v). 'MOVE' is a
    no-op here (translation is move_rect's job); an unknown handle is ignored.
    The result is re-normalized, so dragging an edge past its opposite flips
    cleanly instead of inverting."""
    u0, v0, u1, v1 = rect
    if handle in ('BL', 'TL', 'L'):
        u0 = u
    if handle in ('BR', 'TR', 'R'):
        u1 = u
    if handle in ('BL', 'BR', 'B'):
        v0 = v
    if handle in ('TL', 'TR', 'T'):
        v1 = v
    return normalize_rect((u0, v0, u1, v1))


def move_rect(rect, du, dv):
    """Translate a rect by (du, dv), keeping its size and clamping so it stays
    fully inside the unit square (the offset is shortened at the border rather
    than the rect being squashed)."""
    u0, v0, u1, v1 = rect
    u0 += du
    u1 += du
    v0 += dv
    v1 += dv
    if u0 < 0.0:
        u1 -= u0
        u0 = 0.0
    if u1 > 1.0:
        u0 -= (u1 - 1.0)
        u1 = 1.0
    if v0 < 0.0:
        v1 -= v0
        v0 = 0.0
    if v1 > 1.0:
        v0 -= (v1 - 1.0)
        v1 = 1.0
    return normalize_rect((u0, v0, u1, v1))


def guillotine_split(rect, axis, t):
    """Cut a rect in two at fraction `t` (0..1) along an axis: 'U' splits into
    (left, right) at u = u0 + t*width, 'V' into (bottom, top) at v = v0 +
    t*height. `t` is clamped away from the edges so neither piece is degenerate.
    Returns (rect_a, rect_b)."""
    u0, v0, u1, v1 = normalize_rect(rect)
    t = 0.001 if t < 0.001 else 0.999 if t > 0.999 else t
    if axis == 'V':
        vm = v0 + t * (v1 - v0)
        return ((u0, v0, u1, vm), (u0, vm, u1, v1))
    um = u0 + t * (u1 - u0)
    return ((u0, v0, um, v1), (um, v0, u1, v1))


def remap_uv(u, v, slot):
    """Compose a [0,1] UV with a slot rect (u0,v0,u1,v1): map the unit square into
    the slot. Used to retarget a decal's existing UVs (whole image or trim cell)
    onto its slot in a packed atlas, so the composition handles both cases."""
    u0, v0, u1, v1 = slot
    return (u0 + u * (u1 - u0), v0 + v * (v1 - v0))


def blit_pixels(dst, dst_w, dst_h, src, src_w, src_h, x0, y0):
    """Copy an RGBA source pixel block into dst at bottom-left pixel (x0, y0).
    Both buffers are flat float lists in Blender's image layout: 4 floats per
    pixel, row 0 at the BOTTOM, row-major. Pixels outside dst are clipped, so an
    oversized or off-edge source never raises. Mutates and returns dst."""
    for r in range(src_h):
        dy = y0 + r
        if dy < 0 or dy >= dst_h:
            continue
        s_start = (r * src_w) * 4
        if 0 <= x0 and x0 + src_w <= dst_w:
            # fast path: whole row fits -> one slice copy
            di = (dy * dst_w + x0) * 4
            dst[di:di + src_w * 4] = src[s_start:s_start + src_w * 4]
            continue
        for c in range(src_w):           # clipped path: per-pixel
            dx = x0 + c
            if dx < 0 or dx >= dst_w:
                continue
            di = (dy * dst_w + dx) * 4
            si = s_start + c * 4
            dst[di:di + 4] = src[si:si + 4]
    return dst


# --- chroma-key / background removal (v1.17) ---------------------------------
# Knock a solid-colour background (a green screen, a flat matte) out of an image
# by colour, so a sheet of decals shot on one background becomes transparent and
# the individual graphics separate cleanly. Pure pixel arithmetic on Blender's
# flat RGBA float layout (4 floats/pixel, row 0 at the bottom) -- the bpy side
# (reading image.pixels, the operator, the numpy fast path) lives in
# operators/trim_editor.py; this stays unit-testable on plain lists.

def color_distance(a, b):
    """Euclidean distance between two RGB colours (each an (r, g, b) sequence) in
    linear [0, 1] space. 0 = identical; sqrt(3) ~= 1.732 is the maximum (black vs
    white). The metric the chroma key compares each pixel against the key colour."""
    dr = a[0] - b[0]
    dg = a[1] - b[1]
    db = a[2] - b[2]
    return (dr * dr + dg * dg + db * db) ** 0.5


def pixel_rgb(pixels, width, x, y):
    """(r, g, b) of the pixel at column x, row y (row 0 = bottom) in a flat RGBA
    float list. Returns (0, 0, 0) if the coordinate falls outside the buffer, so
    corner-sampling a key colour never raises."""
    x, y, width = int(x), int(y), int(width)
    # Range-check the column/row explicitly: a negative x with y >= 1 still yields
    # a positive flat index that lands on the previous row, so the old
    # `i < 0` guard would silently return a neighbouring pixel instead of black.
    if x < 0 or y < 0 or width <= 0 or x >= width:
        return (0.0, 0.0, 0.0)
    i = (y * width + x) * 4
    if i + 2 >= len(pixels):
        return (0.0, 0.0, 0.0)
    return (pixels[i], pixels[i + 1], pixels[i + 2])


def chroma_key(pixels, key_rgb, tolerance, softness=0.0):
    """Make the background transparent by colour. For every pixel in the flat RGBA
    list `pixels`, measure its RGB distance to `key_rgb`:

      * distance <= `tolerance`               -> alpha driven to 0 (cut out)
      * `tolerance` < distance < tolerance+`softness` (only if softness > 0)
                                              -> alpha faded linearly 0..1 across
                                                 the band (a feathered edge, so
                                                 the cut is not a hard jaggy line)
      * distance >= tolerance+softness         -> alpha left untouched (kept)

    The feather only ever LOWERS alpha (min with the existing value), so a source
    that already has partial transparency is never made more opaque. Mutates
    `pixels` in place and returns the count of fully-cut (alpha 0) pixels -- what
    the operator reports. `key_rgb` is (r, g, b) in the same linear 0..1 space as
    image.pixels. Distances/colours are pure floats; no bpy."""
    kr, kg, kb = key_rgb[0], key_rgb[1], key_rgb[2]
    t = tolerance if tolerance > 0.0 else 0.0
    soft = softness if softness > 0.0 else 0.0
    edge = t + soft
    n = len(pixels)
    count = 0
    i = 0
    while i + 3 < n:
        dr = pixels[i] - kr
        dg = pixels[i + 1] - kg
        db = pixels[i + 2] - kb
        d = (dr * dr + dg * dg + db * db) ** 0.5
        if d <= t:
            pixels[i + 3] = 0.0
            count += 1
        elif soft > 0.0 and d < edge:
            a = (d - t) / soft
            if a < pixels[i + 3]:
                pixels[i + 3] = a
        i += 4
    return count


def rect_to_uv(x, y, w, h, atlas_w, atlas_h):
    """Convert a top-left pixel rect (image space, y down) into a UV rect
    (u0,v0,u1,v1) (Blender space, v up). The top edge of the image is v=1."""
    if atlas_w <= 0 or atlas_h <= 0:
        return (0.0, 0.0, 1.0, 1.0)
    u0 = x / atlas_w
    u1 = (x + w) / atlas_w
    v1 = 1.0 - y / atlas_h
    v0 = 1.0 - (y + h) / atlas_h
    return (u0, v0, u1, v1)
