# Decal placement + management (DECALmachine spirit).
#
# HARDFLOW_OT_place_decal: a modal tool. The mouse ray is cast into the scene;
# the decal previews on whatever surface is under the cursor, aligned to the hit
# normal. The mouse wheel scales, [ / ] roll the decal around the normal, left
# click places it. The placed decal adheres via a SHRINKWRAP (PROJECT) modifier
# and is parented to the hit object (see core/decal.py).
import math

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, FloatProperty, IntProperty, StringProperty

from ..core import raycast, decal, decal_math
from ..preferences import get_prefs
from ..ui import draw as hud


class HARDFLOW_OT_place_decal(Operator):
    bl_idname = "object.hardflow_place_decal"
    bl_label = "Place Decal"
    bl_description = ("Stick a decal onto the surface under the cursor "
                      "(wheel = scale, [ / ] = roll, click = place)")
    bl_options = {'REGISTER', 'UNDO'}

    decal_type: EnumProperty(name="Type", items=decal.DECAL_TYPES, default='INFO')
    size: FloatProperty(name="Size (m)", default=0.2, min=0.001, soft_max=5.0)
    roll: FloatProperty(name="Roll (rad)", default=0.0)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Run inside View3D")
            return {'CANCELLED'}
        prefs = get_prefs(context)
        self.size = prefs.decal_size
        self.roll = 0.0
        self._hit = None          # (location, normal, object)
        self._screen = None       # cursor screen pos for the HUD marker

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        context.area.tag_redraw()
        region, rv3d = context.region, context.region_data

        if event.type == 'MOUSEMOVE':
            self._screen = (event.mouse_region_x, event.mouse_region_y)
            self._hit = raycast.ray_cast_surface(context, region, rv3d, self._screen)

        elif event.type in {'WHEELUPMOUSE'} and event.value == 'PRESS':
            if event.ctrl:
                return {'PASS_THROUGH'}        # let the user zoom with Ctrl
            self.size = min(self.size * 1.1, 50.0)

        elif event.type in {'WHEELDOWNMOUSE'} and event.value == 'PRESS':
            if event.ctrl:
                return {'PASS_THROUGH'}
            self.size = max(self.size * 0.9, 0.001)

        elif event.type == 'LEFT_BRACKET' and event.value == 'PRESS':
            self.roll -= math.radians(15)

        elif event.type == 'RIGHT_BRACKET' and event.value == 'PRESS':
            self.roll += math.radians(15)

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if self._hit is None:
                self.report({'WARNING'}, "No surface under the cursor")
                return {'RUNNING_MODAL'}
            return self._commit(context)

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._cleanup(context)
            return {'CANCELLED'}

        elif event.type in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    def _tangent(self, normal):
        base = decal_math.base_tangent(tuple(normal))
        return decal_math.rotate_about_axis(base, tuple(normal), self.roll)

    def _draw_px(self, context):
        prefs = get_prefs(context)
        region, rv3d = context.region, context.region_data
        lines = ["Decal (%s) — click place · wheel scale · [ ] roll · Esc cancel"
                 % self.decal_type.capitalize(),
                 "Size: %.3f m" % self.size]

        if self._hit is not None:
            location, normal, obj = self._hit
            tangent = self._tangent(normal)
            # preview outline: the four decal corners projected to screen
            mat = decal.decal_matrix(location, normal, tangent, scale=self.size)
            from mathutils import Vector
            local = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
            pts = []
            for u, v in local:
                world = mat @ Vector((u, v, 0.0))
                s = raycast.world_to_screen(region, rv3d, world)
                if s is not None:
                    pts.append((s[0], s[1]))
            hud.draw_shape(pts, tuple(prefs.line_color), closed=True)
            tgt = obj.name if obj is not None else "?"
            lines.append("Target: %s" % tgt)
        elif self._screen is not None:
            hud.draw_points([self._screen], (1.0, 0.3, 0.3, 1.0))
            lines.append("No surface under cursor")

        hud.draw_hud(region, lines)

    def _commit(self, context):
        location, normal, obj = self._hit
        prefs = get_prefs(context)
        try:
            tangent = self._tangent(normal)
            new = decal.make_decal(
                context, obj, location, normal, tangent,
                width=self.size, height=self.size,
                decal_type=self.decal_type, offset=prefs.decal_offset)
            for o in list(context.selected_objects):
                o.select_set(False)
            new.select_set(True)
            context.view_layer.objects.active = new
        except Exception as ex:  # noqa: BLE001
            self.report({'ERROR'}, f"Hardflow Decal: {ex}")
            self._cleanup(context)
            return {'CANCELLED'}
        self._cleanup(context)
        return {'FINISHED'}

    def _cleanup(self, context):
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        context.area.tag_redraw()


class HARDFLOW_OT_select_decal(Operator):
    bl_idname = "object.hardflow_select_decal"
    bl_label = "Select Decal"
    bl_description = "Make the decal visible, select and activate it (to edit)"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        if ob is None:
            self.report({'WARNING'}, "Decal not found")
            return {'CANCELLED'}
        for o in list(context.selected_objects):
            o.select_set(False)
        ob.hide_viewport = False
        ob.hide_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {'FINISHED'}


class HARDFLOW_OT_remove_decal(Operator):
    bl_idname = "object.hardflow_remove_decal"
    bl_label = "Delete Decal"
    bl_description = "Delete the decal from the scene (reversible with undo)"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        if ob is None:
            return {'CANCELLED'}
        bpy.data.objects.remove(ob, do_unlink=True)
        return {'FINISHED'}


class HARDFLOW_OT_bake_decal(Operator):
    bl_idname = "object.hardflow_bake_decal"
    bl_label = "Bake Decal to Map"
    bl_description = ("Bake the decal's detail into an image on the target mesh "
                      "(Cycles, selected-to-active). Target needs a UV map")
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()
    bake_type: EnumProperty(
        name="Bake",
        items=[('NORMAL', "Normal", "Bake the decal's surface normal detail"),
               ('COMBINED', "Combined", "Bake the decal's full shaded color")],
        default='NORMAL',
    )
    size: IntProperty(name="Resolution", default=1024, min=64, max=8192)

    def invoke(self, context, event):
        self.size = get_prefs(context).bake_size
        return self.execute(context)

    def execute(self, context):
        deco = (bpy.data.objects.get(self.name) if self.name
                else context.active_object)
        if deco is None or deco.get("hf_decal_type") is None:
            self.report({'WARNING'}, "Select a Hardflow decal to bake")
            return {'CANCELLED'}
        target = deco.parent
        if target is None or target.type != 'MESH':
            self.report({'WARNING'}, "Decal has no mesh target to bake into")
            return {'CANCELLED'}
        if not target.data.uv_layers:
            self.report({'ERROR'}, "Target has no UV map -- unwrap it first")
            return {'CANCELLED'}

        scene = context.scene
        view_layer = context.view_layer
        is_data = (self.bake_type == 'NORMAL')
        img = decal.bake_image(
            "HF_Bake_%s_%s" % (target.name, self.bake_type.capitalize()),
            self.size, is_data=is_data)
        mat = decal.ensure_material(target)
        decal.bake_image_node(mat, img)

        # save the bits of scene state we are about to change, restore in finally
        prev_engine = scene.render.engine
        prev_active = view_layer.objects.active
        prev_selected = list(context.selected_objects)
        prev_s2a = scene.render.bake.use_selected_to_active
        prev_ext = scene.render.bake.cage_extrusion
        prev_ray = scene.render.bake.max_ray_distance
        try:
            scene.render.engine = 'CYCLES'
            bake = scene.render.bake
            bake.use_selected_to_active = True
            # the decal hugs the surface; a small cage reliably catches it
            reach = max(0.1, max(deco.dimensions) * 0.25)
            bake.cage_extrusion = reach
            bake.max_ray_distance = reach * 2.0

            for o in prev_selected:
                o.select_set(False)
            deco.select_set(True)          # source
            target.select_set(True)        # destination (must be active)
            view_layer.objects.active = target

            bpy.ops.object.bake(type=self.bake_type)
            img.pack()
        except RuntimeError as ex:
            self.report({'ERROR'}, "Bake failed: %s" % ex)
            return {'CANCELLED'}
        finally:
            scene.render.engine = prev_engine
            scene.render.bake.use_selected_to_active = prev_s2a
            scene.render.bake.cage_extrusion = prev_ext
            scene.render.bake.max_ray_distance = prev_ray
            for o in context.selected_objects:
                o.select_set(False)
            for o in prev_selected:
                if o is not None:
                    o.select_set(True)
            view_layer.objects.active = prev_active

        self.report({'INFO'}, "Baked '%s' (%dx%d)" % (img.name, self.size,
                                                       self.size))
        return {'FINISHED'}
