# Viewport ustu GPU cizimi ve blf metin HUD'u.
import gpu
import blf
from gpu_extras.batch import batch_for_shader

_shader = gpu.shader.from_builtin('UNIFORM_COLOR')


def _draw_lines(points, color, primitive='LINE_STRIP', width=2.0):
    if len(points) < 2:
        return
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(width)
    # UNIFORM_COLOR shader'i pos icin vec3 bekler (2D_UNIFORM_COLOR kaldirildi);
    # ekran-uzayi 2D noktalari z=0 ile 3D'ye tasi.
    coords = [(p[0], p[1], 0.0) for p in points]
    batch = batch_for_shader(_shader, primitive, {"pos": coords})
    _shader.bind()
    _shader.uniform_float("color", color)
    batch.draw(_shader)
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')


def draw_grid(grid_verts, color):
    _draw_lines(grid_verts, color, primitive='LINES', width=1.0)


def draw_shape(points, line_color, closed=True):
    if len(points) < 2:
        # tek nokta varsa kucuk bir isaret cizmeye gerek yok
        return
    pts = list(points)
    if closed and len(pts) >= 3:
        pts = pts + [pts[0]]
    _draw_lines(pts, line_color, primitive='LINE_STRIP', width=2.0)


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


def draw_hud(region, lines, color=(1.0, 1.0, 1.0, 0.9)):
    """Sol altta cok satirli durum metni."""
    font_id = 0
    blf.color(font_id, *color)
    blf.size(font_id, 13)
    x = 18
    y = 18 + (len(lines) - 1) * 18
    for text in lines:
        blf.position(font_id, x, y, 0)
        blf.draw(font_id, text)
        y -= 18
