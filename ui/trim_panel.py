# N-panel "Trim Sheet Editor" section (v1.16): pick / load a sheet image, open
# the interactive UV-region editor, and manage the carved regions (place one as
# a decal, re-trim a placed decal, rename, remove). Sits under the Decals panel.
#
# The region data lives on the Image datablock (bpy.types.Image.hardflow_trim);
# the scene points at the active sheet (Scene.hardflow_trim_image). All the ops
# live in operators/trim_editor.py.
from bpy.types import Panel


class HARDFLOW_PT_trim(Panel):
    bl_label = "Trim Sheet Editor"
    bl_idname = "HARDFLOW_PT_trim"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_decals"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.template_ID(scene, "hardflow_trim_image")
        row = layout.row(align=True)
        row.operator("object.hardflow_load_trim_image", text="Load Sheet…",
                     icon='FILE_IMAGE')

        img = getattr(scene, "hardflow_trim_image", None)
        if img is None:
            layout.label(text="Pick or load a trim-sheet image", icon='INFO')
            return

        trim = img.hardflow_trim
        row = layout.row(align=True)
        row.operator("object.hardflow_trim_editor", text="Open Editor",
                     icon='UV_DATA')
        row.operator("object.hardflow_trim_grid_regions", text="From Grid",
                     icon='MESH_GRID')
        layout.operator("object.hardflow_trim_chroma_key",
                        text="Remove Background…", icon='IMAGE_ALPHA')

        if not len(trim.regions):
            layout.label(text="No regions yet — Open Editor to cut", icon='INFO')
        else:
            box = layout.box().column(align=True)
            for i, r in enumerate(trim.regions):
                row = box.row(align=True)
                row.prop(r, "name", text="")
                row.operator("object.hardflow_place_trim_region", text="",
                             icon='TEXTURE').index = i
                row.operator("object.hardflow_retrim_region", text="",
                             icon='GROUP_UVS').index = i
                row.operator("object.hardflow_trim_region_remove", text="",
                             icon='X').index = i
        layout.operator("object.hardflow_trim_region_add", text="Add Region",
                        icon='ADD')
