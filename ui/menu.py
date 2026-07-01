# 3D-View header dropdown: a classic "Hardflow" menu next to View/Select/Add.
#
# Complements the Alt+Q pie (ui/pie.py): the pie is fast for the modeling tools;
# this dropdown is the discoverable, keyboard-free home for EVERY tool -- it adds
# the Decals and Assets categories the pie has no room for. Both are thin: they
# only fire operators that already exist.
#
# The categories are data-driven (see the *_ITEMS tables) so adding a tool is a
# one-line edit; each submenu just renders its table.
import bpy
from bpy.types import Menu

from ..core import decal


# Each item is (operator_idname, label, icon, {properties}); None = separator.
# Lead with the hero (Cut), then the other operations, then the Polyline and
# shape variants, then the selected-object boolean + finalize.
_BOOLEAN_ITEMS = (
    ("mesh.hardflow_draw", "Cut", 'MOD_BOOLEAN', {'mode': 'CUT'}),
    ("mesh.hardflow_draw", "Slice", 'MOD_EDGESPLIT', {'mode': 'SLICE'}),
    ("mesh.hardflow_draw", "Make (Union)", 'MESH_PLANE', {'mode': 'MAKE'}),
    ("mesh.hardflow_draw", "Join (Add Solid)", 'MESH_CUBE', {'mode': 'JOIN'}),
    ("mesh.hardflow_draw", "Intersect", 'MOD_BOOLEAN', {'mode': 'INTERSECT'}),
    ("mesh.hardflow_draw", "Knife (Score)", 'MOD_LINEART', {'mode': 'KNIFE'}),
    None,
    ("mesh.hardflow_draw", "Polyline Trim", 'IPO_LINEAR', {'shape': 'POLY', 'mode': 'CUT'}),
    ("mesh.hardflow_draw", "Polyline Add", 'IPO_LINEAR', {'shape': 'POLY', 'mode': 'MAKE'}),
    None,
    ("mesh.hardflow_draw", "Circle Cut", 'MESH_CIRCLE', {'shape': 'CIRCLE', 'mode': 'CUT'}),
    ("mesh.hardflow_draw", "N-gon Cut", 'MESH_CYLINDER', {'shape': 'NGON', 'mode': 'CUT'}),
    ("mesh.hardflow_draw", "Slot Cut", 'MESH_CAPSULE', {'shape': 'SLOT', 'mode': 'CUT'}),
    ("mesh.hardflow_draw", "Star Cut", 'SOLO_ON', {'shape': 'STAR', 'mode': 'CUT'}),
    ("mesh.hardflow_draw", "Arc Cut", 'MOD_SIMPLEDEFORM', {'shape': 'ARC', 'mode': 'CUT'}),
    None,
    ("object.hardflow_boolean", "Boolean (Selected)", 'MOD_BOOLEAN', {}),
    ("object.hardflow_apply_cutters", "Apply Cutters", 'CHECKMARK', {}),
)

# Build = create geometry: primitives, sketch faces, construction helpers.
_BUILD_ITEMS = (
    ("object.hardflow_add_primitive", "Cube", 'MESH_CUBE', {'kind': 'CUBE'}),
    ("object.hardflow_add_primitive", "Plane", 'MESH_PLANE', {'kind': 'PLANE'}),
    ("object.hardflow_add_primitive", "Cylinder", 'MESH_CYLINDER',
     {'kind': 'CYLINDER'}),
    ("object.hardflow_add_primitive", "Cone", 'CONE', {'kind': 'CONE'}),
    ("object.hardflow_add_primitive", "Sphere", 'MESH_UVSPHERE',
     {'kind': 'SPHERE'}),
    ("object.hardflow_add_primitive", "Tube", 'MESH_CYLINDER', {'kind': 'TUBE'}),
    None,
    ("mesh.hardflow_draw", "Rectangle", 'MESH_PLANE', {'shape': 'BOX', 'mode': 'FACE'}),
    ("mesh.hardflow_draw", "Polygon", 'MESH_DATA', {'shape': 'POLY', 'mode': 'FACE'}),
    ("mesh.hardflow_draw", "Circle", 'MESH_CIRCLE', {'shape': 'CIRCLE', 'mode': 'FACE'}),
    ("mesh.hardflow_draw", "N-gon", 'MESH_CYLINDER', {'shape': 'NGON', 'mode': 'FACE'}),
    None,
    ("object.hardflow_add_grid", "Construction Grid", 'MESH_GRID', {}),
    ("object.hardflow_add_guide", "Guide Line", 'IPO_LINEAR', {}),
    ("object.hardflow_loft", "Loft / Bridge", 'MOD_SIMPLEDEFORM', {}),
)

# Edit = direct-modeling tools that reshape existing geometry.
_EDIT_ITEMS = (
    ("mesh.hardflow_push_pull", "Push/Pull", 'EMPTY_SINGLE_ARROW', {}),
    ("mesh.hardflow_offset", "Offset", 'MOD_SOLIDIFY', {}),
    None,
    ("mesh.hardflow_edge_bevel", "Edge Bevel", 'MOD_BEVEL', {}),
    ("mesh.hardflow_loop_cut", "Loop Cut", 'MOD_MULTIRES', {}),
    None,
    ("mesh.hardflow_mode_knife", "HardFlow Mode: Knife", 'MOD_LINEART', {}),
    ("mesh.hardflow_mode_extrude", "HardFlow Mode: Extrude",
     'MOD_SIMPLEDEFORM', {}),
)

_DISPLAY_ITEMS = (
    ("object.hardflow_display_toggle", "Wireframe", 'SHADING_WIRE',
     {'mode': 'WIRE'}),
    ("object.hardflow_display_toggle", "Sharp Edges", 'SNAP_EDGE',
     {'mode': 'SHARP'}),
    ("object.hardflow_display_toggle", "Cutters", 'MOD_BOOLEAN',
     {'mode': 'CUTTERS'}),
    None,
    ("object.hardflow_random_color", "Random Colors", 'COLOR', {}),
    ("object.hardflow_copy_material", "Copy Material", 'MATERIAL', {}),
    ("mesh.hardflow_edge_weight", "Edge Weight (Edit)", 'MOD_BEVEL', {}),
    None,
    ("object.hardflow_recalc_normals", "Recalculate Normals", 'NORMALS_FACE', {}),
)

_CURVE_ITEMS = (
    ("mesh.hardflow_pipe", "Pipe", 'MOD_SCREW', {}),
    ("mesh.hardflow_cable", "Cable / Rope", 'FORCE_CURVE', {}),
    ("mesh.hardflow_sweep", "Sweep (Follow Me)", 'MOD_SIMPLEDEFORM', {}),
)

_ASSET_ITEMS = (
    ("object.hardflow_load_asset", "Place INSERT...", 'IMPORT', {}),
    ("object.hardflow_material_insert", "Material INSERT...", 'MATERIAL', {}),
    None,
    ("object.hardflow_mark_asset", "Mark as Asset", 'OBJECT_DATA', {}),
    ("object.hardflow_export_asset", "Export INSERT...", 'EXPORT', {}),
)


def _render(layout, items):
    """Render an item table into a menu/column layout."""
    for entry in items:
        if entry is None:
            layout.separator()
            continue
        idname, text, icon, props = entry
        op = layout.operator(idname, text=text, icon=icon)
        for key, val in props.items():
            setattr(op, key, val)


class HARDFLOW_MT_menu_boolean(Menu):
    bl_label = "Boolean"

    def draw(self, context):
        _render(self.layout, _BOOLEAN_ITEMS)


class HARDFLOW_MT_menu_build(Menu):
    bl_label = "Build"

    def draw(self, context):
        _render(self.layout, _BUILD_ITEMS)


class HARDFLOW_MT_menu_edit(Menu):
    bl_label = "Edit"

    def draw(self, context):
        _render(self.layout, _EDIT_ITEMS)


class HARDFLOW_MT_menu_curves(Menu):
    bl_label = "Curves"

    def draw(self, context):
        _render(self.layout, _CURVE_ITEMS)


class HARDFLOW_MT_menu_display(Menu):
    bl_label = "Display & Mesh"

    def draw(self, context):
        _render(self.layout, _DISPLAY_ITEMS)


class HARDFLOW_MT_menu_decals(Menu):
    bl_label = "Decals"

    def draw(self, context):
        layout = self.layout
        for type_id, label, _desc in decal.DECAL_TYPES:
            layout.operator("object.hardflow_place_decal",
                            text=label, icon='TEXTURE').decal_type = type_id
        layout.separator()
        layout.operator("object.hardflow_load_decal_image",
                        text="Place Image...", icon='IMAGE_DATA')
        layout.operator("object.hardflow_load_trim_sheet",
                        text="Load Trim Sheet...", icon='UV_DATA')
        layout.separator()
        layout.operator("object.hardflow_create_decal",
                        text="Create from High-poly", icon='RENDER_STILL')
        layout.operator("object.hardflow_match_decal",
                        text="Match to Surface", icon='NODE_MATERIAL')
        layout.operator("object.hardflow_conform_decal",
                        text="Auto-cut to Surface", icon='MOD_SHRINKWRAP')
        layout.operator("object.hardflow_transfer_decal",
                        text="Transfer to Surface", icon='EXPORT')
        layout.operator("object.hardflow_atlas_decals",
                        text="Atlas Decals", icon='IMGDISPLAY')


class HARDFLOW_MT_menu_assets(Menu):
    bl_label = "Assets"

    def draw(self, context):
        _render(self.layout, _ASSET_ITEMS)


class HARDFLOW_MT_menu(Menu):
    bl_label = "Hardflow"

    def draw(self, context):
        layout = self.layout
        # Same category order as the pie + the N-panel: learn it once.
        layout.menu("HARDFLOW_MT_menu_boolean", icon='MOD_BOOLEAN')
        layout.menu("HARDFLOW_MT_menu_build", icon='MESH_GRID')
        layout.menu("HARDFLOW_MT_menu_edit", icon='TOOL_SETTINGS')
        layout.menu("HARDFLOW_MT_menu_curves", icon='MOD_SCREW')
        layout.menu("HARDFLOW_MT_menu_display", icon='OVERLAY')
        layout.separator()
        layout.menu("HARDFLOW_MT_menu_decals", icon='TEXTURE')
        layout.menu("HARDFLOW_MT_menu_assets", icon='FILE_BLEND')
        layout.separator()
        layout.operator("wm.call_menu_pie", text="Pie Menu",
                        icon='COLLAPSEMENU').name = "HARDFLOW_MT_pie"


def _draw_header(self, context):
    """Inject the top-level menu into the 3D-View header menu bar."""
    self.layout.menu("HARDFLOW_MT_menu")


def register():
    bpy.types.VIEW3D_MT_editor_menus.append(_draw_header)


def unregister():
    bpy.types.VIEW3D_MT_editor_menus.remove(_draw_header)
