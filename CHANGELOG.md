# Changelog

Notable changes in this project. Versioning follows [SemVer](https://semver.org)
logic; since the project is pre-1.0, minor versions add features.

## [Unreleased]

_Nothing yet._

## [1.2.0] — 2026-06-29

The SketchUp-style direct-modeling milestone: drag faces in/out (Push/Pull),
inset face borders (Offset), and drop a construction-grid reference object to
model against. Pure logic is unit-tested without Blender (`44/44` passing); the
bpy-dependent paths have headless coverage and still await a live-Blender smoke
test.

### Added
- **Push/Pull (SketchUp)** — `HARDFLOW_OT_push_pull` (`operators/push_pull.py`):
  raycast a face, lock it, then drag along its normal to extrude in or out with
  world-grid snap and numeric entry; bmesh extrude, no `bpy.ops`. Reuses
  `core/raycast.py`, `core/grid.py`, and `core/geometry.py`.
- **Offset (SketchUp)** — `HARDFLOW_OT_offset` (`operators/offset.py`): raycast a
  face and drag to inset its border inward by a measured distance (grid-snapped,
  numeric entry), committing a bmesh inset. Pure 2D inset/offset math in
  `core/offset.py` (`signed_area`, `offset_polygon`), stdlib only.
- **Construction grid** — `HARDFLOW_OT_add_grid` (`operators/construction.py`):
  a non-modal operator that drops a wire reference grid at the 3D cursor on the
  XY / XZ / YZ plane to model against; built from `core/grid.py
  centered_grid_segments` + `core/geometry.py build_grid_mesh`.
- All three tools are surfaced in the N-panel tools section.

## [1.1.0] — 2026-06-29

### Added
- **Live placement preview (decals & assets)** — the decal and asset placement
  tools now show the **real object** under the cursor instead of a flat wireframe
  outline, so you see exactly what you'll get before clicking (the DECALmachine /
  BoxCutter / KitOps flow).
  - Decals (`HARDFLOW_OT_place_decal`): the actual textured/material decal is
    materialised on the first surface hit and follows the cursor; it is rebuilt
    only when the target object, size, or trim cell changes and merely re-oriented
    on every mouse move. The preview **is** the final decal on click; Esc deletes
    it.
  - Assets (`HARDFLOW_OT_place_asset`): the `.blend` part is appended **once** on
    invoke and the real geometry follows the cursor; on click it is finalised in
    place (decoration) or re-bound as boolean cutters, and on Esc the preview is
    discarded. New `core/asset.py` helpers `bind_cutters` (shared cutter binding)
    and `flatten_objects` (drop preview parenting, keep world pose) support the
    reuse; `make_asset_cutter` now delegates to `bind_cutters`.

## [1.0.0] — 2026-06-29

The v1.0 milestone: the KitOps-style asset/kitbash system lands and the Hard Ops
modeling toolset is rounded out (boolean-from-selection, array, radial array,
symmetrize, sharpen). Pure logic is unit-tested without Blender; the
bpy-dependent paths have headless coverage and still await a live-Blender smoke
test.

### Added
- **Asset / kitbash system (v1.0, KitOps spirit)** — a new subsystem for placing
  ready-made parts ("INSERTs") onto surfaces. Architecture mirrors the decal
  subsystem: pure logic in `core/asset_lib.py` (library scan, tested) +
  `core/asset.py` (append/orient/bind, bpy-data only), action in
  `operators/assets.py`, interface in `ui/asset_panel.py`.
  - **INSERT placement** (`HARDFLOW_OT_place_asset`, modal): appends the objects
    of a `.blend`, previews the footprint aligned to the surface normal under the
    cursor; wheel scales, `[` / `]` roll, left click places. Parts are parented
    under an oriented Empty (`asset.place_asset`), reusing the shared
    `core/decal_math.orientation_basis`.
  - **Boolean INSERTs** — with "Asset as Cutter" on, each mesh of the part becomes
    a CUT/MAKE boolean cutter on the surface object, bound non-destructively via
    `core/boolean.py` + `stash_cutter` (`asset.make_asset_cutter`).
  - **Asset library** — `.blend` parts in the `asset_library_path` folder shown as
    an N-panel "Asset Library" grid; clicking places one
    (`HARDFLOW_OT_asset_library_place`). Pure folder scan in
    `core/asset_lib.py scan_assets` (tested).
  - **Wrap / Conform** — `asset.conform_asset` shrinkwraps the part onto a curved
    surface (preference `asset_conform`); **shading transfer** —
    `asset.transfer_shading` applies the surface's material + smooth state
    (preference `asset_transfer_shading`).
  - **Asset Browser integration** — `HARDFLOW_OT_mark_asset` marks selected
    objects as Blender assets (`asset_mark` + `asset_generate_preview`).
  - Preferences: `asset_library_path`, `asset_as_cutter`, `asset_boolean`,
    `asset_conform`, `asset_transfer_shading`.
- **Boolean from selection (Hard Ops)** — `HARDFLOW_OT_boolean`: boolean the
  selected meshes using the active object as the cutter (Difference / Union /
  Intersect / Slice), honouring the non-destructive preference. Reuses
  `core/boolean.py`; no drawing required.
- **Array (Hard Ops)** — `HARDFLOW_OT_array`: a linear Array modifier along a
  world axis, relative or constant offset (`core/transform.py
  array_offset_vector`, tested).
- **Radial array (Hard Ops)** — `HARDFLOW_OT_radial_array`: an Array modifier
  driven by a rotated offset Empty parented at the 3D cursor; `count` copies
  evenly around an axis. Pure angle math in `core/transform.py
  radial_step_radians` / `radial_angles_deg` (tested).
- **Symmetrize (Hard Ops)** — `HARDFLOW_OT_symmetrize` /
  `core/geometry.symmetrize_mesh`: mirror one half of the mesh onto the other
  across an object-local axis (bmesh `symmetrize`, no `bpy.ops`).
- **Sharpen / SSharp (Hard Ops)** — `HARDFLOW_OT_sharpen` /
  `core/geometry.mark_sharp_by_angle`: mark edges sharp by angle, smooth the
  faces, add a Weighted Normal modifier for clean shading, and optionally an
  angle-limited bevel.
- **Tests** — `tests/test_core.py` (+6: `transform`, `asset_lib`), and
  `tests/test_blender.py` (+10: symmetrize/sharpen, boolean-from-selection,
  array/radial, asset matrix/placement/cutter/conform/shading, registration).

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
