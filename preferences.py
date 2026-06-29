# Addon preferences and a prefs accessor reachable from anywhere.
import bpy
from bpy.types import AddonPreferences
from bpy.props import (BoolProperty, IntProperty, FloatProperty,
                       FloatVectorProperty, EnumProperty)


def get_prefs(context=None):
    """This module's __package__ is the base addon package (e.g. 'hardflow' or
    'bl_ext.user_default.hardflow'), so it gives the correct key even when
    called from submodules."""
    context = context or bpy.context
    return context.preferences.addons[__package__].preferences


class HARDFLOW_Preferences(AddonPreferences):
    bl_idname = __package__

    snap_enabled: BoolProperty(
        name="Grid Snap",
        description="Lock drawing points to the grid",
        default=True,
    )
    grid_size: IntProperty(
        name="Grid Size (px)",
        description="Old screen-space grid spacing (legacy, unused)",
        default=24, min=2, max=256,
    )
    grid_world: FloatProperty(
        name="Grid Size (m)",
        description="World-scale grid spacing (meters); consistent on the "
                    "projection plane, camera-independent snap",
        default=0.1, min=0.001, soft_max=10.0,
    )
    geo_snap: BoolProperty(
        name="Vertex/Edge Snap",
        description="Lock the drawing point to an existing geometry's "
                    "vertex/edge/midpoint (overrides the grid)",
        default=True,
    )
    snap_pixels: IntProperty(
        name="Snap Distance (px)",
        description="Screen-space capture radius for geometry snap",
        default=12, min=4, max=64,
    )
    angle_step: IntProperty(
        name="Angle Step (deg)",
        description="Angle step the drawing direction locks to while Shift is held",
        default=15, min=1, max=90,
    )
    pipe_radius: FloatProperty(
        name="Pipe Radius (m)",
        description="Round cross-section radius of the pipe tool",
        default=0.05, min=0.001, soft_max=1.0,
    )
    non_destructive: BoolProperty(
        name="Non-Destructive",
        description="Leave a live modifier instead of applying the boolean; stash "
                    "cutters in a separate 'Hardflow Cutters' collection "
                    "(BoxCutter style)",
        default=False,
    )
    multi_object: BoolProperty(
        name="Multi Object",
        description="Apply CUT/MAKE to all selected mesh objects (single cutter, "
                    "multiple targets)",
        default=False,
    )
    cleanup_after_cut: BoolProperty(
        name="Clean After Cut",
        description="Clean up the mesh after a destructive cut (remove doubles + "
                    "merge coplanar faces)",
        default=False,
    )
    default_solver: EnumProperty(
        name="Boolean Solver",
        items=[
            ('EXACT', "Exact", "More accurate, slower"),
            ('FAST', "Fast", "Faster, more fragile"),
        ],
        default='EXACT',
    )
    line_color: FloatVectorProperty(
        name="Line Color", subtype='COLOR', size=4,
        default=(0.15, 0.8, 1.0, 1.0), min=0.0, max=1.0,
    )
    fill_color: FloatVectorProperty(
        name="Fill Color", subtype='COLOR', size=4,
        default=(0.15, 0.8, 1.0, 0.12), min=0.0, max=1.0,
    )
    grid_color: FloatVectorProperty(
        name="Grid Color", subtype='COLOR', size=4,
        default=(1.0, 1.0, 1.0, 0.06), min=0.0, max=1.0,
    )

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "snap_enabled")
        col.prop(self, "grid_world")
        col.prop(self, "geo_snap")
        col.prop(self, "snap_pixels")
        col.prop(self, "angle_step")
        col.prop(self, "pipe_radius")
        col.prop(self, "non_destructive")
        col.prop(self, "multi_object")
        col.prop(self, "cleanup_after_cut")
        col.prop(self, "default_solver")
        row = col.row(align=True)
        row.prop(self, "line_color")
        row.prop(self, "fill_color")
        row.prop(self, "grid_color")
        col.separator()
        box = col.box()
        box.label(text="Shortcuts", icon='KEYINGSET')
        from . import keymaps
        keymaps.draw_keymap_prefs(box, context)
