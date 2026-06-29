# Hard Ops tarzi pie menu: tum operatorlere tek kisayoldan eris.
import bpy
from bpy.types import Menu


class HARDFLOW_MT_pie(Menu):
    bl_label = "Hardflow"

    def draw(self, context):
        pie = self.layout.menu_pie()

        # Sol
        pie.operator("mesh.hardflow_draw", text="Cut", icon='MOD_BOOLEAN').mode = 'CUT'
        # Sag
        pie.operator("mesh.hardflow_draw", text="Slice", icon='MOD_EDGESPLIT').mode = 'SLICE'
        # Alt
        op = pie.operator("mesh.hardflow_draw", text="Make", icon='MESH_PLANE')
        op.mode = 'MAKE'
        # Ust
        pie.operator("object.hardflow_bevel", text="Bevel", icon='MOD_BEVEL')
        # Kose slotlari
        pie.operator("object.hardflow_mirror", text="Mirror", icon='MOD_MIRROR')
        circle = pie.operator("mesh.hardflow_draw", text="Circle Cut", icon='MESH_CIRCLE')
        circle.shape = 'CIRCLE'
        circle.mode = 'CUT'
        pie.operator("mesh.hardflow_pipe", text="Pipe", icon='MOD_SCREW')
        pie.operator("object.hardflow_clean", text="Clean", icon='BRUSH_DATA')
