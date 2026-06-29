# N-panel "Assets" section (KitOps spirit): place INSERTs, browse a .blend kit
# library as a grid, mark objects as Blender assets, and list placed inserts.
# Mirrors ui/decal_panel.py + ui/decal_library.py.
import bpy
from bpy.types import Panel

from ..core import asset, asset_lib
from ..preferences import get_prefs


class HARDFLOW_PT_assets(Panel):
    bl_label = "Assets"
    bl_idname = "HARDFLOW_PT_assets"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        prefs = get_prefs(context)

        col = layout.column(align=True)
        col.label(text="Place INSERT", icon='FILE_BLEND')
        col.operator("object.hardflow_load_asset", icon='IMPORT')
        col.operator("object.hardflow_material_insert", icon='MATERIAL')
        row = col.row(align=True)
        row.prop(prefs, "asset_as_cutter", toggle=True)
        row.prop(prefs, "asset_boolean", text="")
        row = col.row(align=True)
        row.prop(prefs, "asset_conform", toggle=True)
        row.prop(prefs, "asset_transfer_shading", toggle=True)
        row = col.row(align=True)
        row.prop(prefs, "asset_auto_scale", toggle=True)
        row.prop(prefs, "asset_grid_snap", toggle=True)
        row = col.row(align=True)
        row.operator("object.hardflow_mark_asset", icon='OBJECT_DATA')
        row.operator("object.hardflow_export_asset", icon='EXPORT')

        coll = bpy.data.collections.get(asset.ASSET_COLLECTION)
        if coll is not None and coll.objects:
            layout.prop(coll, "hide_viewport", text="Hide collection",
                        icon='HIDE_ON' if coll.hide_viewport else 'HIDE_OFF')


class HARDFLOW_PT_asset_library(Panel):
    bl_label = "Asset Library"
    bl_idname = "HARDFLOW_PT_asset_library"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_assets"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        prefs = get_prefs(context)

        layout.prop(prefs, "asset_library_path", text="")
        folder = bpy.path.abspath(prefs.asset_library_path) \
            if prefs.asset_library_path else ""
        items = asset_lib.scan_assets(folder)
        if not items:
            layout.label(text="Set a folder with .blend kit parts", icon='INFO')
            return

        grid = layout.grid_flow(row_major=True, columns=2, even_columns=True,
                                even_rows=True, align=True)
        for name, path in items:
            op = grid.operator("object.hardflow_asset_library_place", text=name,
                               icon='FILE_BLEND')
            op.filepath = path
