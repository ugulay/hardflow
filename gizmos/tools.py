# Workspace Tools (left toolbar, T) -- the active-tool counterpart to the
# always-on persistent gizmos. Each tool shows one Hardflow gizmo group while it
# is active. Move/Rotate/Scale/Bevel are Object-Mode gizmo tools; Push/Pull is
# a gizmo tool in Edit Mode (drag selected faces) and an operator-launch tool in
# Object Mode (the raycast hover-pick modal, which has no fixed gizmo to show).
#
# register_tool/unregister_tool are wrapped: they can raise in headless/
# background Blender (no toolbar), and a failure there must not abort the whole
# add-on registration.
import bpy
from bpy.types import WorkSpaceTool


class HARDFLOW_T_move(WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = "hardflow.move"
    bl_label = "Hardflow Move"
    bl_description = "Move the active object with the Hardflow gizmo"
    bl_icon = "ops.transform.translate"
    bl_widget = "HARDFLOW_GGT_move"


class HARDFLOW_T_rotate(WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = "hardflow.rotate"
    bl_label = "Hardflow Rotate"
    bl_description = "Rotate the active object with the Hardflow gizmo"
    bl_icon = "ops.transform.rotate"
    bl_widget = "HARDFLOW_GGT_rotate"


class HARDFLOW_T_scale(WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = "hardflow.scale"
    bl_label = "Hardflow Scale"
    bl_description = "Scale the active object with the Hardflow gizmo"
    bl_icon = "ops.transform.resize"
    bl_widget = "HARDFLOW_GGT_scale"


class HARDFLOW_T_bevel(WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = "hardflow.bevel"
    bl_label = "Hardflow Bevel"
    bl_description = "Drag the gizmo to set the HF_Bevel width (adds it if absent)"
    bl_icon = "ops.mesh.bevel"
    bl_widget = "HARDFLOW_GGT_bevel"


class HARDFLOW_T_push_pull(WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = "hardflow.push_pull"
    bl_label = "Hardflow Push/Pull"
    bl_description = "Hover a face and drag along its normal (Push/Pull)"
    bl_icon = "ops.mesh.extrude_region_move"
    bl_keymap = (
        ("mesh.hardflow_push_pull",
         {"type": 'LEFTMOUSE', "value": 'PRESS'}, None),
    )


class HARDFLOW_T_push_pull_edit(WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'EDIT_MESH'
    bl_idname = "hardflow.push_pull_edit"
    bl_label = "Hardflow Push/Pull"
    bl_description = "Drag the gizmo to extrude the selected faces along their normal"
    bl_icon = "ops.mesh.extrude_region_move"
    bl_widget = "HARDFLOW_GGT_push_pull"


# (tool class, register_tool kwargs). `after` chains them so they sit together
# below the built-in transform tools.
#
# The anchor is `builtin.transform`, NOT `builtin.scale`: scale lives inside the
# (scale, scale_cage) *group tuple*, and `bpy.utils.register_tool` splices an
# `after` match into the group it was found in. That buried every Hardflow tool
# in the built-in Scale dropdown and -- with `separator=True` -- wrote a bare
# `None` between `builtin.scale_cage` and `hardflow.move`. Blender's own
# `ToolSelectPanelHelper._tool_get_group_by_id` walks group members unguarded,
# so that `None` raised `AttributeError: 'NoneType' object has no attribute
# 'idname'` on every toolbar redraw and tool-button hover (issue #4).
#
# No `separator` on the first tool either: Blender already places one after
# `builtin.transform`, and a second would draw a double gap.
_TOOLS = (
    (HARDFLOW_T_move, {"after": {"builtin.transform"}}),
    (HARDFLOW_T_rotate, {"after": {"hardflow.move"}}),
    (HARDFLOW_T_scale, {"after": {"hardflow.rotate"}}),
    (HARDFLOW_T_push_pull, {"after": {"hardflow.scale"}}),
    (HARDFLOW_T_bevel, {"after": {"hardflow.push_pull"}}),
    (HARDFLOW_T_push_pull_edit, {"separator": True}),
)


def _toolbar_items(space_type, context_mode):
    """The live toolbar list for a space/mode, or None when unavailable."""
    try:
        from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
        cls = ToolSelectPanelHelper._tool_class_from_space_type(space_type)
        if cls is None:
            return None
        return cls._tools.get(context_mode)
    except Exception:                                 # noqa: BLE001
        return None


def _anchor_is_standalone(cls, after):
    """
    True when every `after` id is a top-level (non-grouped) toolbar entry.

    Guards the issue-#4 failure mode generically: if a future Blender moves our
    anchor inside a group tuple, inserting after it would nest Hardflow's tools
    in that group -- and a `separator` would drop a `None` in there, which
    Blender's group iteration cannot survive. In that case we drop `after` and
    append to the end of the toolbar instead: worse placement, never a crash.
    Group entries are plain tuples; a `ToolDef` is a NamedTuple, hence the
    `type(...) is tuple` test (the same one Blender uses).
    """
    items = _toolbar_items(cls.bl_space_type, cls.bl_context_mode)
    if items is None:
        return False
    standalone = {
        item.idname for item in items
        if item is not None and type(item) is not tuple
    }
    return after <= standalone


def register():
    for cls, kwargs in _TOOLS:
        after = kwargs.get("after")
        if after and not _anchor_is_standalone(cls, after):
            print("Hardflow: toolbar anchor", sorted(after),
                  "is grouped/missing, appending", cls.bl_idname, "instead")
            kwargs = {k: v for k, v in kwargs.items() if k != "after"}
        try:
            bpy.utils.register_tool(cls, **kwargs)
        except Exception as ex:                       # noqa: BLE001
            print("Hardflow: skipped tool", cls.bl_idname, "->", ex)


def unregister():
    for cls, _kwargs in reversed(_TOOLS):
        try:
            bpy.utils.unregister_tool(cls)
        except Exception:                             # noqa: BLE001
            pass
