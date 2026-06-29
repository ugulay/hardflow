# Construction grid object: a wire reference grid placed in the scene to model
# against (SketchUp's ground plane / construction geometry).
#
# Non-destructive and non-modal: builds a grid mesh from pure segment math
# (core.grid.centered_grid_segments + core.geometry.build_grid_mesh), drops it at
# the 3D cursor on the chosen axis plane, and leaves it unselectable-friendly as
# a reference. Spacing follows the same grid size as the draw/snap tools.
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, FloatProperty, BoolProperty
from mathutils import Matrix

from ..core import grid, geometry
from ..preferences import get_prefs


_PLANES = [
    ('XY', "XY (Top)", "Ground plane, normal +Z"),
    ('XZ', "XZ (Front)", "Front plane, normal -Y"),
    ('YZ', "YZ (Side)", "Side plane, normal +X"),
]

# Rotation that takes the local XY grid onto each world plane.
_PLANE_ROT = {
    'XY': Matrix.Identity(4),
    'XZ': Matrix.Rotation(1.5707963267948966, 4, 'X'),
    'YZ': Matrix.Rotation(1.5707963267948966, 4, 'Y'),
}


def _object_loop(obj):
    """World-space vertex loop of a profile object: the first polygon's loop if
    it has faces, otherwise all vertices in order."""
    me = obj.data
    mw = obj.matrix_world
    if me.polygons:
        return [mw @ me.vertices[i].co for i in me.polygons[0].vertices]
    return [mw @ v.co for v in me.vertices]


class HARDFLOW_OT_loft(Operator):
    bl_idname = "object.hardflow_loft"
    bl_label = "Hardflow Loft"
    bl_description = ("Bridge two selected profile objects into a solid "
                      "(Grid Modeler loft / bridge); the two loops need an equal "
                      "vertex count")
    bl_options = {'REGISTER', 'UNDO'}

    caps: BoolProperty(name="Cap Ends", default=True)

    @classmethod
    def poll(cls, context):
        sel = [o for o in context.selected_objects if o.type == 'MESH']
        return context.mode == 'OBJECT' and len(sel) == 2

    def execute(self, context):
        sel = [o for o in context.selected_objects if o.type == 'MESH']
        loop_a = _object_loop(sel[0])
        loop_b = _object_loop(sel[1])
        if len(loop_a) != len(loop_b):
            self.report({'WARNING'},
                        "Loft needs equal vertex counts (%d vs %d)"
                        % (len(loop_a), len(loop_b)))
            return {'CANCELLED'}
        mesh = geometry.build_loft(loop_a, loop_b, caps=self.caps)
        if mesh is None:
            self.report({'WARNING'}, "Could not loft these profiles")
            return {'CANCELLED'}
        obj = bpy.data.objects.new("Hardflow_Loft", mesh)
        context.collection.objects.link(obj)
        for o in list(context.selected_objects):
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {'FINISHED'}


class HARDFLOW_OT_add_grid(Operator):
    bl_idname = "object.hardflow_add_grid"
    bl_label = "Add Construction Grid"
    bl_description = ("Add a wire reference grid at the 3D cursor to model "
                      "against (SketchUp construction plane)")
    bl_options = {'REGISTER', 'UNDO'}

    plane: EnumProperty(name="Plane", items=_PLANES, default='XY')
    extent: FloatProperty(
        name="Half Extent (m)",
        description="The grid spans +/- this distance on both axes",
        default=2.0, min=0.01, soft_max=50.0,
    )
    spacing: FloatProperty(
        name="Spacing (m)",
        description="Distance between grid lines",
        default=0.1, min=0.001, soft_max=10.0,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def invoke(self, context, event):
        prefs = get_prefs(context)
        self.extent = prefs.build_grid_extent
        self.spacing = prefs.grid_world
        return self.execute(context)

    def execute(self, context):
        segs = grid.centered_grid_segments(self.extent, self.spacing)
        if not segs:
            self.report({'WARNING'},
                        "Grid is empty or too dense; raise spacing / lower extent")
            return {'CANCELLED'}
        mesh = geometry.build_grid_mesh(segs)
        if mesh is None:
            self.report({'WARNING'}, "Could not build grid")
            return {'CANCELLED'}

        obj = bpy.data.objects.new("Hardflow_Grid", mesh)
        obj.show_in_front = True
        obj.hide_render = True
        obj.display_type = 'WIRE'
        context.collection.objects.link(obj)
        # Position after linking (matrix_world on an unlinked object is unreliable).
        obj.matrix_world = (Matrix.Translation(context.scene.cursor.location)
                            @ _PLANE_ROT[self.plane])
        for o in list(context.selected_objects):
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {'FINISHED'}
