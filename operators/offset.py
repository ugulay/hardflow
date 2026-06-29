# Offset: pick a face, drag to inset its border inward by a measured thickness
# (SketchUp's Offset tool). Grid-snapped, with numeric entry; click again or
# Enter to apply.
#
# Object Mode, active mesh. Like Push/Pull the face index comes from a raycast,
# so generative modifiers that change the face count are not supported.
import bpy
from bpy.types import Operator
from mathutils import Vector

from ..core import raycast, geometry, grid
from ..preferences import get_prefs
from ..ui import draw as hud


_HOVER_FILL = (0.15, 0.8, 1.0, 0.18)
_LOCK_FILL = (0.2, 1.0, 0.5, 0.20)


class HARDFLOW_OT_offset(Operator):
    bl_idname = "mesh.hardflow_offset"
    bl_label = "Hardflow Offset"
    bl_description = "Inset a face's border inward by a measured distance (SketchUp Offset)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Run inside View3D")
            return {'CANCELLED'}
        self.obj = context.active_object
        self.snap = get_prefs(context).snap_enabled
        self.face_index = -1
        self.locked = False
        self.plane_co = None      # world face center (the inset's plane)
        self.plane_no = None      # world face normal
        self.pick0 = None         # world point where the drag started
        self.thickness = 0.0
        self.typed = ""

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        context.area.tag_redraw()
        co = (event.mouse_region_x, event.mouse_region_y)

        if event.type == 'MOUSEMOVE':
            if self.locked:
                self._update_thickness(context, co)
            else:
                self._hover_face(context, co)

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if not self.locked:
                if self.face_index >= 0:
                    self._lock_face(context, co)
            else:
                return self._commit(context)

        elif (event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS'
              and self.locked):
            return self._commit(context)

        elif event.type == 'X' and event.value == 'PRESS':
            self.snap = not self.snap

        elif self.locked and event.value == 'PRESS' and self._edit_typed(event):
            pass

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._cleanup(context)
            return {'CANCELLED'}

        elif event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
                            'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    # --- picking / dragging ---------------------------------------------

    def _hover_face(self, context, co):
        from bpy_extras import view3d_utils
        region, rv3d = context.region, context.region_data
        v = Vector((co[0], co[1]))
        ray_dir = view3d_utils.region_2d_to_vector_3d(region, rv3d, v)
        ray_o = view3d_utils.region_2d_to_origin_3d(region, rv3d, v)
        mw_inv = self.obj.matrix_world.inverted()
        ok, _loc, _nrm, index = self.obj.ray_cast(
            mw_inv @ ray_o, mw_inv.to_3x3() @ ray_dir)
        # Clamp the evaluated-mesh index to the base mesh range (see push_pull).
        self.face_index = index if (ok and index < len(self.obj.data.polygons)) \
            else -1

    def _lock_face(self, context, co):
        poly = self.obj.data.polygons[self.face_index]
        mw = self.obj.matrix_world
        self.plane_co = mw @ poly.center
        self.plane_no = (mw.to_3x3() @ poly.normal).normalized()
        region, rv3d = context.region, context.region_data
        self.pick0 = raycast.ray_to_plane(region, rv3d, co,
                                          self.plane_co, self.plane_no)
        self.thickness = 0.0
        self.typed = ""
        self.locked = True

    def _update_thickness(self, context, co):
        region, rv3d = context.region, context.region_data
        p = raycast.ray_to_plane(region, rv3d, co, self.plane_co, self.plane_no)
        if p is None or self.pick0 is None:
            return
        d = (p - self.pick0).length
        self.thickness = grid.snap_scalar(d, get_prefs(context).grid_world,
                                          self.snap)
        self.typed = ""

    def _edit_typed(self, event):
        digits = {'ZERO': '0', 'ONE': '1', 'TWO': '2', 'THREE': '3',
                  'FOUR': '4', 'FIVE': '5', 'SIX': '6', 'SEVEN': '7',
                  'EIGHT': '8', 'NINE': '9',
                  'NUMPAD_0': '0', 'NUMPAD_1': '1', 'NUMPAD_2': '2',
                  'NUMPAD_3': '3', 'NUMPAD_4': '4', 'NUMPAD_5': '5',
                  'NUMPAD_6': '6', 'NUMPAD_7': '7', 'NUMPAD_8': '8',
                  'NUMPAD_9': '9'}
        if event.type in digits:
            self.typed += digits[event.type]
        elif event.type in {'PERIOD', 'NUMPAD_PERIOD'} and '.' not in self.typed:
            self.typed += '.'
        elif event.type == 'BACK_SPACE':
            self.typed = self.typed[:-1]
        else:
            return False
        try:
            self.thickness = max(0.0, float(self.typed))
        except ValueError:
            pass
        return True

    # --- visual feedback -------------------------------------------------

    def _face_screen_points(self, context):
        if self.face_index < 0:
            return []
        poly = self.obj.data.polygons[self.face_index]
        mw = self.obj.matrix_world
        region, rv3d = context.region, context.region_data
        verts = self.obj.data.vertices
        pts = []
        for vi in poly.vertices:
            s = raycast.world_to_screen(region, rv3d, mw @ verts[vi].co)
            if s is None:
                return []
            pts.append((s[0], s[1]))
        return pts

    def _draw_px(self, context):
        prefs = get_prefs(context)
        pts = self._face_screen_points(context)
        if pts:
            fill = _LOCK_FILL if self.locked else _HOVER_FILL
            hud.draw_face_fill(pts, fill)
            hud.draw_shape(pts, tuple(prefs.line_color), closed=True)

        accent = tuple(prefs.line_color)[:3] + (1.0,)
        dim = (0.72, 0.72, 0.72, 1.0)
        if not self.locked:
            top = ("Hover a face, then click to offset", accent)
        else:
            typed = ("  [typing %s]" % self.typed) if self.typed else ""
            top = ("Thickness:  %.3f m%s" % (self.thickness, typed), accent)
        lines = [
            top,
            ("Click face = lock    drag / type number = thickness    "
             "X snap %s" % ('ON' if self.snap else 'OFF'), dim),
            ("Enter / click apply    Esc cancel", dim),
        ]
        hud.draw_hud(context.region, lines)

    # --- apply -----------------------------------------------------------

    def _commit(self, context):
        if self.thickness > 1e-6:
            try:
                ok = geometry.inset_faces(self.obj, [self.face_index],
                                          self.thickness)
                if not ok:
                    self.report({'WARNING'}, "Offset failed (no face)")
            except Exception as ex:
                self.report({'ERROR'}, f"Hardflow: {ex}")
        self._cleanup(context)
        return {'FINISHED'}

    def _cleanup(self, context):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        context.area.tag_redraw()
