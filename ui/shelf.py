# Viewport Asset Shelf for the decal + INSERT library.
#
# The N-panel grids are fine for picking from a short list, but they are a
# narrow sidebar column: the shelf is the wide, preview-first strip along the
# bottom of the viewport that Blender itself uses for brushes and poses, and it
# is where a kitbash library belongs.
#
# One shelf, not two. A shelf region shows a single shelf type at a time, so
# splitting decals and INSERTs into separate shelves would mean mode-juggling
# to pick between them; instead this one accepts both kinds and the activate
# operator dispatches on the clicked asset's id_type. The user's own image and
# object assets show up here too -- filtering strictly to Hardflow's catalogs
# would hide the library they already have.
#
# A shelf browses *assets*, which live inside .blend files, so the loose PNGs
# in library/decals are invisible to it; tools/make_library.py republishes them
# as marked image assets in library/catalog/decals.blend, and
# preferences.register_asset_library() points Blender at the whole folder.
import bpy
from bpy.types import AssetShelf, Operator


class HARDFLOW_AST_library(AssetShelf):
    bl_idname = "HARDFLOW_AST_library"
    bl_space_type = 'VIEW_3D'
    bl_activate_operator = "object.hardflow_shelf_place"
    bl_default_preview_size = 64
    # Deliberately NOT DEFAULT_VISIBLE: a third-party add-on should not push a
    # shelf into every viewport unasked. View > Asset Shelf opens it, and the
    # N-panel says so.

    @classmethod
    def poll(cls, context):
        # Both placement tools are Object-Mode raycast modals.
        return context.mode == 'OBJECT'

    @classmethod
    def asset_poll(cls, asset):
        # Exactly the two kinds Hardflow can place.
        return asset.id_type in {'IMAGE', 'OBJECT'}


def _asset_image(asset):
    """The image datablock for an IMAGE asset, appending it when it is not
    already in this file. Returns None when it cannot be resolved."""
    if asset.local_id is not None:
        return asset.local_id
    path = asset.full_library_path
    if not path:
        return None
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.images = [n for n in src.images if n == asset.name]
    loaded = [i for i in dst.images if i is not None]
    return loaded[0] if loaded else None


class HARDFLOW_OT_shelf_place(Operator):
    bl_idname = "object.hardflow_shelf_place"
    bl_label = "Place Asset"
    bl_description = ("Place the clicked asset on the surface under the cursor: "
                      "an image becomes a decal, an object becomes an INSERT")
    bl_options = {'REGISTER', 'UNDO'}

    # Blender hands an activate operator the asset's library coordinates. They
    # are declared so the assignment never fails, but the resolution goes
    # through context.asset, which is the whole AssetRepresentation (id_type,
    # library path, and the local datablock when there is one).
    asset_library_type: bpy.props.StringProperty(options={'SKIP_SAVE'})
    asset_library_identifier: bpy.props.StringProperty(options={'SKIP_SAVE'})
    relative_asset_identifier: bpy.props.StringProperty(options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        asset = getattr(context, "asset", None)
        if asset is None:
            self.report({'ERROR'}, "No asset under the cursor")
            return {'CANCELLED'}

        if asset.id_type == 'IMAGE':
            img = _asset_image(asset)
            if img is None:
                self.report({'ERROR'},
                            "Could not load image asset '%s'" % asset.name)
                return {'CANCELLED'}
            return bpy.ops.object.hardflow_place_decal(
                'INVOKE_DEFAULT', image_name=img.name)

        if asset.id_type == 'OBJECT':
            path = asset.full_library_path
            if not path:
                # An object asset already in this file has no library path to
                # append from; the placement modal needs one.
                self.report({'WARNING'},
                            "'%s' is local to this file -- use the Assets "
                            "panel to place it" % asset.name)
                return {'CANCELLED'}
            return bpy.ops.object.hardflow_place_asset(
                'INVOKE_DEFAULT', filepath=path, object_name=asset.name)

        self.report({'WARNING'}, "Hardflow places image and object assets")
        return {'CANCELLED'}
