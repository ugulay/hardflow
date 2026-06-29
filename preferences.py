# Addon preferences and a prefs accessor reachable from anywhere.
import bpy
from bpy.types import AddonPreferences
from bpy.props import (BoolProperty, IntProperty, FloatProperty,
                       FloatVectorProperty, EnumProperty, StringProperty)


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
    ngon_sides: IntProperty(
        name="N-gon Sides",
        description="Default side count for the N-gon draw shape; adjust live "
                    "with [ and ] while drawing",
        default=6, min=3, max=64,
    )
    decal_size: FloatProperty(
        name="Decal Size (m)",
        description="Default size of a placed decal; adjust live with the wheel",
        default=0.2, min=0.001, soft_max=5.0,
    )
    decal_offset: FloatProperty(
        name="Decal Offset (m)",
        description="How far the decal hovers above the surface (avoids "
                    "z-fighting); shrinkwrap ABOVE_SURFACE distance",
        default=0.001, min=0.0, soft_max=0.1,
    )
    bake_size: IntProperty(
        name="Bake Resolution",
        description="Resolution (px) of the image when baking a decal into the "
                    "target's texture map",
        default=1024, min=64, max=8192,
    )
    decal_library_path: StringProperty(
        name="Decal Library",
        description="Folder scanned for decal images (PNG/JPG/TGA...); shown as "
                    "an icon grid in the N-panel 'Decal Library' section",
        subtype='DIR_PATH', default="",
    )
    atlas_max_width: IntProperty(
        name="Atlas Max Width",
        description="Maximum width (px) when packing image decals into a single "
                    "atlas texture; the atlas height grows to fit",
        default=2048, min=64, max=8192,
    )
    asset_library_path: StringProperty(
        name="Asset Library",
        description="Folder scanned for .blend kit parts (INSERTs); shown as a "
                    "grid in the N-panel 'Asset Library' section",
        subtype='DIR_PATH', default="",
    )
    asset_as_cutter: BoolProperty(
        name="Asset as Cutter",
        description="Placed kit parts become boolean cutters on the surface "
                    "object instead of plain decorations (KitOps cutter INSERTs)",
        default=False,
    )
    asset_boolean: EnumProperty(
        name="Asset Boolean",
        description="Boolean used when an asset is placed as a cutter",
        items=[('CUT', "Cut", "DIFFERENCE -- carve the part out of the surface"),
               ('MAKE', "Make", "UNION -- merge the part into the surface")],
        default='CUT',
    )
    asset_conform: BoolProperty(
        name="Conform Asset",
        description="Wrap placed parts onto the surface with a shrinkwrap "
                    "(KitOps wrap/conform)",
        default=False,
    )
    asset_transfer_shading: BoolProperty(
        name="Transfer Shading",
        description="Give placed parts the surface object's active material and "
                    "smooth-shading state",
        default=False,
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
        col.prop(self, "ngon_sides")
        col.prop(self, "pipe_radius")
        col.prop(self, "decal_size")
        col.prop(self, "decal_offset")
        col.prop(self, "bake_size")
        col.prop(self, "decal_library_path")
        col.prop(self, "atlas_max_width")
        col.prop(self, "asset_library_path")
        col.prop(self, "asset_as_cutter")
        col.prop(self, "asset_boolean")
        col.prop(self, "asset_conform")
        col.prop(self, "asset_transfer_shading")
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
