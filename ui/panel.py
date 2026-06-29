# N-panel (View3D > Sidebar > Hardflow): tools, snap settings, cutter list.
import bpy
from bpy.types import Panel

from ..preferences import get_prefs
from ..core import boolean


class HARDFLOW_PT_tools(Panel):
    bl_label = "Hardflow"
    bl_idname = "HARDFLOW_PT_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"

    def draw(self, context):
        layout = self.layout

        col = layout.column(align=True)
        col.label(text="Boolean Draw", icon='MOD_BOOLEAN')
        row = col.row(align=True)
        row.operator("mesh.hardflow_draw", text="Cut").mode = 'CUT'
        row.operator("mesh.hardflow_draw", text="Slice").mode = 'SLICE'
        row.operator("mesh.hardflow_draw", text="Make").mode = 'MAKE'
        circle = col.operator("mesh.hardflow_draw", text="Circle Cut",
                              icon='MESH_CIRCLE')
        circle.shape = 'CIRCLE'
        circle.mode = 'CUT'
        col.operator("object.hardflow_boolean", text="Boolean (Selected)",
                     icon='MOD_BOOLEAN')

        col = layout.column(align=True)
        col.label(text="Modifier", icon='MODIFIER')
        row = col.row(align=True)
        row.operator("object.hardflow_bevel", text="Bevel", icon='MOD_BEVEL')
        row.operator("object.hardflow_mirror", text="Mirror", icon='MOD_MIRROR')
        row = col.row(align=True)
        row.operator("object.hardflow_array", text="Array", icon='MOD_ARRAY')
        row.operator("object.hardflow_radial_array", text="Radial",
                     icon='MOD_ARRAY')
        row = col.row(align=True)
        row.operator("object.hardflow_symmetrize", text="Symmetrize",
                     icon='MOD_MIRROR')
        row.operator("object.hardflow_sharpen", text="Sharpen", icon='MOD_BEVEL')
        col.operator("object.hardflow_clean", text="Clean", icon='BRUSH_DATA')
        col.operator("mesh.hardflow_pipe", text="Pipe", icon='MOD_SCREW')


class HARDFLOW_PT_snap(Panel):
    bl_label = "Snapping & Settings"
    bl_idname = "HARDFLOW_PT_snap"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        prefs = get_prefs(context)
        col = layout.column()
        col.prop(prefs, "snap_enabled")
        col.prop(prefs, "grid_world")
        col.separator()
        col.prop(prefs, "geo_snap")
        col.prop(prefs, "snap_pixels")
        col.prop(prefs, "angle_step")
        col.separator()
        col.prop(prefs, "non_destructive")
        col.prop(prefs, "multi_object")
        col.prop(prefs, "cleanup_after_cut")
        col.prop(prefs, "default_solver")
        col.separator()
        col.prop(prefs, "pipe_radius")
        col.separator()
        col.label(text="Colors (live preview)")
        row = col.row(align=True)
        row.prop(prefs, "line_color", text="")
        row.prop(prefs, "grid_color", text="")


class HARDFLOW_PT_cutters(Panel):
    bl_label = "Cutters"
    bl_idname = "HARDFLOW_PT_cutters"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        if context.active_object is not None:
            layout.operator("object.hardflow_apply_cutters",
                            text="Apply Cutters (Bake)", icon='CHECKMARK')

        coll = bpy.data.collections.get(boolean.CUTTER_COLLECTION)
        if coll is None or not coll.objects:
            layout.label(text="No stashed cutters", icon='INFO')
            layout.label(text="(Cut with non-destructive 'N')")
            return

        layout.prop(coll, "hide_viewport", text="Hide collection",
                    icon='HIDE_ON' if coll.hide_viewport else 'HIDE_OFF')
        box = layout.box().column(align=True)
        for ob in coll.objects:
            row = box.row(align=True)
            row.operator("object.hardflow_select_cutter", text=ob.name,
                         icon='MESH_CUBE', emboss=False).name = ob.name
            row.prop(ob, "hide_viewport", text="",
                     icon='HIDE_ON' if ob.hide_viewport else 'HIDE_OFF',
                     emboss=False)
            row.operator("object.hardflow_remove_cutter", text="",
                         icon='X', emboss=False).name = ob.name
