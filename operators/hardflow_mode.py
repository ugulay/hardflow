# HardFlow Mode -- the "Shadowing Engine" shell for the streamlined draw verbs.
#
# What "shadowing" means here (and what it does NOT):
#   You cannot wrap Blender's native `mesh.knife_tool` / `mesh.extrude_*` modal
#   operators and intercept their mouse events -- a modal operator that INVOKEs
#   another modal does not get to filter the child's events. So HardFlow Mode does
#   the only thing that works: it *shadows* the native tool. It owns its own modal
#   loop, reads the raw mouse, routes it through core/raycast + core/snapping +
#   core/grid (the Ghost Grid), and calls bmesh via the pure core builders
#   directly. That IS the hijack.
#
# `_HardflowModeModal` is the shared shell (the modal-hijack loop + Ghost-Grid
# snap chain + per-session Command-Pattern undo journal + HUD). Each verb --
# Knife, Extrude, ... -- is a thin subclass that only fills `_build()` (what the
# drawn footprint becomes on commit) plus its optional per-verb keys. This mirrors
# the existing shared bases: face_tool._FaceDragModal and pipe._CurveDraw.
#
# Layer rule respected: this operator (ops) reaches DOWN into core only. The whole
# tool session is ONE operator invocation, which Blender records as a single
# (atomic) undo step on FINISHED -- the per-modal atomic macro.
import bpy
from bpy.types import Operator
from mathutils import Vector

from ..core import raycast, grid, snapping, geometry, command, boolean
from ..preferences import get_prefs
from ..ui import draw as hud
from . import base


# Ghost-Grid construction planes cycled with the arrow keys. SURFACE aligns to
# the face under the first click (promoted from draw_cut._plane_basis); EDGES is
# Edit-Mode-only (selected edges) and so does not apply to this Object-Mode shell.
_PLANES = ('VIEW', 'SURFACE', 'X', 'Y', 'Z')

# The tool verbs Tab cycles between within one mode session, and their HUD labels.
# KNIFE / EXTRUDE are the non-boolean verbs; CUT / ADD / SLICE / INTERSECT extrude
# the footprint into a cutter and boolean it against the active mesh (draw-to-cut).
_VERBS = ('KNIFE', 'EXTRUDE', 'CUT', 'ADD', 'SLICE', 'INTERSECT')
_VERB_LABELS = {'KNIFE': 'Knife', 'EXTRUDE': 'Extrude', 'CUT': 'Cut',
                'ADD': 'Add', 'SLICE': 'Slice', 'INTERSECT': 'Intersect'}
# The boolean verbs and the modifier operation each maps to.
_BOOL_OPS = {'CUT': 'DIFFERENCE', 'ADD': 'UNION', 'INTERSECT': 'INTERSECT'}


class _HardflowModeModal:
    """Shared shell for the HardFlow Mode verbs: draw a snapped polyline on the
    Ghost Grid, then commit it into geometry. Owns the modal loop, the snap chain,
    the plane cycle, the per-session CommandManager and the HUD; subclasses only
    fill the commit.

    Verbs live on the shell (dispatched by self._active_verb) so Tab can switch
    the active verb mid-session the way draw_cut's Tab cycles the boolean mode --
    Knife (score the footprint onto the active mesh) and Extrude (build a prism
    solid from the footprint). Each Operator subclass only sets `_START_VERB`
    (the verb it enters with) and its poll; the commit logic is shared here.
    """

    _START_VERB = 'KNIFE'
    _MIN_POINTS = 3
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    # --- lifecycle -------------------------------------------------------

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Run inside the 3D Viewport")
            return {'CANCELLED'}
        prefs = get_prefs(context)
        self.snap = prefs.snap_enabled          # X toggles the Ghost Grid snap
        self._grid = prefs.grid_world           # Ghost Grid spacing (meters)
        self._snap_px = prefs.snap_pixels       # geometry-snap capture radius
        self.world_points = []                  # placed points, world space
        self._cursor = None                     # live snapped cursor (world)
        self._snap_kind = None                  # 'VERT'/'MID'/'EDGE'/'GRID'/None
        self._plane = 'VIEW'                     # construction plane (arrow keys)
        self._surface_basis = None              # cached at first click on SURFACE
        self._surface_hold = None               # last good SURFACE plane (miss hold)
        self._surface_miss = False              # SURFACE ray missed geometry
        self._last_co = (event.mouse_region_x, event.mouse_region_y)
        self._active_verb = self._START_VERB    # Tab cycles Knife <-> Extrude
        self.verb = _VERB_LABELS[self._active_verb]
        self.depth = max(self._grid * 4.0, 0.1)  # Extrude verb depth (PgUp/PgDn)
        self._commands = command.CommandManager()
        self._mesh_cmds = []                    # MeshSnapshotCommands to free()
        self._basis = self._plane_basis(context)

        # Pre-collect snap geometry once; verts/edges don't move while drawing.
        self.geo = (snapping.collect_geo(context, prefs.snap_target)
                    if prefs.geo_snap else None)

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        try:
            context.window_manager.modal_handler_add(self)
        except Exception:   # never orphan the draw handler if modal won't start
            self._cleanup(context)
            raise
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        context.area.tag_redraw()
        co = (event.mouse_region_x, event.mouse_region_y)
        self._last_co = co                      # SURFACE preview-track needs it

        if event.type == 'MOUSEMOVE':
            # THE hijack: the raw mouse position is handed straight to the core
            # snapping chain, not to Blender's tool. Re-derive the basis first so
            # the VIEW / SURFACE planes track the current orbit / cursor.
            self._basis = self._plane_basis(context)
            self._cursor = self._snap_screen(context, co)

        elif event.value == 'PRESS' and self._handle_verb_key(context, event):
            pass                                # verb consumed the key (e.g. depth)

        elif event.type == 'TAB' and event.value == 'PRESS':
            self._cycle_verb()                  # switch Knife <-> Extrude in place

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            # First click on the SURFACE plane locks the construction basis to the
            # face under the cursor, so the whole footprint stays on one plane.
            if self._plane == 'SURFACE' and self._surface_basis is None:
                # Lock to the face under the click; if the click just missed the
                # surface, fall back to the last face we hovered (the held plane)
                # rather than leaving the basis unlocked and drawing at object
                # depth.
                self._surface_basis = (self._surface_basis_at(context, co)
                                       or self._surface_hold)
                self._basis = self._plane_basis(context)
                self._cursor = self._snap_screen(context, co)
            if self._cursor is not None:
                self._commands.do(base.PlacePointCommand(
                    self.world_points, self._cursor.copy()))

        elif event.type == 'BACK_SPACE' and event.value == 'PRESS':
            self._commands.undo()               # step one placement back

        elif event.type == 'X' and event.value == 'PRESS':
            self.snap = not self.snap

        elif (event.type in {'LEFT_ARROW', 'RIGHT_ARROW'}
              and event.value == 'PRESS'):
            self._cycle_plane(1 if event.type == 'RIGHT_ARROW' else -1)
            self._surface_basis = None          # re-track the surface on the new plane
            self._surface_hold = None           # drop any held plane from a prior pass
            self._basis = self._plane_basis(context)
            self._cursor = self._snap_screen(context, co)

        elif (event.type in {'RET', 'NUMPAD_ENTER', 'Z'}
              and event.value == 'PRESS'):
            return self._commit(context)

        elif event.type == 'LEFTMOUSE' and event.value == 'DOUBLE_CLICK':
            return self._commit(context)

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._commands.undo_all()           # nothing committed yet: roll back
            self._cleanup(context)
            return {'CANCELLED'}

        elif event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
                            'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}             # let the user orbit / zoom

        return {'RUNNING_MODAL'}

    # --- the snapping chain (the "Ghost Grid") ---------------------------

    def _snap_screen(self, context, screen_co):
        """Route the raw 2D mouse position through the shared core snapping chain
        and return a 3D world point (or None if the ray misses the plane):

          1) geometry snap -- nearest vertex / edge-midpoint / on-edge point
             (core/snapping.geo_snap_3d); overrides the grid so precision wins.
          2) Ghost Grid -- project onto the construction plane, round the plane's
             (u, v) meter coordinate to the grid (core/grid.snap_world).
          3) raw plane hit -- when snap is off.

        The ONE place the three core modules are composed; every verb shares it."""
        region, rv3d = context.region, context.region_data
        self._snap_kind = None

        if self.geo is not None and self.geo.enabled:
            hit = snapping.geo_snap_3d(region, rv3d, screen_co, self.geo,
                                       self._snap_px)
            if hit is not None:
                point, kind = hit
                self._snap_kind = kind
                return point

        origin, right, up, normal = self._basis
        world = raycast.ray_to_plane(region, rv3d, screen_co, origin, normal)
        if world is None:
            return None
        u, v = raycast.world_to_plane_uv(world, origin, right, up)
        if self.snap:
            u, v = grid.snap_world(u, v, self._grid, True)
            self._snap_kind = 'GRID'
        return raycast.plane_uv_to_world(u, v, origin, right, up)

    def _origin(self, context):
        """The construction-plane origin: the active object's origin when there is
        one, else the 3D cursor (so Extrude works from an empty scene)."""
        obj = context.active_object
        if obj is not None:
            return obj.matrix_world.translation.copy()
        return context.scene.cursor.location.copy()

    def _plane_basis(self, context):
        """(origin, right, up, normal) for the current construction plane. VIEW
        faces the camera through the origin; SURFACE aligns to the face under the
        cursor (cached at first click); X / Y / Z are the world axis planes."""
        origin = self._origin(context)
        if self._plane == 'VIEW':
            self._surface_miss = False
            return self._view_basis(context, origin)
        if self._plane == 'SURFACE':
            b = self._surface_basis
            if b is None:                        # before the first click: preview-track
                live = self._surface_basis_at(context, self._last_co)
                if live is not None:
                    self._surface_hold = live    # remember the last face hovered
                # On a miss, hold the last good surface plane instead of snapping
                # the cursor onto the object-centre VIEW plane -- that jump is
                # what reads as the cursor "going behind" the surface.
                b = live if live is not None else self._surface_hold
            self._surface_miss = b is None
            return b if b is not None else self._view_basis(context, origin)
        self._surface_miss = False
        normal = {'X': Vector((1.0, 0.0, 0.0)),
                  'Y': Vector((0.0, 1.0, 0.0)),
                  'Z': Vector((0.0, 0.0, 1.0))}[self._plane]
        right, up, n = raycast.basis_from_normal(normal)
        return origin, right, up, n

    def _view_basis(self, context, origin):
        return raycast.view_basis(context.region_data, origin)

    def _surface_basis_at(self, context, screen_co):
        """Construction basis aligned to the face under screen_co (delegates to
        the shared raycast.surface_basis_at). The shell draws GPU only -- no live
        preview object -- so nothing is ignored by the raycast."""
        return raycast.surface_basis_at(
            context, context.region, context.region_data, screen_co, None)

    def _cycle_plane(self, step):
        self._plane = _PLANES[(_PLANES.index(self._plane) + step) % len(_PLANES)]

    def _cycle_verb(self):
        """Tab: switch the active verb (Knife <-> Extrude) without leaving the
        session, keeping the points placed so far."""
        i = _VERBS.index(self._active_verb)
        self._active_verb = _VERBS[(i + 1) % len(_VERBS)]
        self.verb = _VERB_LABELS[self._active_verb]

    # --- commit / teardown ------------------------------------------------

    def _commit(self, context):
        """Run the verb's `_build`, then clear the in-modal journal so the whole
        session hands off as ONE Blender undo step (the per-modal atomic macro).
        A raising `_build` cancels cleanly -- nothing is committed."""
        if len(self.world_points) < self._MIN_POINTS:
            self.report({'WARNING'}, "%s needs at least %d points"
                        % (self.verb, self._MIN_POINTS))
            return {'RUNNING_MODAL'}
        try:
            message = self._build(context)
        except Exception as ex:   # noqa: BLE001 -- report, never crash the modal
            self.report({'ERROR'}, "HardFlow %s: %s" % (self.verb, ex))
            self._cleanup(context)
            return {'CANCELLED'}
        self._commands.clear()           # hand the net change to Blender's undo
        self.report({'INFO'}, message or "HardFlow Mode: %s done" % self.verb)
        self._cleanup(context)
        return {'FINISHED'}

    def _cleanup(self, context):
        # Free every mesh snapshot regardless of undo/redo-stack state (a
        # committed edit keeps the mutated mesh; a cancelled one was already
        # restored by undo_all). free() is idempotent.
        for cmd in self._mesh_cmds:
            cmd.free()
        self._mesh_cmds = []
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        if context.area is not None:
            context.area.tag_redraw()

    # --- verb dispatch (Tab switches self._active_verb) ------------------

    def _handle_verb_key(self, context, event):
        """Every verb except Knife owns PageUp/PageDown to set its depth (Extrude
        height, boolean cutter reach); Knife scores at zero depth and has no key."""
        if self._active_verb != 'KNIFE' and event.type in {'PAGE_UP',
                                                            'PAGE_DOWN'}:
            step = self._grid if event.type == 'PAGE_UP' else -self._grid
            self.depth = max(self._grid, round(self.depth + step, 6))
            return True
        return False

    def _verb_hud(self):
        if self._active_verb != 'KNIFE':
            return "   depth %.3f m (PgUp/PgDn)" % self.depth
        return ""

    def _build(self, context):
        if self._active_verb == 'KNIFE':
            return self._build_knife(context)
        if self._active_verb == 'EXTRUDE':
            return self._build_extrude(context)
        return self._build_boolean(context, self._active_verb)

    def _build_knife(self, context):
        """Score the drawn footprint onto the active mesh as a MeshSnapshotCommand,
        recorded in the in-modal journal so the knife is undoable mid-session too."""
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            raise RuntimeError("Knife needs an active mesh (Tab to Extrude)")
        mw_inv = obj.matrix_world.inverted_safe()
        local = [mw_inv @ w for w in self.world_points]
        view_dir = mw_inv.to_3x3() @ raycast.view_direction(context.region_data)

        def _score(o):
            geometry.knife_polygon(o, local, view_dir)

        knife = base.MeshSnapshotCommand(obj, _score, label="Knife",
                                         snapshot_name="hf_mode_knife")
        self._mesh_cmds.append(knife)
        self._commands.do(knife)         # snapshot 'before' + score, recorded
        return "HardFlow Mode: knifed the drawn footprint"

    def _build_extrude(self, context):
        """Build a prism from the drawn footprint, extruded along the plane normal,
        and drop it in as a new active object."""
        origin, right, up, normal = self._basis
        me = geometry.build_prism(self.world_points, normal, self.depth)
        if me is None:
            raise RuntimeError("degenerate footprint")
        obj = bpy.data.objects.new("Hardflow_Extrude", me)
        context.collection.objects.link(obj)
        for o in context.selected_objects:
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return ("HardFlow Mode: extruded a %d-gon solid (depth %.3f m)"
                % (len(self.world_points), self.depth))

    # --- boolean verbs (draw-to-cut) --------------------------------------

    def _pierce_thickness(self, target):
        """A cutter depth big enough to pierce `target` clean through along the
        plane normal, never below the live depth. The footprint sits at the SURFACE
        (mid-cutter), so only half the thickness reaches inward -- size it at
        2.2 x the bounding-box diagonal so that inward half (~1.1 x diag) always
        clears the whole mesh wherever the footprint was drawn on it."""
        diag = 0.1
        if target is not None:
            d = target.dimensions
            diag = (d.x * d.x + d.y * d.y + d.z * d.z) ** 0.5
        return max(diag * 2.2, self.depth, 0.1)

    def _boolean_cutter_mesh(self, context, verb, target):
        """The prism cutter for a boolean verb. CUT/SLICE/INTERSECT straddle the
        surface with a pierce-through thickness (the footprint sits mid-cutter so
        it reaches both ways); ADD stands a boss of `depth` proud of the surface
        along +normal. Returns mesh data, or None on a degenerate footprint."""
        origin, right, up, normal = self._basis
        if verb == 'ADD':
            shift = normal * (self.depth * 0.5)
            corners = [w + shift for w in self.world_points]
            thickness = self.depth
        else:                                   # CUT / SLICE / INTERSECT
            corners = list(self.world_points)
            thickness = self._pierce_thickness(target)
        return geometry.build_prism(corners, normal, thickness,
                                    name="hf_mode_cutter")

    def _build_boolean(self, context, verb):
        """Extrude the drawn footprint into a cutter and boolean it against the
        active mesh: CUT (difference), ADD (union), INTERSECT (keep the overlap),
        SLICE (difference on the target + intersect on a kept duplicate). One
        atomic MacroCommand of BooleanCutCommands, so a solver failure rolls the
        whole thing back instead of leaving a half-cut mesh; the cutter is
        destructive (removed after applying)."""
        target = context.active_object
        if target is None or target.type != 'MESH':
            raise RuntimeError("%s needs an active mesh (Tab to Extrude)"
                               % self.verb)
        mesh = self._boolean_cutter_mesh(context, verb, target)
        if mesh is None:
            raise RuntimeError("degenerate footprint")
        cutter = bpy.data.objects.new("hf_mode_cutter", mesh)
        context.collection.objects.link(cutter)

        solver = get_prefs(context).default_solver
        other = None
        if verb == 'SLICE':
            other = boolean.duplicate_object(context, target)
            pairs = [(target, 'DIFFERENCE'), (other, 'INTERSECT')]
        else:
            pairs = [(target, _BOOL_OPS[verb])]
        cmds = [base.BooleanCutCommand(context, tgt, cutter, op, solver,
                                       snapshot_name="hf_mode_bool_%d" % i)
                for i, (tgt, op) in enumerate(pairs)]
        self._mesh_cmds.extend(cmds)
        macro = command.MacroCommand(cmds, label="HardFlow %s" % self.verb)
        try:
            self._commands.do(macro)            # atomic: rolls back on failure
        except Exception:
            if other is not None and other.name in bpy.data.objects:
                bpy.data.objects.remove(other, do_unlink=True)
            if cutter.name in bpy.data.objects:
                bpy.data.objects.remove(cutter, do_unlink=True)
            raise
        bpy.data.objects.remove(cutter, do_unlink=True)   # destructive cutter
        context.view_layer.objects.active = target
        note = ""
        if cmds and cmds[-1].solver_used == 'FAST' and solver != 'FAST':
            note = " (FAST solver fallback)"
        return "HardFlow Mode: %s applied%s" % (self.verb, note)

    # --- HUD --------------------------------------------------------------

    # Axis colors for the world-axis construction planes; VIEW / SURFACE fall
    # back to the accent so the guide still reads as "the plane you draw on".
    _AXIS_GUIDE = {'X': (1.0, 0.35, 0.35, 0.5),
                   'Y': (0.45, 1.0, 0.45, 0.5),
                   'Z': (0.45, 0.6, 1.0, 0.5)}

    def _draw_plane_guides(self, context):
        """Dashed, translucent guide lines along the construction plane's two
        in-plane axes, through the snapped cursor -- the 'locked to this plane /
        this direction' feedback. Screen-projected from the world basis, so they
        track the orbit and the active plane."""
        if self._basis is None or self._cursor is None:
            return
        region, rv3d = context.region, context.region_data
        _origin, right, up, _normal = self._basis
        span = max(self._grid * 6.0, 0.5)
        col = self._AXIS_GUIDE.get(
            self._plane, tuple(get_prefs(context).line_color)[:3] + (0.45,))
        for axis in (right, up):
            a = raycast.world_to_screen(region, rv3d, self._cursor - axis * span)
            b = raycast.world_to_screen(region, rv3d, self._cursor + axis * span)
            if a is not None and b is not None:
                hud.draw_dashed_line(a, b, col)

    def _draw_px(self, context):
        prefs = get_prefs(context)
        region, rv3d = context.region, context.region_data
        line = tuple(prefs.line_color)
        accent = line[:3] + (1.0,)

        # Placed points + the rubber-band segment to the live cursor.
        screen = []
        for w in self.world_points:
            s = raycast.world_to_screen(region, rv3d, w)
            if s is not None:
                screen.append((s[0], s[1]))
        preview = list(screen)
        if self._cursor is not None:
            c = raycast.world_to_screen(region, rv3d, self._cursor)
            if c is not None:
                preview.append((c[0], c[1]))
        if len(preview) >= 2:
            closed = len(self.world_points) >= 3 and self._cursor is None
            hud.draw_shape(preview, line, closed=closed)

        # Dynamic alignment guides: a dashed full-span line when the live cursor is
        # square with a placed point (complements the per-plane axis guides below).
        if screen and self._cursor is not None:
            c = raycast.world_to_screen(region, rv3d, self._cursor)
            if c is not None:
                hud.draw_alignment_guides(region, screen, (c[0], c[1]))

        # Live cursor: translucent in-plane axis guides + a ring snap marker
        # colored by what it locked onto (premium feedback over the plain box).
        if self._cursor is not None:
            c = raycast.world_to_screen(region, rv3d, self._cursor)
            if c is not None:
                self._draw_plane_guides(context)
                mark = {
                    'VERT': (1.0, 0.9, 0.2, 1.0),   # yellow = vertex
                    'MID': (0.2, 1.0, 0.4, 1.0),    # green  = midpoint
                    'EDGE': (0.3, 0.6, 1.0, 1.0),   # blue   = on-edge
                    'GRID': (1.0, 1.0, 1.0, 0.85),  # white  = grid
                }.get(self._snap_kind, accent)
                hud.draw_snap_ring(c, 7.0, mark, width=1.75)
                hud.draw_points([c], hud.fade_color(mark, 0.9), size=4.0)

        snap_txt = self._snap_kind or "free"
        plane_txt = self._plane + ("(miss)" if self._surface_miss else "")
        depth = self._verb_hud().strip()
        info = ("%d pt   plane %s   snap %s%s"
                % (len(self.world_points), plane_txt,
                   'ON' if self.snap else 'OFF',
                   ("   " + depth) if depth else ""))
        hud.draw_hud(region, [
            (info, accent),
            ("Click add   Z / dbl-click commit   [%s]" % snap_txt,
             (0.72, 0.72, 0.72, 1.0)),
        ], title="HardFlow Mode · %s" % self.verb, accent=accent)

        # Premium shortcut bar along the bottom with the live engaged state.
        hud.draw_shortcut_bar(region, [
            ("Tab", self.verb),
            ("←/→", "Plane: %s" % self._plane),
            ("PgUp/Dn", "Depth", self._active_verb == 'EXTRUDE'),
            ("X", "Snap", self.snap),
            ("Bksp", "Undo"),
            ("Enter", "Commit"),
            ("Esc", "Cancel"),
        ])


class HARDFLOW_OT_mode_knife(_HardflowModeModal, Operator):
    """HardFlow Mode, entered on the Knife verb: draw a snapped polyline on the
    Ghost Grid and score it onto the active mesh. Tab switches to Extrude
    mid-session. The reference verb for the modal-hijack + Ghost-Grid snap +
    Command-Pattern undo architecture."""

    bl_idname = "mesh.hardflow_mode_knife"
    bl_label = "HardFlow Mode Knife"
    bl_description = ("Snapped polyline knife driven by the HardFlow core snapping "
                      "+ command modules (Tab -> Extrude)")

    _START_VERB = 'KNIFE'

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')


class HARDFLOW_OT_mode_extrude(_HardflowModeModal, Operator):
    """HardFlow Mode, entered on the Extrude verb: draw a snapped footprint on the
    Ghost Grid, then extrude it into a solid along the plane normal. The 'draw a
    shape, make it a thing' verb -- the SketchUp Push/Pull-from-nothing flow, on
    the shared shell. PageUp / PageDown set the extrude depth; Tab switches to
    Knife mid-session."""

    bl_idname = "mesh.hardflow_mode_extrude"
    bl_label = "HardFlow Mode Extrude"
    bl_description = ("Draw a snapped footprint on the Ghost Grid and extrude it "
                      "into a solid (Tab -> Knife)")

    _START_VERB = 'EXTRUDE'


class HARDFLOW_OT_mode_cut(_HardflowModeModal, Operator):
    """HardFlow Mode, entered on the Cut verb: draw a snapped footprint on the
    Ghost Grid, extrude it into a cutter and boolean-subtract it from the active
    mesh -- the draw-to-cut hard-surface staple, on the shared shell. Tab cycles
    on to Add / Slice / Intersect / Knife / Extrude; PageUp/PageDown set the
    cutter depth (Cut/Slice/Intersect auto-pierce, so depth is only a floor)."""

    bl_idname = "mesh.hardflow_mode_cut"
    bl_label = "HardFlow Mode Cut"
    bl_description = ("Draw a snapped footprint and boolean-cut it from the active "
                      "mesh (Tab -> Add / Slice / Intersect)")

    _START_VERB = 'CUT'

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'OBJECT')
