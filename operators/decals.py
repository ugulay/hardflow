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
from bpy_extras.io_utils import ImportHelper

from ..core import raycast, decal, decal_math, decal_image, atlas
from ..preferences import get_prefs
from ..ui import draw as hud


def _invoke_place(context, op, **kwargs):
    """Start the modal place-decal tool in a 3D viewport, overriding context when
    the caller runs elsewhere (e.g. the file browser). Returns an operator result
    set so callers can `return _invoke_place(...)`."""
    win = context.window
    area = context.area if (context.area and context.area.type == 'VIEW_3D') else None
    if area is None and win is not None:
        area = next((a for a in win.screen.areas if a.type == 'VIEW_3D'), None)
    region = (next((r for r in area.regions if r.type == 'WINDOW'), None)
              if area else None)
    if area is None or region is None:
        op.report({'WARNING'}, "Open a 3D viewport to place the decal")
        return {'CANCELLED'}
    with context.temp_override(window=win, area=area, region=region):
        bpy.ops.object.hardflow_place_decal('INVOKE_DEFAULT', **kwargs)
    return {'FINISHED'}


class HARDFLOW_OT_place_decal(Operator):
    bl_idname = "object.hardflow_place_decal"
    bl_label = "Place Decal"
    bl_description = ("Stick a decal onto the surface under the cursor "
                      "(wheel = scale, [ / ] = roll, click = place)")
    bl_options = {'REGISTER', 'UNDO'}

    decal_type: EnumProperty(name="Type", items=decal.DECAL_TYPES, default='INFO')
    size: FloatProperty(name="Size (m)", default=0.2, min=0.001, soft_max=5.0)
    roll: FloatProperty(name="Roll (rad)", default=0.0)
    image_name: StringProperty(
        name="Image",
        description="Name of an already-loaded image; when set, the decal carries "
                    "this image (color+alpha) sized to its aspect ratio",
    )
    trim_cols: IntProperty(
        name="Trim Columns", default=0, min=0, max=64,
        description="Trim-sheet column count; 0 = use the whole image",
    )
    trim_rows: IntProperty(
        name="Trim Rows", default=0, min=0, max=64,
        description="Trim-sheet row count; 0 = use the whole image",
    )
    trim_index: IntProperty(
        name="Trim Cell", default=0,
        description="Which grid cell of the trim sheet to place "
                    "(cycle with Up/Down arrows)",
    )

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
        self._image = bpy.data.images.get(self.image_name) if self.image_name else None
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

        elif event.type == 'UP_ARROW' and event.value == 'PRESS' and self._is_trim():
            self.trim_index += 1

        elif event.type == 'DOWN_ARROW' and event.value == 'PRESS' and self._is_trim():
            self.trim_index -= 1

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

    def _is_trim(self):
        """True when placing a trim-sheet cell (an image plus a valid grid)."""
        return (self._image is not None
                and self.trim_cols > 0 and self.trim_rows > 0)

    def _uv_rect(self):
        """UV sub-rect of the image to map onto the quad: a trim-sheet cell when
        trimming, otherwise the whole image."""
        if self._is_trim():
            return atlas.cell_rect(self.trim_cols, self.trim_rows, self.trim_index)
        return (0.0, 0.0, 1.0, 1.0)

    def _wh(self):
        """Decal (width, height) in meters. An image decal keeps the image's (or
        the trim cell's) aspect ratio with `size` as the longest side; a plain
        type decal is square."""
        img = self._image
        if img is not None and img.size[0] and img.size[1]:
            if self._is_trim():
                pw, ph = atlas.rect_pixels(self._uv_rect(), img.size[0], img.size[1])
                return decal_image.aspect_size(pw, ph, self.size)
            return decal_image.aspect_size(img.size[0], img.size[1], self.size)
        return (self.size, self.size)

    def _draw_px(self, context):
        prefs = get_prefs(context)
        region, rv3d = context.region, context.region_data
        label = (self._image.name if self._image is not None
                 else self.decal_type.capitalize())
        lines = ["Decal (%s) — click place · wheel scale · [ ] roll · Esc cancel"
                 % label,
                 "Size: %.3f m" % self.size]
        if self._is_trim():
            cells = self.trim_cols * self.trim_rows
            lines.append("Trim cell %d/%d (Up/Down) — %dx%d sheet"
                         % (self.trim_index % cells + 1, cells,
                            self.trim_cols, self.trim_rows))

        if self._hit is not None:
            location, normal, obj = self._hit
            tangent = self._tangent(normal)
            # preview outline: the four decal corners projected to screen
            w, h = self._wh()
            mat = decal.decal_matrix(location, normal, tangent)
            from mathutils import Vector
            local = [(-0.5 * w, -0.5 * h), (0.5 * w, -0.5 * h),
                     (0.5 * w, 0.5 * h), (-0.5 * w, 0.5 * h)]
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
            w, h = self._wh()
            if self._image is not None:
                new = decal.make_image_decal(
                    context, obj, location, normal, tangent, self._image,
                    width=w, height=h, offset=prefs.decal_offset,
                    uv_rect=self._uv_rect())
            else:
                new = decal.make_decal(
                    context, obj, location, normal, tangent,
                    width=w, height=h,
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


class HARDFLOW_OT_load_decal_image(Operator, ImportHelper):
    bl_idname = "object.hardflow_load_decal_image"
    bl_label = "Decal from Image"
    bl_description = ("Pick an image file and place it as a decal on the surface "
                      "(color + alpha, sized to the image's aspect ratio)")
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: StringProperty(
        default="*.png;*.jpg;*.jpeg;*.tga;*.tif;*.tiff;*.bmp;*.exr;*.hdr;*.webp",
        options={'HIDDEN'},
    )

    def execute(self, context):
        try:
            img = bpy.data.images.load(self.filepath, check_existing=True)
        except RuntimeError as ex:
            self.report({'ERROR'}, "Could not load image: %s" % ex)
            return {'CANCELLED'}
        return _invoke_place(context, self, image_name=img.name)


class HARDFLOW_OT_library_place(Operator):
    bl_idname = "object.hardflow_library_place"
    bl_label = "Place Library Decal"
    bl_description = "Load this library image and place it as a decal on the surface"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        if not self.filepath:
            return {'CANCELLED'}
        try:
            img = bpy.data.images.load(self.filepath, check_existing=True)
        except RuntimeError as ex:
            self.report({'ERROR'}, "Could not load image: %s" % ex)
            return {'CANCELLED'}
        return _invoke_place(context, self, image_name=img.name)


class HARDFLOW_OT_load_trim_sheet(Operator, ImportHelper):
    bl_idname = "object.hardflow_load_trim_sheet"
    bl_label = "Trim Sheet from Image"
    bl_description = ("Pick a trim-sheet image and place one of its grid cells as "
                      "a decal (cycle cells with Up/Down while placing)")
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: StringProperty(
        default="*.png;*.jpg;*.jpeg;*.tga;*.tif;*.tiff;*.bmp;*.exr;*.hdr;*.webp",
        options={'HIDDEN'},
    )
    cols: IntProperty(name="Columns", default=4, min=1, max=64)
    rows: IntProperty(name="Rows", default=4, min=1, max=64)

    def execute(self, context):
        try:
            img = bpy.data.images.load(self.filepath, check_existing=True)
        except RuntimeError as ex:
            self.report({'ERROR'}, "Could not load image: %s" % ex)
            return {'CANCELLED'}
        return _invoke_place(context, self, image_name=img.name,
                             trim_cols=self.cols, trim_rows=self.rows,
                             trim_index=0)


def _image_decals(context):
    """Image-driven decals in the Hardflow Decals collection that still have a
    loadable source image, as a list of (decal_object, source_image)."""
    coll = bpy.data.collections.get(decal.DECAL_COLLECTION)
    if coll is None:
        return []
    out = []
    for ob in coll.objects:
        if ob.get("hf_decal_type") != 'IMAGE':
            continue
        img = bpy.data.images.get(ob.get("hf_decal_image", ""))
        if img is None or not (img.size[0] and img.size[1]):
            continue
        out.append((ob, img))
    return out


class HARDFLOW_OT_atlas_decals(Operator):
    bl_idname = "object.hardflow_atlas_decals"
    bl_label = "Atlas Image Decals"
    bl_description = ("Pack all image decals' textures into one atlas image and "
                      "retarget their UVs + material to it (fewer materials)")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        pairs = _image_decals(context)
        if not pairs:
            self.report({'WARNING'}, "No image decals to atlas")
            return {'CANCELLED'}

        # Pack the UNIQUE source images; many decals may share one image.
        images = []
        seen = set()
        for _ob, img in pairs:
            if img.name not in seen:
                seen.add(img.name)
                images.append(img)

        max_w = get_prefs(context).atlas_max_width
        sizes = [(int(img.size[0]), int(img.size[1])) for img in images]
        places, aw, ah = atlas.pack_shelves(sizes, max_w)
        final_w, final_h = atlas.next_pow2(aw), atlas.next_pow2(ah)

        # Assemble the atlas pixel buffer (transparent black), blitting each
        # source image into its slot. Slots are top-left; Blender pixels are
        # bottom-up, so the slot's bottom row is final_h - (y + h).
        dst = [0.0] * (final_w * final_h * 4)
        slots = {}                    # image name -> UV slot rect
        for img, (x, y, w, h) in zip(images, places):
            src = [0.0] * (4 * w * h)
            img.pixels.foreach_get(src)
            atlas.blit_pixels(dst, final_w, final_h, src, w, h,
                              x, final_h - (y + h))
            slots[img.name] = atlas.rect_to_uv(x, y, w, h, final_w, final_h)

        atlas_img = decal.atlas_image("HF_Decal_Atlas", final_w, final_h)
        atlas_img.pixels.foreach_set(dst)
        atlas_img.update()
        atlas_img.pack()
        atlas_mat = decal.image_decal_material(atlas_img)

        # Retarget every decal: compose its existing UVs into its source's slot,
        # then swap to the single shared atlas material.
        for ob, img in pairs:
            slot = slots[img.name]
            me = ob.data
            uv_layer = me.uv_layers.active
            if uv_layer is not None:
                for loop in me.loops:
                    u, v = uv_layer.data[loop.index].uv
                    uv_layer.data[loop.index].uv = atlas.remap_uv(u, v, slot)
            me.materials.clear()
            me.materials.append(atlas_mat)
            ob["hf_decal_atlas"] = atlas_img.name

        self.report({'INFO'}, "Atlased %d decals (%d images) into %dx%d"
                    % (len(pairs), len(images), final_w, final_h))
        return {'FINISHED'}
