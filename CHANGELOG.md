# Changelog

Notable changes in this project. Versioning follows [SemVer](https://semver.org)
logic; since the project is pre-1.0, minor versions add features.

## [0.9.0] — 2026-06-29

The decal subsystem (v0.7 placement → v0.8 PBR material/bake → v0.9 image
library, trim sheets, atlasing) is feature-complete. Pure logic is unit-tested
without Blender; the bpy-dependent paths still await a live-Blender smoke test.

### Added
- **Decals (v0.7 placement core)** — a new DECALmachine-style subsystem. Stick a
  thin plane onto any surface under the cursor: it adheres via a SHRINKWRAP
  (PROJECT) modifier and is parented to the hit object, following the surface.
  - **Place tool** (`HARDFLOW_OT_place_decal`, modal): raycasts the surface under
    the cursor, previews the decal aligned to the hit normal; mouse wheel scales,
    `[` / `]` roll around the normal, left click places.
  - **Decal types** — Info (emissive accent), Panel (dark recessed), Subset
    (masked patch); each is a reusable material template.
  - **Decal collection** — placed decals are gathered in "Hardflow Decals"; the
    N-panel "Decals" section lists them with show/hide, select, and delete (same
    pattern as cutters).
  - Pure orientation math in `core/decal_math.py` (bpy-free, tested:
    `orientation_basis`, `base_tangent`, `rotate_about_axis`); bpy logic in
    `core/decal.py`; surface raycast helper `raycast.ray_cast_surface`.
  - Preferences: `decal_size`, `decal_offset`.
- **Decals (v0.8 PBR material)** — decal materials now instance a shared
  `HF_DecalShader` node group (`core/decal.py _decal_node_group`) instead of a
  bare Principled BSDF. The group exposes base color / metallic / roughness / AO
  / normal / emission / alpha channels (AO multiplies base color; emission and
  alpha wired through), so per-type templates tune one shared graph and the v0.9
  image library can plug textures into the same sockets. Eevee + Cycles
  compatible (plain Principled + Mix). Alpha blending via `surface_render_method`
  ('BLENDED') on EEVEE Next, with a `blend_method` fallback for older builds.
- **Decals (v0.8 parallax depth)** — the shader group gained Height + Depth
  channels feeding a Bump node, recessing panel lines once a height map is
  present (the PANEL preset turns Depth on). View-dependent parallax-occlusion is
  deferred to v0.9 with the image library.
- **Decals (v0.8 bake)** — `HARDFLOW_OT_bake_decal` bakes a decal's Normal or
  Combined detail into an image on the target mesh via Cycles selected-to-active
  (`core/decal.py bake_image` / `ensure_material` / `bake_image_node`). New
  `bake_size` preference and a per-decal bake button in the N-panel "Decals"
  list. The target must be UV-unwrapped; render-engine and selection state are
  saved and restored around the bake.
- **Decals (v0.9 image library)** — place any image as a decal. "Decal from
  Image" (`HARDFLOW_OT_load_decal_image`) picks a file from disk; an image decal
  drives the shared `HF_DecalShader` group from the image's Color + Alpha
  (`core/decal.py image_decal_material` / `make_image_decal`) and is sized to the
  image's aspect ratio (`core/decal_image.py aspect_size`, tested). The modal
  place tool gained an `image_name` property so the same wheel-scale / `[` `]`
  roll / click-to-place flow applies.
- **Decals (v0.9 library browser)** — a "Decal Library" N-panel section
  (`ui/decal_library.py`) shows the images in a user folder as an icon grid
  (thumbnails via `bpy.utils.previews`); clicking one places it. New
  `decal_library_path` preference; pure folder scan in `core/decal_image.py`
  `scan_library` (tested).
- **Decals (v0.9 trim sheets)** — place one cell of a grid-sliced sheet as a
  decal. "Trim Sheet from Image" (`HARDFLOW_OT_load_trim_sheet`, Columns/Rows)
  starts the place tool with trim params; Up/Down cycle the cell and the quad is
  sized to the cell's aspect. `core/atlas.py` (new, pure, tested) does the UV
  math (`slice_grid`, `cell_rect`, `rect_pixels`); `core/decal.py
  build_decal_mesh` gained a `uv_rect` argument threaded through
  `make_image_decal`.
- **Decals (v0.9 atlasing)** — `HARDFLOW_OT_atlas_decals` (N-panel "Decals"
  section) packs every image decal's texture into one `HF_Decal_Atlas` image,
  retargets each decal's UVs into its slot, and collapses them to a single shared
  material. Pure core in `core/atlas.py`: `pack_shelves` (shelf bin-packing),
  `blit_pixels` (RGBA block copy with clipping), `remap_uv`, `rect_to_uv`,
  `next_pow2` — all tested. The operator does pixel + UV data only (no
  `bpy.ops`), so it is covered by a headless test. New `atlas_max_width`
  preference; `core/decal.py atlas_image` allocates the target image.

## [0.6.0] — 2026-06-29

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
