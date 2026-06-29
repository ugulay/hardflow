# Hardflow - acik kaynak hard-surface boolean modelleme araci.
# Kayit orkestrasyonu: alt modulleri toplar, sinif ve kisayollari kaydeder.
import bpy

from . import preferences
from .operators import draw_cut, modifiers
from .ui import pie

# Kayit sirasi onemli degil ama duzenli olsun:
_classes = (
    preferences.HARDFLOW_Preferences,
    draw_cut.HARDFLOW_OT_draw,
    modifiers.HARDFLOW_OT_bevel,
    modifiers.HARDFLOW_OT_mirror,
    pie.HARDFLOW_MT_pie,
)

_addon_keymaps = []


def _register_keymaps():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return
    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')

    # Pie menu -> Alt+D
    kmi = km.keymap_items.new(
        'wm.call_menu_pie', 'D', 'PRESS', alt=True)
    kmi.properties.name = pie.HARDFLOW_MT_pie.__name__
    _addon_keymaps.append((km, kmi))

    # Dogrudan cut -> Ctrl+Shift+D
    kmi = km.keymap_items.new(
        draw_cut.HARDFLOW_OT_draw.bl_idname, 'D', 'PRESS', ctrl=True, shift=True)
    _addon_keymaps.append((km, kmi))


def _unregister_keymaps():
    for km, kmi in _addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except RuntimeError:
            pass
    _addon_keymaps.clear()


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    _register_keymaps()


def unregister():
    _unregister_keymaps()
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
