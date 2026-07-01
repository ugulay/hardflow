# Hardflow - open-source hard-surface boolean modeling tool.
# Registration orchestration: gathers submodules, registers classes and shortcuts.
import bpy
from bpy.props import PointerProperty

from . import preferences, keymaps, gizmos
from .operators import (draw_cut, cutters, pipe, decals,
                        boolean_ops, assets, push_pull, offset,
                        construction, hardops, edge_tool, hardflow_mode,
                        trim_editor)
from .ui import (pie, menu, panel, decal_panel, decal_library, asset_panel,
                 trim_panel)

# Registration order doesn't matter, but keep it tidy:
_classes = (
    preferences.HARDFLOW_Preferences,
    draw_cut.HARDFLOW_OT_draw,
    boolean_ops.HARDFLOW_OT_boolean,
    pipe.HARDFLOW_OT_pipe,
    pipe.HARDFLOW_OT_cable,
    pipe.HARDFLOW_OT_sweep,
    push_pull.HARDFLOW_OT_push_pull,
    offset.HARDFLOW_OT_offset,
    edge_tool.HARDFLOW_OT_edge_bevel,
    edge_tool.HARDFLOW_OT_loop_cut,
    hardflow_mode.HARDFLOW_OT_mode_knife,
    hardflow_mode.HARDFLOW_OT_mode_extrude,
    construction.HARDFLOW_OT_add_primitive,
    construction.HARDFLOW_OT_add_guide,
    construction.HARDFLOW_OT_add_grid,
    construction.HARDFLOW_OT_loft,
    hardops.HARDFLOW_OT_edge_weight,
    hardops.HARDFLOW_OT_display_toggle,
    hardops.HARDFLOW_OT_random_color,
    hardops.HARDFLOW_OT_copy_material,
    hardops.HARDFLOW_OT_smart_sharpen,
    hardops.HARDFLOW_OT_recalc_normals,
    cutters.HARDFLOW_OT_apply_cutters,
    cutters.HARDFLOW_OT_select_cutter,
    cutters.HARDFLOW_OT_remove_cutter,
    decals.HARDFLOW_OT_place_decal,
    decals.HARDFLOW_OT_select_decal,
    decals.HARDFLOW_OT_remove_decal,
    decals.HARDFLOW_OT_bake_decal,
    decals.HARDFLOW_OT_load_decal_image,
    decals.HARDFLOW_OT_library_place,
    decals.HARDFLOW_OT_load_trim_sheet,
    decals.HARDFLOW_OT_atlas_decals,
    decals.HARDFLOW_OT_match_decal,
    decals.HARDFLOW_OT_retrim_decal,
    decals.HARDFLOW_OT_conform_decal,
    decals.HARDFLOW_OT_transfer_decal,
    decals.HARDFLOW_OT_create_decal,
    decals.HARDFLOW_OT_library_rename,
    decals.HARDFLOW_OT_library_delete,
    trim_editor.HARDFLOW_TrimRegion,
    trim_editor.HARDFLOW_TrimSheet,
    trim_editor.HARDFLOW_OT_trim_editor,
    trim_editor.HARDFLOW_OT_load_trim_image,
    trim_editor.HARDFLOW_OT_trim_chroma_key,
    trim_editor.HARDFLOW_OT_trim_region_add,
    trim_editor.HARDFLOW_OT_trim_region_remove,
    trim_editor.HARDFLOW_OT_trim_grid_regions,
    trim_editor.HARDFLOW_OT_place_trim_region,
    trim_editor.HARDFLOW_OT_retrim_region,
    assets.HARDFLOW_OT_place_asset,
    assets.HARDFLOW_OT_load_asset,
    assets.HARDFLOW_OT_asset_library_place,
    assets.HARDFLOW_OT_material_insert,
    assets.HARDFLOW_OT_export_asset,
    assets.HARDFLOW_OT_mark_asset,
    pie.HARDFLOW_MT_pie,
    pie.HARDFLOW_MT_pie_boolean,
    pie.HARDFLOW_MT_pie_build,
    pie.HARDFLOW_MT_pie_edit,
    pie.HARDFLOW_MT_pie_curves,
    menu.HARDFLOW_MT_menu,
    menu.HARDFLOW_MT_menu_boolean,
    menu.HARDFLOW_MT_menu_build,
    menu.HARDFLOW_MT_menu_edit,
    menu.HARDFLOW_MT_menu_curves,
    menu.HARDFLOW_MT_menu_display,
    menu.HARDFLOW_MT_menu_decals,
    menu.HARDFLOW_MT_menu_assets,
    panel.HARDFLOW_PT_tools,
    panel.HARDFLOW_PT_gizmos,
    panel.HARDFLOW_PT_snap,
    panel.HARDFLOW_PT_cutter_options,
    panel.HARDFLOW_PT_modifiers,
    panel.HARDFLOW_PT_cutters,
    decal_panel.HARDFLOW_PT_decals,
    decal_library.HARDFLOW_PT_decal_library,
    trim_panel.HARDFLOW_PT_trim,
    asset_panel.HARDFLOW_PT_assets,
    asset_panel.HARDFLOW_PT_asset_library,
)

def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    # Trim-sheet region data lives on the Image datablock (travels with the
    # sheet, saves with the .blend); the scene points at the active sheet. The
    # TrimSheet/TrimRegion groups are registered above, so the pointers resolve.
    bpy.types.Image.hardflow_trim = PointerProperty(
        type=trim_editor.HARDFLOW_TrimSheet)
    bpy.types.Scene.hardflow_trim_image = PointerProperty(type=bpy.types.Image)
    decal_library.register()
    menu.register()        # header dropdown (after the menu classes exist)
    keymaps.register_keymaps()
    # Gizmos last + guarded: gizmo/Workspace-Tool registration can raise in
    # headless or edge contexts, and that must not strand the rest of the add-on
    # half-registered (menus/keymaps already wired up above).
    try:
        gizmos.register()  # gizmo groups + Workspace Tools + scene settings
    except Exception as ex:  # noqa: BLE001
        print("Hardflow: gizmo registration skipped (%s)" % ex)


def unregister():
    keymaps.unregister_keymaps()
    menu.unregister()
    decal_library.unregister()
    gizmos.unregister()
    if hasattr(bpy.types.Scene, "hardflow_trim_image"):
        del bpy.types.Scene.hardflow_trim_image
    if hasattr(bpy.types.Image, "hardflow_trim"):
        del bpy.types.Image.hardflow_trim
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
