# Hardflow - open-source hard-surface boolean modeling tool.
# Registration orchestration: gathers submodules, registers classes and shortcuts.
import bpy

from . import preferences, keymaps
from .operators import draw_cut, modifiers, cutters, pipe, decals
from .ui import pie, panel, decal_panel

# Registration order doesn't matter, but keep it tidy:
_classes = (
    preferences.HARDFLOW_Preferences,
    draw_cut.HARDFLOW_OT_draw,
    modifiers.HARDFLOW_OT_bevel,
    modifiers.HARDFLOW_OT_mirror,
    modifiers.HARDFLOW_OT_clean,
    pipe.HARDFLOW_OT_pipe,
    cutters.HARDFLOW_OT_apply_cutters,
    cutters.HARDFLOW_OT_select_cutter,
    cutters.HARDFLOW_OT_remove_cutter,
    decals.HARDFLOW_OT_place_decal,
    decals.HARDFLOW_OT_select_decal,
    decals.HARDFLOW_OT_remove_decal,
    decals.HARDFLOW_OT_bake_decal,
    pie.HARDFLOW_MT_pie,
    panel.HARDFLOW_PT_tools,
    panel.HARDFLOW_PT_snap,
    panel.HARDFLOW_PT_cutters,
    decal_panel.HARDFLOW_PT_decals,
)

def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    keymaps.register_keymaps()


def unregister():
    keymaps.unregister_keymaps()
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
