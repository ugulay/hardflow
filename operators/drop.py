# Drag-and-drop into the 3D viewport.
#
# Drag a PNG out of the file manager onto a model and it becomes a decal under
# the cursor; drag a .blend and it becomes an INSERT. Both land straight in the
# existing placement modal, so the drop *starts* the familiar tool (wheel =
# scale, [ ] = roll, click = place, Esc = cancel) rather than dumping an object
# at the origin.
#
# Blender resolves this through FileHandler: a handler ties a set of file
# extensions to an import operator, and `poll_drop` decides which editors accept
# it. Stock Blender already registers two image handlers for the 3D view
# (reference empty, camera background), so a drop that matches several handlers
# showing a small menu is the normal, supported case -- Hardflow simply adds its
# entry to that menu instead of taking the drop over.
#
# The operators themselves are the ones the library grids already use
# (object.hardflow_library_place / object.hardflow_asset_library_place); the
# only thing needed for drag-and-drop is that their `filepath` carries
# SKIP_SAVE, which the API requires so a dropped path is never remembered and
# replayed on a later run.
from bpy.types import FileHandler

from ..core import asset_lib, decal_image


def _exts(extensions):
    """Format an extension set the way FileHandler wants it (".png;.jpg").

    Derived from the same constants the loaders validate against
    (core.decal_image.IMAGE_EXTS / core.asset_lib.ASSET_EXTS), so the formats
    offered on drop can never drift from the formats that actually open."""
    return ";".join(sorted(extensions))


def _poll_view3d(context):
    """Accept the drop in a 3D viewport only.

    Deliberately narrower than bpy_extras.io_utils.poll_file_object_drop, which
    also offers the Outliner: both targets start a modal placement tool that
    needs a viewport and a surface under the cursor, so offering it anywhere
    else would just produce a 'open a 3D viewport' warning.
    """
    area = getattr(context, "area", None)
    return area is not None and area.type == 'VIEW_3D'


class HARDFLOW_FH_decal_image(FileHandler):
    bl_idname = "HARDFLOW_FH_decal_image"
    bl_label = "Hardflow Decal"
    bl_import_operator = "object.hardflow_library_place"
    bl_file_extensions = _exts(decal_image.IMAGE_EXTS)

    @classmethod
    def poll_drop(cls, context):
        return _poll_view3d(context)


class HARDFLOW_FH_asset_blend(FileHandler):
    bl_idname = "HARDFLOW_FH_asset_blend"
    bl_label = "Hardflow INSERT"
    bl_import_operator = "object.hardflow_asset_library_place"
    bl_file_extensions = _exts(asset_lib.ASSET_EXTS)

    @classmethod
    def poll_drop(cls, context):
        return _poll_view3d(context)
