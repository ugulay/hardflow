# Decal placement + management.
#
# HARDFLOW_OT_place_decal: a modal tool. The mouse ray is cast into the scene;
# the decal previews on whatever surface is under the cursor, aligned to the hit
# normal. The mouse wheel scales, [ / ] roll the decal around the normal, left
# click places it. The placed decal adheres via a SHRINKWRAP (PROJECT) modifier
# and is parented to the hit object (see core/decal.py).
import math
import os

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
        result = bpy.ops.object.hardflow_place_decal('INVOKE_DEFAULT', **kwargs)
    # Propagate an immediate cancel (no viewport / bad args) so the wrapper does
    # not report success -- and so a just-loaded image isn't left by a no-op
    # undo step. A started modal returns RUNNING_MODAL; the launch succeeded.
    return {'CANCELLED'} if result == {'CANCELLED'} else {'FINISHED'}


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
    region_index: IntProperty(
        name="Trim Region", default=-1,
        description="Index into the image's custom trim regions "
                    "(hardflow_trim); -1 = not using a stored region",
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
        self._preview = None      # live, real decal object that follows the cursor
        self._preview_key = None  # (target, size, trim) -- rebuild when it changes

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        context.area.tag_redraw()
        region, rv3d = context.region, context.region_data

        if event.type == 'MOUSEMOVE':
            self._screen = (event.mouse_region_x, event.mouse_region_y)
            # Skip the live preview decal so the ray lands on the target surface,
            # not on the preview that follows the cursor.
            ignore = (self._preview,) if self._preview is not None else None
            self._hit = raycast.ray_cast_surface(context, region, rv3d,
                                                 self._screen, ignore=ignore)

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

        elif event.type == 'UP_ARROW' and event.value == 'PRESS':
            if self._is_region():
                # Wrap within [0, n) so cycling never lands on the -1 "no region"
                # sentinel and silently drops region mode.
                self.region_index = (self.region_index + 1) % len(self._regions())
            elif self._is_trim():
                self.trim_index += 1

        elif event.type == 'DOWN_ARROW' and event.value == 'PRESS':
            if self._is_region():
                self.region_index = (self.region_index - 1) % len(self._regions())
            elif self._is_trim():
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

        self._update_preview(context)
        return {'RUNNING_MODAL'}

    def _tangent(self, normal):
        base = decal_math.base_tangent(tuple(normal))
        return decal_math.rotate_about_axis(base, tuple(normal), self.roll)

    def _is_trim(self):
        """True when placing a trim-sheet cell (an image plus a valid grid)."""
        return (self._image is not None
                and self.trim_cols > 0 and self.trim_rows > 0)

    def _regions(self):
        """The image's custom trim regions collection, or None."""
        if self._image is None or self.region_index < 0:
            return None
        trim = getattr(self._image, "hardflow_trim", None)
        regs = trim.regions if trim is not None else None
        return regs if (regs and len(regs)) else None

    def _is_region(self):
        """True when placing a custom (editor-carved) trim region."""
        return self._regions() is not None

    def _uv_rect(self):
        """UV sub-rect of the image to map onto the quad: a custom editor region
        first, then an equal trim-sheet cell, otherwise the whole image."""
        regs = self._regions()
        if regs is not None:
            r = regs[self.region_index % len(regs)]
            return atlas.normalize_rect((r.u0, r.v0, r.u1, r.v1))
        if self._is_trim():
            return atlas.cell_rect(self.trim_cols, self.trim_rows, self.trim_index)
        return (0.0, 0.0, 1.0, 1.0)

    def _wh(self):
        """Decal (width, height) in meters. An image decal keeps the image's (or
        the trim cell's) aspect ratio with `size` as the longest side; a plain
        type decal is square."""
        img = self._image
        if img is not None and img.size[0] and img.size[1]:
            # The sub-rect (whole image, trim cell, or custom region) sets the
            # aspect; rect_pixels of (0,0,1,1) is just the full image size.
            pw, ph = atlas.rect_pixels(self._uv_rect(), img.size[0], img.size[1])
            return decal_image.aspect_size(pw, ph, self.size)
        return (self.size, self.size)

    def _draw_px(self, context):
        prefs = get_prefs(context)
        region, rv3d = context.region, context.region_data
        label = (self._image.name if self._image is not None
                 else self.decal_type.capitalize())
        lines = ["Decal (%s) — click place · wheel scale · [ ] roll · Esc cancel"
                 % label,
                 "Size: %.3f m" % self.size]
        regs = self._regions()
        if regs is not None:
            n = len(regs)
            r = regs[self.region_index % n]
            lines.append("Trim region '%s' %d/%d (Up/Down)"
                         % (r.name, self.region_index % n + 1, n))
        elif self._is_trim():
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

    def _build_decal(self, context):
        """Create the real decal object for the current hit + params (the live
        preview and the final result are one and the same object)."""
        location, normal, obj = self._hit
        if obj is None:
            return None
        prefs = get_prefs(context)
        tangent = self._tangent(normal)
        w, h = self._wh()
        # 0 in the preference means "auto" -> let the build pick a size-scaled gap.
        offset = prefs.decal_offset or None
        segments = prefs.decal_resolution
        normal_transfer = getattr(prefs, "decal_normal_transfer", False)
        if self._image is not None:
            hname = getattr(prefs, "decal_height_image", "")
            height_image = bpy.data.images.get(hname) if hname else None
            # A height map is only meaningful when distinct from the color image
            # (otherwise the color's own luminance is already the height source).
            if height_image is self._image:
                height_image = None
            return decal.make_image_decal(
                context, obj, location, normal, tangent, self._image,
                width=w, height=h, offset=offset,
                uv_rect=self._uv_rect(), segments=segments,
                parallax=getattr(prefs, "decal_parallax", False),
                parallax_layers=getattr(prefs, "decal_parallax_layers", 8),
                parallax_depth=getattr(prefs, "decal_parallax_depth", 0.05),
                height_image=height_image,
                height_invert=getattr(prefs, "decal_height_invert", False),
                bump_strength=getattr(prefs, "decal_bump_strength", 0.0),
                normal_transfer=normal_transfer)
        return decal.make_decal(
            context, obj, location, normal, tangent, width=w, height=h,
            decal_type=self.decal_type, offset=offset, segments=segments,
            normal_transfer=normal_transfer)

    def _delete_preview(self):
        if self._preview is not None and self._preview.name in bpy.data.objects:
            bpy.data.objects.remove(self._preview, do_unlink=True)
        self._preview = None

    def _update_preview(self, context):
        """Keep a real decal under the cursor: rebuild it when the target object,
        size, or trim cell changes (mesh/material differ); otherwise just move it
        (cheap, every mouse move)."""
        if self._hit is None:
            return
        location, normal, obj = self._hit
        key = (obj.name if obj is not None else None,
               round(self.size, 6), self.trim_index, self.region_index)
        if self._preview is None or key != self._preview_key:
            self._delete_preview()
            try:
                self._preview = self._build_decal(context)
            except Exception as ex:  # noqa: BLE001
                self.report({'WARNING'}, "Decal preview: %s" % ex)
                self._preview = None
            self._preview_key = key
        if self._preview is not None:
            self._preview.matrix_world = decal.decal_matrix(
                location, normal, self._tangent(normal))

    def _commit(self, context):
        if self._preview is None:           # not built yet -> build at the hit
            self._update_preview(context)
        new = self._preview
        if new is None:
            self.report({'ERROR'}, "Hardflow Decal: could not place")
            self._cleanup(context)
            return {'CANCELLED'}
        self._preview = None                # release: cleanup must keep it
        for o in list(context.selected_objects):
            o.select_set(False)
        new.select_set(True)
        context.view_layer.objects.active = new
        self._cleanup(context)
        return {'FINISHED'}

    def _cleanup(self, context):
        self._delete_preview()              # no-op once committed (released above)
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        if context.area is not None:
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
            # WARNING (not ERROR) so this is a clean rejection: an ERROR report
            # makes bpy.ops raise for script callers instead of returning
            # CANCELLED, and the sibling guards above already use WARNING.
            self.report({'WARNING'}, "Target has no UV map -- unwrap it first")
            return {'CANCELLED'}

        scene = context.scene
        view_layer = context.view_layer
        is_data = (self.bake_type == 'NORMAL')
        img_name = "HF_Bake_%s_%s" % (target.name, self.bake_type.capitalize())
        # Remember what already existed so a failed bake only rolls back what
        # THIS call created (never a prior good result reused by bake_image).
        img_existed = img_name in bpy.data.images
        img = decal.bake_image(img_name, self.size, is_data=is_data)
        mat = decal.ensure_material(target)
        node_existed = any(n.type == 'TEX_IMAGE' and n.image == img
                           for n in mat.node_tree.nodes)
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
            # Don't leave an orphan image + dangling node in the target material.
            decal.discard_bake_image(mat, img, remove_node=not node_existed,
                                     remove_image=not img_existed)
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


class HARDFLOW_OT_load_height_map(Operator, ImportHelper):
    bl_idname = "object.hardflow_load_height_map"
    bl_label = "Load Height Map"
    bl_description = ("Load a grayscale image as the decal height map -- drives "
                      "Parallax + Relief depth independently of the color image. "
                      "Clears the field if the browser is cancelled elsewhere")
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
        get_prefs(context).decal_height_image = img.name
        self.report({'INFO'}, "Decal height map set: %s" % img.name)
        return {'FINISHED'}


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


def _get_decal(context, name):
    """Resolve a decal by name (or fall back to the active object) and verify it
    is a Hardflow decal. Returns the object or None."""
    deco = bpy.data.objects.get(name) if name else context.active_object
    if deco is None or deco.get("hf_decal_type") is None:
        return None
    return deco


class HARDFLOW_OT_match_decal(Operator):
    bl_idname = "object.hardflow_match_decal"
    bl_label = "Match Decal to Surface"
    bl_description = ("Match the decal's blend (metallic / roughness / tint) to "
                      "its target's active material so it reads as the same "
                      "surface (material match)")
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        deco = _get_decal(context, self.name)
        if deco is None:
            self.report({'WARNING'}, "Select a Hardflow decal")
            return {'CANCELLED'}
        target = deco.parent
        if target is None:
            self.report({'WARNING'}, "Decal has no target to match")
            return {'CANCELLED'}
        sample = decal.sample_material(target)
        if not decal.match_decal_to_material(deco, sample):
            self.report({'WARNING'}, "Nothing to match (no material on target)")
            return {'CANCELLED'}
        self.report({'INFO'}, "Matched '%s' to %s" % (deco.name, target.name))
        return {'FINISHED'}


class HARDFLOW_OT_retrim_decal(Operator):
    bl_idname = "object.hardflow_retrim_decal"
    bl_label = "Re-trim Decal"
    bl_description = ("Change which trim-sheet cell a placed decal uses by "
                      "rewriting its UVs (interactive trim-UV editor)")
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()
    cols: IntProperty(name="Columns", default=4, min=1, max=64)
    rows: IntProperty(name="Rows", default=4, min=1, max=64)
    index: IntProperty(name="Cell", default=0)

    def execute(self, context):
        deco = _get_decal(context, self.name)
        if deco is None:
            self.report({'WARNING'}, "Select a Hardflow decal")
            return {'CANCELLED'}
        rect = atlas.cell_rect(self.cols, self.rows, self.index)
        if not decal.set_decal_uv_rect(deco, rect):
            self.report({'WARNING'}, "Decal has no UV map")
            return {'CANCELLED'}
        cells = self.cols * self.rows
        self.report({'INFO'}, "Trim cell %d/%d" % (self.index % cells + 1, cells))
        return {'FINISHED'}


class HARDFLOW_OT_conform_decal(Operator):
    bl_idname = "object.hardflow_conform_decal"
    bl_label = "Auto-cut Decal to Surface"
    bl_description = ("Subdivide the decal and trim faces that float over a "
                      "boolean cut / edge so it follows the surface boundary")
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()
    subdivisions: IntProperty(name="Subdivisions", default=8, min=0, max=64)
    max_gap: FloatProperty(name="Max Gap (m)", default=0.05, min=0.0001,
                           soft_max=1.0)

    def execute(self, context):
        deco = _get_decal(context, self.name)
        if deco is None:
            self.report({'WARNING'}, "Select a Hardflow decal")
            return {'CANCELLED'}
        target = deco.parent
        if target is None or target.type != 'MESH':
            self.report({'WARNING'}, "Decal has no mesh target")
            return {'CANCELLED'}
        removed = decal.conform_trim_decal(context, deco, target,
                                           self.subdivisions, self.max_gap)
        self.report({'INFO'}, "Trimmed %d face(s) off the surface" % removed)
        return {'FINISHED'}


class HARDFLOW_OT_transfer_decal(Operator):
    bl_idname = "object.hardflow_transfer_decal"
    bl_label = "Transfer Decal to Surface"
    bl_description = ("Move the selected decal(s) onto the active mesh: re-point "
                      "their shrinkwrap and re-parent, keeping the world pose "
                      "(decal transfer)")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        target = context.active_object
        if target is None or target.type != 'MESH':
            return False
        return any(o is not target and o.get("hf_decal_type") is not None
                   for o in context.selected_objects)

    def execute(self, context):
        target = context.active_object
        decals = [o for o in context.selected_objects
                  if o is not target and o.get("hf_decal_type") is not None]
        if not decals:
            self.report({'WARNING'},
                        "Select decal(s) plus an active target mesh")
            return {'CANCELLED'}
        for d in decals:
            decal.retarget_decal(d, target)
        self.report({'INFO'}, "Transferred %d decal(s) to %s"
                    % (len(decals), target.name))
        return {'FINISHED'}


class HARDFLOW_OT_create_decal(Operator):
    bl_idname = "object.hardflow_create_decal"
    bl_label = "Create Decal (Bake)"
    bl_description = ("Bake the selected high-poly source's normal onto the active "
                      "plane and save it into the decal library (create decal). "
                      "Active plane needs a UV map")
    bl_options = {'REGISTER', 'UNDO'}

    decal_name: StringProperty(name="Decal Name", default="HF_NewDecal")
    size: IntProperty(name="Resolution", default=1024, min=64, max=8192)

    def execute(self, context):
        dest = context.active_object
        sources = [o for o in context.selected_objects
                   if o.type == 'MESH' and o is not dest]
        if dest is None or dest.type != 'MESH' or not sources:
            self.report({'WARNING'},
                        "Select high-poly source(s) + an active plane")
            return {'CANCELLED'}
        if not dest.data.uv_layers:
            self.report({'ERROR'}, "Active plane has no UV map -- unwrap it first")
            return {'CANCELLED'}

        scene, view_layer = context.scene, context.view_layer
        img_name = "HF_DecalSrc_%s" % self.decal_name
        img_existed = img_name in bpy.data.images
        img = decal.bake_image(img_name, self.size, is_data=True)
        mat = decal.ensure_material(dest)
        node_existed = any(n.type == 'TEX_IMAGE' and n.image == img
                           for n in mat.node_tree.nodes)
        decal.bake_image_node(mat, img)

        prev_engine = scene.render.engine
        prev_active = view_layer.objects.active
        prev_selected = list(context.selected_objects)
        prev_s2a = scene.render.bake.use_selected_to_active
        prev_ext = scene.render.bake.cage_extrusion
        prev_ray = scene.render.bake.max_ray_distance
        try:
            scene.render.engine = 'CYCLES'
            scene.render.bake.use_selected_to_active = True
            reach = max(0.1, max(dest.dimensions) * 0.5)
            scene.render.bake.cage_extrusion = reach
            scene.render.bake.max_ray_distance = reach * 2.0

            # Selected-to-active bakes the *selected* sources onto the *active*
            # destination, so arrange the selection explicitly rather than trust
            # whatever ambient selection happens to be set.
            for o in prev_selected:
                o.select_set(False)
            for o in sources:
                o.select_set(True)
            dest.select_set(True)
            view_layer.objects.active = dest

            bpy.ops.object.bake(type='NORMAL')
        except RuntimeError as ex:
            decal.discard_bake_image(mat, img, remove_node=not node_existed,
                                     remove_image=not img_existed)
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

        # Save into the library folder when one is set, else just pack it.
        folder = get_prefs(context).decal_library_path
        if folder:
            folder = bpy.path.abspath(folder)
            # Sanitize the user name so it can't escape the library folder.
            stem = decal_image.safe_filename(self.decal_name)
            try:
                decal.save_image(img, os.path.join(folder, "%s.png" % stem))
            except (RuntimeError, OSError) as ex:
                self.report({'WARNING'}, "Baked but could not save: %s" % ex)
        img.pack()
        self.report({'INFO'}, "Created decal '%s'" % self.decal_name)
        return {'FINISHED'}


class HARDFLOW_OT_library_rename(Operator):
    bl_idname = "object.hardflow_library_rename"
    bl_label = "Rename Library Decal"
    bl_description = "Rename a decal image file in the library folder"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')
    new_name: StringProperty(name="New Name")

    def invoke(self, context, event):
        if self.filepath and not self.new_name:
            self.new_name = os.path.splitext(os.path.basename(self.filepath))[0]
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if not self.filepath or not os.path.isfile(self.filepath):
            self.report({'WARNING'}, "File not found")
            return {'CANCELLED'}
        ext = os.path.splitext(self.filepath)[1]
        dest = os.path.join(os.path.dirname(self.filepath),
                            self.new_name + ext)
        try:
            os.rename(self.filepath, dest)
        except OSError as ex:
            self.report({'ERROR'}, "Rename failed: %s" % ex)
            return {'CANCELLED'}
        self.report({'INFO'}, "Renamed to %s%s" % (self.new_name, ext))
        return {'FINISHED'}


class HARDFLOW_OT_library_delete(Operator):
    bl_idname = "object.hardflow_library_delete"
    bl_label = "Delete Library Decal"
    bl_description = "Delete a decal image file from the library folder"
    bl_options = {'REGISTER'}

    filepath: StringProperty(subtype='FILE_PATH')

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        if not self.filepath or not os.path.isfile(self.filepath):
            self.report({'WARNING'}, "File not found")
            return {'CANCELLED'}
        try:
            os.remove(self.filepath)
        except OSError as ex:
            self.report({'ERROR'}, "Delete failed: %s" % ex)
            return {'CANCELLED'}
        self.report({'INFO'}, "Deleted %s" % os.path.basename(self.filepath))
        return {'FINISHED'}


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

        # Pack the UNIQUE source images; many decals may share one image. Skip
        # any image whose pixel buffer isn't readable (unloaded, zero-size, or a
        # multilayer format whose size and buffer disagree) so one bad image
        # can't abort the whole atlas with a traceback.
        images = []
        seen = set()
        skipped = 0
        for _ob, img in pairs:
            if img.name in seen:
                continue
            w, h = int(img.size[0]), int(img.size[1])
            if w <= 0 or h <= 0 or len(img.pixels) != 4 * w * h:
                seen.add(img.name)
                skipped += 1
                continue
            seen.add(img.name)
            images.append(img)
        if not images:
            self.report({'WARNING'}, "No readable image decals to atlas")
            return {'CANCELLED'}

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
        retargeted = 0
        for ob, img in pairs:
            slot = slots.get(img.name)
            if slot is None:           # its source image was skipped above
                continue
            me = ob.data
            uv_layer = me.uv_layers.active
            if uv_layer is not None:
                for loop in me.loops:
                    u, v = uv_layer.data[loop.index].uv
                    uv_layer.data[loop.index].uv = atlas.remap_uv(u, v, slot)
            me.materials.clear()
            me.materials.append(atlas_mat)
            ob["hf_decal_atlas"] = atlas_img.name
            retargeted += 1

        suffix = " (%d unreadable skipped)" % skipped if skipped else ""
        self.report({'INFO'}, "Atlased %d decals (%d images) into %dx%d%s"
                    % (retargeted, len(images), final_w, final_h, suffix))
        return {'FINISHED'}
