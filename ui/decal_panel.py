# N-panel "Decals" section: place by type + the placed-decal list (hide/show,
# select, delete) -- mirrors the "Cutters" panel.
import bpy
from bpy.types import Panel

from ..core import decal
from ..preferences import get_prefs


class HARDFLOW_PT_decals(Panel):
    bl_label = "Decals"
    bl_idname = "HARDFLOW_PT_decals"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.label(text="Place on Surface", icon='TEXTURE')
        for type_id, label, _desc in decal.DECAL_TYPES:
            col.operator("object.hardflow_place_decal",
                         text=label).decal_type = type_id

        # Depth: the height-map channel that drives Parallax + Relief on the NEXT
        # image decal placed (reads/writes the add-on prefs, mirrored here for
        # quick access).
        prefs = get_prefs(context)
        depth = layout.box().column(align=True)
        depth.label(text="Depth (Image Decals)", icon='MOD_DISPLACE')
        depth.prop(prefs, "decal_bump_strength")
        depth.prop(prefs, "decal_parallax", text="Parallax Occlusion")
        if prefs.decal_parallax:
            row = depth.row(align=True)
            row.prop(prefs, "decal_parallax_depth", text="Depth")
            row.prop(prefs, "decal_parallax_layers", text="Layers")
        row = depth.row(align=True)
        row.prop_search(prefs, "decal_height_image", bpy.data, "images",
                        text="Height")
        row.operator("object.hardflow_load_height_map", text="", icon='FILE_FOLDER')
        depth.prop(prefs, "decal_height_invert")

        coll = bpy.data.collections.get(decal.DECAL_COLLECTION)
        if coll is None or not coll.objects:
            layout.label(text="No decals placed", icon='INFO')
            return

        col.operator("object.hardflow_create_decal", text="Create from High-poly",
                     icon='RENDER_STILL')

        layout.prop(coll, "hide_viewport", text="Hide collection",
                    icon='HIDE_ON' if coll.hide_viewport else 'HIDE_OFF')
        layout.operator("object.hardflow_atlas_decals", icon='IMGDISPLAY')
        box = layout.box().column(align=True)
        for ob in coll.objects:
            row = box.row(align=True)
            row.operator("object.hardflow_select_decal", text=ob.name,
                         icon='TEXTURE', emboss=False).name = ob.name
            row.prop(ob, "hide_viewport", text="",
                     icon='HIDE_ON' if ob.hide_viewport else 'HIDE_OFF',
                     emboss=False)
            row.operator("object.hardflow_match_decal", text="",
                         icon='NODE_MATERIAL', emboss=False).name = ob.name
            row.operator("object.hardflow_conform_decal", text="",
                         icon='MOD_SHRINKWRAP', emboss=False).name = ob.name
            row.operator("object.hardflow_bake_decal", text="",
                         icon='RENDER_STILL', emboss=False).name = ob.name
            row.operator("object.hardflow_remove_decal", text="",
                         icon='X', emboss=False).name = ob.name
