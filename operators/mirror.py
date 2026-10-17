# Hard-surface Mirror / Symmetry -- the one-keystroke symmetry pass.
#
# Blender already has a Mirror modifier and a Symmetrize operator, which is why
# v1.13 dropped Hardflow's thin wrappers around them. What a hard-surface
# modeler actually presses a key for is the *decision*: model one half, then
# mirror it across the right axis, about the right pivot, throwing away the half
# that is in the way -- without opening a modifier panel, picking an axis from a
# dropdown or choosing a bisect direction. That is what this operator does, and
# it is what the paid incumbents (HardOps' Alt+X) get pressed for all day.
#
# Layering: every decision (which axis, which half, which bisect normal, whether
# a pivot helper is needed) is pure math in core/mirror.py; this file is the bpy
# glue -- modifier wiring, the bmesh symmetrize, and the stack sort that puts the
# Mirror where core/modifiers says it belongs.
import bmesh
import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from mathutils import Vector

from ..core import boolean, mirror as mirror_math
from .hardops import sort_modifier_stack

# The managed modifier, matched by name so a re-run / F9 updates it in place
# instead of stacking copies (same contract as HF_Bevel in smart_sharpen).
MIRROR_NAME = "HF_Mirror"
# Reused hidden empty that lets a Mirror modifier mirror about the 3D cursor.
PIVOT_PREFIX = "HF_MirrorPivot"

_MODES = (
    ('MODIFIER', "Modifier (live)",
     "Add a live Mirror modifier and sort it into the hard-surface stack "
     "position -- keep modeling one half and watch both sides update"),
    ('BISECT', "Bisect + Mirror",
     "Make it symmetric as real geometry now: cut on the mirror plane, discard "
     "the far half and mirror the near one, welded on the seam"),
)

_AXES = (
    ('VIEW', "View", "Take the axis from the viewport: the left-right axis of "
                     "the way you are looking (never the depth axis)"),
    ('X', "X", "Mirror across the YZ plane"),
    ('Y', "Y", "Mirror across the XZ plane"),
    ('Z', "Z", "Mirror across the XY plane"),
)

_PIVOTS = (
    ('ORIGIN', "Object Origin", "Mirror about the object's own origin"),
    ('CURSOR', "3D Cursor", "Mirror about the 3D cursor (a hidden helper empty "
                            "carries the plane for the modifier path)"),
    ('ACTIVE', "Active Object", "Mirror the selected objects about the ACTIVE "
                                "object's origin -- for mirroring a part across "
                                "the hull it belongs to"),
)


def view_direction(context):
    """The direction the user is looking (camera -> scene), or None outside a 3D
    view. Lives here so core/mirror stays free of bpy."""
    space = getattr(context, "space_data", None)
    rv3d = getattr(space, "region_3d", None) if space is not None else None
    if rv3d is None:
        return None
    # Row 2 of the view rotation is the view's +Z (pointing at the camera), so
    # the look direction is its negation.
    row = rv3d.view_matrix.to_3x3().row[2]
    return (-row[0], -row[1], -row[2])


def resolve_axis(context, axis):
    """Turn the `axis` property into a concrete 'X'/'Y'/'Z'. 'VIEW' resolves to
    the left-right axis of the current view (core.mirror.screen_axis), falling
    back to X with no viewport (headless, or F9 replayed from a script)."""
    if axis != 'VIEW':
        return axis
    direction = view_direction(context)
    if direction is None:
        return 'X'
    return mirror_math.screen_axis(direction)


def resolve_keep_positive(context, axis, flip=False):
    """Which half to keep: the one facing the camera, inverted by `flip`. With
    no viewport, keeps +axis so the result is deterministic."""
    direction = view_direction(context)
    keep = (mirror_math.keep_positive_side(direction, axis)
            if direction is not None else True)
    return (not keep) if flip else keep


def pivot_world(context, obj, pivot):
    """World-space point the mirror plane passes through."""
    if pivot == 'CURSOR':
        return tuple(context.scene.cursor.location)
    if pivot == 'ACTIVE':
        active = context.active_object
        if active is not None and active is not obj:
            return tuple(active.matrix_world.translation)
    return tuple(obj.matrix_world.translation)


def pivot_empty(context, obj, location):
    """Get/create the hidden empty a Mirror modifier mirrors about, parked in
    Hardflow's helper collection. One per object, reused across re-runs."""
    name = "%s_%s" % (PIVOT_PREFIX, obj.name)
    empty = bpy.data.objects.get(name)
    if empty is None or empty.type != 'EMPTY':
        empty = bpy.data.objects.new(name, None)
        empty.empty_display_size = 0.1
        boolean.helper_collection(context).objects.link(empty)
    empty.location = location
    empty.hide_render = True
    return empty


def apply_mirror_modifier(context, obj, axis, pivot='ORIGIN', bisect=False,
                          flip_bisect=False, clip=True, merge=0.0001,
                          sort=True, booleans_first=True):
    """Add or refresh the managed HF_Mirror modifier on `obj`; returns it.

    Idempotent -- matched by name, so a re-run / F9 updates in place instead of
    stacking a second Mirror."""
    mod = obj.modifiers.get(MIRROR_NAME)
    if mod is not None and mod.type != 'MIRROR':
        obj.modifiers.remove(mod)               # name taken by another type
        mod = None
    if mod is None:
        mod = obj.modifiers.new(MIRROR_NAME, 'MIRROR')
    flags = mirror_math.use_axis_flags(axis)
    mod.use_axis = flags
    mod.use_bisect_axis = tuple(bool(bisect and f) for f in flags)
    mod.use_bisect_flip_axis = tuple(bool(flip_bisect and f) for f in flags)
    mod.use_clip = clip
    mod.use_mirror_merge = merge > 0.0
    mod.merge_threshold = max(merge, 1e-6)
    # A pivot off the object's own origin needs a mirror object to carry the
    # plane -- the modifier can only mirror about an origin.
    target = pivot_world(context, obj, pivot)
    origin = tuple(obj.matrix_world.translation)
    if pivot != 'ORIGIN' and mirror_math.needs_pivot_helper(target, origin):
        active = context.active_object
        if pivot == 'ACTIVE' and active is not None and active is not obj:
            mod.mirror_object = active
        else:
            mod.mirror_object = pivot_empty(context, obj, target)
    else:
        mod.mirror_object = None
    if sort:
        # Put it where core/modifiers says a Mirror belongs (below the booleans,
        # or above them to mirror the raw form). This is the reason it is
        # Hardflow's mirror and not just Blender's button.
        sort_modifier_stack(obj, booleans_first)
    return mod


def make_symmetric(obj, axis, pivot, keep_positive, merge=0.0001):
    """Make `obj` symmetric as real geometry: cut on the mirror plane, discard
    the far half and mirror the near one, welded on the seam.

    `pivot` is world-space; it is taken into the object's local space, where the
    mirror axis is the object's own -- the same semantics as the Mirror modifier,
    so the two modes agree on a rotated object. Returns the new vertex count.
    Object Mode, bmesh only (no bpy.ops), so it is safe inside a batch."""
    me = obj.data
    i = mirror_math.axis_index(axis)
    local = obj.matrix_world.inverted_safe() @ Vector(pivot)
    shift = local[i]
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        if abs(shift) > 1e-9:
            for v in bm.verts:                  # work about the plane, then undo
                v.co[i] -= shift
        # Refuse to mirror away the whole object: if nothing is on the kept
        # side, symmetrize would clear every vertex and hand back an empty mesh.
        # That happens easily with an off-origin pivot (a part entirely on one
        # side of the 3D cursor), so bail out and leave the mesh untouched --
        # the caller reports it.
        tol = max(merge, 1e-6)
        if not any((v.co[i] >= -tol) if keep_positive else (v.co[i] <= tol)
                   for v in bm.verts):
            return 0
        bmesh.ops.symmetrize(
            bm, input=bm.verts[:] + bm.edges[:] + bm.faces[:],
            direction=mirror_math.symmetrize_direction(axis, keep_positive),
            dist=max(merge, 1e-6))
        if abs(shift) > 1e-9:
            for v in bm.verts:
                v.co[i] += shift
        bm.normal_update()
        bm.to_mesh(me)
        count = len(bm.verts)
    finally:
        bm.free()
    me.update()
    return count


class HARDFLOW_OT_mirror(Operator):
    bl_idname = "object.hardflow_mirror"
    bl_label = "Hardflow Mirror"
    bl_description = ("Mirror the selected mesh(es) in one press: the axis comes "
                      "from the way you are looking, the half you can see is the "
                      "one that is kept, and a live Mirror modifier lands in the "
                      "right stack position. Re-runs / F9 update in place")
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(name="Mode", items=_MODES, default='MODIFIER')
    axis: EnumProperty(name="Axis", items=_AXES, default='VIEW')
    pivot: EnumProperty(name="Pivot", items=_PIVOTS, default='ORIGIN')
    flip: BoolProperty(
        name="Flip Side", default=False,
        description="Keep the far half instead of the one facing you",
    )
    bisect: BoolProperty(
        name="Bisect", default=True,
        description="Trim geometry that crosses the mirror plane instead of "
                    "letting the two halves overlap (modifier mode)",
    )
    clip: BoolProperty(
        name="Clip", default=True,
        description="Stop vertices from being dragged through the mirror plane "
                    "(modifier mode)",
    )
    merge: FloatProperty(
        name="Merge Distance", subtype='DISTANCE', default=0.0001,
        min=0.0, soft_max=0.1,
        description="Weld vertices this close to the mirror plane; 0 leaves the "
                    "seam open",
    )
    booleans_first: BoolProperty(
        name="Booleans First", default=True,
        description="Where the new Mirror lands in the stack: just below the "
                    "booleans (default), or above them to mirror the raw form. "
                    "Same choice as Sort Modifier Stack",
    )

    @classmethod
    def poll(cls, context):
        return (context.mode == 'OBJECT'
                and any(o.type == 'MESH' for o in context.selected_objects))

    def _targets(self, context):
        sel = [o for o in context.selected_objects if o.type == 'MESH']
        if self.pivot == 'ACTIVE' and len(sel) > 1:
            # Mirroring ABOUT the active object: it is the pivot, not a target.
            sel = [o for o in sel if o is not context.active_object]
        return sel

    def execute(self, context):
        targets = self._targets(context)
        if not targets:
            self.report({'ERROR'}, "Mirror: select a mesh")
            return {'CANCELLED'}
        axis = resolve_axis(context, self.axis)
        keep_positive = resolve_keep_positive(context, axis, self.flip)
        done = 0
        for obj in targets:
            try:
                if self.mode == 'MODIFIER':
                    apply_mirror_modifier(
                        context, obj, axis, pivot=self.pivot,
                        bisect=self.bisect,
                        # The modifier's bisect keeps the half on the + side of
                        # the axis unless flipped, so match the resolved choice.
                        flip_bisect=not keep_positive,
                        clip=self.clip, merge=self.merge,
                        booleans_first=self.booleans_first)
                else:
                    kept = make_symmetric(
                        obj, axis, pivot_world(context, obj, self.pivot),
                        keep_positive, merge=self.merge)
                    if not kept:
                        self.report(
                            {'WARNING'},
                            "Mirror skipped %s: nothing on the %s%s side of the "
                            "plane (try Flip Side)"
                            % (obj.name, '+' if keep_positive else '-', axis))
                        continue
                done += 1
            except Exception as ex:  # noqa: BLE001 -- one bad mesh can't abort all
                self.report({'WARNING'},
                            "Mirror failed on %s: %s" % (obj.name, ex))
        if not done:
            self.report({'ERROR'}, "Mirror: nothing mirrored")
            return {'CANCELLED'}
        self.report(
            {'INFO'}, "Mirror: %d object(s) on %s, kept %s%s (%s)"
            % (done, axis, '+' if keep_positive else '-', axis,
               "live modifier" if self.mode == 'MODIFIER' else "geometry"))
        return {'FINISHED'}

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "mode")
        col.prop(self, "axis")
        col.prop(self, "pivot")
        col.prop(self, "flip")
        if self.mode == 'MODIFIER':
            col.prop(self, "bisect")
            col.prop(self, "clip")
            col.prop(self, "booleans_first")
        col.prop(self, "merge")
