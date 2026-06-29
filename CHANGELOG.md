# Changelog

Notable changes in this project. Versioning follows [SemVer](https://semver.org)
logic; since the project is pre-1.0, minor versions add features.

## [Unreleased]

### Added
- **N-gon draw shape** — a regular-polygon primitive in the draw tool (shape key
  `R`); side count from the `ngon_sides` preference, adjustable live with `[` and
  `]`. Pure-core `grid.ngon_points` (tested).
- **World-scale grid snap** — snap now operates on the projection plane's local
  (u,v) meter axes instead of screen pixels; a consistent grid independent of
  camera/zoom. Preference: `grid_world` (meters).
- **Vertex / edge snap** — lock the drawing point to the corner / edge / edge
  midpoint of existing geometry; colored cursor (🟡 corner, 🟢 midpoint, 🔵
  edge). Toggle with `V`; `geo_snap` + `snap_pixels` preferences. Disables
  automatically on dense meshes.
- **Angle lock** — while Shift is held, the drawing direction locks to an angle
  step (`angle_step`, default 15°).
- **Non-destructive mode** — leaves a live modifier instead of applying the
  boolean; cutters are kept in the "Hardflow Cutters" collection (wire, render
  disabled, parented to the target). Toggle with `N`; `non_destructive`
  preference.
- **N-panel** — tools, snap settings, and the stashed cutter list in the View3D
  sidebar.
- **Self-intersection detection** — a broken polygon is rejected before the cut.
- **Rotating the grid plane** — `←/→` switches the plane between VIEW / world X /
  Y / Z; the cutter is extruded along the plane normal (`ray_to_plane`).
- **Create Face mode** — key `4` in the drawing tool: a single n-gon surface
  object from the drawn shape (not a boolean).
- **Cutter management** — select/remove a cutter from the N-panel + "Apply
  Cutters (Bake)" (`operators/cutters.py`).
- **Clean operator** — remove doubles + coplanar merge + delete loose (Hard Ops
  "clean"); also automatic after a cut via `cleanup_after_cut`.
- **Pipe tool** — a round-profile pipe from the drawn line (`HARDFLOW_OT_pipe`,
  `pipe_radius`).
- **Advanced bevel** — interactive modal (drag = width, wheel = segments),
  profile + angle limit + width-type, and the **Weighted Normal** modifier
  (clean hard-surface shading).
- **Multi-object** — `multi_object`: CUT/MAKE is applied to all selected meshes.
- **HUD measurement display** — size in meters while drawing.
- **Test suite** — `tests/test_core.py` (11, without bpy) + `tests/test_blender.py`
  (headless: build_prism/boolean/cutters/clean/pipe/face/multi-object).
- **ROADMAP** — added a DECALmachine-style decal subsystem (v0.7–v0.9).

### Fixed
- Bevel: removed the `Mesh.use_auto_smooth` call that was removed in Blender
  4.1+ (it was crashing the operator); replaced it with smooth shading.
- GPU drawing: ensured the `UNIFORM_COLOR` shader is fed a vec3 (z=0).
- Cutter objects are now cleaned up via `try/finally` even when the boolean
  fails.
- Pie menu shortcut `Alt+D` → `Alt+Q` (Alt+D collided with Duplicate Linked in
  Object Mode).
- The roving cursor is no longer added as an extra vertex on POLY commit.

## [0.1.0]
- First modular architecture: modal drawing operator (Box/Circle/Polygon),
  Cut/Slice/Make modes, screen-space grid snap, smart bevel + mirror, pie menu,
  preferences, keymap.
