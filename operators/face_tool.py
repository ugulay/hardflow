# Shared modal base for the SketchUp-style "pick a face, drag a value" direct
# modeling tools (Push/Pull, Offset). Both have the same shell -- hover-pick a
# face, click to lock it, drag or type a measured value with a live
# snapshot/restore preview, commit or cancel -- and differ only in how they build
# the drag basis from the face and what they do with the value. Subclasses fill
# the hooks; everything common lives here so a fix/feature lands once.
#
# This is a plain mixin (NOT an Operator and NOT registered); each tool subclasses
# it alongside bpy.types.Operator. Layer rule respected: ops -> core only.
import bpy
from mathutils import Vector

from ..core import raycast, geometry, grid, snap
from ..preferences import get_prefs
from ..ui import draw as hud


# Shared numeric-entry key map (top row + numpad).
_DIGITS = {'ZERO': '0', 'ONE': '1', 'TWO': '2', 'THREE': '3', 'FOUR': '4',
           'FIVE': '5', 'SIX': '6', 'SEVEN': '7', 'EIGHT': '8', 'NINE': '9',
           'NUMPAD_0': '0', 'NUMPAD_1': '1', 'NUMPAD_2': '2', 'NUMPAD_3': '3',
           'NUMPAD_4': '4', 'NUMPAD_5': '5', 'NUMPAD_6': '6', 'NUMPAD_7': '7',
           'NUMPAD_8': '8', 'NUMPAD_9': '9'}


class _FaceDragModal:
    """Hover-pick a face, lock it, drag/type a value with live preview, apply.

    Subclass contract -- class attributes:
        _HOVER_FILL / _LOCK_FILL : RGBA face tints for hovered / locked.
        _snapshot_name           : unique mesh-snapshot datablock name.
        _select_warning          : Edit-Mode "nothing selected" message.
        allow_negative           : True if a typed value may be negative.

    Subclass contract -- methods:
        _init_tool(context, event)   : init tool-specific state (the drag value).
        _lock_face(context, co)      : build the drag basis from self.face_index
                                       + snapshot the mesh (Object Mode pick).
        _lock_edit(context, event)   : same from the selected faces (Edit Mode);
                                       return False when nothing is selected.
        _update_drag(context, co)    : set the drag value from the cursor.
        _set_value(v)                : set the drag value from a typed float.
        _refresh_preview()           : restore snapshot + re-apply the value.
        _repeat_last()               : set the value to the remembered last one.
        _remember_last()             : store the committed value for repeat.
        _hud_lines(context, prefs)   : the HUD text lines.
        _handle_key(context, event)  : optional extra keys; return True if used.
    """

    _HOVER_FILL = (0.15, 0.8, 1.0, 0.18)
    _LOCK_FILL = (1.0, 0.6, 0.1, 0.22)
    _snapshot_name = "hf_facetool_base"
    _select_warning = "Select face(s) first"
    allow_negative = True

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode in {'OBJECT', 'EDIT_MESH'})

    # --- lifecycle -------------------------------------------------------

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Run inside View3D")
            return {'CANCELLED'}
        self.obj = context.active_object
        self.edit = context.mode == 'EDIT_MESH'   # Edit Mode = drag selected faces
        self.snap = get_prefs(context).snap_enabled
        self.face_index = -1      # face under the cursor (Object Mode pick)
        self.locked = False       # has a face been picked?
        self.typed = ""           # numeric entry buffer
        self._infer = []          # axis-drag inference candidates (shared)
        self._infer_hit = False   # drag currently snapped to geometry
        self._base = None         # mesh snapshot for the live preview
        self._committed = False
        self._init_tool(context, event)

        # Edit Mode: there is no hover-pick -- lock straight onto the selection.
        if self.edit and not self._lock_edit(context, event):
            self.report({'WARNING'}, self._select_warning)
            return {'CANCELLED'}

        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            self._draw_px, (context,), 'WINDOW', 'POST_PIXEL')
        try:
            context.window_manager.modal_handler_add(self)
        except Exception:  # never orphan the draw handler if the modal won't start
            self._cleanup(context)
            raise
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        context.area.tag_redraw()
        co = (event.mouse_region_x, event.mouse_region_y)

        if event.type == 'MOUSEMOVE':
            if self.locked:
                self._update_drag(context, co)
                self._refresh_preview()
            else:
                self._hover_face(context, co)

        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if not self.locked:
                if self.face_index >= 0:
                    self._lock_face(context, co)
            else:
                return self._commit(context)

        elif (event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS'
              and self.locked):
            return self._commit(context)

        elif event.type == 'X' and event.value == 'PRESS':
            self.snap = not self.snap

        # R: repeat the last committed value on the locked face.
        elif event.type == 'R' and event.value == 'PRESS' and self.locked:
            self._repeat_last()
            self.typed = ""
            self._refresh_preview()

        # Tool-specific keys (e.g. Push/Pull's C copy toggle).
        elif event.value == 'PRESS' and self._handle_key(context, event):
            pass

        elif self.locked and event.value == 'PRESS' and self._edit_typed(event):
            self._refresh_preview()  # numeric entry handled

        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            self._cleanup(context)
            return {'CANCELLED'}

        elif event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE',
                            'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}

        return {'RUNNING_MODAL'}

    # --- shared picking / numeric entry ----------------------------------

    def _hover_face(self, context, co):
        """Raycast the active object; remember the base-mesh polygon index under
        the cursor (-1 when the cursor misses). `ray_cast` indexes the EVALUATED
        mesh -- a direct hit on the base mesh is used as-is; a hit on geometry a
        generative modifier added (index past the base mesh) is mapped back to the
        nearest base face so the tools still work on modified objects."""
        from bpy_extras import view3d_utils
        region, rv3d = context.region, context.region_data
        v = Vector((co[0], co[1]))
        ray_dir = view3d_utils.region_2d_to_vector_3d(region, rv3d, v)
        ray_o = view3d_utils.region_2d_to_origin_3d(region, rv3d, v)
        mw_inv = self.obj.matrix_world.inverted_safe()
        ok, loc, _nrm, index = self.obj.ray_cast(
            mw_inv @ ray_o, mw_inv.to_3x3() @ ray_dir)
        if not ok:
            self.face_index = -1
        elif index < len(self.obj.data.polygons):
            self.face_index = index                      # direct base-face hit
        else:
            self.face_index = geometry.nearest_face_to_point(self.obj, loc)

    def _edit_typed(self, event):
        """Build a numeric value from key presses, routing it to `_set_value`.
        Returns True if the key was consumed."""
        if event.type in _DIGITS:
            self.typed += _DIGITS[event.type]
        elif event.type in {'PERIOD', 'NUMPAD_PERIOD'} and '.' not in self.typed:
            self.typed += '.'
        elif event.type == 'MINUS' and self.allow_negative:
            self.typed = self.typed[1:] if self.typed.startswith('-') \
                else '-' + self.typed
        elif event.type == 'BACK_SPACE':
            self.typed = self.typed[:-1]
        else:
            return False
        try:
            self._set_value(float(self.typed))
        except ValueError:
            pass  # partial entry like "-" or "." -> keep the last good value
        return True

    # --- shared visual feedback ------------------------------------------

    def _face_screen_points(self, context):
        if self.edit or self.face_index < 0:   # Edit Mode: rely on mesh highlight
            return []
        poly = self.obj.data.polygons[self.face_index]
        mw = self.obj.matrix_world
        region, rv3d = context.region, context.region_data
        verts = self.obj.data.vertices
        pts = []
        for vi in poly.vertices:
            s = raycast.world_to_screen(region, rv3d, mw @ verts[vi].co)
            if s is None:
                return []
            pts.append((s[0], s[1]))
        return pts

    def _draw_px(self, context):
        prefs = get_prefs(context)
        pts = self._face_screen_points(context)
        if pts:
            fill = self._LOCK_FILL if self.locked else self._HOVER_FILL
            hud.draw_face_fill(pts, fill)
            hud.draw_shape(pts, tuple(prefs.line_color), closed=True)
        hud.draw_hud(context.region, self._hud_lines(context, prefs))

    # --- shared apply / teardown -----------------------------------------

    def _commit(self, context):
        # The live preview already wrote the change into the mesh; make sure it
        # reflects the final value, remember it for R, then keep it.
        try:
            self._refresh_preview()
        except Exception as ex:
            self.report({'ERROR'}, f"Hardflow: {ex}")
        self._remember_last()
        self._committed = True
        self._cleanup(context)
        return {'FINISHED'}

    def _cleanup(self, context):
        # Cancelled mid-preview -> roll the mesh back to the snapshot.
        if self._base is not None:
            if not self._committed:
                if self.edit:
                    geometry.restore_edit_mesh(self.obj, self._base)
                else:
                    geometry.restore_mesh(self.obj, self._base)
            geometry.free_mesh(self._base)
            self._base = None
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
        except (ValueError, AttributeError):
            pass
        context.area.tag_redraw()

    # --- shared axis-drag inference --------------------------------------

    def _capture_axis_inference(self, axis_co, axis_dir):
        """Build the candidate scalar positions a drag along (axis_co, axis_dir)
        can infer/snap to: every vertex and edge-midpoint of the locked object
        projected onto the axis (SketchUp-style inference -- e.g. snap an extrude
        to another feature's height). Captured once from the pre-edit snapshot;
        skipped on very dense meshes. Stores self._infer (sorted)."""
        src = self._base if self._base is not None else self.obj.data
        self._infer_hit = False
        if src is None or len(src.vertices) > 50000:
            self._infer = []
            return
        mw = self.obj.matrix_world
        vco = [mw @ v.co for v in src.vertices]
        cands = {round((p - axis_co).dot(axis_dir), 6) for p in vco}
        for e in src.edges:
            a, b = e.vertices
            mid = (vco[a] + vco[b]) * 0.5
            cands.add(round((mid - axis_co).dot(axis_dir), 6))
        self._infer = sorted(cands)

    def _snap_axis_value(self, value, context):
        """Inference-then-grid snap for an axis drag. Sets self._infer_hit and
        returns the snapped value (raw value when snap is off)."""
        self._infer_hit = False
        if not self.snap:
            return value
        prefs = get_prefs(context)
        tol = max(1e-4, prefs.grid_world * 0.5)
        inferred = snap.snap_to_candidates(value, self._infer, tol)
        if inferred != value:
            self._infer_hit = True
            return inferred
        return grid.snap_scalar(value, prefs.grid_world, True)

    # --- default hooks (subclasses override) -----------------------------

    def _handle_key(self, context, event):
        return False
