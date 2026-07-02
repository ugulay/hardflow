# N-panel (View3D > Sidebar > Hardflow): tools, snap settings, cutter list.
import bpy
from bpy.types import Panel
from bpy.props import EnumProperty, PointerProperty

from ..preferences import get_prefs
from ..core import boolean


# Persistent Boolean draw operation for the N-panel: pick the operation once
# (it sticks on the scene), then click any shape to draw with it -- so every
# mode x shape combo is one click instead of a fixed CUT-only shape row. Kept in
# panel.py (its owner) and registered on the Scene by register() below.
DRAW_MODE_ITEMS = [
    ('CUT', "Cut", "Boolean DIFFERENCE -- carve the drawn shape out"),
    ('SLICE', "Slice", "Slice the object in two along the drawn shape"),
    ('MAKE', "Make", "Add geometry (UNION)"),
    ('INTERSECT', "Intersect", "Keep only what's inside the drawn volume"),
    ('JOIN', "Join", "Add the drawn shape as a separate solid (no boolean)"),
    ('KNIFE', "Knife", "Score the surface only (zero-depth cut)"),
]

# Shape launchers for the Boolean draw grid: (shape id, label, icon).
DRAW_SHAPE_ITEMS = [
    ('BOX', "Box", 'MESH_PLANE'),
    ('CIRCLE', "Circle", 'MESH_CIRCLE'),
    ('NGON', "N-gon", 'MESH_CYLINDER'),
    ('SLOT', "Slot", 'MESH_CAPSULE'),
    ('STAR', "Star", 'SOLO_ON'),
    ('ARC', "Arc", 'MOD_SIMPLEDEFORM'),
    ('VENT', "Vent", 'ALIGN_JUSTIFY'),
]


# Single-slot cache for the pre-cut health summary. `mesh_health` rebuilds a
# bmesh, and the N-panel redraws constantly (hover, selection, any UI poke), so
# recomputing it every repaint is pure waste. Keyed on the cheap signals that a
# boolean/delete/add changes (vert + poly count); an Object-Mode edit that keeps
# both counts but alters manifoldness is rare and self-corrects on the next count
# change. Edit Mode is never cached -- object data counts are stale mid-edit.
_HEALTH_CACHE = {"key": None, "summary": ""}


def _cached_health_summary(obj):
    me = obj.data
    if me.is_editmode:
        return boolean._health_summary(obj)
    key = (obj.name, len(me.vertices), len(me.polygons))
    if _HEALTH_CACHE["key"] != key:
        _HEALTH_CACHE["key"] = key
        _HEALTH_CACHE["summary"] = boolean._health_summary(obj)
    return _HEALTH_CACHE["summary"]


class HARDFLOW_PT_tools(Panel):
    bl_label = "Hardflow"
    bl_idname = "HARDFLOW_PT_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"

    def draw(self, context):
        layout = self.layout

        prefs = get_prefs(context)
        if getattr(prefs, "show_quickstart", False):
            self._draw_quickstart(layout, prefs)

        # Contextual hint: the draw / edit operators poll on an active mesh, so
        # Blender already greys their buttons out -- this says WHY (Build tools
        # below still work, so scope the wording to Boolean/Edit).
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            layout.label(text="Boolean & Edit need an active mesh", icon='INFO')

        # 1. Boolean -- the signature draw-to-cut workflow. Pick the operation
        # once (it sticks on the scene), then click any shape to draw with it, so
        # every mode x shape combo is one click.
        scene = context.scene
        mode = getattr(scene, "hardflow_draw_mode", 'CUT')
        col = layout.column(align=True)
        col.label(text="Boolean Draw", icon='MOD_BOOLEAN')
        if hasattr(scene, "hardflow_draw_mode"):
            col.prop(scene, "hardflow_draw_mode", text="Mode")
        # Hero launch button: the current mode with the default Box shape.
        hero = col.row(align=True)
        hero.scale_y = 1.5
        op = hero.operator("mesh.hardflow_draw",
                           text="Draw  (%s)" % mode.title(), icon='GREASEPENCIL')
        op.mode = mode
        op.shape = 'BOX'
        # Shape launchers -- each draws with the CURRENT mode (compact icon grid).
        col.label(text="Shape")
        grid = col.grid_flow(row_major=True, columns=3, align=True)
        for shp, label, icon in DRAW_SHAPE_ITEMS:
            o = grid.operator("mesh.hardflow_draw", text=label, icon=icon)
            o.mode = mode
            o.shape = shp
        col.separator()
        col.operator("object.hardflow_boolean", text="Boolean (Selected)",
                     icon='MOD_BOOLEAN')
        col.operator("object.hardflow_apply_cutters", text="Apply Cutters",
                     icon='CHECKMARK')
        self._draw_health(context, col)

    # Recomputing mesh health rebuilds a bmesh on every panel redraw; skip it on
    # heavy meshes so the sidebar stays responsive (mirrors the geo-snap cap).
    _HEALTH_MAX_VERTS = 20000

    def _draw_health(self, context, col):
        """Passive pre-cut warning: if the active mesh has boolean-breaking
        problems (non-manifold / zero-area geometry), flag it and offer the
        one-click normal-recalc fix, so failures are caught before drawing."""
        obj = context.active_object
        if (obj is None or obj.type != 'MESH'
                or len(obj.data.vertices) > self._HEALTH_MAX_VERTS):
            return
        summary = _cached_health_summary(obj)
        if not summary:
            return
        box = col.box().column(align=True)
        box.label(text="Cut may fail: " + summary, icon='ERROR')
        box.operator("object.hardflow_recalc_normals",
                     text="Recalculate Normals", icon='NORMALS_FACE')

    def _draw_quickstart(self, layout, prefs):
        """First-run onboarding card: the 3-step hero workflow + a one-click Cut
        and the pie, with a dismiss (X) that persists via the show_quickstart
        preference. Full reference lives in the Help & Shortcuts sub-panel."""
        box = layout.box()
        header = box.row(align=True)
        header.label(text="Quick Start", icon='INFO')
        header.prop(prefs, "show_quickstart", text="", icon='X', emboss=False)
        col = box.column(align=True)
        col.label(text="1.  Select a mesh (Object Mode)")
        col.label(text="2.  Ctrl+Shift+D — draw a shape to cut it")
        col.label(text="3.  Tab cycles Cut / Slice / Make mid-draw")
        row = box.row(align=True)
        row.operator("mesh.hardflow_draw", text="Cut Now",
                     icon='MOD_BOOLEAN').mode = 'CUT'
        row.operator("wm.call_menu_pie", text="Pie (Alt+Q)",
                     icon='COLLAPSEMENU').name = "HARDFLOW_MT_pie"


class HARDFLOW_PT_build(Panel):
    bl_label = "Build"
    bl_idname = "HARDFLOW_PT_build"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_tools"

    def draw(self, context):
        col = self.layout.column(align=True)
        row = col.row(align=True)
        row.operator("object.hardflow_add_primitive", text="Cube",
                     icon='MESH_CUBE').kind = 'CUBE'
        row.operator("object.hardflow_add_primitive", text="Plane",
                     icon='MESH_PLANE').kind = 'PLANE'
        row = col.row(align=True)
        row.operator("object.hardflow_add_primitive", text="Cylinder",
                     icon='MESH_CYLINDER').kind = 'CYLINDER'
        row.operator("object.hardflow_add_primitive", text="Cone",
                     icon='CONE').kind = 'CONE'
        row = col.row(align=True)
        row.operator("object.hardflow_add_primitive", text="Sphere",
                     icon='MESH_UVSPHERE').kind = 'SPHERE'
        row.operator("object.hardflow_add_primitive", text="Tube",
                     icon='MESH_CYLINDER').kind = 'TUBE'
        # Sketch a face in FACE mode: real geometry, ready to Push/Pull.
        col.label(text="Sketch face")
        row = col.row(align=True)
        rect = row.operator("mesh.hardflow_draw", text="Rectangle",
                            icon='MESH_PLANE')
        rect.shape = 'BOX'
        rect.mode = 'FACE'
        poly = row.operator("mesh.hardflow_draw", text="Polygon",
                            icon='MESH_DATA')
        poly.shape = 'POLY'
        poly.mode = 'FACE'
        row = col.row(align=True)
        scircle = row.operator("mesh.hardflow_draw", text="Circle",
                               icon='MESH_CIRCLE')
        scircle.shape = 'CIRCLE'
        scircle.mode = 'FACE'
        sngon = row.operator("mesh.hardflow_draw", text="N-gon",
                             icon='MESH_CYLINDER')
        sngon.shape = 'NGON'
        sngon.mode = 'FACE'
        row = col.row(align=True)
        row.operator("object.hardflow_add_grid", text="Grid", icon='MESH_GRID')
        row.operator("object.hardflow_add_guide", text="Guide", icon='IPO_LINEAR')
        row.operator("object.hardflow_loft", text="Loft", icon='MOD_SIMPLEDEFORM')


class HARDFLOW_PT_edit(Panel):
    bl_label = "Edit"
    bl_idname = "HARDFLOW_PT_edit"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_tools"

    def draw(self, context):
        col = self.layout.column(align=True)
        row = col.row(align=True)
        row.operator("mesh.hardflow_push_pull", text="Push/Pull",
                     icon='EMPTY_SINGLE_ARROW')
        row.operator("mesh.hardflow_offset", text="Offset", icon='MOD_SOLIDIFY')
        # Object-Mode edge tools (no Edit Mode needed).
        row = col.row(align=True)
        row.operator("mesh.hardflow_edge_bevel", text="Edge Bevel",
                     icon='MOD_BEVEL')
        row.operator("mesh.hardflow_loop_cut", text="Loop Cut",
                     icon='MOD_MULTIRES')
        # One-shot hard-surface init: sharpen + bevel + weighted normal.
        col.operator("object.hardflow_smart_sharpen", text="Smart Sharpen",
                     icon='MOD_BEVEL')
        row = col.row(align=True)
        row.operator("object.hardflow_fix_shading", text="Fix Shading",
                     icon='NODE_MATERIAL')
        row.operator("object.hardflow_sort_modifiers", text="Sort Stack",
                     icon='SORTSIZE')
        # Edit-Mode edge-flow tools: panel lines + reusable cutters.
        row = col.row(align=True)
        row.operator("mesh.hardflow_panel_line", text="Panel Line",
                     icon='MOD_SCREW')
        row.operator("mesh.hardflow_extract_cutter", text="Extract Cutter",
                     icon='MOD_BOOLEAN')


class HARDFLOW_PT_curves(Panel):
    bl_label = "Curves"
    bl_idname = "HARDFLOW_PT_curves"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.operator("mesh.hardflow_pipe", text="Pipe", icon='MOD_SCREW')
        row.operator("mesh.hardflow_cable", text="Cable", icon='FORCE_CURVE')
        row.operator("mesh.hardflow_sweep", text="Sweep", icon='MOD_SIMPLEDEFORM')
        scene = context.scene
        if hasattr(scene, "hardflow_profile_object"):
            col = layout.column(align=True)
            col.prop(scene, "hardflow_profile_object", text="Profile")
            col.prop(scene, "hardflow_detail_object", text="Detail")
            col.operator("object.hardflow_path_detail",
                         text="Detail Along Path", icon='MOD_ARRAY')
            if not (context.active_object is not None
                    and context.active_object.type == 'CURVE'):
                col.label(text="Detail needs an active curve", icon='INFO')


class HARDFLOW_PT_display(Panel):
    bl_label = "Display & Mesh"
    bl_idname = "HARDFLOW_PT_display"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        col = self.layout.column(align=True)
        row = col.row(align=True)
        row.operator("object.hardflow_display_toggle", text="Wire",
                     icon='SHADING_WIRE').mode = 'WIRE'
        row.operator("object.hardflow_display_toggle", text="Sharp",
                     icon='SNAP_EDGE').mode = 'SHARP'
        row.operator("object.hardflow_display_toggle", text="Cutters",
                     icon='MOD_BOOLEAN').mode = 'CUTTERS'
        row = col.row(align=True)
        row.operator("object.hardflow_random_color", text="Random Colors",
                     icon='COLOR')
        row.operator("object.hardflow_copy_material", text="Copy Mat",
                     icon='MATERIAL')


class HARDFLOW_PT_help(Panel):
    bl_label = "Help & Shortcuts"
    bl_idname = "HARDFLOW_PT_help"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_tools"
    bl_options = {'DEFAULT_CLOSED'}

    @staticmethod
    def _kv(col, key, desc):
        """One aligned key/description row -- the shortcut is left, its meaning
        right, so the list scans like a cheat-sheet."""
        split = col.split(factor=0.44, align=True)
        split.label(text=key)
        split.label(text=desc)

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="Global", icon='KEYINGSET')
        col = box.column(align=True)
        self._kv(col, "Alt+Q", "Pie menu")
        self._kv(col, "Ctrl+Shift+D", "Draw / Cut")
        self._kv(col, "Ctrl+Shift+X", "HardFlow Mode")

        box = layout.box()
        box.label(text="While drawing", icon='MOD_BOOLEAN')
        col = box.column(align=True)
        self._kv(col, "Tab", "Cut / Slice / Make / …")
        self._kv(col, "Q W E R T Y U", "Shape")
        self._kv(col, "type number", "Exact size")
        self._kv(col, "[  ]", "Sides / arc")
        self._kv(col, "X · V", "Grid · vertex snap")
        self._kv(col, "< >", "Projection plane")
        self._kv(col, "J", "Live boolean preview")

        box = layout.box()
        box.label(text="Direct modeling", icon='TOOL_SETTINGS')
        col = box.column(align=True)
        self._kv(col, "Push/Pull", "Drag a face along its normal")
        self._kv(col, "Offset", "Inset a face border (E = extrude)")
        self._kv(col, "Edge Bevel", "Bevel an edge, no Edit Mode")
        self._kv(col, "Loop Cut", "Insert an edge loop")

        layout.label(text="Rebind keys in Preferences ▸ Shortcuts", icon='INFO')


class HARDFLOW_PT_gizmos(Panel):
    bl_label = "Gizmos"
    bl_idname = "HARDFLOW_PT_gizmos"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        s = getattr(context.scene, "hardflow_gizmos", None)
        if s is None:
            layout.label(text="Gizmos unavailable", icon='ERROR')
            return
        layout.prop(s, "show", text="Always-On Gizmos", icon='GIZMO')
        col = layout.column(align=True)
        col.active = s.show
        row = col.row(align=True)
        row.prop(s, "move", toggle=True)
        row.prop(s, "rotate", toggle=True)
        row.prop(s, "scale", toggle=True)
        col.prop(s, "bevel", text="Bevel Width (Object Mode)", toggle=True)
        col.prop(s, "push_pull", text="Push/Pull (Edit Mode faces)", toggle=True)
        layout.label(text="Or pick a Hardflow tool in the toolbar (T)",
                     icon='TOOL_SETTINGS')


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

        # Snap: a compact toggle row (shared by every draw tool) + tuning.
        box = layout.box()
        box.label(text="Snap (all draw tools)", icon='SNAP_ON')
        row = box.row(align=True)
        row.prop(prefs, "snap_enabled", text="Grid", toggle=True,
                 icon='SNAP_GRID')
        row.prop(prefs, "geo_snap", text="Vertex", toggle=True,
                 icon='SNAP_VERTEX')
        row.prop(prefs, "surface_snap", text="Surface", toggle=True,
                 icon='SNAP_FACE')
        box.prop(prefs, "snap_target", text="")
        col = box.column(align=True)
        col.prop(prefs, "grid_world")
        col.prop(prefs, "build_grid_extent")
        col.prop(prefs, "snap_pixels")
        col.prop(prefs, "angle_step")

        # Boolean defaults.
        box = layout.box()
        box.label(text="Boolean", icon='MOD_BOOLEAN')
        col = box.column(align=True)
        col.prop(prefs, "non_destructive")
        col.prop(prefs, "multi_object")
        col.prop(prefs, "cleanup_after_cut")
        box.prop(prefs, "default_solver", text="Solver")

        # Curves (pipe / cable).
        box = layout.box()
        box.label(text="Curves", icon='MOD_SCREW')
        col = box.column(align=True)
        col.prop(prefs, "pipe_radius")
        col.prop(prefs, "pipe_offset")
        col.prop(prefs, "pipe_profile", text="")
        col.prop(prefs, "pipe_follow_surface")
        col.prop(prefs, "pipe_follow_segments")
        col = box.column(align=True)
        col.prop(prefs, "cable_radius")
        col.prop(prefs, "cable_sag")
        col.prop(prefs, "cable_segments")

        # Live-preview colors.
        box = layout.box()
        box.label(text="Preview Colors", icon='COLOR')
        row = box.row(align=True)
        row.prop(prefs, "line_color", text="")
        row.prop(prefs, "fill_color", text="")
        row.prop(prefs, "grid_color", text="")


class HARDFLOW_PT_cutter_options(Panel):
    bl_label = "Cutter Options"
    bl_idname = "HARDFLOW_PT_cutter_options"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        prefs = get_prefs(context)
        col = layout.column()
        col.label(text="Defaults for the next boolean draw")
        col.prop(prefs, "live_boolean_preview")
        col.prop(prefs, "draw_inset")
        col.prop(prefs, "draw_bevel_cut")
        col.prop(prefs, "draw_cutter_bevel")
        row = col.row(align=True)
        row.prop(prefs, "draw_array_count")
        row.prop(prefs, "draw_array_axis", text="")
        col.prop(prefs, "draw_vent_ratio")
        legend = col.box().column(align=True)
        legend.label(text="Live keys while drawing", icon='INFO')
        legend.label(text="−/=  inset       ,/.  rotate")
        legend.label(text="A/D  array (D: X/Y/Z/Radial)   B/C  bevel")
        legend.label(text="J  preview     H  origin (radial pivot)")
        col.separator()
        col.label(text="Topology & Shading")
        col.prop(prefs, "cut_dissolve_ngons")
        col.prop(prefs, "fix_shading_after_cut")
        col.prop(prefs, "sort_modifiers_after_cut")
        col.prop(prefs, "smart_bevel_default")
        col.separator()
        col.label(text="Cut-to-Trim (Decal bridge)")
        col.prop(prefs, "auto_trim_after_cut", text="")
        if prefs.auto_trim_after_cut != 'OFF':
            col.prop(prefs, "auto_trim_radius")
            col.prop(prefs, "auto_trim_lift")


class HARDFLOW_PT_modifiers(Panel):
    bl_label = "Modifier Stack"
    bl_idname = "HARDFLOW_PT_modifiers"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Hardflow"
    bl_parent_id = "HARDFLOW_PT_tools"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        if obj is None or not obj.modifiers:
            layout.label(text="No modifiers on the active object", icon='INFO')
            return
        # One-click hard-surface sort: booleans on top, bevel below, weighted
        # normal at the bottom (core.modifiers ordering).
        layout.operator("object.hardflow_sort_modifiers",
                        text="Sort (Hard-Surface Order)", icon='SORTSIZE')
        # Compact mod-list: name + show/hide + move + apply + remove. Drives
        # Blender's own modifier operators (a compact modifier-stack manager).
        box = layout.box().column(align=True)
        for mod in obj.modifiers:
            row = box.row(align=True)
            row.label(text=mod.name, icon='MODIFIER')
            row.prop(mod, "show_viewport", text="", emboss=False,
                     icon='RESTRICT_VIEW_OFF' if mod.show_viewport
                     else 'RESTRICT_VIEW_ON')
            row.operator("object.modifier_move_up", text="",
                         icon='TRIA_UP').modifier = mod.name
            row.operator("object.modifier_move_down", text="",
                         icon='TRIA_DOWN').modifier = mod.name
            row.operator("object.modifier_apply", text="",
                         icon='CHECKMARK').modifier = mod.name
            row.operator("object.modifier_remove", text="",
                         icon='X').modifier = mod.name


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
            layout.operator("object.hardflow_cutter_scroll",
                            text="Cutter Scroll", icon='LOOP_FORWARDS')

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


# The panel PropertyGroups/Panels register through __init__'s _classes tuple;
# these add the panel-owned Scene state (the persistent Boolean draw mode +
# the Curves tool object pickers) and are called from
# __init__.register()/unregister().
def _poll_profile_object(self, obj):
    return obj.type in {'MESH', 'CURVE'}


def _poll_detail_object(self, obj):
    return obj.type == 'MESH'


def register():
    bpy.types.Scene.hardflow_draw_mode = EnumProperty(
        name="Draw Mode", description="Boolean operation the Draw tool performs; "
        "pick it once here, then click any shape to draw with it",
        items=DRAW_MODE_ITEMS, default='CUT')
    bpy.types.Scene.hardflow_profile_object = PointerProperty(
        type=bpy.types.Object, name="Profile Object",
        description="CUSTOM cross-section for Pipe/Sweep: a flat mesh outline "
                    "(its boundary is swept as a solid) or a curve (native "
                    "non-destructive bevel profile). P cycles onto CUSTOM "
                    "while drawing once this is set",
        poll=_poll_profile_object)
    bpy.types.Scene.hardflow_detail_object = PointerProperty(
        type=bpy.types.Object, name="Detail Object",
        description="Mesh repeated along the active curve by Detail Along "
                    "Path (Array Fit-Curve + Curve deform, non-destructive)",
        poll=_poll_detail_object)


def unregister():
    for prop in ("hardflow_draw_mode", "hardflow_profile_object",
                 "hardflow_detail_object"):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
