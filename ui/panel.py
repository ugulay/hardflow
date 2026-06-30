# N-panel (View3D > Sidebar > Hardflow): tools, snap settings, cutter list.
import bpy
from bpy.types import Panel

from ..preferences import get_prefs
from ..core import boolean


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

        # 1. Boolean -- the signature draw-to-cut workflow.
        col = layout.column(align=True)
        col.label(text="Boolean Draw", icon='MOD_BOOLEAN')
        row = col.row(align=True)
        row.operator("mesh.hardflow_draw", text="Cut").mode = 'CUT'
        row.operator("mesh.hardflow_draw", text="Slice").mode = 'SLICE'
        row.operator("mesh.hardflow_draw", text="Make").mode = 'MAKE'
        row = col.row(align=True)
        row.operator("mesh.hardflow_draw", text="Intersect").mode = 'INTERSECT'
        row.operator("mesh.hardflow_draw", text="Join").mode = 'JOIN'
        row.operator("mesh.hardflow_draw", text="Knife").mode = 'KNIFE'
        # Cutter shape: each draws a CUT by default; the mode buttons above set
        # the operation, the shape buttons set the outline.
        col.label(text="Shape (cut)")
        row = col.row(align=True)
        circle = row.operator("mesh.hardflow_draw", text="Circle",
                              icon='MESH_CIRCLE')
        circle.shape = 'CIRCLE'
        circle.mode = 'CUT'
        ngon = row.operator("mesh.hardflow_draw", text="N-gon",
                            icon='MESH_CYLINDER')
        ngon.shape = 'NGON'
        ngon.mode = 'CUT'
        row = col.row(align=True)
        slot = row.operator("mesh.hardflow_draw", text="Slot",
                            icon='MESH_CAPSULE')
        slot.shape = 'SLOT'
        slot.mode = 'CUT'
        star = row.operator("mesh.hardflow_draw", text="Star", icon='SOLO_ON')
        star.shape = 'STAR'
        star.mode = 'CUT'
        arc = row.operator("mesh.hardflow_draw", text="Arc",
                           icon='MOD_SIMPLEDEFORM')
        arc.shape = 'ARC'
        arc.mode = 'CUT'
        col.operator("object.hardflow_boolean", text="Boolean (Selected)",
                     icon='MOD_BOOLEAN')
        col.operator("object.hardflow_apply_cutters", text="Apply Cutters",
                     icon='CHECKMARK')
        self._draw_health(context, col)

        # 2. Build -- create geometry to model on.
        col = layout.column(align=True)
        col.label(text="Build", icon='MESH_GRID')
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

        # 3. Edit -- direct-modeling tools that reshape existing geometry.
        col = layout.column(align=True)
        col.label(text="Edit", icon='TOOL_SETTINGS')
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

        # 4. Curves -- pipes, cables, swept profiles.
        col = layout.column(align=True)
        col.label(text="Curves", icon='MOD_SCREW')
        row = col.row(align=True)
        row.operator("mesh.hardflow_pipe", text="Pipe", icon='MOD_SCREW')
        row.operator("mesh.hardflow_cable", text="Cable", icon='FORCE_CURVE')
        row.operator("mesh.hardflow_sweep", text="Sweep", icon='MOD_SIMPLEDEFORM')

        # 5. Display & mesh helpers.
        col = layout.column(align=True)
        col.label(text="Display", icon='OVERLAY')
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
        col = layout.column()
        col.label(text="Snap (shared by all draw tools)")
        col.prop(prefs, "snap_enabled", text="Grid")
        col.prop(prefs, "geo_snap", text="Vertex/Edge")
        col.prop(prefs, "surface_snap", text="Surface/Face")
        col.prop(prefs, "snap_target")
        col.separator()
        col.prop(prefs, "grid_world")
        col.prop(prefs, "build_grid_extent")
        col.prop(prefs, "snap_pixels")
        col.prop(prefs, "angle_step")
        col.separator()
        col.prop(prefs, "non_destructive")
        col.prop(prefs, "multi_object")
        col.prop(prefs, "cleanup_after_cut")
        col.prop(prefs, "default_solver")
        col.separator()
        col.prop(prefs, "pipe_radius")
        col.prop(prefs, "pipe_offset")
        col.prop(prefs, "pipe_profile")
        col.prop(prefs, "pipe_follow_surface")
        col.prop(prefs, "pipe_follow_segments")
        col.prop(prefs, "cable_radius")
        col.prop(prefs, "cable_sag")
        col.prop(prefs, "cable_segments")
        col.separator()
        col.label(text="Colors (live preview)")
        row = col.row(align=True)
        row.prop(prefs, "line_color", text="")
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
        col.label(text="Live keys while drawing: -/= , . A D B C J",
                  icon='INFO')


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
