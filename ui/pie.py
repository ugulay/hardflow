# Hard Ops style pie menu: access all operators from a single shortcut.
import bpy
from bpy.types import Menu


class HARDFLOW_MT_pie(Menu):
    bl_label = "Hardflow"

    def draw(self, context):
        pie = self.layout.menu_pie()

        # Left
        pie.operator("mesh.hardflow_draw", text="Cut", icon='MOD_BOOLEAN').mode = 'CUT'
        # Right
        pie.operator("mesh.hardflow_draw", text="Slice", icon='MOD_EDGESPLIT').mode = 'SLICE'
        # Bottom
        op = pie.operator("mesh.hardflow_draw", text="Make", icon='MESH_PLANE')
        op.mode = 'MAKE'
        # Top
        pie.operator("object.hardflow_bevel", text="Bevel", icon='MOD_BEVEL')
        # Corner slots
        pie.operator("object.hardflow_mirror", text="Mirror", icon='MOD_MIRROR')
        circle = pie.operator("mesh.hardflow_draw", text="Circle Cut", icon='MESH_CIRCLE')
        circle.shape = 'CIRCLE'
        circle.mode = 'CUT'
        pie.operator("mesh.hardflow_pipe", text="Pipe", icon='MOD_SCREW')
        pie.operator("object.hardflow_clean", text="Clean", icon='BRUSH_DATA')
