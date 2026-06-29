# GPU drawing over the viewport and blf text HUD.
import gpu
import blf
from gpu_extras.batch import batch_for_shader

_shader = gpu.shader.from_builtin('UNIFORM_COLOR')

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
    batch = batch_for_shader(_shader, primitive, {"pos": coords})
    _shader.bind()
    _shader.uniform_float("color", color)
    batch.draw(_shader)
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
    batch = batch_for_shader(_shader, 'POINTS', {"pos": coords})
    _shader.bind()
    _shader.uniform_float("color", color)
    batch.draw(_shader)
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
    batch = batch_for_shader(_shader, 'TRIS', {"pos": verts})
    _shader.bind()
    _shader.uniform_float("color", color)
    batch.draw(_shader)
    gpu.state.blend_set('NONE')


def _draw_rect(x, y, w, h, color):
    """Filled rectangle (two triangles) -- for the HUD background."""
    gpu.state.blend_set('ALPHA')
    verts = [(x, y, 0.0), (x + w, y, 0.0), (x + w, y + h, 0.0),
             (x, y, 0.0), (x + w, y + h, 0.0), (x, y + h, 0.0)]
    batch = batch_for_shader(_shader, 'TRIS', {"pos": verts})
    _shader.bind()
    _shader.uniform_float("color", color)
    batch.draw(_shader)
    gpu.state.blend_set('NONE')


# Default text color and HUD background color.
_HUD_TEXT = (0.92, 0.92, 0.92, 1.0)
_HUD_BG = (0.0, 0.0, 0.0, 0.55)


def draw_hud(region, lines, color=_HUD_TEXT):
    """Multi-line status text in the bottom left; with a background panel for
    readability.

    `lines` items can be either a plain str or a (text, rgba) pair; a line given
    as a pair is drawn in its own color (e.g. to highlight the measurement
    line)."""
    if not lines:
        return
    font_id = 0
    size = 14
    pad = 12        # panel padding
    line_h = 24     # line height
    margin = 16     # distance from the screen edge

    blf.size(font_id, size)

    # Panel width based on the widest line.
    texts = [ln[0] if isinstance(ln, tuple) else ln for ln in lines]
    box_w = max(blf.dimensions(font_id, t)[0] for t in texts) + pad * 2
    box_h = line_h * len(lines) + pad * 2

    x0, y0 = margin, margin
    _draw_rect(x0, y0, box_w, box_h, _HUD_BG)

    # Draw top to bottom (lines[0] at the top).
    tx = x0 + pad
    ty = y0 + box_h - pad - size
    for ln in lines:
        text, col = ln if isinstance(ln, tuple) else (ln, color)
        blf.color(font_id, *col)
        blf.position(font_id, tx, ty, 0)
        blf.draw(font_id, text)
        ty -= line_h
