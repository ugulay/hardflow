# Construction grid object: a wire reference grid placed in the scene to model
# against (a construction plane / construction geometry).
#
# Non-destructive and non-modal: builds a grid mesh from pure segment math
# (core.grid.centered_grid_segments + core.geometry.build_grid_mesh), drops it at
# the 3D cursor on the chosen axis plane, and leaves it unselectable-friendly as
# a reference. Spacing follows the same grid size as the draw/snap tools.
import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, FloatProperty, BoolProperty, IntProperty
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
                      "(loft / bridge); the two loops need an equal "
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


class HARDFLOW_OT_add_primitive(Operator):
    bl_idname = "object.hardflow_add_primitive"
    bl_label = "Add Primitive"
    bl_description = ("Create a starter primitive at the 3D cursor to model on "
                      "with the direct-modeling tools (Push/Pull, Offset, draw)")
    bl_options = {'REGISTER', 'UNDO'}

    kind: EnumProperty(
        name="Type",
        items=[('CUBE', "Cube", "A solid cube"),
               ('PLANE', "Plane", "A flat square face"),
               ('CYLINDER', "Cylinder", "A capped cylinder"),
               ('CONE', "Cone", "A cone"),
               ('SPHERE', "Sphere", "A UV sphere"),
               ('TUBE', "Tube", "A hollow tube (cylinder with a bore)")],
        default='CUBE',
    )
    size: FloatProperty(name="Size (m)", default=1.0, min=1e-4, soft_max=50.0)
    radius: FloatProperty(name="Radius (m)", default=0.5, min=1e-4, soft_max=50.0)
    inner_radius: FloatProperty(name="Inner Radius (m)", default=0.3, min=1e-5,
                                soft_max=50.0)
    depth: FloatProperty(name="Height (m)", default=1.0, min=1e-4, soft_max=50.0)
    segments: IntProperty(name="Segments", default=32, min=3, max=256)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        if self.kind == 'CUBE':
            mesh, name = geometry.build_box(self.size), "Hardflow_Cube"
        elif self.kind == 'PLANE':
            mesh, name = geometry.build_plane(self.size), "Hardflow_Plane"
        elif self.kind == 'CYLINDER':
            mesh = geometry.build_cylinder(self.radius, self.depth, self.segments)
            name = "Hardflow_Cylinder"
        elif self.kind == 'CONE':
            mesh = geometry.build_cone(self.radius, self.depth, self.segments)
            name = "Hardflow_Cone"
        elif self.kind == 'SPHERE':
            mesh = geometry.build_uv_sphere(self.radius, self.segments)
            name = "Hardflow_Sphere"
        else:  # TUBE
            mesh = geometry.build_tube(self.radius, self.inner_radius,
                                       self.depth, self.segments)
            name = "Hardflow_Tube"
        if mesh is None:
            self.report({'WARNING'}, "Could not build primitive")
            return {'CANCELLED'}
        obj = bpy.data.objects.new(name, mesh)
        context.collection.objects.link(obj)
        # Position after linking (cursor location; matrix on an unlinked object
        # is unreliable).
        obj.matrix_world = Matrix.Translation(context.scene.cursor.location)
        for o in list(context.selected_objects):
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {'FINISHED'}


class HARDFLOW_OT_add_guide(Operator):
    bl_idname = "object.hardflow_add_guide"
    bl_label = "Add Guide Line"
    bl_description = ("Add a construction guide line at the 3D cursor to snap "
                      "against (construction guides)")
    bl_options = {'REGISTER', 'UNDO'}

    axis: EnumProperty(
        name="Axis",
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", "")],
        default='X',
    )
    length: FloatProperty(name="Length (m)", default=4.0, min=0.01, soft_max=100.0)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        mesh = geometry.build_line(self.length, self.axis)
        if mesh is None:
            self.report({'WARNING'}, "Could not build guide")
            return {'CANCELLED'}
        obj = bpy.data.objects.new("Hardflow_Guide", mesh)
        obj.show_in_front = True
        obj.hide_render = True
        obj.display_type = 'WIRE'
        context.collection.objects.link(obj)
        obj.matrix_world = Matrix.Translation(context.scene.cursor.location)
        for o in list(context.selected_objects):
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {'FINISHED'}


class HARDFLOW_OT_add_grid(Operator):
    bl_idname = "object.hardflow_add_grid"
    bl_label = "Add Construction Grid"
    bl_description = ("Add a wire reference grid at the 3D cursor to model "
                      "against (a construction plane)")
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
