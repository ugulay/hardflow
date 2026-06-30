# Gizmo subsystem: always-on persistent viewport handles + Workspace Tools.
#
# Self-contained registration (its own register/unregister, called from the
# add-on's __init__) keeps the gizmo group / gizmo / tool classes -- which use
# different Blender register paths (register_class vs register_tool) -- out of
# the top-level _classes tuple.
import bpy
from bpy.props import BoolProperty, PointerProperty
from bpy.types import PropertyGroup

from . import custom, groups, tools


def _redraw(self, context):
    """Toggling a gizmo setting must re-poll the gizmo groups, which happens on
    the next viewport redraw -- so nudge every View3D."""
    screen = getattr(context, "screen", None)
    if screen is None:
        return
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


class HARDFLOW_GizmoSettings(PropertyGroup):
    show: BoolProperty(
        name="Always-On Gizmos", default=False, update=_redraw,
        description="Draw the Hardflow gizmos on the active object without "
                    "switching to a tool")
    move: BoolProperty(name="Move", default=True, update=_redraw)
    rotate: BoolProperty(name="Rotate", default=True, update=_redraw)
    scale: BoolProperty(name="Scale", default=False, update=_redraw)
    bevel: BoolProperty(
        name="Bevel Width", default=False, update=_redraw,
        description="Object Mode: drag to set the HF_Bevel modifier width")
    push_pull: BoolProperty(
        name="Push/Pull", default=False, update=_redraw,
        description="Edit Mode: drag the selected faces along their normal")


# Gizmo + GizmoGroup classes (the Gizmo type must come before the groups that
# instantiate it). Workspace Tools register separately via tools.register().
_classes = (
    HARDFLOW_GizmoSettings,
    custom.HARDFLOW_GT_drag_extrude,
    groups.HARDFLOW_GGT_persistent,
    groups.HARDFLOW_GGT_move,
    groups.HARDFLOW_GGT_rotate,
    groups.HARDFLOW_GGT_scale,
    groups.HARDFLOW_GGT_bevel,
    groups.HARDFLOW_GGT_push_pull,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.hardflow_gizmos = PointerProperty(type=HARDFLOW_GizmoSettings)
    tools.register()


def unregister():
    try:
        tools.unregister()
    except Exception:  # noqa: BLE001
        pass
    if hasattr(bpy.types.Scene, "hardflow_gizmos"):
        del bpy.types.Scene.hardflow_gizmos
    # Defensive per-class: register() may have stopped part-way (e.g. headless),
    # so a class in the tuple might never have been registered.
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except (RuntimeError, ValueError):
            pass
