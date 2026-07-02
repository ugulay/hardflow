# Addon preferences and a prefs accessor reachable from anywhere.
import bpy
from bpy.types import AddonPreferences
from bpy.props import (BoolProperty, IntProperty, FloatProperty,
                       FloatVectorProperty, EnumProperty, StringProperty)


def get_prefs(context=None):
    """This module's __package__ is the base addon package (e.g. 'hardflow' or
    'bl_ext.user_default.hardflow'), so it gives the correct key even when
    called from submodules.

    When the package is registered but not an *enabled* add-on (it is imported
    directly, e.g. by the headless test harness), there is no entry in
    ``preferences.addons``; fall back to a stand-in carrying the declared
    property defaults so operators don't hard-crash."""
    context = context or bpy.context
    addon = context.preferences.addons.get(__package__)
    if addon is not None:
        return addon.preferences
    return _default_prefs()


def _default_prefs():
    """A throwaway object exposing each preference at its declared default,
    read from the registered class's RNA so the defaults never drift."""
    import types
    ns = types.SimpleNamespace()
    rna = getattr(HARDFLOW_Preferences, "bl_rna", None)
    if rna is None:
        # Not even registered: re-raise the original lookup error for clarity.
        return bpy.context.preferences.addons[__package__].preferences
    for prop in rna.properties:
        if prop.identifier == "rna_type":
            continue
        if getattr(prop, "is_array", False):
            setattr(ns, prop.identifier, tuple(prop.default_array))
        else:
            setattr(ns, prop.identifier, getattr(prop, "default", None))
    return ns


class HARDFLOW_Preferences(AddonPreferences):
    bl_idname = __package__

    # Collapse state for the preference sections (the flat ~60-prop list is
    # grouped into boxed, foldable sections; core sections open, the heavy /
    # occasional ones folded so the page opens compact). UI-only booleans.
    ui_show_snapping: BoolProperty(default=True)
    ui_show_boolean: BoolProperty(default=True)
    ui_show_curves: BoolProperty(default=False)
    ui_show_decals: BoolProperty(default=False)
    ui_show_assets: BoolProperty(default=False)
    ui_show_appearance: BoolProperty(default=True)
    ui_show_shortcuts: BoolProperty(default=True)

    # Onboarding: the dismissible Quick Start card at the top of the N-panel.
    # Flipped off by the card's own "Got it" button; persists across sessions.
    show_quickstart: BoolProperty(
        name="Show Quick Start",
        description="Show the Quick Start card at the top of the Hardflow N-panel",
        default=True,
    )

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
    surface_snap: BoolProperty(
        name="Surface/Face Snap",
        description="Stick drawing/anchor points to the face under the cursor; "
                    "the ADD tool can also align its whole cut plane to that "
                    "face (Surface plane mode)",
        default=True,
    )
    default_plane: EnumProperty(
        name="Default Plane",
        description="Projection/construction plane the Draw tool starts on; "
                    "save the live plane as the default with S while drawing",
        items=[
            ('VIEW', "View", "Perpendicular to the view (screen-aligned)"),
            ('SURFACE', "Surface", "Aligned to the face under the first click"),
            ('EDGES', "Edges", "Aligned to the selected edit-mesh edge(s)"),
            ('X', "X", "World X-axis aligned grid"),
            ('Y', "Y", "World Y-axis aligned grid"),
            ('Z', "Z", "World Z-axis aligned grid"),
        ],
        default='VIEW',
    )
    snap_target: EnumProperty(
        name="Snap Target",
        description="Which geometry vertex/edge/surface snapping considers",
        items=[
            ('ACTIVE', "Active Object",
             "Snap to the active object's geometry only (faster, predictable)"),
            ('VISIBLE', "Visible Meshes",
             "Snap to any visible mesh under the cursor (vertex count is capped "
             "for performance)"),
        ],
        default='ACTIVE',
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
    pipe_offset: FloatProperty(
        name="Pipe/Cable Clearance (m)",
        description="Extra gap between the tube's OUTER surface and the model "
                    "surface. The tube is always lifted by its own radius first "
                    "(so it rests on the surface, never sinks in); this adds a "
                    "further clearance on top. Live-adjust with Ctrl+Wheel",
        default=0.0, min=0.0, soft_max=1.0,
    )
    pipe_follow_surface: BoolProperty(
        name="Pipe Follows Surface",
        description="Drape the pipe over the model: each span is re-sampled and "
                    "snapped onto the nearest surface so the tube hugs contours "
                    "and wraps edges instead of cutting straight through. Toggle "
                    "live with F (pipe only; the cable always hangs free)",
        default=True,
    )
    pipe_profile: EnumProperty(
        name="Pipe Profile",
        description="Cross-section of the pipe tool; SQUARE/RECT sweep a mesh "
                    "tube, ROUND uses a curve bevel. Cycle live with P",
        items=[('ROUND', "Round", "Round curve bevel (classic pipe)"),
               ('SQUARE', "Square", "Square swept cross-section"),
               ('RECT', "Rectangular", "Wide rectangular swept cross-section")],
        default='ROUND',
    )
    pipe_follow_segments: IntProperty(
        name="Pipe Follow Segments",
        description="Sub-divisions per span when draping the pipe over a "
                    "surface; more = tighter contour following, slightly slower",
        default=8, min=1, max=64,
    )
    pipe_smooth: BoolProperty(
        name="Smooth Path",
        description="Interpolate the pipe/sweep path through the placed anchors "
                    "with a smooth spline (centripetal Catmull-Rom) instead of "
                    "straight segments; with a ROUND profile and Follow off the "
                    "result is an editable auto-handle Bezier curve. Toggle "
                    "live with C while drawing",
        default=False,
    )
    cable_radius: FloatProperty(
        name="Cable Radius (m)",
        description="Round cross-section radius of the cable/rope tool",
        default=0.02, min=0.001, soft_max=1.0,
    )
    cable_sag: FloatProperty(
        name="Cable Sag (m)",
        description="How far the cable droops at mid-span under gravity; 0 is a "
                    "straight line. Live-adjust with Shift+Wheel",
        default=0.2, min=0.0, soft_max=5.0,
    )
    cable_segments: IntProperty(
        name="Cable Segments",
        description="Sub-divisions per cable span; more = smoother sag",
        default=12, min=1, max=128,
    )
    cable_gravity: BoolProperty(
        name="Cable Gravity Settle",
        description="Hang the cable by relaxing a pinned particle chain under "
                    "gravity (position-based physics) instead of the analytic "
                    "sag -- the rope drapes over obstacles and rests on scene "
                    "geometry. Toggle live with G while drawing",
        default=False,
    )
    cable_slack: FloatProperty(
        name="Cable Slack",
        description="Extra rope length for the gravity settle, as a multiple "
                    "of the straight span (1.0 = taut, 1.15 = 15% extra). "
                    "Live-adjust with Shift+Wheel while gravity is on",
        default=1.15, min=1.0, soft_max=3.0,
    )
    cable_collision: BoolProperty(
        name="Cable Scene Collision",
        description="Let the gravity-settled cable collide with (rest on) the "
                    "visible scene meshes; turn off in heavy scenes if the "
                    "live preview gets slow",
        default=True,
    )
    ngon_sides: IntProperty(
        name="N-gon Sides",
        description="Default side count for the N-gon draw shape; adjust live "
                    "with [ and ] while drawing",
        default=6, min=3, max=64,
    )
    build_grid_extent: FloatProperty(
        name="Construction Grid Extent (m)",
        description="Half-size of the construction grid object added by the "
                    "Build tools; the grid spans +/- this on both axes "
                    "(spacing follows Grid Size)",
        default=2.0, min=0.01, soft_max=50.0,
    )
    decal_size: FloatProperty(
        name="Decal Size (m)",
        description="Default size of a placed decal; adjust live with the wheel",
        default=0.2, min=0.001, soft_max=5.0,
    )
    decal_offset: FloatProperty(
        name="Decal Offset (m)",
        description="How far the decal hovers above the surface (avoids "
                    "z-fighting); shrinkwrap ABOVE_SURFACE distance. "
                    "0 = auto (scaled to the target's size)",
        default=0.0, min=0.0, soft_max=0.1,
    )
    decal_resolution: IntProperty(
        name="Decal Resolution",
        description="Grid cells per axis of a placed decal. 1 is a flat quad; "
                    "higher lets the shrinkwrap bend the decal to curved / "
                    "multi-face surfaces instead of clipping through them",
        default=12, min=1, soft_max=64,
    )
    decal_parallax: BoolProperty(
        name="Parallax Occlusion",
        description="Give image decals true, view-dependent depth: a Parallax "
                    "Occlusion Mapping shader shifts the sampled UV along the "
                    "camera vector using the image's luminance as a height map, "
                    "so panel lines recess and rivets self-occlude at grazing "
                    "angles instead of reading as a flat sticker",
        default=False,
    )
    decal_parallax_depth: FloatProperty(
        name="Parallax Depth",
        description="Apparent recess depth of the parallax effect, in UV units. "
                    "Larger looks deeper but exaggerates the swim at extreme "
                    "grazing angles",
        default=0.05, min=0.0, soft_max=0.5,
    )
    decal_parallax_layers: IntProperty(
        name="Parallax Layers",
        description="Ray-march steps of the parallax shader. More layers are "
                    "smoother at grazing angles but build a heavier node graph",
        default=8, min=2, max=24,
    )
    decal_height_image: StringProperty(
        name="Height Map",
        description="Name of a loaded grayscale image to drive image-decal depth "
                    "(Parallax + Relief) independently of the color image -- the "
                    "dedicated height-map channel. Blank = use the color image's "
                    "own luminance as the height field",
        default="",
    )
    decal_height_invert: BoolProperty(
        name="Invert Height",
        description="Flip the height convention: by default a BRIGHT texel is the "
                    "flush outer surface and a DARK texel is the deepest recess; "
                    "enable for height maps authored the other way (bright = deep)",
        default=False,
    )
    decal_bump_strength: FloatProperty(
        name="Relief (Bump)",
        description="Normal-relief strength driven by the height map: adds real "
                    "shaded depth to image decals (works with or combined with "
                    "Parallax Occlusion). 0 = off (flat shading)",
        default=0.0, min=0.0, soft_max=2.0,
    )
    decal_normal_transfer: BoolProperty(
        name="Decal Normal Transfer",
        description="Add a Data Transfer modifier so a placed decal borrows the "
                    "target's surface normals and shades as part of the curved "
                    "surface, instead of catching its own flat lighting",
        default=False,
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
                    "object instead of plain decorations (boolean cutter INSERTs)",
        default=False,
    )
    asset_boolean: EnumProperty(
        name="Asset Boolean",
        description="Boolean used when an asset is placed as a cutter",
        items=[('CUT', "Cut", "DIFFERENCE -- carve the part out of the surface"),
               ('MAKE', "Make", "UNION -- merge the part into the surface")],
        default='CUT',
    )
    asset_auto_scale: BoolProperty(
        name="Auto Scale",
        description="Scale the INSERT to a fraction of the target's local feature "
                    "size on the first surface hit (smart scale)",
        default=False,
    )
    asset_fit_fraction: FloatProperty(
        name="Fit Fraction",
        description="Auto-scale target: the INSERT's largest side becomes this "
                    "fraction of the target's smallest dimension",
        default=0.25, min=0.01, soft_max=2.0,
    )
    asset_grid_snap: BoolProperty(
        name="Insert Grid Snap",
        description="Snap INSERT placement to a world grid or to existing insert "
                    "anchors, for clean repeated arrays (grid / anchor snapping)",
        default=False,
    )
    asset_grid_spacing: FloatProperty(
        name="Insert Grid Spacing (m)",
        description="World grid spacing for insert factory snapping",
        default=0.25, min=0.001, soft_max=10.0,
    )
    asset_conform: BoolProperty(
        name="Conform Asset",
        description="Wrap placed parts onto the surface with a shrinkwrap "
                    "(wrap / conform)",
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
                    "(non-destructive)",
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
    cut_dissolve_ngons: BoolProperty(
        name="Re-quad Cut N-gons",
        description="After a destructive boolean cut, triangulate + rejoin the "
                    "n-gons the cut left so the surface stays quad-friendly "
                    "(core.geometry.dissolve_boolean_ngons)",
        default=False,
    )
    auto_trim_after_cut: EnumProperty(
        name="Cut-to-Trim",
        description="After a boolean CUT, auto-route a pipe/panel-line along the "
                    "drawn cut boundary (draped onto the surface) so the cut is "
                    "instantly detailed -- the Hard-Surface -> Decal bridge",
        items=[
            ('OFF', "Off", "No automatic trim after a cut"),
            ('PIPE', "Pipe", "Round pipe/cable along the cut boundary"),
            ('PANEL', "Panel Line", "Thin recessed panel-line along the cut "
             "boundary (small round bead)"),
        ],
        default='OFF',
    )
    auto_trim_radius: FloatProperty(
        name="Trim Radius (m)",
        description="Cross-section radius of the auto-placed cut-boundary pipe / "
                    "panel line",
        default=0.01, min=0.0001, soft_max=0.5,
    )
    auto_trim_lift: FloatProperty(
        name="Trim Lift (m)",
        description="Lift the auto trim above the surface (0 = rest on it; "
                    "negative recesses it into a panel groove)",
        default=0.0, soft_min=-0.2, soft_max=0.2,
    )
    fix_shading_after_cut: BoolProperty(
        name="Fix Shading After Cut",
        description="Snapshot the target's clean normals before a destructive "
                    "cut and bind a Data Transfer modifier afterwards, so the "
                    "n-gon faces the boolean leaves shade flat instead of "
                    "smearing (the boolean-shading fix)",
        default=False,
    )
    sort_modifiers_after_cut: BoolProperty(
        name="Auto-Sort Modifier Stack",
        description="After a non-destructive cut, reorder the target's modifiers "
                    "into hard-surface order (Booleans on top, Bevel below, "
                    "Weighted Normal at the bottom)",
        default=True,
    )
    live_boolean_preview: BoolProperty(
        name="Live Boolean Preview",
        description="While drawing a Cut/Make/Intersect, show the actual boolean "
                    "RESULT live on the target (a temporary modifier, removed on "
                    "commit/cancel) instead of only the wire cutter cage. Toggle "
                    "with J while drawing; skipped on heavy targets for speed",
        default=False,
    )
    live_preview_max_verts: IntProperty(
        name="Live Preview Vertex Cap",
        description="Skip the live boolean RESULT (show only the wire cutter cage) "
                    "on targets heavier than this vertex count, so a high-poly "
                    "mesh stays responsive while drawing. Targets the cutter's "
                    "bounding box doesn't even reach are skipped regardless",
        default=8000, min=0, soft_max=200000,
    )
    draw_inset: FloatProperty(
        name="Cutter Inset (m)",
        description="Default amount the drawn loop is offset in (-) / out (+) "
                    "before the cut; adjust live with - and = while drawing",
        default=0.0, soft_min=-1.0, soft_max=1.0,
    )
    draw_bevel_cut: BoolProperty(
        name="Bevel On Cut",
        description="Default: add a small angle-limited bevel to the target's cut "
                    "edge so it reads chamfered; toggle live with B",
        default=False,
    )
    draw_cutter_bevel: BoolProperty(
        name="Bevelled Cutter",
        description="Default: chamfer the cutter walls so the recess has bevelled "
                    "sides; toggle live with C",
        default=False,
    )
    smart_bevel_default: BoolProperty(
        name="Smart Edge Bevel",
        description="Object-Mode Edge Bevel starts in Smart mode: add support / "
                    "holding loops and clean n-gons so the bevel survives "
                    "Subdivision (toggle live with S). EXPERIMENTAL",
        default=False,
    )
    draw_array_count: IntProperty(
        name="Cutter Array",
        description="Default number of array copies stamped into one cutter; "
                    "cycle live with A (axis with D)",
        default=1, min=1, max=64,
    )
    draw_array_axis: EnumProperty(
        name="Array Axis",
        description="World axis the cutter array repeats along; Radial spins "
                    "the copies about the construction-plane / grid origin "
                    "(set it live with H) for bolt circles",
        items=[('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", ""),
               ('RADIAL', "Radial", "Spin the copies about the grid origin")],
        default='X',
    )
    draw_vent_ratio: FloatProperty(
        name="Vent Slot Ratio",
        description="VENT shape: fraction of each pitch that is open slot "
                    "(the rest stays solid rib; border ribs match)",
        default=0.5, min=0.05, max=0.95, subtype='FACTOR',
    )
    default_solver: EnumProperty(
        name="Boolean Solver",
        items=[
            ('EXACT', "Exact", "More accurate, slower"),
            ('FAST', "Fast", "Faster, more fragile"),
            ('MANIFOLD', "Manifold", "Fastest; manifold meshes only (Blender 4.5+)"),
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
    line_width: FloatProperty(
        name="Line Width (px)",
        description="Thickness of the drawn shape outline (scaled by the UI "
                    "scale)",
        default=2.0, min=1.0, soft_max=8.0,
    )

    def _section(self, layout, key, title, icon):
        """Draw a foldable, boxed preference section. Returns the body column when
        the section is expanded, else None (so the caller skips its props). Keeps
        the long preference list scannable instead of one flat wall of ~60 rows."""
        box = layout.box()
        header = box.row(align=True)
        expanded = getattr(self, key)
        header.prop(self, key, text="", emboss=False,
                    icon='DISCLOSURE_TRI_DOWN' if expanded
                    else 'DISCLOSURE_TRI_RIGHT')
        header.label(text=title, icon=icon)
        return box.column() if expanded else None

    def draw(self, context):
        layout = self.layout

        col = self._section(layout, "ui_show_snapping", "Snapping & Grid",
                            'SNAP_ON')
        if col:
            col.prop(self, "snap_enabled")
            col.prop(self, "geo_snap")
            col.prop(self, "surface_snap")
            col.prop(self, "snap_target")
            col.separator()
            col.prop(self, "grid_world")
            col.prop(self, "snap_pixels")
            col.prop(self, "angle_step")
            col.prop(self, "ngon_sides")
            col.prop(self, "build_grid_extent")
            col.prop(self, "default_plane")

        col = self._section(layout, "ui_show_boolean", "Boolean & Cutters",
                            'MOD_BOOLEAN')
        if col:
            col.prop(self, "default_solver")
            col.prop(self, "non_destructive")
            col.prop(self, "multi_object")
            col.prop(self, "cleanup_after_cut")
            col.separator()
            col.label(text="Live preview", icon='HIDE_OFF')
            col.prop(self, "live_boolean_preview")
            col.prop(self, "live_preview_max_verts")
            col.separator()
            col.label(text="Cutter defaults (seed the next draw)", icon='MOD_BOOLEAN')
            col.prop(self, "draw_inset")
            col.prop(self, "draw_bevel_cut")
            col.prop(self, "draw_cutter_bevel")
            row = col.row(align=True)
            row.prop(self, "draw_array_count")
            row.prop(self, "draw_array_axis", text="")
            col.prop(self, "draw_vent_ratio")
            col.separator()
            col.label(text="Topology & shading", icon='MOD_DATA_TRANSFER')
            col.prop(self, "cut_dissolve_ngons")
            col.prop(self, "fix_shading_after_cut")
            col.prop(self, "sort_modifiers_after_cut")
            col.prop(self, "smart_bevel_default")
            col.separator()
            col.label(text="Cut-to-Trim (Decal bridge)", icon='UV_DATA')
            col.prop(self, "auto_trim_after_cut")
            if self.auto_trim_after_cut != 'OFF':
                col.prop(self, "auto_trim_radius")
                col.prop(self, "auto_trim_lift")

        col = self._section(layout, "ui_show_curves", "Curves (Pipe / Cable / Sweep)",
                            'MOD_SCREW')
        if col:
            col.prop(self, "pipe_radius")
            col.prop(self, "pipe_offset")
            col.prop(self, "pipe_profile")
            col.prop(self, "pipe_follow_surface")
            col.prop(self, "pipe_follow_segments")
            col.prop(self, "pipe_smooth")
            col.separator()
            col.prop(self, "cable_radius")
            col.prop(self, "cable_sag")
            col.prop(self, "cable_segments")
            col.prop(self, "cable_gravity")
            col.prop(self, "cable_slack")
            col.prop(self, "cable_collision")

        col = self._section(layout, "ui_show_decals", "Decals", 'TEXTURE')
        if col:
            col.prop(self, "decal_size")
            col.prop(self, "decal_offset")
            col.prop(self, "decal_resolution")
            col.prop(self, "decal_normal_transfer")
            col.separator()
            col.label(text="Depth (image decals)", icon='MOD_DISPLACE')
            col.prop(self, "decal_parallax")
            col.prop(self, "decal_parallax_depth")
            col.prop(self, "decal_parallax_layers")
            col.prop(self, "decal_bump_strength")
            col.prop_search(self, "decal_height_image", bpy.data, "images")
            col.prop(self, "decal_height_invert")
            col.separator()
            col.prop(self, "bake_size")
            col.prop(self, "decal_library_path")
            col.prop(self, "atlas_max_width")

        col = self._section(layout, "ui_show_assets", "Assets / INSERTs",
                            'FILE_BLEND')
        if col:
            col.prop(self, "asset_library_path")
            col.prop(self, "asset_as_cutter")
            col.prop(self, "asset_boolean")
            col.separator()
            col.prop(self, "asset_auto_scale")
            col.prop(self, "asset_fit_fraction")
            col.prop(self, "asset_grid_snap")
            col.prop(self, "asset_grid_spacing")
            col.prop(self, "asset_conform")
            col.prop(self, "asset_transfer_shading")

        col = self._section(layout, "ui_show_appearance", "Appearance", 'COLOR')
        if col:
            col.label(text="Live-preview colors")
            row = col.row(align=True)
            row.prop(self, "line_color", text="")
            row.prop(self, "fill_color", text="")
            row.prop(self, "grid_color", text="")
            col.prop(self, "line_width")

        col = self._section(layout, "ui_show_shortcuts", "Shortcuts", 'KEYINGSET')
        if col:
            from . import keymaps
            keymaps.draw_keymap_prefs(col, context)
