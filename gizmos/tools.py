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
_TOOLS = (
    (HARDFLOW_T_move, {"after": {"builtin.scale"}, "separator": True}),
    (HARDFLOW_T_rotate, {"after": {"hardflow.move"}}),
    (HARDFLOW_T_scale, {"after": {"hardflow.rotate"}}),
    (HARDFLOW_T_push_pull, {"after": {"hardflow.scale"}}),
    (HARDFLOW_T_bevel, {"after": {"hardflow.push_pull"}}),
    (HARDFLOW_T_push_pull_edit, {"separator": True}),
)


def register():
    for cls, kwargs in _TOOLS:
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
