# Boru/profil cizim operatoru: bir cizgi ciz, yuvarlak kesitli boruya cevir.
# Grid Modeler "pipes" akisinin sade hali.
#
# Kisayollar (modal): sol tik nokta, Enter olustur, Backspace geri al,
#                     sag tik / Esc iptal, orta tik / tekerlek navigasyon.
import bpy
from bpy.types import Operator

from ..core import raycast, geometry
from ..preferences import get_prefs
from ..ui import draw as hud


class HARDFLOW_OT_pipe(Operator):
    bl_idname = "mesh.hardflow_pipe"
    bl_label = "Hardflow Pipe"
    bl_description = "Bir çizgi çiz, yuvarlak kesitli boruya çevir"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "View3D icinde calistir")
            return {'CANCELLED'}
        # Duzlemi invoke aninda sabitle (kullanici orbit etse de tutarli kalsin).
        rv3d = context.region_data
        obj = context.active_object
        self._origin = (obj.matrix_world.translation if obj is not None
                        else context.scene.cursor.location.copy())
        self._normal = raycast.view_direction(rv3d)
        self._pts = []            # onaylanmis 3D noktalar
        self._cursor3d = None     # anlik 3D nokta

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        context.area.tag_redraw()
        region, rv3d = context.region, context.region_data

        if event.type == 'MOUSEMOVE':
            self._cursor3d = raycast.ray_to_plane(
                region, rv3d, (event.mouse_region_x, event.mouse_region_y),
                self._origin, self._normal)

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if self._cursor3d is not None:
                self._pts.append(self._cursor3d.copy())

        elif event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            if len(self._pts) >= 2:
                return self._commit(context)

        elif event.type == 'BACK_SPACE' and event.value == 'PRESS':
            if self._pts:
                self._pts.pop()

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._cleanup(context)
            return {'CANCELLED'}

        elif event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
                            'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def _screen_points(self, context):
        region, rv3d = context.region, context.region_data
        pts3d = list(self._pts)
        if self._cursor3d is not None:
            pts3d = pts3d + [self._cursor3d]
        out = []
        for p in pts3d:
            s = raycast.world_to_screen(region, rv3d, p)
            if s is not None:
                out.append((s[0], s[1]))
        return out

    def _draw_px(self, context):
        prefs = get_prefs(context)
        hud.draw_shape(self._screen_points(context),
                       tuple(prefs.line_color), closed=False)
        hud.draw_points([s for s in self._screen_points(context)][:len(self._pts)],
                        tuple(prefs.line_color))
        hud.draw_hud(context.region, [
            "Pipe — sol tık nokta · Enter oluştur · Backspace geri · Esc iptal",
            "Yarıçap: %.3f m (tercihlerden ayarla)" % prefs.pipe_radius,
        ])

    def _commit(self, context):
        prefs = get_prefs(context)
        try:
            curve = geometry.build_pipe(self._pts, radius=prefs.pipe_radius)
            if curve is not None:
                obj = bpy.data.objects.new("Hardflow_Pipe", curve)
                context.collection.objects.link(obj)
                for o in list(context.selected_objects):
                    o.select_set(False)
                obj.select_set(True)
                context.view_layer.objects.active = obj
        except Exception as ex:  # noqa: BLE001
            self.report({'ERROR'}, f"Hardflow Pipe: {ex}")
        self._cleanup(context)
        return {'FINISHED'}

    def _cleanup(self, context):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        context.area.tag_redraw()
