# GPU drawing over the viewport and blf text HUD.
import math

import gpu
import blf
from gpu_extras.batch import batch_for_shader

# Created lazily on first draw. gpu.shader.from_builtin() raises a SystemError
# in --background mode (no GPU), and doing it at import time would break headless
# import of the whole add-on (e.g. tests/test_blender.py). Drawing only happens
# in a real viewport, where the GPU module is always available.
_shader = None
_image_shader = None


def _get_shader():
    global _shader
    if _shader is None:
        _shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _shader


def _get_image_shader():
    global _image_shader
    if _image_shader is None:
        _image_shader = gpu.shader.from_builtin('IMAGE')
    return _image_shader


def draw_image(texture, x, y, w, h):
    """Draw a GPU texture as a screen-space quad at (x, y) with size (w, h) --
    the trim-sheet canvas behind the region overlay. `texture` is a GPUTexture
    (build it once with gpu.texture.from_image(image), not per-frame). Two TRIS
    (TRI_FAN is deprecated); the IMAGE builtin takes 2D `pos` + `texCoord`."""
    pos = [(x, y), (x + w, y), (x + w, y + h),
           (x, y), (x + w, y + h), (x, y + h)]
    uv = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0),
          (0.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    gpu.state.blend_set('ALPHA')
    shader = _get_image_shader()
    batch = batch_for_shader(shader, 'TRIS', {"pos": pos, "texCoord": uv})
    shader.bind()
    shader.uniform_sampler("image", texture)
    batch.draw(shader)
    gpu.state.blend_set('NONE')

# Snap-marker colors shared by every draw tool (kind -> RGBA) so the cursor hint
# means the same thing everywhere: yellow vertex, green midpoint, blue edge,
# orange surface/face, grey grid.
SNAP_COLORS = {
    'VERT':    (1.0, 0.9, 0.2, 1.0),   # vertex
    'MID':     (0.3, 1.0, 0.4, 1.0),   # edge midpoint
    'EDGE':    (0.3, 0.9, 1.0, 1.0),   # on edge
    'FACE':    (1.0, 0.6, 0.2, 1.0),   # surface / face
    'GRID':    (0.7, 0.7, 0.7, 1.0),   # grid
}


def _draw_lines(points, color, primitive='LINE_STRIP', width=2.0):
    if len(points) < 2:
        return
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(width)
    # The UNIFORM_COLOR shader expects vec3 for pos (2D_UNIFORM_COLOR removed);
    # lift screen-space 2D points to 3D with z=0.
    coords = [(p[0], p[1], 0.0) for p in points]
    shader = _get_shader()
    batch = batch_for_shader(shader, primitive, {"pos": coords})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')


def draw_grid(grid_verts, color):
    _draw_lines(grid_verts, color, primitive='LINES', width=1.0)


def draw_shape(points, line_color, closed=True, width=2.0):
    if len(points) < 2:
        # if there is a single point, no need to draw a small marker
        return
    pts = list(points)
    if closed and len(pts) >= 3:
        pts = pts + [pts[0]]
    _draw_lines(pts, line_color, primitive='LINE_STRIP', width=width)


def draw_points(points, color, size=6.0):
    if not points:
        return
    gpu.state.blend_set('ALPHA')
    gpu.state.point_size_set(size)
    coords = [(p[0], p[1], 0.0) for p in points]
    shader = _get_shader()
    batch = batch_for_shader(shader, 'POINTS', {"pos": coords})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.point_size_set(1.0)
    gpu.state.blend_set('NONE')


def draw_face_fill(points, color):
    """Filled convex/star polygon from screen points, as a triangle fan built
    around the centroid (TRIS -- LINE_LOOP/TRI_FAN are deprecated). Used to
    highlight the face under the cursor in Push/Pull and Offset."""
    if len(points) < 3:
        return
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    verts = []
    n = len(points)
    for i in range(n):
        a = points[i]
        b = points[(i + 1) % n]
        verts.append((cx, cy, 0.0))
        verts.append((a[0], a[1], 0.0))
        verts.append((b[0], b[1], 0.0))
    gpu.state.blend_set('ALPHA')
    shader = _get_shader()
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set('NONE')


def _draw_rect(x, y, w, h, color):
    """Filled rectangle (two triangles) -- for the HUD background."""
    gpu.state.blend_set('ALPHA')
    verts = [(x, y, 0.0), (x + w, y, 0.0), (x + w, y + h, 0.0),
             (x, y, 0.0), (x + w, y + h, 0.0), (x, y + h, 0.0)]
    shader = _get_shader()
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set('NONE')


def draw_rect_fill(x, y, w, h, color):
    """Public filled rectangle -- a colored panel/backdrop (e.g. behind the trim
    editor canvas). Thin wrapper over the HUD's internal fill."""
    _draw_rect(x, y, w, h, color)


def draw_rect_outline(x, y, w, h, color, width=1.0):
    """A 1px (or `width`) border rectangle -- the HUD panel frame + guide boxes.
    Uses a LINE_STRIP loop (LINE_LOOP is deprecated)."""
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(width)
    pts = [(x, y, 0.0), (x + w, y, 0.0), (x + w, y + h, 0.0),
           (x, y + h, 0.0), (x, y, 0.0)]
    shader = _get_shader()
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": pts})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')


def fade_color(color, factor):
    """Scale an RGBA color's alpha by `factor` (clamped 0..1) -- the primitive
    behind translucent guides and fade-in overlays. Returns a new 4-tuple; a
    3-tuple color is treated as fully opaque first."""
    f = 0.0 if factor < 0.0 else 1.0 if factor > 1.0 else factor
    r, g, b, a = (tuple(color) + (1.0,))[:4]
    return (r, g, b, a * f)


def draw_guide_line(p1, p2, color, width=1.5):
    """A solid translucent guide segment between two screen points -- a snapped
    axis / cut-direction hint."""
    _draw_lines([p1, p2], color, primitive='LINE_STRIP', width=width)


def draw_dashed_line(p1, p2, color, dash=12.0, gap=7.0, width=1.5):
    """A dashed 2D screen segment from p1 to p2 -- the guide-line look for snap
    axes and mirror lines. No-op for a zero-length segment."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return
    ux, uy = dx / length, dy / length
    segs = []
    d = 0.0
    while d < length:
        a, b = d, min(length, d + dash)
        segs.append((p1[0] + ux * a, p1[1] + uy * a, 0.0))
        segs.append((p1[0] + ux * b, p1[1] + uy * b, 0.0))
        d += dash + gap
    if len(segs) < 2:
        return
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(width)
    shader = _get_shader()
    batch = batch_for_shader(shader, 'LINES', {"pos": segs})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')


def draw_snap_ring(center, radius, color, segments=20, width=1.5):
    """A small ring around a snapped screen point -- a softer, premium snap
    marker. Drawn as a closed polyline circle."""
    pts = [(center[0] + radius * math.cos(t), center[1] + radius * math.sin(t))
           for t in [i * math.tau / segments for i in range(segments)]]
    _draw_lines(pts + [pts[0]], color, primitive='LINE_STRIP', width=width)


def draw_mirror_plane(quad, fill_color, line_color=None):
    """A translucent filled quad (+ optional outline) for a mirror / cut-plane
    hint. `quad` is 3+ screen points in order; skipped when degenerate."""
    if len(quad) < 3:
        return
    draw_face_fill(quad, fill_color)
    if line_color is not None:
        draw_shape(list(quad), line_color, closed=True, width=1.5)


# Default text color, HUD background, border and accent (the brand blue, matching
# the default line_color). The accent + border lift the HUD from a bare black box
# to a framed panel every tool shares.
_HUD_TEXT = (0.92, 0.92, 0.92, 1.0)
_HUD_BG = (0.03, 0.03, 0.05, 0.72)
_HUD_BORDER = (1.0, 1.0, 1.0, 0.14)
_HUD_ACCENT = (0.15, 0.8, 1.0, 1.0)


def draw_text(x, y, text, color=_HUD_TEXT, size=13):
    """A single blf label at screen (x, y) -- used for per-region names in the
    trim editor. Kept tiny so callers don't touch blf directly."""
    font_id = 0
    blf.size(font_id, size)
    blf.color(font_id, *(tuple(color) + (1.0,))[:4])
    blf.position(font_id, x, y, 0)
    blf.draw(font_id, text)


def draw_hud(region, lines, color=_HUD_TEXT, title=None, accent=None):
    """Multi-line status text in the bottom left, over a framed background panel
    (fill + subtle border). When `title` is given, a header row is drawn with a
    short accent bar and the title in `accent` (defaulting to the brand blue) --
    a consistent, premium HUD frame every tool gets for free.

    `lines` items can be either a plain str or a (text, rgba) pair; a line given
    as a pair is drawn in its own color (e.g. to highlight the measurement
    line)."""
    if not lines and not title:
        return
    font_id = 0
    size = 14
    title_size = 13
    pad = 12        # panel padding
    line_h = 24     # line height
    header_h = (title_size + 10) if title else 0
    margin = 16     # distance from the screen edge
    accent = tuple(accent) if accent is not None else _HUD_ACCENT

    blf.size(font_id, size)
    texts = [ln[0] if isinstance(ln, tuple) else ln for ln in lines]
    widths = [blf.dimensions(font_id, t)[0] for t in texts]
    if title:
        blf.size(font_id, title_size)
        widths.append(blf.dimensions(font_id, title)[0] + 14)  # room for the bar
        blf.size(font_id, size)
    box_w = (max(widths) if widths else 0) + pad * 2
    box_h = line_h * len(lines) + pad * 2 + header_h

    x0, y0 = margin, margin
    _draw_rect(x0, y0, box_w, box_h, _HUD_BG)
    draw_rect_outline(x0, y0, box_w, box_h, _HUD_BORDER)

    ty = y0 + box_h - pad
    if title:
        bar_h = title_size
        _draw_rect(x0 + pad, ty - bar_h, 3, bar_h, accent)     # left accent bar
        blf.size(font_id, title_size)
        blf.color(font_id, *accent)
        blf.position(font_id, x0 + pad + 10, ty - bar_h + 1, 0)
        blf.draw(font_id, title)
        blf.size(font_id, size)
        ty -= header_h

    # Draw top to bottom (lines[0] just under the header).
    tx = x0 + pad
    ty -= size
    for ln in lines:
        text, col = ln if isinstance(ln, tuple) else (ln, color)
        blf.color(font_id, *col)
        blf.position(font_id, tx, ty, 0)
        blf.draw(font_id, text)
        ty -= line_h
