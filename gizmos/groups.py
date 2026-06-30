# GizmoGroups: the always-on persistent widget + one group per Workspace Tool.
#
# Move / Rotate / Scale wrap Blender's built-in transform operators (rock-solid,
# free snapping + numeric entry + axis constraints). Bevel drives an HF_Bevel
# modifier's width live via a property handler. Push/Pull is the custom modal
# gizmo from custom.py. The shared _make_* / _place_* builders keep the
# persistent group and the per-tool groups from duplicating setup code.
import bpy
from bpy.types import GizmoGroup
from mathutils import Matrix, Vector
from math import radians

from ..core import geometry
from .custom import HARDFLOW_GT_drag_extrude

# Per-axis index, name, RGB -- roughly Blender's gizmo theme so the handles read
# as X/Y/Z at a glance.
_AXES = (
    (0, 'X', (1.0, 0.2, 0.322)),
    (1, 'Y', (0.545, 0.863, 0.0)),
    (2, 'Z', (0.157, 0.565, 1.0)),
)
_HILITE = (1.0, 1.0, 1.0)


# --- math helpers ----------------------------------------------------------

def _unit(idx):
    v = [0.0, 0.0, 0.0]
    v[idx] = 1.0
    return Vector(v)


def _axis_basis(vec):
    """4x4 rotation mapping the gizmo's local +Z onto `vec` (arrow_3d and
    dial_3d both point along / spin about local +Z)."""
    z = Vector(vec).normalized()
    up = Vector((0.0, 0.0, 1.0))
    if abs(z.dot(up)) > 0.999:
        up = Vector((0.0, 1.0, 0.0))
    x = up.cross(z).normalized()
    y = z.cross(x).normalized()
    return Matrix(((x.x, y.x, z.x, 0.0),
                   (x.y, y.y, z.y, 0.0),
                   (x.z, y.z, z.z, 0.0),
                   (0.0, 0.0, 0.0, 1.0)))


def _axis_matrix(loc, idx):
    return Matrix.Translation(loc) @ _axis_basis(_unit(idx))


# --- bevel handler (module-level so it isn't bound to a stale object) -------

def _bevel_get():
    obj = bpy.context.active_object
    if obj is None or obj.type != 'MESH':
        return 0.0
    mod = obj.modifiers.get("HF_Bevel")
    return mod.width if mod is not None else 0.0


def _bevel_set(value):
    obj = bpy.context.active_object
    if obj is None or obj.type != 'MESH':
        return
    mod = obj.modifiers.get("HF_Bevel")
    if mod is None:
        if value <= 1e-6:
            return                       # don't spawn a zero-width modifier
        mod = obj.modifiers.new("HF_Bevel", 'BEVEL')
        mod.segments = 2
        mod.limit_method = 'ANGLE'
        mod.angle_limit = radians(30.0)
        mod.use_clamp_overlap = True
        mod.harden_normals = True
        mod.miter_outer = 'MITER_ARC'
    mod.width = max(0.0, value)


# --- gizmo builders --------------------------------------------------------

def _style(gz, color):
    gz.use_draw_modal = True
    gz.color = color
    gz.alpha = 0.65
    gz.color_highlight = _HILITE
    gz.alpha_highlight = 1.0


def _make_transform(group, operator, draw_style):
    """Three axis gizmos bound to a built-in transform operator (translate /
    resize -> arrow, rotate -> dial). Returns [(idx, gizmo), ...]."""
    out = []
    dial = operator == "transform.rotate"
    for idx, _name, color in _AXES:
        gz = group.gizmos.new("GIZMO_GT_dial_3d" if dial
                              else "GIZMO_GT_arrow_3d")
        if dial:
            gz.draw_options = {'ANGLE_VALUE'}
            gz.line_width = 3.0
        else:
            gz.draw_style = draw_style
            gz.length = 0.85
        props = gz.target_set_operator(operator)
        props.constraint_axis = (idx == 0, idx == 1, idx == 2)
        props.orient_type = 'GLOBAL'
        props.release_confirm = True
        _style(gz, color)
        out.append((idx, gz))
    return out


def _make_bevel(group):
    gz = group.gizmos.new("GIZMO_GT_arrow_3d")
    gz.draw_style = 'NORMAL'
    gz.length = 0.9
    gz.target_set_handler("offset", get=_bevel_get, set=_bevel_set)
    _style(gz, (0.15, 0.8, 1.0))
    gz.color_highlight = (0.4, 0.95, 1.0)
    return gz


def _make_pushpull(group):
    gz = group.gizmos.new(HARDFLOW_GT_drag_extrude.bl_idname)
    _style(gz, (1.0, 0.6, 0.1))
    gz.color_highlight = (1.0, 0.8, 0.3)
    return gz


# --- placement helpers -----------------------------------------------------

def _place_transform(pairs, loc, hide):
    for idx, gz in pairs:
        gz.hide = hide
        gz.matrix_basis = _axis_matrix(loc, idx)


def _setup_pushpull(gz, obj):
    """Aim the Push/Pull arrow at the selected faces' average center/normal.
    Returns False (hide it) when nothing usable is selected. Skipped mid-drag so
    the live extrude doesn't shift the drag axis under the cursor."""
    if getattr(gz, "_dragging", False):
        return True
    basis = geometry.selected_face_basis(obj)
    if basis is None:
        return False
    center, normal = basis
    mw = obj.matrix_world
    co = mw @ center
    nrm = (mw.to_3x3() @ normal).normalized()
    gz._obj = obj
    gz._edit = True
    gz._face_index = -1
    gz._axis_co = co
    gz._axis_dir = nrm
    # Size the handle to the object so it stays visible on big and small meshes.
    s = max(obj.dimensions) if any(obj.dimensions) else 1.0
    s = min(max(0.25 * s, 0.05), 2.0)
    gz.matrix_basis = (Matrix.Translation(co) @ _axis_basis(nrm)
                       @ Matrix.Scale(s, 4))
    return True


def _active_mesh(context, mode=None):
    obj = context.active_object
    if obj is None or obj.type != 'MESH':
        return False
    return mode is None or context.mode == mode


# --- persistent always-on group -------------------------------------------

class HARDFLOW_GGT_persistent(GizmoGroup):
    bl_idname = "HARDFLOW_GGT_persistent"
    bl_label = "Hardflow Gizmos"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT'}

    @classmethod
    def poll(cls, context):
        s = getattr(context.scene, "hardflow_gizmos", None)
        if s is None or not s.show:
            return False
        return _active_mesh(context) and context.mode in {'OBJECT', 'EDIT_MESH'}

    def setup(self, context):
        self._move = _make_transform(self, "transform.translate", 'NORMAL')
        self._rotate = _make_transform(self, "transform.rotate", 'NORMAL')
        self._scale = _make_transform(self, "transform.resize", 'BOX')
        self._bevel = _make_bevel(self)
        self._pushpull = _make_pushpull(self)

    def refresh(self, context):
        s = context.scene.hardflow_gizmos
        obj = context.active_object
        loc = obj.matrix_world.translation.copy()
        is_object = context.mode == 'OBJECT'
        is_edit = context.mode == 'EDIT_MESH'

        _place_transform(self._move, loc, not (s.move and is_object))
        _place_transform(self._rotate, loc, not (s.rotate and is_object))
        _place_transform(self._scale, loc, not (s.scale and is_object))

        self._bevel.hide = not (s.bevel and is_object)
        self._bevel.matrix_basis = obj.matrix_world.normalized()

        ok = bool(s.push_pull and is_edit and _setup_pushpull(self._pushpull, obj))
        self._pushpull.hide = not ok


# --- per-tool groups (shown only while their Workspace Tool is active) ------

class _HFToolGroup(GizmoGroup):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D'}


class HARDFLOW_GGT_move(_HFToolGroup):
    bl_idname = "HARDFLOW_GGT_move"
    bl_label = "Hardflow Move"

    @classmethod
    def poll(cls, context):
        return _active_mesh(context, 'OBJECT')

    def setup(self, context):
        self._move = _make_transform(self, "transform.translate", 'NORMAL')

    def refresh(self, context):
        loc = context.active_object.matrix_world.translation.copy()
        _place_transform(self._move, loc, False)


class HARDFLOW_GGT_rotate(_HFToolGroup):
    bl_idname = "HARDFLOW_GGT_rotate"
    bl_label = "Hardflow Rotate"

    @classmethod
    def poll(cls, context):
        return _active_mesh(context, 'OBJECT')

    def setup(self, context):
        self._rotate = _make_transform(self, "transform.rotate", 'NORMAL')

    def refresh(self, context):
        loc = context.active_object.matrix_world.translation.copy()
        _place_transform(self._rotate, loc, False)


class HARDFLOW_GGT_scale(_HFToolGroup):
    bl_idname = "HARDFLOW_GGT_scale"
    bl_label = "Hardflow Scale"

    @classmethod
    def poll(cls, context):
        return _active_mesh(context, 'OBJECT')

    def setup(self, context):
        self._scale = _make_transform(self, "transform.resize", 'BOX')

    def refresh(self, context):
        loc = context.active_object.matrix_world.translation.copy()
        _place_transform(self._scale, loc, False)


class HARDFLOW_GGT_bevel(_HFToolGroup):
    bl_idname = "HARDFLOW_GGT_bevel"
    bl_label = "Hardflow Bevel"

    @classmethod
    def poll(cls, context):
        return _active_mesh(context, 'OBJECT')

    def setup(self, context):
        self._bevel = _make_bevel(self)

    def refresh(self, context):
        self._bevel.matrix_basis = context.active_object.matrix_world.normalized()


class HARDFLOW_GGT_push_pull(_HFToolGroup):
    bl_idname = "HARDFLOW_GGT_push_pull"
    bl_label = "Hardflow Push/Pull"

    @classmethod
    def poll(cls, context):
        return _active_mesh(context, 'EDIT_MESH')

    def setup(self, context):
        self._pushpull = _make_pushpull(self)

    def refresh(self, context):
        ok = _setup_pushpull(self._pushpull, context.active_object)
        self._pushpull.hide = not ok
