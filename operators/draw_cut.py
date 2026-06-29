# Ana cizim operatoru: ekrana sekil ciz, 3D'ye yansit, boolean uygula.
#
# SHAPE: BOX / CIRCLE / POLY      MODE: CUT / SLICE / MAKE
# Kisayollar (modal icinde):
#   Sol tik   nokta koy / sekli baslat-bitir
#   Enter     POLY'yi kapat ve uygula
#   Backspace son POLY noktasini sil
#   Q/W/E     shape = BOX / CIRCLE / POLY
#   1/2/3     mode  = CUT / SLICE / MAKE
#   X         snap ac/kapat
#   Sag tik / ESC  iptal
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty
from mathutils import Vector

from ..core import raycast, geometry, boolean, grid
from ..preferences import get_prefs
from ..ui import draw as hud


_SHAPES = [
    ('BOX', "Box", "Dikdortgen"),
    ('CIRCLE', "Circle", "Cember"),
    ('POLY', "Polygon", "Serbest cokgen"),
]
_MODES = [
    ('CUT', "Cut", "Boolean DIFFERENCE"),
    ('SLICE', "Slice", "Nesneyi ikiye bol"),
    ('MAKE', "Make", "Geometri ekle (UNION)"),
]


class HARDFLOW_OT_draw(Operator):
    bl_idname = "mesh.hardflow_draw"
    bl_label = "Hardflow Draw"
    bl_options = {'REGISTER', 'UNDO'}

    shape: EnumProperty(name="Shape", items=_SHAPES, default='BOX')
    mode: EnumProperty(name="Mode", items=_MODES, default='CUT')

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "View3D icinde calistir")
            return {'CANCELLED'}

        prefs = get_prefs(context)
        self.snap = prefs.snap_enabled
        self.points = []          # onaylanmis ekran noktalari
        self.cursor = (0, 0)      # anlik (snapli) fare noktasi
        self.committing = False

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    # --- olay dongusu ----------------------------------------------------

    def modal(self, context, event):
        context.area.tag_redraw()
        prefs = get_prefs(context)

        if event.type == 'MOUSEMOVE':
            self.cursor = grid.snap_point(
                (event.mouse_region_x, event.mouse_region_y),
                prefs.grid_size, self.snap)

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            p = self.cursor
            if self.shape == 'POLY':
                self.points.append(p)
            else:  # BOX / CIRCLE: iki tik
                if not self.points:
                    self.points.append(p)
                else:
                    self.points.append(p)
                    return self._commit(context)

        elif event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            if self.shape == 'POLY' and len(self.points) >= 3:
                return self._commit(context)

        elif event.type == 'BACK_SPACE' and event.value == 'PRESS':
            if self.points:
                self.points.pop()

        elif event.type in {'Q', 'W', 'E'} and event.value == 'PRESS':
            self.shape = {'Q': 'BOX', 'W': 'CIRCLE', 'E': 'POLY'}[event.type]
            self.points = []

        elif event.type in {'ONE', 'TWO', 'THREE'} and event.value == 'PRESS':
            self.mode = {'ONE': 'CUT', 'TWO': 'SLICE', 'THREE': 'MAKE'}[event.type]

        elif event.type == 'X' and event.value == 'PRESS':
            self.snap = not self.snap

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._cleanup(context)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    # --- gorsel geri bildirim -------------------------------------------

    def _shape_screen_points(self):
        if self.shape == 'POLY':
            pts = list(self.points)
            if pts:
                pts = pts + [self.cursor]
            return pts
        if not self.points:
            return []
        a = self.points[0]
        b = self.points[1] if len(self.points) > 1 else self.cursor
        if self.shape == 'BOX':
            return grid.box_points(a, b)
        if self.shape == 'CIRCLE':
            return grid.circle_points(a, b)
        return []

    def _draw_px(self, context):
        prefs = get_prefs(context)
        region = context.region

        if self.snap:
            hud.draw_grid(grid.grid_lines(region, prefs.grid_size, True),
                          tuple(prefs.grid_color))

        pts = self._shape_screen_points()
        closed = self.shape != 'POLY' or len(self.points) >= 2
        hud.draw_shape(pts, tuple(prefs.line_color), closed=closed)
        hud.draw_points(self.points, tuple(prefs.line_color))

        hud.draw_hud(region, [
            f"Shape: {self.shape}   Mode: {self.mode}   Snap: {'ON' if self.snap else 'OFF'}",
            "Q/W/E shape   1/2/3 mode   X snap   Enter apply   Esc cancel",
        ])

    # --- geometri uygulama ----------------------------------------------

    def _commit(self, context):
        try:
            self._build_and_apply(context)
        except Exception as ex:  # cizim modunu temiz kapat
            self.report({'ERROR'}, f"Hardflow: {ex}")
        self._cleanup(context)
        return {'FINISHED'}

    def _build_and_apply(self, context):
        region = context.region
        rv3d = context.region_data
        target = context.active_object
        prefs = get_prefs(context)

        screen_pts = self._shape_screen_points()
        if len(screen_pts) < 3:
            return

        plane_co = target.matrix_world.translation
        corners = [raycast.screen_to_plane(region, rv3d, p, plane_co)
                   for p in screen_pts]
        view_dir = raycast.view_direction(rv3d)
        thickness = geometry.estimate_thickness(target)

        cutter_mesh = geometry.build_prism(corners, view_dir, thickness)
        if cutter_mesh is None:
            self.report({'WARNING'}, "Gecersiz sekil")
            return
        cutter = bpy.data.objects.new("hf_cutter", cutter_mesh)
        context.collection.objects.link(cutter)

        solver = prefs.default_solver
        if self.mode == 'CUT':
            boolean.apply_boolean(context, target, cutter, 'DIFFERENCE', solver)
        elif self.mode == 'MAKE':
            boolean.apply_boolean(context, target, cutter, 'UNION', solver)
        elif self.mode == 'SLICE':
            other = boolean.duplicate_object(context, target)
            boolean.apply_boolean(context, target, cutter, 'DIFFERENCE', solver)
            boolean.apply_boolean(context, other, cutter, 'INTERSECT', solver)

        bpy.data.objects.remove(cutter, do_unlink=True)

    def _cleanup(self, context):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        context.area.tag_redraw()
