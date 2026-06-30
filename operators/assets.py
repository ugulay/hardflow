# Asset / kitbash placement + management.
#
# HARDFLOW_OT_place_asset: a modal tool. It loads a part (an "INSERT") from a
# .blend library, then previews it on whatever surface is under the cursor,
# aligned to the hit normal. The mouse wheel scales, [ / ] roll around the
# normal, left click places. Depending on preferences the part is either a plain
# decoration (parented under an oriented Empty), a boolean cutter, conformed to
# the surface, and/or given the target's shading.
import math
import os

import bpy
from bpy.types import Operator
from bpy.props import FloatProperty, StringProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper

from ..core import raycast, asset, decal_math, snapping, decal_image
from ..preferences import get_prefs
from ..ui import draw as hud


def _invoke_place(context, op, **kwargs):
    """Start the modal place-asset tool in a 3D viewport, overriding context when
    the caller runs elsewhere (e.g. the file browser). Mirrors
    operators/decals.py _invoke_place."""
    win = context.window
    area = context.area if (context.area and context.area.type == 'VIEW_3D') else None
    if area is None and win is not None:
        area = next((a for a in win.screen.areas if a.type == 'VIEW_3D'), None)
    region = (next((r for r in area.regions if r.type == 'WINDOW'), None)
              if area else None)
    if area is None or region is None:
        op.report({'WARNING'}, "Open a 3D viewport to place the asset")
        return {'CANCELLED'}
    with context.temp_override(window=win, area=area, region=region):
        result = bpy.ops.object.hardflow_place_asset('INVOKE_DEFAULT', **kwargs)
    # Propagate an immediate cancel (no viewport / bad args) instead of always
    # reporting success; a started modal returns RUNNING_MODAL -- launch is done.
    return {'CANCELLED'} if result == {'CANCELLED'} else {'FINISHED'}


class HARDFLOW_OT_place_asset(Operator):
    bl_idname = "object.hardflow_place_asset"
    bl_label = "Place Asset"
    bl_description = ("Place a kit part (INSERT) onto the surface under the cursor "
                      "(wheel = scale, [ / ] = roll, click = place)")
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(
        name="Asset .blend",
        description="Library file whose objects are appended as the INSERT",
        subtype='FILE_PATH',
    )
    size: FloatProperty(name="Scale", default=1.0, min=0.001, soft_max=20.0)
    roll: FloatProperty(name="Roll (rad)", default=0.0)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Run inside View3D")
            return {'CANCELLED'}
        if not self.filepath:
            self.report({'WARNING'}, "No asset .blend chosen")
            return {'CANCELLED'}
        self.roll = 0.0
        self._hit = None          # (location, normal, object)
        self._edge_tangent = None  # face-edge-aligned base tangent (smart orient)
        self._screen = None
        self._root = None         # oriented Empty the previewed INSERT hangs under
        self._finalized = False
        self._auto_scaled = False  # auto-scale fires once, on the first hit
        try:
            self._objects = asset.load_blend_objects(self.filepath, link=False)
        except Exception as ex:   # noqa: BLE001
            self.report({'ERROR'}, "Could not load asset: %s" % ex)
            return {'CANCELLED'}
        if not self._objects:
            self.report({'WARNING'}, "Asset .blend has no objects")
            return {'CANCELLED'}

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        context.area.tag_redraw()
        region, rv3d = context.region, context.region_data

        if event.type == 'MOUSEMOVE':
            self._screen = (event.mouse_region_x, event.mouse_region_y)
            # Skip the previewed INSERT parts (and their root) so the ray finds
            # the target surface, not the preview hovering under the cursor.
            ignore = list(self._objects)
            if self._root is not None:
                ignore.append(self._root)
            ex = raycast.ray_cast_surface_ex(context, region, rv3d,
                                             self._screen, ignore=ignore)
            if ex is None:
                self._hit = None
                self._edge_tangent = None
            else:
                location, normal, obj, index, matrix = ex
                self._hit = (location, normal, obj)
                # Align the INSERT to the hit face's dominant edge (smart orient),
                # so greeble snaps to panel lines; the user still rolls from there.
                self._edge_tangent = raycast.face_edge_tangent(
                    obj, index, matrix, normal)
            self._apply_smart_placement(context)

        elif event.type == 'WHEELUPMOUSE' and event.value == 'PRESS':
            if event.ctrl:
                return {'PASS_THROUGH'}
            self.size = min(self.size * 1.1, 100.0)
        elif event.type == 'WHEELDOWNMOUSE' and event.value == 'PRESS':
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

        self._update_preview(context)
        return {'RUNNING_MODAL'}

    def _apply_smart_placement(self, context):
        """Smart placement (v1.8): snap the hit to an insert grid / anchor, and
        auto-scale the INSERT to the target's feature size on the first hit."""
        if self._hit is None:
            return
        prefs = get_prefs(context)
        location, normal, obj = self._hit
        if prefs.asset_grid_snap:
            coll = bpy.data.collections.get(asset.ASSET_COLLECTION)
            # exclude this insert's own live preview root from the anchors
            skip = {self._root} | set(self._objects)
            anchors = [o.matrix_world.translation for o in coll.objects
                       if o not in skip] if coll is not None else []
            location = snapping.snap_insert_point(
                location, prefs.asset_grid_spacing, anchors,
                threshold=prefs.asset_grid_spacing * 0.5)
            self._hit = (location, normal, obj)
        if (prefs.asset_auto_scale and not self._auto_scaled
                and obj is not None and obj.type == 'MESH'):
            from ..core import transform
            insert = asset.bound_size(self._objects)
            feature = asset.surface_feature_size(obj)
            self.size = transform.fit_scale(insert, feature,
                                            prefs.asset_fit_fraction, self.size)
            self._auto_scaled = True

    def _tangent(self, normal):
        # Prefer the face-edge-aligned tangent (smart orient) over the generic
        # world-derived one; the user's roll is applied on top of whichever.
        if self._edge_tangent is not None:
            base = tuple(self._edge_tangent)
        else:
            base = decal_math.base_tangent(tuple(normal))
        return decal_math.rotate_about_axis(base, tuple(normal), self.roll)

    def _draw_px(self, context):
        prefs = get_prefs(context)
        region, rv3d = context.region, context.region_data
        name = bpy.path.display_name_from_filepath(self.filepath)
        mode = "Cutter" if prefs.asset_as_cutter else "Insert"
        lines = ["Asset (%s) — click place · wheel scale · [ ] roll · Esc cancel"
                 % name,
                 "Scale: %.3f   Mode: %s" % (self.size, mode)]

        if self._hit is not None:
            location, normal, obj = self._hit
            tangent = self._tangent(normal)
            mat = asset.asset_matrix(location, normal, tangent, self.size)
            from mathutils import Vector
            half = 0.5
            local = [(-half, -half), (half, -half), (half, half), (-half, half)]
            pts = []
            for u, v in local:
                world = mat @ Vector((u, v, 0.0))
                s = raycast.world_to_screen(region, rv3d, world)
                if s is not None:
                    pts.append((s[0], s[1]))
            hud.draw_shape(pts, tuple(prefs.line_color), closed=True)
            lines.append("Target: %s" % (obj.name if obj is not None else "?"))
        elif self._screen is not None:
            hud.draw_points([self._screen], (1.0, 0.3, 0.3, 1.0))
            lines.append("No surface under cursor")

        hud.draw_hud(region, lines)

    def _update_preview(self, context):
        """Keep the real (already-loaded) INSERT under the cursor: create the
        oriented root on the first hit, then just re-orient it as the cursor and
        scale/roll change. The previewed objects become the placed result."""
        if self._hit is None:
            return
        location, normal, obj = self._hit
        tangent = self._tangent(normal)
        if self._root is None:
            name = bpy.path.display_name_from_filepath(self.filepath)
            self._root = asset.place_asset(context, self._objects, location,
                                           normal, tangent, scale=self.size,
                                           name=name)
        else:
            self._root.matrix_world = asset.asset_matrix(
                location, normal, tangent, self.size)

    def _commit(self, context):
        if self._hit is None:
            self.report({'WARNING'}, "No surface under the cursor")
            return {'RUNNING_MODAL'}
        if self._root is None:                  # never previewed -> place now
            self._update_preview(context)
        location, normal, obj = self._hit
        prefs = get_prefs(context)
        try:
            if prefs.asset_as_cutter and obj is not None and obj.type == 'MESH':
                # re-bind the previewed parts as independent boolean cutters
                asset.flatten_objects(self._objects)
                if self._root is not None and self._root.name in bpy.data.objects:
                    bpy.data.objects.remove(self._root, do_unlink=True)
                    self._root = None
                meshes = [o for o in self._objects if o.type == 'MESH']
                op = 'DIFFERENCE' if prefs.asset_boolean == 'CUT' else 'UNION'
                failures = []
                asset.bind_cutters(context, meshes, obj, operation=op,
                                   solver=prefs.default_solver,
                                   non_destructive=prefs.non_destructive,
                                   failures=failures)
                if not prefs.non_destructive:
                    for o in self._objects:
                        if o.type != 'MESH' and o.name in bpy.data.objects:
                            bpy.data.objects.remove(o, do_unlink=True)
                if failures:
                    self.report({'WARNING'}, failures[0])
                self._select(context, meshes[0] if meshes else obj)
            else:
                if prefs.asset_conform and obj is not None and obj.type == 'MESH':
                    asset.conform_asset(self._objects, obj)
                if prefs.asset_transfer_shading and obj is not None \
                        and obj.type == 'MESH':
                    asset.transfer_shading(obj, self._objects)
                self._select(context, self._root)
            self._finalized = True
        except Exception as ex:  # noqa: BLE001
            self.report({'ERROR'}, "Hardflow Asset: %s" % ex)
            self._cleanup(context)
            return {'CANCELLED'}
        self._cleanup(context)
        return {'FINISHED'}

    def _select(self, context, active):
        for o in list(context.selected_objects):
            o.select_set(False)
        if active is not None and active.name in context.view_layer.objects:
            active.select_set(True)
            context.view_layer.objects.active = active

    def _cleanup(self, context):
        if not self._finalized:                 # cancelled -> discard the preview
            for o in list(getattr(self, "_objects", [])):
                if o.name in bpy.data.objects:
                    bpy.data.objects.remove(o, do_unlink=True)
            if self._root is not None and self._root.name in bpy.data.objects:
                bpy.data.objects.remove(self._root, do_unlink=True)
            self._root = None
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        if context.area is not None:
            context.area.tag_redraw()


class HARDFLOW_OT_load_asset(Operator, ImportHelper):
    bl_idname = "object.hardflow_load_asset"
    bl_label = "Asset from .blend"
    bl_description = "Pick a .blend file and place its objects as an INSERT"
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: StringProperty(default="*.blend", options={'HIDDEN'})

    def execute(self, context):
        return _invoke_place(context, self, filepath=self.filepath)


class HARDFLOW_OT_asset_library_place(Operator):
    bl_idname = "object.hardflow_asset_library_place"
    bl_label = "Place Library Asset"
    bl_description = "Place this library .blend as an INSERT on the surface"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        if not self.filepath:
            return {'CANCELLED'}
        return _invoke_place(context, self, filepath=self.filepath)


class HARDFLOW_OT_material_insert(Operator, ImportHelper):
    bl_idname = "object.hardflow_material_insert"
    bl_label = "Material INSERT"
    bl_description = ("Append the first material from a .blend and apply it to the "
                      "selected meshes (material insert)")
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: StringProperty(default="*.blend", options={'HIDDEN'})

    def execute(self, context):
        try:
            mats = asset.load_blend_materials(self.filepath, link=False)
        except Exception as ex:   # noqa: BLE001
            self.report({'ERROR'}, "Could not load materials: %s" % ex)
            return {'CANCELLED'}
        if not mats:
            self.report({'WARNING'}, "No materials in that .blend")
            return {'CANCELLED'}
        mat = mats[0]
        targets = [o for o in context.selected_objects if o.type == 'MESH']
        if not targets and context.active_object is not None:
            targets = [context.active_object]
        n = sum(1 for o in targets if asset.apply_material(o, mat))
        self.report({'INFO'}, "Applied '%s' to %d mesh(es)" % (mat.name, n))
        return {'FINISHED'}


class HARDFLOW_OT_export_asset(Operator):
    bl_idname = "object.hardflow_export_asset"
    bl_label = "Export INSERT"
    bl_description = ("Write the selected objects to a .blend in the asset library "
                      "and mark them as assets (asset-pack INSERT export)")
    bl_options = {'REGISTER'}

    name: StringProperty(name="INSERT Name", default="HF_Insert")
    mark_asset: BoolProperty(name="Mark as Asset", default=True)

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def _dest_path(self, context):
        """Resolved library path for the (sanitized) name, or '' with no folder."""
        prefs = get_prefs(context)
        folder = bpy.path.abspath(prefs.asset_library_path) \
            if prefs.asset_library_path else ""
        if not folder:
            return ""
        return os.path.join(folder, "%s.blend" % decal_image.safe_filename(self.name))

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "name")
        layout.prop(self, "mark_asset")
        # Surface a silent overwrite before the user confirms the dialog.
        path = self._dest_path(context)
        if path and os.path.isfile(path):
            layout.label(text="Overwrites %s" % os.path.basename(path),
                         icon='ERROR')

    def execute(self, context):
        prefs = get_prefs(context)
        folder = bpy.path.abspath(prefs.asset_library_path) \
            if prefs.asset_library_path else ""
        if not folder or not os.path.isdir(folder):
            self.report({'ERROR'}, "Set a valid Asset Library folder first")
            return {'CANCELLED'}
        objects = [o for o in context.selected_objects]
        if not objects:
            self.report({'WARNING'}, "Nothing selected")
            return {'CANCELLED'}
        if self.mark_asset:
            for ob in objects:
                ob.asset_mark()
                try:
                    ob.asset_generate_preview()
                except (AttributeError, RuntimeError):
                    pass
        # Sanitize the user name so it can't escape the library folder.
        path = os.path.join(folder, "%s.blend" % decal_image.safe_filename(self.name))
        overwrote = os.path.isfile(path)
        try:
            asset.write_objects_blend(path, objects)
        except (RuntimeError, OSError) as ex:
            self.report({'ERROR'}, "Export failed: %s" % ex)
            return {'CANCELLED'}
        verb = "Overwrote" if overwrote else "Exported"
        self.report({'INFO'}, "%s INSERT %s" % (verb, path))
        return {'FINISHED'}


class HARDFLOW_OT_mark_asset(Operator):
    bl_idname = "object.hardflow_mark_asset"
    bl_label = "Mark as Asset"
    bl_description = ("Mark the selected objects as Blender assets (Asset Browser) "
                      "and generate previews, so kit parts can be dragged in")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o for o in context.selected_objects)

    def execute(self, context):
        marked = 0
        for ob in context.selected_objects:
            ob.asset_mark()
            try:
                ob.asset_generate_preview()
            except (AttributeError, RuntimeError):
                pass
            marked += 1
        self.report({'INFO'}, "Marked %d asset(s)" % marked)
        return {'FINISHED'}
