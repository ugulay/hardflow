# Keymap registration + rebind UI for preferences.
#
# Defaults: pie menu = Alt+Q, direct cut = Ctrl+Shift+D.
# The user can change these from the standard Blender keymap editor in
# Edit > Preferences > Add-ons > Hardflow; changes are written to the user
# keyconfig and persist across sessions.
import bpy
import rna_keymap_ui

# (km, kmi) pairs -- populated in register, used in draw.
addon_keymaps = []

# Shortcuts owned by this addon (idname, properties.name or None).
# properties_name is only for menu/pie calls; it distinguishes different
# menus of the same idname.
_OWNED = (
    ('wm.call_menu_pie', 'HARDFLOW_MT_pie'),
    ('mesh.hardflow_draw', None),
    ('mesh.hardflow_mode_knife', None),
)


def register_keymaps():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return
    from .operators import draw_cut, hardflow_mode
    from .ui import pie

    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')

    # Pie menu -> Alt+Q  (Alt+D conflicts with Duplicate Linked in Object Mode)
    kmi = km.keymap_items.new('wm.call_menu_pie', 'Q', 'PRESS', alt=True)
    kmi.properties.name = pie.HARDFLOW_MT_pie.__name__
    addon_keymaps.append((km, kmi))

    # Direct cut -> Ctrl+Shift+D
    kmi = km.keymap_items.new(
        draw_cut.HARDFLOW_OT_draw.bl_idname, 'D', 'PRESS', ctrl=True, shift=True)
    addon_keymaps.append((km, kmi))

    # HardFlow Mode -> Ctrl+Shift+X. Enters on the Knife verb; Tab switches to
    # Extrude in-session. (Not a default Blender 3D-View shortcut; rebindable.)
    kmi = km.keymap_items.new(
        hardflow_mode.HARDFLOW_OT_mode_knife.bl_idname, 'X', 'PRESS',
        ctrl=True, shift=True)
    addon_keymaps.append((km, kmi))


def unregister_keymaps():
    for km, kmi in addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except RuntimeError:
            pass
    addon_keymaps.clear()


def _find_user_kmi(km, idname, properties_name):
    """Find the relevant keymap item in the user keyconfig (rebinds are written
    here; the addon keyconfig is a read-only layer)."""
    for kmi in km.keymap_items:
        if kmi.idname != idname:
            continue
        if properties_name is not None:
            if getattr(kmi.properties, 'name', None) != properties_name:
                continue
        return kmi
    return None


def draw_keymap_prefs(layout, context):
    """Draw the shortcuts in preferences with the standard Blender keymap widget."""
    kc = context.window_manager.keyconfigs.user
    km = kc.keymaps.get('3D View')
    if km is None:
        layout.label(text="Shortcuts could not load (no keyconfig)", icon='ERROR')
        return
    for idname, properties_name in _OWNED:
        kmi = _find_user_kmi(km, idname, properties_name)
        if kmi is None:
            continue
        layout.context_pointer_set("keymap", km)
        rna_keymap_ui.draw_kmi([], kc, km, kmi, layout, 0)
