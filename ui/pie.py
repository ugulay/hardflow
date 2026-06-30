# Hard Ops style pie menu system.
#
# The toolset outgrew a single 8-slot ring, so the pie is now categorized: a
# MAIN pie (Alt+Q) whose slots either fire the most-common operator directly or
# open a focused SUB-pie (Build / Boolean / Modify / Curves). Every tool is
# reachable in at most two clicks, and adding a tool is a one-line edit in the
# relevant sub-pie.
#
# Pie slot order: menu_pie() places calls W, E, S, N, NW, NE, SW, SE.
# Sub-pies keep their SW slot as a "Back" link to the main pie.
import bpy
from bpy.types import Menu


def _open(pie, menu_idname, text, icon):
    """Add a pie slot that opens another pie menu (used for sub-pies + Back)."""
    op = pie.operator("wm.call_menu_pie", text=text, icon=icon)
    op.name = menu_idname


def _draw(pie, idname, text, icon, **props):
    """Add a pie slot that runs an operator, setting any properties."""
    op = pie.operator(idname, text=text, icon=icon)
    for key, val in props.items():
        setattr(op, key, val)


class HARDFLOW_MT_pie(Menu):
    bl_label = "Hardflow"

    def draw(self, context):
        pie = self.layout.menu_pie()
        # W / E / S / N
        _draw(pie, "mesh.hardflow_draw", "Cut", 'MOD_BOOLEAN', mode='CUT')
        _open(pie, "HARDFLOW_MT_pie_build", "Build ▸", 'MESH_GRID')
        _open(pie, "HARDFLOW_MT_pie_modify", "Modify ▸", 'MODIFIER')
        _open(pie, "HARDFLOW_MT_pie_boolean", "Boolean ▸", 'MOD_BOOLEAN')
        # Corners: NW / NE / SW / SE
        _draw(pie, "object.hardflow_bevel", "Bevel", 'MOD_BEVEL')
        _draw(pie, "object.hardflow_mirror", "Mirror", 'MOD_MIRROR')
        _open(pie, "HARDFLOW_MT_pie_curves", "Curves ▸", 'MOD_SCREW')
        _draw(pie, "object.hardflow_clean", "Clean", 'BRUSH_DATA')


class HARDFLOW_MT_pie_build(Menu):
    bl_label = "Build (SketchUp)"

    def draw(self, context):
        pie = self.layout.menu_pie()
        # Sketch a face, then Push/Pull / Offset it.
        _draw(pie, "mesh.hardflow_draw", "Rectangle", 'MESH_PLANE',
              shape='BOX', mode='FACE')
        _draw(pie, "mesh.hardflow_push_pull", "Push/Pull", 'EMPTY_SINGLE_ARROW')
        _draw(pie, "mesh.hardflow_offset", "Offset", 'MOD_SOLIDIFY')
        _draw(pie, "mesh.hardflow_draw", "Line", 'IPO_LINEAR',
              shape='POLY', mode='FACE')
        _draw(pie, "object.hardflow_add_grid", "Grid", 'MESH_GRID')
        _draw(pie, "mesh.hardflow_draw", "Circle", 'MESH_CIRCLE',
              shape='CIRCLE', mode='FACE')
        _open(pie, "HARDFLOW_MT_pie", "◂ Back", 'LOOP_BACK')
        _draw(pie, "mesh.hardflow_draw", "N-gon", 'MESH_CYLINDER',
              shape='NGON', mode='FACE')


class HARDFLOW_MT_pie_boolean(Menu):
    bl_label = "Boolean"

    def draw(self, context):
        pie = self.layout.menu_pie()
        _draw(pie, "mesh.hardflow_draw", "Cut", 'MOD_BOOLEAN', mode='CUT')
        _draw(pie, "mesh.hardflow_draw", "Slice", 'MOD_EDGESPLIT', mode='SLICE')
        _draw(pie, "mesh.hardflow_draw", "Make", 'MESH_PLANE', mode='MAKE')
        _draw(pie, "mesh.hardflow_draw", "Polyline Trim", 'IPO_LINEAR',
              shape='POLY', mode='CUT')
        _draw(pie, "object.hardflow_boolean", "Boolean (Sel)", 'MOD_BOOLEAN')
        _draw(pie, "mesh.hardflow_draw", "N-gon Cut", 'MESH_CYLINDER',
              shape='NGON', mode='CUT')
        _open(pie, "HARDFLOW_MT_pie", "◂ Back", 'LOOP_BACK')
        _draw(pie, "object.hardflow_apply_cutters", "Apply Cutters", 'CHECKMARK')


class HARDFLOW_MT_pie_modify(Menu):
    bl_label = "Modify"

    def draw(self, context):
        pie = self.layout.menu_pie()
        _draw(pie, "object.hardflow_bevel", "Bevel", 'MOD_BEVEL')
        _draw(pie, "object.hardflow_mirror", "Mirror", 'MOD_MIRROR')
        _draw(pie, "object.hardflow_array", "Array", 'MOD_ARRAY')
        _draw(pie, "object.hardflow_radial_array", "Radial", 'MOD_ARRAY')
        _draw(pie, "object.hardflow_symmetrize", "Symmetrize", 'MOD_MIRROR')
        _draw(pie, "object.hardflow_sharpen", "Sharpen", 'MOD_BEVEL')
        _open(pie, "HARDFLOW_MT_pie", "◂ Back", 'LOOP_BACK')
        _draw(pie, "object.hardflow_clean", "Clean", 'BRUSH_DATA')


class HARDFLOW_MT_pie_curves(Menu):
    bl_label = "Curves"

    def draw(self, context):
        pie = self.layout.menu_pie()
        _draw(pie, "mesh.hardflow_pipe", "Pipe", 'MOD_SCREW')
        _draw(pie, "mesh.hardflow_cable", "Cable", 'FORCE_CURVE')
        _open(pie, "HARDFLOW_MT_pie", "◂ Back", 'LOOP_BACK')
