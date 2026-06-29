# Hardflow - open-source hard-surface boolean modeling tool.
# Registration orchestration: gathers submodules, registers classes and shortcuts.
import bpy

from . import preferences, keymaps
from .operators import (draw_cut, modifiers, cutters, pipe, decals,
                        boolean_ops, array, assets, push_pull, offset,
                        construction, hardops)
from .ui import pie, menu, panel, decal_panel, decal_library, asset_panel

# Registration order doesn't matter, but keep it tidy:
_classes = (
    preferences.HARDFLOW_Preferences,
    draw_cut.HARDFLOW_OT_draw,
    modifiers.HARDFLOW_OT_bevel,
    modifiers.HARDFLOW_OT_mirror,
    modifiers.HARDFLOW_OT_clean,
    modifiers.HARDFLOW_OT_symmetrize,
    modifiers.HARDFLOW_OT_sharpen,
    boolean_ops.HARDFLOW_OT_boolean,
    array.HARDFLOW_OT_array,
    array.HARDFLOW_OT_radial_array,
    pipe.HARDFLOW_OT_pipe,
    pipe.HARDFLOW_OT_cable,
    push_pull.HARDFLOW_OT_push_pull,
    offset.HARDFLOW_OT_offset,
    construction.HARDFLOW_OT_add_grid,
    construction.HARDFLOW_OT_loft,
    hardops.HARDFLOW_OT_dice,
    hardops.HARDFLOW_OT_edge_weight,
    hardops.HARDFLOW_OT_display_toggle,
    hardops.HARDFLOW_OT_random_color,
    hardops.HARDFLOW_OT_copy_material,
    hardops.HARDFLOW_OT_add_step,
    hardops.HARDFLOW_OT_add_taper,
    hardops.HARDFLOW_OT_add_knurl,
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
    decals.HARDFLOW_OT_create_decal,
    decals.HARDFLOW_OT_library_rename,
    decals.HARDFLOW_OT_library_delete,
    assets.HARDFLOW_OT_place_asset,
    assets.HARDFLOW_OT_load_asset,
    assets.HARDFLOW_OT_asset_library_place,
    assets.HARDFLOW_OT_material_insert,
    assets.HARDFLOW_OT_export_asset,
    assets.HARDFLOW_OT_mark_asset,
    pie.HARDFLOW_MT_pie,
    pie.HARDFLOW_MT_pie_build,
    pie.HARDFLOW_MT_pie_boolean,
    pie.HARDFLOW_MT_pie_modify,
    pie.HARDFLOW_MT_pie_curves,
    menu.HARDFLOW_MT_menu,
    menu.HARDFLOW_MT_menu_build,
    menu.HARDFLOW_MT_menu_boolean,
    menu.HARDFLOW_MT_menu_modify,
    menu.HARDFLOW_MT_menu_curves,
    menu.HARDFLOW_MT_menu_greeble,
    menu.HARDFLOW_MT_menu_decals,
    menu.HARDFLOW_MT_menu_assets,
    panel.HARDFLOW_PT_tools,
    panel.HARDFLOW_PT_snap,
    panel.HARDFLOW_PT_modifiers,
    panel.HARDFLOW_PT_cutters,
    decal_panel.HARDFLOW_PT_decals,
    decal_library.HARDFLOW_PT_decal_library,
    asset_panel.HARDFLOW_PT_assets,
    asset_panel.HARDFLOW_PT_asset_library,
)

def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    decal_library.register()
    menu.register()        # header dropdown (after the menu classes exist)
    keymaps.register_keymaps()


def unregister():
    keymaps.unregister_keymaps()
    menu.unregister()
    decal_library.unregister()
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
