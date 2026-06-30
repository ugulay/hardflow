# Categorized pie menu system.
#
# The toolset outgrew a single 8-slot ring, so the pie is categorized: a MAIN
# pie (Alt+Q) whose ring mixes the three HERO tools every hard-surface session
# leans on -- Cut, Push/Pull, Offset -- with one opener per tool CATEGORY
# (Boolean / Build / Edit / Curves). Every tool is reachable in at most two
# flicks, and adding a tool is a one-line edit in the relevant sub-pie.
#
# Design rules (keep these stable -- pie speed IS muscle memory):
#   * The same four categories appear here, in the header menu, and in the
#     N-panel, in the same order. Learn the layout once, use it everywhere.
#   * The main ring PROMOTES each category's most-used tool for 1-click speed
#     (Cut, Push/Pull, Offset). A sub-pie still lists the full category so the
#     promoted tool has a discoverable home too -- intentional redundancy.
#   * Sub-pies keep "Back" near the South-West slot (matches long-standing
#     habit); the small Curves pie lands it at its natural slot.
#
# Pie slot order: menu_pie() fills W, E, S, N, NW, NE, SW, SE.
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
        # Cardinals (W/E/S/N): the three hero tools + the Boolean category.
        _draw(pie, "mesh.hardflow_draw", "Cut", 'MOD_BOOLEAN', mode='CUT')
        _draw(pie, "mesh.hardflow_push_pull", "Push/Pull", 'EMPTY_SINGLE_ARROW')
        _draw(pie, "mesh.hardflow_offset", "Offset", 'MOD_SOLIDIFY')
        _open(pie, "HARDFLOW_MT_pie_boolean", "Boolean ▸", 'MOD_BOOLEAN')
        # Corners (NW/NE/SW/SE): the remaining categories + finalize.
        _open(pie, "HARDFLOW_MT_pie_build", "Build ▸", 'MESH_GRID')
        _open(pie, "HARDFLOW_MT_pie_edit", "Edit ▸", 'TOOL_SETTINGS')
        _open(pie, "HARDFLOW_MT_pie_curves", "Curves ▸", 'MOD_SCREW')
        _draw(pie, "object.hardflow_apply_cutters", "Apply Cutters", 'CHECKMARK')


class HARDFLOW_MT_pie_boolean(Menu):
    bl_label = "Boolean"

    def draw(self, context):
        pie = self.layout.menu_pie()
        _draw(pie, "mesh.hardflow_draw", "Cut", 'MOD_BOOLEAN', mode='CUT')
        _draw(pie, "mesh.hardflow_draw", "Slice", 'MOD_EDGESPLIT', mode='SLICE')
        _draw(pie, "mesh.hardflow_draw", "Make", 'MESH_PLANE', mode='MAKE')
        _draw(pie, "mesh.hardflow_draw", "Intersect", 'MOD_BOOLEAN',
              mode='INTERSECT')
        _draw(pie, "mesh.hardflow_draw", "Join", 'MESH_CUBE', mode='JOIN')
        _draw(pie, "mesh.hardflow_draw", "Knife", 'MOD_LINEART', mode='KNIFE')
        _open(pie, "HARDFLOW_MT_pie", "◂ Back", 'LOOP_BACK')
        _draw(pie, "object.hardflow_boolean", "Boolean (Sel)", 'MOD_BOOLEAN')


class HARDFLOW_MT_pie_build(Menu):
    bl_label = "Build"

    def draw(self, context):
        pie = self.layout.menu_pie()
        _draw(pie, "object.hardflow_add_primitive", "Cube", 'MESH_CUBE',
              kind='CUBE')
        _draw(pie, "object.hardflow_add_primitive", "Cylinder", 'MESH_CYLINDER',
              kind='CYLINDER')
        _draw(pie, "object.hardflow_add_primitive", "Plane", 'MESH_PLANE',
              kind='PLANE')
        _draw(pie, "object.hardflow_add_primitive", "Sphere", 'MESH_UVSPHERE',
              kind='SPHERE')
        # Sketch a face to model on (ready for Push/Pull / Offset).
        _draw(pie, "mesh.hardflow_draw", "Rectangle", 'MESH_PLANE',
              shape='BOX', mode='FACE')
        _draw(pie, "mesh.hardflow_draw", "Circle", 'MESH_CIRCLE',
              shape='CIRCLE', mode='FACE')
        _open(pie, "HARDFLOW_MT_pie", "◂ Back", 'LOOP_BACK')
        _draw(pie, "object.hardflow_add_grid", "Grid", 'MESH_GRID')


class HARDFLOW_MT_pie_edit(Menu):
    bl_label = "Edit"

    def draw(self, context):
        pie = self.layout.menu_pie()
        _draw(pie, "mesh.hardflow_push_pull", "Push/Pull", 'EMPTY_SINGLE_ARROW')
        _draw(pie, "mesh.hardflow_offset", "Offset", 'MOD_SOLIDIFY')
        _draw(pie, "mesh.hardflow_edge_bevel", "Edge Bevel", 'MOD_BEVEL')
        _draw(pie, "mesh.hardflow_loop_cut", "Loop Cut", 'MOD_MULTIRES')
        _open(pie, "HARDFLOW_MT_pie", "◂ Back", 'LOOP_BACK')


class HARDFLOW_MT_pie_curves(Menu):
    bl_label = "Curves"

    def draw(self, context):
        pie = self.layout.menu_pie()
        _draw(pie, "mesh.hardflow_pipe", "Pipe", 'MOD_SCREW')
        _draw(pie, "mesh.hardflow_cable", "Cable", 'FORCE_CURVE')
        _draw(pie, "mesh.hardflow_sweep", "Sweep", 'MOD_SIMPLEDEFORM')
        _open(pie, "HARDFLOW_MT_pie", "◂ Back", 'LOOP_BACK')
