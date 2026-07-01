# Non-destructive cutter management: apply (bake), select, delete, extract,
# scroll. The "Cutters" list in the N-panel delegates to these operators.
import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, StringProperty, FloatProperty

from ..core import boolean, geometry
from ..preferences import get_prefs


def _still_used(cutter, ignore=None):
    """Is any object still using this cutter in a boolean modifier?"""
    for ob in bpy.data.objects:
        if ob is ignore:
            continue
        for m in ob.modifiers:
            if getattr(m, "object", None) is cutter:
                return True
    return False


class HARDFLOW_OT_apply_cutters(Operator):
    bl_idname = "object.hardflow_apply_cutters"
    bl_label = "Apply Cutters"
    bl_description = ("Apply all live Hardflow booleans on the active object "
                      "(bake); delete cutters no longer used")
    bl_options = {'REGISTER', 'UNDO'}

    delete_cutters: BoolProperty(
        name="Delete Cutters",
        description="After applying, delete cutters not used anywhere else",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj) and any(m.name.startswith("HF_Bool")
                                 for m in obj.modifiers)

    def execute(self, context):
        obj = context.active_object
        used = []
        failed = 0
        not_first = 0
        for mod in list(obj.modifiers):
            if not mod.name.startswith("HF_Bool"):
                continue
            if mod.type == 'BOOLEAN' and mod.object is not None:
                used.append(mod.object)
            # By now every HF_Bool above this one has been applied/removed, so if
            # this boolean still isn't first a NON-Hardflow modifier sits above
            # it -- Blender then applies it out of stack order and the result can
            # differ from the live preview. Surface that rather than hide it.
            if obj.modifiers and obj.modifiers[0].name != mod.name:
                not_first += 1
            if not self._apply_with_fallback(context, obj, mod):
                failed += 1

        # Opt-in topology cleanup: re-quad the n-gons the baked booleans left.
        if get_prefs(context).cut_dissolve_ngons and obj.type == 'MESH':
            geometry.dissolve_boolean_ngons(obj)

        removed = 0
        if self.delete_cutters:
            for cutter in set(used):
                if not _still_used(cutter):
                    bpy.data.objects.remove(cutter, do_unlink=True)
                    removed += 1
        if failed:
            self.report({'WARNING'},
                        "%d cutter(s) failed to apply (left as live modifiers). "
                        "Fix the target's normals/non-manifold geometry." % failed)
        elif not_first:
            self.report({'WARNING'},
                        "Applied, but %d cutter(s) sat below other modifiers; the "
                        "result may differ from the preview. Move Hardflow "
                        "booleans to the top of the stack." % not_first)
        else:
            self.report({'INFO'}, "Cutters applied (%d deleted)" % removed)
        return {'FINISHED'}

    def _apply_with_fallback(self, context, obj, mod):
        """Apply one HF_Bool modifier, retrying with the FAST solver and a cutter
        normal repair when the preferred solver chokes. Returns True on success;
        on total failure the modifier is left live (non-destructive) so nothing is
        silently lost."""
        cutter = getattr(mod, "object", None)
        for repair in (False, True):
            if repair and mod.type == 'BOOLEAN':
                mod.solver = 'FAST'
                if cutter is not None:
                    boolean.recalc_normals(cutter)
            try:
                with context.temp_override(active_object=obj, object=obj):
                    bpy.ops.object.modifier_apply(modifier=mod.name)
                return True
            except RuntimeError:
                continue
        return False


class HARDFLOW_OT_select_cutter(Operator):
    bl_idname = "object.hardflow_select_cutter"
    bl_label = "Select Cutter"
    bl_description = "Make the cutter visible, select and activate it (to edit)"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        cutter = bpy.data.objects.get(self.name)
        if cutter is None:
            self.report({'WARNING'}, "Cutter not found")
            return {'CANCELLED'}
        for o in list(context.selected_objects):
            o.select_set(False)
        cutter.hide_viewport = False
        cutter.hide_set(False)
        cutter.select_set(True)
        context.view_layer.objects.active = cutter
        return {'FINISHED'}


class HARDFLOW_OT_remove_cutter(Operator):
    bl_idname = "object.hardflow_remove_cutter"
    bl_label = "Delete Cutter"
    bl_description = ("Delete the cutter from the scene; boolean modifiers using "
                      "it become ineffective (reversible with undo)")
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        cutter = bpy.data.objects.get(self.name)
        if cutter is None:
            return {'CANCELLED'}
        bpy.data.objects.remove(cutter, do_unlink=True)
        return {'FINISHED'}


class HARDFLOW_OT_extract_cutter(Operator):
    bl_idname = "mesh.hardflow_extract_cutter"
    bl_label = "Extract Cutter"
    bl_description = ("Copy the selected faces into a new standalone cutter "
                      "object (optionally solidified into a closed volume), at "
                      "the same world transform -- reuse the exact form to cut "
                      "somewhere else. Edit Mode, face selection")
    bl_options = {'REGISTER', 'UNDO'}

    thickness: FloatProperty(
        name="Thickness", subtype='DISTANCE',
        description="Solidify the extracted patch into a closed volume by this "
                    "much (0 = leave a flat face patch)",
        default=0.1, min=0.0, soft_max=5.0,
    )
    stash: BoolProperty(
        name="Stash As Cutter",
        description="Move the new object into the Hardflow Cutters collection and "
                    "show it as wire",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj is not None and obj.type == 'MESH'
                and context.mode == 'EDIT_MESH')

    def execute(self, context):
        import bmesh
        obj = context.active_object
        bm = bmesh.from_edit_mesh(obj.data)
        sel = [f.index for f in bm.faces if f.select]
        if not sel:
            self.report({'WARNING'}, "Select the faces to extract first")
            return {'CANCELLED'}
        # Flush the edit to object data so extract_faces reads current coords;
        # the face indices are stable across the mode switch (no topology change).
        bpy.ops.object.mode_set(mode='OBJECT')
        mesh = geometry.extract_faces(
            obj.data, sel, thickness=self.thickness, name=obj.name + "_cutter")
        if mesh is None:
            bpy.ops.object.mode_set(mode='EDIT')
            self.report({'WARNING'}, "Nothing extracted")
            return {'CANCELLED'}
        cutter = bpy.data.objects.new(obj.name + "_cutter", mesh)
        cutter.matrix_world = obj.matrix_world.copy()   # world-aligned to source
        context.collection.objects.link(cutter)
        if self.stash:
            boolean.stash_cutter(context, cutter, obj)
        for o in list(context.selected_objects):
            o.select_set(False)
        cutter.select_set(True)
        context.view_layer.objects.active = cutter
        self.report({'INFO'}, "Extracted %d face(s) into '%s'"
                    % (len(sel), cutter.name))
        return {'FINISHED'}


# --- Cutter Scroll: cycle a target's stashed cutters, show one at a time ------

def _target_cutters(target):
    """The stashed cutter objects still driving a live HF_Bool modifier on
    `target`, in stack order -- the cut history to scroll through. Uses the
    modifier order (top = most recent cut on top of the stack) so scrolling
    matches how the cuts were layered."""
    out = []
    seen = set()
    for m in target.modifiers:
        if (m.type == 'BOOLEAN' and m.name.startswith("HF_Bool")
                and m.object is not None and m.object.name not in seen):
            out.append(m.object)
            seen.add(m.object.name)
    return out


class HARDFLOW_OT_cutter_scroll(Operator):
    bl_idname = "object.hardflow_cutter_scroll"
    bl_label = "Cutter Scroll"
    bl_description = ("Step through the cutters that carved the active object: "
                      "reveal one cutter, select it (to move / edit / delete), "
                      "and hide the rest. Wheel / arrows scroll, Enter keeps the "
                      "shown cutter selected, Esc restores visibility")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and bool(_target_cutters(obj))

    def invoke(self, context, event):
        self.target = context.active_object
        self.cutters = _target_cutters(self.target)
        if not self.cutters:
            self.report({'WARNING'}, "No cutters on the active object")
            return {'CANCELLED'}
        # Remember each cutter's viewport visibility so Esc can restore it.
        self._prev_hide = {c.name: (c.hide_viewport, c.hide_get())
                           for c in self.cutters}
        self.index = 0
        self._show_only(context, self.index)
        context.window_manager.modal_handler_add(self)
        self._banner(context)
        return {'RUNNING_MODAL'}

    def _show_only(self, context, index):
        """Reveal + select cutter `index`, hide the others."""
        for i, c in enumerate(self.cutters):
            shown = i == index
            c.hide_viewport = not shown
            c.hide_set(not shown)
            c.select_set(shown)
        cur = self.cutters[index]
        context.view_layer.objects.active = cur

    def _banner(self, context):
        cur = self.cutters[self.index]
        context.workspace.status_text_set(
            "Cutter Scroll  [%d/%d]  %s   |  Wheel/Arrows scroll   Enter keep   "
            "Esc restore" % (self.index + 1, len(self.cutters), cur.name))

    def _finish(self, context):
        context.workspace.status_text_set(None)

    def modal(self, context, event):
        if event.type in {'WHEELDOWNMOUSE', 'DOWN_ARROW', 'RIGHT_ARROW'} \
                and event.value == 'PRESS':
            self.index = (self.index + 1) % len(self.cutters)
            self._show_only(context, self.index)
            self._banner(context)
            return {'RUNNING_MODAL'}
        if event.type in {'WHEELUPMOUSE', 'UP_ARROW', 'LEFT_ARROW'} \
                and event.value == 'PRESS':
            self.index = (self.index - 1) % len(self.cutters)
            self._show_only(context, self.index)
            self._banner(context)
            return {'RUNNING_MODAL'}
        if event.type in {'RET', 'NUMPAD_ENTER', 'LEFTMOUSE'} \
                and event.value == 'PRESS':
            # Keep the shown cutter selected + active; leave the rest hidden as
            # wire so the user can grab/edit this one immediately.
            self._finish(context)
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            # Restore every cutter's original visibility (non-committal browse).
            for c in self.cutters:
                prev = self._prev_hide.get(c.name)
                if prev is not None:
                    c.hide_viewport, hidden = prev[0], prev[1]
                    c.hide_set(hidden)
            self._finish(context)
            return {'CANCELLED'}
        # Let the viewport navigate while scrolling.
        if event.type in {'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM'}:
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}
