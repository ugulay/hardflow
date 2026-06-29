# N-panel "Decal Library" section: an icon grid of the images in the user's decal
# library folder (preference `decal_library_path`). Clicking a thumbnail loads the
# image and starts the place-decal tool. There is also a "Decal from Image" button
# that picks any image from disk.
#
# Thumbnails use a bpy.utils.previews collection, lazily filled as folders are
# scanned and freed on unregister. The pure scanning logic lives in
# core/decal_image.py (unit-tested); this module is the bpy/UI glue.
import bpy
import bpy.utils.previews
from bpy.types import Panel

from ..core import decal_image
from ..preferences import get_prefs


_preview_coll = None


def _previews():
    global _preview_coll
    if _preview_coll is None:
        _preview_coll = bpy.utils.previews.new()
    return _preview_coll


def _icon_id(path):
    """Icon id for a library image, loading (and caching) its thumbnail. Returns
    0 if the preview cannot be built, so the caller can fall back to a stock icon."""
    pcoll = _previews()
    item = pcoll.get(path)
    if item is None:
        try:
            item = pcoll.load(path, path, 'IMAGE')
        except (KeyError, RuntimeError):
            return 0
    return item.icon_id


class HARDFLOW_PT_decal_library(Panel):
    bl_label = "Decal Library"
    bl_idname = "HARDFLOW_PT_decal_library"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_decals"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        prefs = get_prefs(context)

        layout.prop(prefs, "decal_library_path", text="")
        row = layout.row(align=True)
        row.operator("object.hardflow_load_decal_image", icon='FILE_IMAGE')
        row.operator("object.hardflow_load_trim_sheet", icon='MESH_GRID')

        folder = bpy.path.abspath(prefs.decal_library_path) \
            if prefs.decal_library_path else ""
        items = decal_image.scan_library(folder)
        if not items:
            layout.label(text="Set a library folder with images", icon='INFO')
            return

        grid = layout.grid_flow(row_major=True, columns=3, even_columns=True,
                                even_rows=True, align=True)
        for name, path in items:
            cell = grid.column(align=True)
            icon = _icon_id(path)
            op = cell.operator("object.hardflow_library_place", text=name,
                               icon_value=icon) if icon else \
                cell.operator("object.hardflow_library_place", text=name,
                              icon='IMAGE_DATA')
            op.filepath = path
            # Editable library: rename / delete the file on disk (v1.7).
            edit = cell.row(align=True)
            edit.operator("object.hardflow_library_rename", text="",
                          icon='GREASEPENCIL').filepath = path
            edit.operator("object.hardflow_library_delete", text="",
                          icon='TRASH').filepath = path


def register():
    # Previews are created lazily on first draw; nothing to do here.
    pass


def unregister():
    global _preview_coll
    if _preview_coll is not None:
        bpy.utils.previews.remove(_preview_coll)
        _preview_coll = None
