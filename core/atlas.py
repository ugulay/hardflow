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
