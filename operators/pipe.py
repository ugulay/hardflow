# Pipe + cable/rope draw operators: draw a poly-line, convert it to a round
# tube (pipe) or a sagging cable. A surface-snapping "pipes" flow plus a
# hanging-cable tool.
#
# Both share one modal (the _CurveDraw mixin). Two precision fixes over the old
# version:
#   * Burying: every point is lifted by the tube's own RADIUS (+ a clearance)
#     along the surface normal, so the round section rests on the surface instead
#     of sinking half-in.
#   * Routing: the pipe is DRAPED -- each span is re-sampled and snapped onto the
#     nearest surface (core.snapping.drape_path) so the tube hugs contours and
#     wraps edges instead of cutting straight through the model. The cable keeps
#     a free-hanging catenary sag (it is meant to span gaps, not follow the wall).
#
# The real curve object is built and updated LIVE under the cursor, so the tube
# you see while clicking is exactly what gets committed (Esc discards it).
#
# Input is IMPLICIT click-or-stroke (v1.20): a plain LMB click places one
# anchor exactly as before, while pressing and DRAGGING past a few pixels
# records a freehand stroke -- sampled through the same snap chain (so a stroke
# dragged across the model hugs the surface), then reduced to clean anchors
# with Ramer-Douglas-Peucker on release (core/path.rdp_simplify). Clicks and
# strokes mix freely in one session; Backspace removes a whole stroke at once.
# `C` toggles Smooth Path: a centripetal Catmull-Rom (core/path.catmull_rom)
# through the anchors -- and when the profile is ROUND with Follow off, a light
# AUTO-handle Bezier curve you can keep editing after commit.
#
# Shortcuts (modal): LMB click add point / drag freehand, Enter create,
#   Backspace undo, Esc/RMB cancel, Wheel radius, Ctrl+Wheel clearance,
#   Tab/S toggle surface snap, V vertex/edge snap, X grid snap,
#   F follow-surface (pipe), C smooth path, (cable only) Shift+Wheel sag,
#   MMB navigation.
import bpy
from bpy.types import Operator
from mathutils import Vector

from ..core import raycast, geometry, transform, snapping, path
from ..preferences import get_prefs
from ..ui import draw as hud


def _px_dist2(a, b):
    dx, dy = a[0] - b[0], a[1] - b[1]
    return dx * dx + dy * dy


class _CurveDraw:
    """Shared modal logic for drawing a poly-line on surfaces. Subclasses set
    `_title`, `_has_sag`, override `_init_params`, `_route_points` and `_commit`.
    Not an Operator itself -- the concrete tools mix it with bpy.types.Operator."""

    _title = "Pipe"
    _has_sag = False
    _can_follow = True
    _can_smooth = True     # cable overrides: sag defines its shape, not a spline
    _has_profile = False   # pipe overrides: square/rect swept cross-sections
    # Cross-sections the P key cycles through (subclasses override). ROUND falls
    # back to the curve bevel; the rest sweep a mesh section (build_pipe_mesh).
    _PROFILE_CYCLE = ('ROUND', 'SQUARE', 'RECT')
    # Implicit click-vs-stroke gates (screen px): drag past START to begin a
    # freehand stroke; record a sample every GATE px along it.
    _STROKE_START_PX = 8
    _STROKE_GATE_PX = 6

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Run inside View3D")
            return {'CANCELLED'}
        # Fixed fallback plane (used only when the surface ray misses): through
        # the active object's origin, facing the camera at invoke time.
        rv3d = context.region_data
        obj = context.active_object
        self._origin = (obj.matrix_world.translation if obj is not None
                        else context.scene.cursor.location.copy())
        self._normal = raycast.view_direction(rv3d)
        self._pts = []            # confirmed 3D points (Vectors), already lifted
        self._groups = []         # anchors per click/stroke -- whole-stroke undo
        self._cursor3d = None     # current 3D point
        self._on_surface = False  # did the last sample hit a surface?
        self._snap_kind = None    # VERT/MID/EDGE/FACE/GRID/None -- HUD marker
        self._preview = None      # live curve object (becomes the result)
        self._finalized = False
        self._press_px = None     # LMB press position; None = button is up
        self._stroking = False    # drag passed the start gate -> freehand stroke
        self._stroke = []         # raw stroke samples (Vectors) while dragging
        self._last_stroke_px = None

        prefs = get_prefs(context)
        # Session-local snap toggles, seeded from prefs and flipped live with the
        # same keys as the ADD tool (Tab/S surface, V vertex/edge, X grid).
        self._surface_lock = prefs.surface_snap
        self._geo_snap = prefs.geo_snap
        self._grid_snap = prefs.snap_enabled
        self._follow = self._can_follow and prefs.pipe_follow_surface
        self._follow_segs = prefs.pipe_follow_segments
        self._smooth = self._can_smooth and prefs.pipe_smooth
        self._profile = prefs.pipe_profile if self._has_profile else 'ROUND'
        self._geo = snapping.collect_geo(context, prefs.snap_target)

        self._init_params(prefs)

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        try:
            context.window_manager.modal_handler_add(self)
        except Exception:  # never orphan the draw handler if the modal won't start
            self._cleanup(context)
            raise
        try:
            chips = self._shortcut_chips()
            context.workspace.status_text_set(
                "%s    " % self._title
                + "    ".join("%s: %s" % (c[0], c[1]) for c in chips))
        except Exception:
            pass
        return {'RUNNING_MODAL'}

    def _init_params(self, prefs):
        """Pull the starting radius/clearance/sag from preferences. Subclasses
        override to read their own keys."""
        self._radius = prefs.pipe_radius
        self._offset = prefs.pipe_offset
        self._sag = 0.0
        self._segments = 12

    def _lift(self):
        """Distance to push each point off the surface along its normal: the
        tube's radius (so the round section rests ON the surface) plus the user
        clearance. This is the core fix for the tube sinking into the model."""
        return self._radius + self._offset

    def _sample(self, context, event):
        """Resolve the mouse to a 3D point through the shared snap chain:
        vertex/edge (exact) -> surface/face (lifted by radius+clearance) ->
        grid -> free fallback plane. Each tier is independently toggleable."""
        region, rv3d = context.region, context.region_data
        coord = (event.mouse_region_x, event.mouse_region_y)
        prefs = get_prefs(context)
        self._on_surface = False

        # 1) vertex / edge snap -- exact, highest priority
        if self._geo_snap:
            hit = snapping.geo_snap_3d(region, rv3d, coord, self._geo,
                                       prefs.snap_pixels)
            if hit is not None:
                self._snap_kind = hit[1]
                return hit[0].copy()

        # 2) surface / face snap -- lift off the surface by radius + clearance
        if self._surface_lock:
            surf = raycast.ray_cast_surface(context, region, rv3d, coord)
            if surf is not None:
                location, normal, _obj = surf
                self._on_surface = True
                self._snap_kind = 'FACE'
                return location + normal.normalized() * self._lift()

        # 3) free point on the fallback plane, optionally locked to the grid
        point = raycast.ray_to_plane(region, rv3d, coord,
                                     self._origin, self._normal)
        if point is not None and self._grid_snap:
            self._snap_kind = 'GRID'
            return snapping.grid_snap_3d(point, prefs.grid_world, True)
        self._snap_kind = None
        return point

    def _adjust(self, event, sign):
        """Wheel live-tuning: bare = radius, Ctrl = clearance, Shift = sag
        (cable only)."""
        if event.ctrl:
            self._offset = max(0.0, self._offset + sign * 0.005)
        elif event.shift and self._has_sag:
            self._sag = max(0.0, self._sag + sign * 0.02)
        else:
            self._radius = max(0.001, self._radius + sign * 0.005)

    # --- routing ---------------------------------------------------------

    def _route_points(self, context, anchors):
        """Convert clicked anchors into the final dense point list. Pipe drapes
        over the surface; the cable subclass overrides this to hang a catenary."""
        if self._follow and len(anchors) >= 2:
            # Freehand strokes and smoothed paths are already dense: snapping
            # each sample (segments=1) is enough and keeps the preview fast.
            segs = 1 if (self._stroking or self._smoothing(anchors)) \
                else self._follow_segs
            return snapping.drape_path(context, anchors, segs, self._lift())
        return list(anchors)

    def _anchor_list(self, include_cursor):
        anchors = list(self._pts) + list(self._stroke)
        if include_cursor and self._cursor3d is not None:
            anchors = anchors + [self._cursor3d]
        return anchors

    def _smoothing(self, anchors):
        """Is the Catmull-Rom pass live for this rebuild? Not while a raw
        freehand stroke is still being dragged (the ink previews as drawn and
        snaps to the clean spline on release)."""
        return self._smooth and not self._stroking and len(anchors) >= 3

    def _end_press(self):
        """LMB released: commit the press as one anchor (plain click) or as a
        freehand stroke reduced to clean anchors (RDP, epsilon scaled to the
        tube radius). Each press lands as ONE undo group for Backspace."""
        if self._stroking and len(self._stroke) >= 2:
            eps = max(self._radius * 0.35, 1e-4)
            new = [Vector(p) for p in
                   path.rdp_simplify([tuple(p) for p in self._stroke], eps)]
        elif self._stroke:                       # a plain click
            new = [self._stroke[0]]
        else:
            new = []
        if new:
            self._pts.extend(new)
            self._groups.append(len(new))
        self._press_px = None
        self._stroking = False
        self._stroke = []
        self._last_stroke_px = None
        return True

    # --- live preview ----------------------------------------------------

    def _build_data(self, context, anchors):
        """Build the tube datablock for the given anchors. ROUND uses a curve
        bevel; SQUARE/RECT sweep a mesh cross-section (build_pipe_mesh). Smooth
        Path interpolates the anchors with a Catmull-Rom first -- or, for a
        ROUND non-follow pipe, emits an editable AUTO-handle Bezier instead of
        a baked poly-line. Returns (data, is_mesh) or (None, False)."""
        if len(anchors) < 2:
            return None, False
        name = "Hardflow_%s" % self._title
        prof = geometry.profile_points(self._profile, self._radius)
        smooth = self._smoothing(anchors)
        if smooth and prof is None and not self._follow:
            return geometry.build_pipe(anchors, radius=self._radius, name=name,
                                       spline_type='BEZIER'), False
        if smooth:
            anchors = [Vector(p) for p in
                       path.catmull_rom([tuple(p) for p in anchors])]
        pts = self._route_points(context, anchors)
        if prof is None:
            return geometry.build_pipe(pts, radius=self._radius, name=name), False
        return geometry.build_pipe_mesh(pts, prof, name=name), True

    def _set_preview_data(self, context, data, is_mesh):
        """Swap the preview object's data in place; recreate the object when the
        data TYPE changed (curve <-> mesh), since an object's type is fixed."""
        if self._preview is not None and (
                (is_mesh and self._preview.type != 'MESH')
                or (not is_mesh and self._preview.type != 'CURVE')):
            self._clear_preview()
        if self._preview is None:
            self._preview = bpy.data.objects.new(data.name, data)
            context.collection.objects.link(self._preview)
        else:
            old = self._preview.data
            self._preview.data = data
            self._free_data(old)

    def _rebuild_preview(self, context):
        """Build / refresh the real tube object so the committed result is exactly
        what is shown."""
        data, is_mesh = self._build_data(context, self._anchor_list(True))
        if data is None:
            self._clear_preview()
            return
        self._set_preview_data(context, data, is_mesh)

    @staticmethod
    def _free_data(data):
        if data is None or data.users != 0:
            return
        if isinstance(data, bpy.types.Mesh):
            bpy.data.meshes.remove(data)
        elif isinstance(data, bpy.types.Curve):
            bpy.data.curves.remove(data)

    def _clear_preview(self):
        if self._preview is not None and self._preview.name in bpy.data.objects:
            data = self._preview.data
            bpy.data.objects.remove(self._preview, do_unlink=True)
            self._free_data(data)
        self._preview = None

    # --- event loop ------------------------------------------------------

    def modal(self, context, event):
        context.area.tag_redraw()
        dirty = False

        if event.type == 'MOUSEMOVE':
            self._cursor3d = self._sample(context, event)
            if self._press_px is not None and self._cursor3d is not None:
                px = (event.mouse_region_x, event.mouse_region_y)
                if (not self._stroking and _px_dist2(px, self._press_px)
                        >= self._STROKE_START_PX ** 2):
                    self._stroking = True   # the press became a freehand drag
                if (self._stroking and _px_dist2(px, self._last_stroke_px)
                        >= self._STROKE_GATE_PX ** 2):
                    self._stroke.append(self._cursor3d.copy())
                    self._last_stroke_px = px
            dirty = True

        elif event.type == 'WHEELUPMOUSE' and event.value == 'PRESS':
            self._adjust(event, +1)
            dirty = True

        elif event.type == 'WHEELDOWNMOUSE' and event.value == 'PRESS':
            self._adjust(event, -1)
            dirty = True

        elif event.type in {'TAB', 'S'} and event.value == 'PRESS':
            self._surface_lock = not self._surface_lock
            self._cursor3d = self._sample(context, event)
            dirty = True

        elif event.type == 'V' and event.value == 'PRESS':
            self._geo_snap = not self._geo_snap
            self._cursor3d = self._sample(context, event)
            dirty = True

        elif event.type == 'X' and event.value == 'PRESS':
            self._grid_snap = not self._grid_snap
            self._cursor3d = self._sample(context, event)
            dirty = True

        elif (event.type == 'F' and event.value == 'PRESS' and self._can_follow):
            self._follow = not self._follow
            dirty = True

        elif (event.type == 'P' and event.value == 'PRESS' and self._has_profile):
            cyc = self._PROFILE_CYCLE
            i = cyc.index(self._profile) if self._profile in cyc else -1
            self._profile = cyc[(i + 1) % len(cyc)]
            dirty = True

        elif (event.type == 'C' and event.value == 'PRESS' and self._can_smooth):
            self._smooth = not self._smooth
            dirty = True

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if self._cursor3d is not None:
                # Click or stroke? Decided by drag distance; resolved on RELEASE.
                self._press_px = (event.mouse_region_x, event.mouse_region_y)
                self._last_stroke_px = self._press_px
                self._stroke = [self._cursor3d.copy()]
                dirty = True

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            if self._press_px is not None:
                dirty = self._end_press()

        elif event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            if len(self._pts) >= 2:
                return self._commit(context)

        elif event.type == 'BACK_SPACE' and event.value == 'PRESS':
            if self._pts:
                take = self._groups.pop() if self._groups else 1
                del self._pts[-max(1, take):]   # a whole stroke undoes at once
                dirty = True

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._cleanup(context)
            return {'CANCELLED'}

        elif event.type in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}

        if dirty:
            self._rebuild_preview(context)
        return {'RUNNING_MODAL'}

    # --- HUD -------------------------------------------------------------

    def _screen_points(self, context):
        region, rv3d = context.region, context.region_data
        pts3d = self._anchor_list(include_cursor=True)
        out = []
        for p in pts3d:
            s = raycast.world_to_screen(region, rv3d, p)
            if s is not None:
                out.append((s[0], s[1]))
        return out

    def _hud_lines(self):
        def onoff(flag):
            return "ON" if flag else "OFF"
        controls = ("Wheel radius · Ctrl+Wheel clearance · "
                    "V vertex · S/Tab surface · X grid")
        params = "Radius %.3f m · Clearance %.3f m" % (self._radius, self._offset)
        if self._can_follow:
            controls += " · F follow"
            params += " · Follow %s" % onoff(self._follow)
        if self._can_smooth:
            controls += " · C smooth"
            params += " · Smooth %s" % onoff(self._smooth)
        if self._has_profile:
            controls += " · P profile"
            params += " · Profile %s" % self._profile
        if self._has_sag:
            controls += " · Shift+Wheel sag"
            params += " · Sag %.3f m" % self._sag
        return [
            "%s — LMB click / drag freehand · Enter create · Backspace undo "
            "· Esc cancel" % self._title,
            controls,
            params,
            "Snap → vertex %s · surface %s · grid %s · now: %s"
            % (onoff(self._geo_snap), onoff(self._surface_lock),
               onoff(self._grid_snap), self._snap_kind or "free"),
        ]

    def _draw_px(self, context):
        prefs = get_prefs(context)
        region, rv3d = context.region, context.region_data
        accent = tuple(prefs.line_color)[:3] + (1.0,)
        pts = self._screen_points(context)
        placed = pts[:len(self._pts)]
        hud.draw_points(placed, tuple(prefs.line_color))

        cursor_px = None
        if self._cursor3d is not None:
            s = raycast.world_to_screen(region, rv3d, self._cursor3d)
            if s is not None:
                cursor_px = (s[0], s[1])
        # Dynamic alignment guides: a dashed full-span line when the live cursor is
        # square with a placed point (the shared BoxCutter-style hint).
        if placed and cursor_px is not None:
            hud.draw_alignment_guides(region, placed, cursor_px)
        # Premium snap marker (ring + dot) at the cursor, colored by snap kind --
        # matching every other draw tool.
        if cursor_px is not None and self._snap_kind is not None:
            hud.draw_snap_marker(cursor_px, kind=self._snap_kind, fallback=accent)

        hud.draw_hud(region, self._hud_lines(), title=self._title, accent=accent)
        hud.draw_shortcut_bar(region, self._shortcut_chips(), accent=accent)

    def _shortcut_chips(self):
        """Bottom shortcut-bar chips with the live engaged state -- the pressable,
        glanceable form of the HUD control line."""
        chips = [("Wheel", "Radius"),
                 ("V", "Vertex", self._geo_snap),
                 ("S/Tab", "Surface", self._surface_lock),
                 ("X", "Grid", self._grid_snap)]
        if self._can_follow:
            chips.append(("F", "Follow", self._follow))
        if self._can_smooth:
            chips.append(("C", "Smooth", self._smooth))
        if self._has_profile:
            chips.append(("P", self._profile))
        if self._has_sag:
            chips.append(("Sh+Wheel", "Sag"))
        return chips + [("Enter", "Create"), ("Esc", "Cancel")]

    # --- commit / cleanup ------------------------------------------------

    def _finalize_preview(self, context):
        """Promote the live preview object to the committed result: drop the
        hovering cursor point, rebuild from the clicked anchors only, select it."""
        anchors = self._anchor_list(include_cursor=False)
        data, is_mesh = self._build_data(context, anchors)
        if data is None:
            return False
        self._set_preview_data(context, data, is_mesh)
        # Mark finalized the moment the object is promoted -- if the selection
        # bookkeeping below raises, _cleanup must NOT delete the committed object.
        self._finalized = True
        for o in list(context.selected_objects):
            o.select_set(False)
        self._preview.select_set(True)
        context.view_layer.objects.active = self._preview
        return True

    def _commit(self, context):
        try:
            if not self._finalize_preview(context):
                self.report({'WARNING'}, "%s: need at least 2 points" % self._title)
        except Exception as ex:  # noqa: BLE001
            self.report({'ERROR'}, "Hardflow %s: %s" % (self._title, ex))
        self._cleanup(context)
        return {'FINISHED'}

    def _cleanup(self, context):
        if not self._finalized:
            self._clear_preview()
        try:
            context.workspace.status_text_set(None)   # restore default hints
        except Exception:
            pass
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        if context.area is not None:
            context.area.tag_redraw()


class HARDFLOW_OT_pipe(_CurveDraw, Operator):
    bl_idname = "mesh.hardflow_pipe"
    bl_label = "Hardflow Pipe"
    bl_description = "Draw a line on the surface, convert it to a round pipe"
    bl_options = {'REGISTER', 'UNDO'}

    _title = "Pipe"
    _has_sag = False
    _can_follow = True
    _has_profile = True


class HARDFLOW_OT_cable(_CurveDraw, Operator):
    bl_idname = "mesh.hardflow_cable"
    bl_label = "Hardflow Cable"
    bl_description = ("Draw anchor points on the surface, connect them with a "
                      "sagging cable / rope")
    bl_options = {'REGISTER', 'UNDO'}

    _title = "Cable"
    _has_sag = True
    _can_follow = False   # a cable hangs free; it does not drape over the wall
    _can_smooth = False   # the sag (or the settle) IS the cable's shape

    def _init_params(self, prefs):
        self._radius = prefs.cable_radius
        self._offset = prefs.pipe_offset
        self._sag = prefs.cable_sag
        self._segments = prefs.cable_segments

    def _route_points(self, context, anchors):
        return transform.cable_chain(
            [(p[0], p[1], p[2]) for p in anchors],
            segments=self._segments, sag=self._sag, axis=2)


class HARDFLOW_OT_sweep(_CurveDraw, Operator):
    bl_idname = "mesh.hardflow_sweep"
    bl_label = "Hardflow Sweep"
    bl_description = ("Draw a path and sweep a structural profile along it "
                      "(Follow-Me / sweep): L / U / T / I / box cross-sections, "
                      "P cycles")
    bl_options = {'REGISTER', 'UNDO'}

    _title = "Sweep"
    _has_sag = False
    _can_follow = True
    _has_profile = True
    # Structural sections (no ROUND -- a sweep is always a meshed cross-section).
    _PROFILE_CYCLE = ('L', 'U', 'T', 'I', 'SQUARE', 'RECT')

    def _init_params(self, prefs):
        self._radius = prefs.pipe_radius
        self._offset = prefs.pipe_offset
        self._sag = 0.0
        self._segments = 12
        self._profile = 'L'      # a structural section, not the round curve
