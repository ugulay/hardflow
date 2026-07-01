# CLAUDE.md — Hardflow

This file exists so that Claude Code approaches the project with the right
context in every session.

## What the project is

Hardflow is an **open-source (GPLv3) hard-surface boolean modeling** toolkit for
Blender 4.2+. The goal: cover the whole hard-surface modeling loop —
draw-to-cut booleans, precise snapping, decals, kitbash assets, and direct
modeling — in one free add-on. **Every roadmap feature is now
implemented** (through v1.15 — v1.14 is the **Super Modeling Mode** and v1.15 is
the **Polish & Performance** pass, both described below) — the core
boolean/snap/cutter workflows; the full decal
subsystem (placement, PBR material, bake, image library, trim sheets, atlasing,
plus v1.7 create/match/retrim/conform + editable library); the asset/kitbash
system (INSERT placement, boolean INSERTs, .blend library, conform, asset-browser
mark, plus v1.8 auto-scale, insert-grid snap, material INSERTs, asset-pack export,
solver fallbacks); the mesh helpers (boolean-from-selection, edge weights,
display toggles, material helpers, recalc-normals — the bevel/mirror/array/
radial/symmetrize/sharpen/dice/clean modifier set and the step/taper/knurl
greeble were removed in v1.13); live placement preview; the direct-modeling
tools (Push/Pull, Offset, construction grid, cable);
**Edit Mode** for draw/Push-Pull/Offset/snap (v1.3); the
**in-draw operations** (knife, inset, array, mirror, bevel-on-cut, in-plane
rotation, stamp/repeat, live grid + depth — v1.4/v1.6); square/rect pipe
profiles + loft (v1.6); the v1.10 **viewport gizmos**; and the v1.11
**direct-modeling depth** — Polyline Trim parity (Join, Project/Fixed, Manifold
solver, double-click), Push/Pull copy/repeat/inference, the Offset recess/panel
chain, Object-Mode **Edge Bevel + Loop Cut**, and picking **through generative
modifiers**, all on the shared `operators/face_tool._FaceDragModal` base; and the
**v1.12 / trailing-v1.9** completions — **loop-cut slide**, **in-plane
offset-thickness inference**, draw-tool **Ctrl+Click set-main-edge** + **`H`
movable grid origin**, and a view-accurate **`knife_project`** KNIFE path (with the
footprint knife as the fallback); and the **v1.13 build/boolean expansion** —
the Greeble + Modifier tool sets removed (Pipe/Cable kept), new **build
primitives** (Cylinder/Cone/Sphere/Tube), new **boolean draw shapes**
(Slot/Star/Arc) with Union/Intersect/Join/Knife surfaced in the panel, a
**Sweep / Follow-Me** tool (L/U/T/I/box cross-sections on the shared
`pipe._CurveDraw` base), and a **live boolean preview** (`J`) plus N-panel
**Cutter Options**; and the **v1.15 Polish & Performance** pass — topology-safe
Smart Bevel (non-quad support loops + a `flank_can_support` safety barrier), a
framed "premium" HUD with translucent viewport guide lines, and a high-poly live
boolean preview that culls non-intersecting targets and gates idle re-evaluation
through the new pure `core/preview_cache`; and the **v1.16 Trim Sheet UV editor** —
an interactive viewport tool (`operators/trim_editor.py`) that carves a trim sheet
into free, unequal named UV rectangles (draw / resize-by-handle / move / guillotine
split), stored on the Image datablock (`bpy.types.Image.hardflow_trim`), which a
decal then borrows via `place_decal`'s new `region_index` (all rect math pure in
`core/atlas.py`). Code is syntax-verified with pure +
headless tests (121 pure + 126 headless, run live against a standalone `bpy`
build); the new bpy paths are also live-verified in Blender 5.1.2, and full GUI
verification of the modal interactions is tracked in `tests/manual_checklist.md`.
Roadmap: `ROADMAP.md`.

**Super Modeling Mode.** The SketchUp-fluidity / pro-pipeline evolution runs on
three layers: (1) the **Shadowing Engine** — `operators/hardflow_mode.py` shadows
native tools on the shared `_HardflowModeModal` shell (own modal loop →
`core/raycast`+`core/snapping`+`core/grid` → bmesh, never `bpy.ops`), with a
VIEW/**SURFACE**/X/Y/Z plane cycle, **`Tab` verb cycle** (Knife → Extrude → **Cut
→ Add → Slice → Intersect** draw-to-cut booleans, each footprint extruded into a
cutter and `robust_boolean`'d against the active mesh via an atomic
`BooleanCutCommand` chain), and a Ctrl+Shift+X keymap + Edit-pie/menu entries
(`mode_knife`/`mode_extrude`/`mode_cut`); (2) the **per-modal atomic macro** —
`core/command.py` + `operators/base.py` give every tool session a Command journal
that commits as one Blender undo step: **adopted** in the `_FaceDragModal` tools
(Push/Pull, Offset, Edge Bevel, Loop Cut — live preview via
`MeshSnapshotCommand`) and in `draw_cut._apply_destructive` (cutter chains are an
all-or-nothing `boolean_chain` MacroCommand); (3) **Smart Topology** —
`core/bevel.py` + `geometry.smart_bevel_edges` / `dissolve_boolean_ngons` add
support loops and clean boolean n-gons (Smart Bevel still EXPERIMENTAL, pending a
live subdivision-tuning pass). Design + status: `docs/hardflow_mode_plan.md`,
`docs/command_refactor.md`.

**Polish & Performance (v1.15).** Three quality upgrades, all keeping the
one-directional (ui/ops → core) rule with the new decision logic in the pure
core: (1) **Smart Bevel topology safety** — `geometry._flank_support_loop` now
supports non-quad flanks (n-gon boolean off-cuts), `core/bevel.flank_can_support`
is a safety barrier that skips flanks too small to hold a loop instead of
collapsing them, and `core/bevel.safe_support_fraction` clamps every split;
`smart_bevel_edges` reports a `skipped` count surfaced live in the Edge Bevel
HUD. (2) **Premium HUD + viewport guides** — `ui/draw.py` `draw_hud` renders a
framed panel with an accent header (`title`/`accent`) plus new translucent GPU
helpers (`draw_guide_line`/`draw_dashed_line`/`draw_snap_ring`/
`draw_mirror_plane`/`draw_rect_outline`/`fade_color`); `operators/hardflow_mode.py`
draws dashed per-plane axis guides + a ring snap marker. (3) **High-poly live
preview** — the new pure `core/preview_cache.py` (distance gate + AABB math)
drives `draw_cut._sync_live_boolean` to preview only targets whose world box
overlaps the cutter cage and to skip idle-frame re-evaluation; cap is the new
`live_preview_max_verts` preference.

**Pro-Pipeline Parity (v1.17).** A BoxCutter/HardOps-parity pass closing the
non-destructive-stack, shading, cutter-management, snapping and cut→decal gaps,
all keeping the one-directional rule (new decision logic in pure core): (1)
**Smart modifier sorting** — pure `core/modifiers.py` (`sorted_order`/
`reorder_moves`/`is_sorted`: Booleans on top, Bevel below, Weighted Normal /
Triangulate at the bottom, Mirror above/below the booleans by a toggle; stable
so re-runs are idempotent) applied by `operators/hardops.sort_modifier_stack`
(`HARDFLOW_OT_sort_modifiers`), auto-run after Smart Sharpen + non-destructive
Cut (pref `sort_modifiers_after_cut`). (2) **Boolean shading fix** —
`core/boolean.capture_normal_source` snapshots a target's clean pre-cut normals
into a hidden helper, `add_normal_transfer` binds a NEAREST_POLYNOR Data
Transfer that reflects them onto the n-gons a cut leaves; wired into destructive
Cut behind `fix_shading_after_cut`, plus the standalone `HARDFLOW_OT_fix_shading`
(smooth-by-angle + Weighted Normal). (3) **Native Smooth by Angle** —
`operators/hardops.ensure_smooth_by_angle` adds the modern GN modifier on 4.1+
(the removed `use_auto_smooth` path was a silent no-op on 4.2+), legacy flag
below. (4) **Bevel hierarchy** — Smart Sharpen's optional second angle-limited
`HF_MicroBevel` for boolean-cut corners (main weight bevel keeps the big round).
(5) **Cutter management** — `core.geometry.extract_faces` +
`HARDFLOW_OT_extract_cutter` (selected faces → standalone solidified cutter) and
`HARDFLOW_OT_cutter_scroll` (modal wheel/arrow scroll through an object's stashed
HF_Bool cutters, reveal-one-at-a-time). (6) **Incremental snapping** — draw tool
Ctrl = momentary force-grid snap (`_snap_screen(force_grid=)`), Shift+PgUp/Dn =
fine 1/10-cell depth. (7) **Cut-to-Trim bridge** (the differentiator) — after a
boolean, `draw_cut._auto_trim` routes a cyclic pipe / recessed panel line along
the drawn boundary (the footprint IS the boundary, so it always matches),
draped onto the ACTIVE target via `snapping.drape_path`, into a "Hardflow Trim"
collection; pure `core/transform.dedup_ring` cleans the ring, `build_pipe` gains
a `closed` cyclic option; prefs `auto_trim_after_cut`/`auto_trim_radius`/
`auto_trim_lift`. (Note: Areas already shipped — fast-preview→exact-commit
solver handoff, in-RAM bmesh preview, Ctrl+Wheel live grid density, and the
pre-click SURFACE face-aligned grid — were verified present, not rebuilt.)

## FIRST TASK: smoke test inside Blender

This code **has been written and syntax-verified, but has not yet been run in a
live Blender.** Before developing any feature:

1. Install the addon, enable it, and verify it registers without errors.
2. Select a cube in Object Mode → Ctrl+Shift+D → draw a Box → see the Cut work.
3. Try the pie menu (Alt+Q), slice/make modes, the new shapes (Slot/Star/Arc),
   the build primitives, and the Sweep tool one by one.
4. Two especially suspect spots: the `temp_override` + `modifier_apply` call in
   `core/boolean.py`, and the geometry/projection math in `_build_and_apply` in
   `operators/draw_cut.py`. These have not been tested at runtime.

If errors come up, fix these first, then move on to the ROADMAP.

## Architecture — an inviolable rule

Layer dependency is **one-directional**:

```
ui  ─┐
     ├─► core      (core NEVER looks upward)
ops ─┘
```

- `core/` is pure logic: it **does not use** `bpy.ops`, `gpu`, or `blf`. The only
  exception: `modifier_apply` inside `core/boolean.py` (a deliberate
  concession).
- `core` must stay testable. A new feature = a pure function in `core` + a thin
  `operator` that calls it.
- UI drawing is gathered in `ui/draw.py`; operators delegate to it.

## File map

| Path | Responsibility |
|-----|-----------|
| `__init__.py` | Registration orchestration, the `_classes` tuple |
| `keymaps.py` | Shortcut registration + preferences rebind UI (`register_keymaps`, `draw_keymap_prefs`); defaults Alt+Q / Ctrl+Shift+D |
| `preferences.py` | Settings + the `get_prefs(context)` accessor |
| `core/raycast.py` | Screen↔3D projection + plane (u,v) + surface ray (`screen_to_plane`, `view_direction`, `world_to_plane_uv`, `plane_uv_to_world`, `world_to_screen`, `ray_cast_surface`/`ray_cast_surface_ex` (w/ `ignore` to skip the live preview), `face_edge_tangent` (smart edge-aligned orient; `near_point` aligns to the edge nearest the click for the SURFACE grid), `basis_from_normal`, `view_basis`/`surface_basis_at` (the shared VIEW + on-face SURFACE construction basis; draw_cut and the HardFlow Mode shell both delegate), `closest_axis_distance`) |
| `core/grid.py` | World-scale + angle + scalar snap, shape points, construction grid, 2D rotation (`snap_world`, `snap_scalar`, `world_grid_segments`, `centered_grid_segments`, `snap_angle`, `box_points`, `circle_points`, `ngon_points`, `slot_points` (stadium), `star_points` (n-pointed star), `arc_points` (pie sector), `centroid`, `rotate_2d`, `is_self_intersecting`, `point_in_polygon`, `polygons_overlap` (knife footprint test), `lock_distance` (numeric exact-size entry)) |
| `core/snap.py` | Vertex/edge geometry snap, pure 2D (`nearest_point`, `closest_point_on_segment`, `nearest_on_segments`, `resolve_snap` (nearest-wins disambiguation, vertex priority breaks ties), `snap_to_candidates` (1-D inference: snap a scalar to the nearest feature value)) |
| `core/snapping.py` | Unified 3D snapping shared by every draw tool (vertex/edge → surface → grid → free) + pipe surface-drape; bpy-data + mathutils, no `bpy.ops`/`gpu`/`blf`; reads the live edit-mesh in Edit Mode (v1.3); delegates picking to `core/snap.py` (`Geo`, `collect_geo`, `geo_snap_3d`, `grid_snap_3d`, `snap_insert_point`, `nearest_surface_point`, `drape_path`) |
| `core/offset.py` | Pure 2D polygon inset/offset math, stdlib only — the Offset tool (`signed_area`, `offset_polygon`, `inset_inference_candidates` (in-plane thickness inference: distances at which the inset border hits a coplanar feature)) |
| `core/bevel.py` | Pure Smart Bevel support-loop placement + clamping math, stdlib only (`holding_loop_factor`, `seg_factor` (v1.16 bevel-exact: tightens the offset for a rounded multi-segment bevel by 2/(segments+1); 1.0 for a chamfer), `subdiv_fillet_radius`/`support_offset_for_radius` (the offset↔subdivided-radius relation, inverses), `support_loop_positions`/`support_loop_fractions` (absolute offsets / (0,1) flank fractions from the bevel border; `tightness` 0..1 hug + segment-aware), `safe_support_fraction` (clamp one split off both ends of a flank — the per-edge safety barrier), `flank_can_support` (skip a flank too small to hold a loop; the non-quad-safe gate)) |
| `core/topology.py` | Pure post-boolean cleanup predicates, stdlib only — the Module 4 (MeshMachine parity / SubD stability) anchor (`triangle_area`, `polygon_area` (Newell cross-sum, translation-invariant), `is_sliver` (near-zero-area face), `collinear`/`redundant_vertex` (a mid-edge valence-2 vert removable from a straight run)). `core/geometry._clean_boolean_slivers` applies them in bmesh |
| `core/preview_cache.py` | Pure live-boolean-preview caching / culling math, stdlib only — the high-poly guard (`moved_enough`/`PreviewGate` distance gate so an idle mouse doesn't re-evaluate the boolean, AABB math `aabb`/`expand_aabb`/`boxes_overlap`/`point_in_box` so only targets the cutter box actually reaches carry the temp modifier). No bpy; consumed by `operators/draw_cut._sync_live_boolean` |
| `core/hud.py` | Pure HUD-layout + viewport-guide math, stdlib only — the Module 2 (BoxCutter-parity) anchor (`shortcut_bar_layout` (centered / margin-anchored chip packing for the bottom shortcut bar), `axis_alignment` + `alignment_guides` (dynamic full-span alignment guides when the cursor is square with a placed point, deduped)). No gpu/blf; `ui/draw.draw_shortcut_bar`/`draw_alignment_guides` render what it returns |
| `core/command.py` | Pure Command-Pattern journal, stdlib only — the per-modal-session undo layer (`Command` (idempotent `execute`/`undo`), `CallbackCommand`, `MacroCommand` (atomic all-or-nothing chain; rolls applied children back on a failing child), `CommandManager` (`do`/`undo`/`redo`/`undo_all`/`clear` journal)) |
| `core/geometry.py` | bmesh generation (`build_prism`/`build_prisms` (`apex` = perspective Project taper), `build_face`/`build_faces`, `build_box`/`build_plane`/`build_line`/`build_cylinder`/`build_cone`/`build_uv_sphere`/`build_tube` (starter primitives + guide line), `extract_faces` (selected faces → new re-indexed mesh, optionally solidified into a closed cutter volume — the Extract Cutter core), `build_pipe` (round pipe curve; `closed` = cyclic spline for the Cut-to-Trim ring)/`build_pipe_mesh`/`profile_points` (round/square/rect + L/U/T/I structural sections for the Sweep tool), `build_loft`, `build_grid_mesh`, `extrude_faces`/`edit_extrude_faces` (clean extrude or `keep_original` copy), `inset_faces`/`inset_extrude_faces` (offset→push/pull recess/panel combo), `knife_polygon` (footprint-restricted via `_knife_footprint_faces`), `bevel_cutter` (chamfer the cutter for bevelled cuts), `nearest_edge_on_face`/`edge_loop`/`edge_ring`/`bevel_object_edges`/`loop_cut` (Object-Mode edge pick + loop/ring walk + bevel + loop cut; `loop_cut` `slide` positions a single loop along its ring via `_oriented_ring`), `nearest_face_to_point` (map an evaluated-mesh hit to a base face -> pick through generative modifiers), `estimate_thickness`, `cleanup_mesh`, `mark_sharp_edges` (Object-Mode: clear + re-mark hard edges — angle-driven sharp + bevel weight + optional crease + shade-smooth, idempotent; the Smart Sharpen bmesh pass), `smart_bevel_edges` (Smart Bevel: bevel + support/holding loops via `_flank_support_loop` — now **non-quad-safe** (n-gon flanks + a `bevel.flank_can_support` safety barrier that skips too-small flanks, reported as a `skipped` count), topology-preserving), `dissolve_boolean_ngons` (triangulate + re-quad the n-gons a boolean/bevel leaves; v1.16 `clean_slivers` first runs `_clean_boolean_slivers` — merge doubles → `dissolve_degenerate` near-zero-area faces/edges → dissolve redundant collinear valence-2 verts via `core/topology`, the SubD-stabilizing pass)) + live-preview snapshot (`snapshot_mesh`, `restore_mesh`, `free_mesh`) + Edit-Mode bridge (v1.3: `flush_edit_mesh`, `restore_edit_mesh`, `edit_extrude_faces`, `edit_inset_faces`, `edit_add_face`, `edit_knife_polygon`, `edit_set_edge_weights`, `selected_face_basis`) |
| `core/boolean.py` | boolean + cutter management (`apply_boolean`, `apply_boolean_fallback` (EXACT→FAST), `robust_boolean` (auto-solver + ordered Manifold→Exact→Fast fallback chain + cutter normal repair + diagnosis), `choose_solver` (health-driven solver pick; Manifold-first on clean watertight meshes), `_coerce_solver`/`_solver_available` (version-safe solver: Manifold→Exact before Blender 4.5, Fast→Float on Blender 5.0+), `recalc_normals`, `mesh_health`/`_health_summary`, `add_boolean`, `duplicate_object`, `stash_cutter`, `cutter_collection`; **shading fix** `helper_collection`, `capture_normal_source` (hidden pre-cut clean-normal snapshot), `add_normal_transfer` (NEAREST_POLYNOR Data Transfer reflecting those normals onto the boolean n-gons)) |
| `core/modifiers.py` | Pure hard-surface modifier-stack ordering, stdlib only — the Sorting Engine (`modifier_priority` (Booleans top, Bevel mid, Weighted Normal/Triangulate bottom; Mirror above/below booleans by the `mirror_after_boolean` toggle), `sorted_order` (stable so re-runs are idempotent + unknown modifiers stay in the middle band), `reorder_moves` (selection-sort (from,to) plan matching bpy `modifiers.move`), `is_sorted`). Applied by `operators/hardops.sort_modifier_stack` |
| `core/transform.py` | Pure cable-sag + sizing math, stdlib only (`cable_points`, `cable_chain`, `dice_coordinates` (split a span into equal pieces), `fit_scale`, `adaptive_dimension` (size-scaled bevel/chamfer width), `dedup_ring` (drop consecutive/closing duplicate points from a Cut-to-Trim boundary loop)) |
| `core/hardsurface.py` | Pure Smart-Sharpen decision math, stdlib only — the Module 3 (HardOps parity) anchor (`dihedral_angle` (face-normal fold, matches bmesh `calc_face_angle`), `should_sharpen`/`sharp_edges` (which edges are "hard" at a threshold), `adaptive_bevel_width` (bevel width scaled to the smallest side)). `core/geometry.mark_sharp_edges` does the bmesh marking; `operators/hardops.HARDFLOW_OT_smart_sharpen` drives it |
| `core/decal_math.py` | Pure orientation math, no bpy/mathutils (`orientation_basis`, `base_tangent`, `dominant_tangent` (longest-edge alignment), `basis_from_edge`/`basis_from_two_edges` (grid-on-edges plane), `best_edge_pair` (deterministic longest-edge main + most-perpendicular partner for the 2-edge plane; `forced_main` overrides the main for Ctrl+Click set-main-edge), `rotate_about_axis`) |
| `core/decal_image.py` | Pure decal-library helpers, stdlib only (`scan_library`, `is_image_file`, `aspect_size`, `safe_filename`) |
| `core/parallax.py` | Pure Parallax Occlusion Mapping math, stdlib only — the depth-decal (Decal-Machine parity) anchor (`luminance` (Rec.709), `tangent_space_view` (world view → (T,B,N)), `dynamic_layer_count` (grazing-aware layer count), `parallax_delta_uv`/`steep_parallax_uv`/`parallax_occlusion_uv` (offset-limiting steep ray-march + occlusion refinement; constant-depth closed form `uv0 − d·P`)). `core/decal._parallax_uv_group` unrolls exactly this march as a shader-node network |
| `core/atlas.py` | Pure UV-rect + pixel math for trim sheets + atlasing (`slice_grid`, `cell_rect`, `rect_pixels`, `pack_shelves`, `remap_uv`, `blit_pixels`, `rect_to_uv`, `next_pow2`) + the **free-rectangle trim editor** math (`normalize_rect`, `rect_area`, `rect_contains`, `rect_at_point` (top-most hit-test), `snap_value`/`snap_rect`, `rect_handle_points`/`nearest_handle` (8-handle pick), `resize_rect`, `move_rect` (unit-clamped), `guillotine_split` (custom-size cut)) + **chroma-key background removal** (`color_distance`, `pixel_rgb`, `chroma_key` — alpha cutout by colour with a feathered edge band, mutates a flat RGBA list) |
| `core/decal.py` | Decal build/stick/material (`make_decal`, `make_image_decal`, `build_decal_mesh` (NxN grid so the shrinkwrap conforms to curved/multi-face surfaces; pref `decal_resolution`), `decal_matrix`, `add_shrinkwrap` (PROJECT both Z dirs), `decal_material`/`image_decal_material` + shared PBR node group `_decal_node_group`/`HF_DecalShader` with base/metallic/roughness/AO/normal/height+depth/emission/alpha, bake helpers `bake_image`/`ensure_material`/`bake_image_node`/`discard_bake_image` (roll back a failed bake), atlas image `atlas_image`, `decal_collection`, `DECAL_TYPES`; v1.7 extras `sample_material`/`match_decal_to_material`/`set_decal_uv_rect`/`conform_trim_decal`/`retarget_decal` (transfer to another surface)/`save_image`; v1.16+ depth extras `_parallax_uv_group`/`_wire_parallax` (per-image POM node graph driven by Camera Vector → tangent-space view, luminance-as-height; prefs `decal_parallax`/`decal_parallax_depth`/`decal_parallax_layers`) + `add_normal_transfer` (Data Transfer of the target's normals so a decal shades into a curved surface; pref `decal_normal_transfer`), all wrapped so a node/API mismatch degrades to the flat decal) |
| `core/asset_lib.py` | Pure `.blend` kit-library scan, stdlib only (`scan_assets`, `is_asset_file`) |
| `core/asset.py` | INSERT append/orient/bind, bpy-data only (`load_blend_objects`, `asset_matrix`, `place_asset`, `make_asset_cutter`, `bind_cutters`, `flatten_objects`, `conform_asset`, `transfer_shading`, `asset_collection`) + v1.8 asset extras (`bound_size`, `surface_feature_size`, `load_blend_materials`, `apply_material`, `write_objects_blend`) |
| `operators/draw_cut.py` | Main modal drawing operator (`HARDFLOW_OT_draw`): shapes box/circle/poly/ngon/**slot**/**star**/**arc** (keys `Q/W/E/R/T/Y/U`; `[ ]` = sides, or ARC sweep), cut/slice/make/**join**(add solid, no boolean)/**intersect**/face/**knife** (mode via `Tab`/`Shift+Tab`), **live boolean preview** (`J` -> temp `HF_LivePreview` modifier shows the real result via `base.LivePreviewCommand`; `_sync_live_boolean`/`_clear_live_boolean`, non-destructive + vertex-capped) + prefs-seeded **cutter options**, per-cut **boolean solver** (Default/Exact/Fast/Manifold), Polyline-Trim **Project/Fixed** extrude orientation (`O`, perspective taper via `_project_apex`), **numeric exact-size entry** (type a dimension -> `_apply_numeric`/`grid.lock_distance`), plane cycling VIEW/SURFACE/**EDGES**(grid on selected edges, longest-edge main via `best_edge_pair`, **Ctrl+Click** sets the main edge via `_pick_selected_edge`)/X/Y/Z (edge- and face-aligned tangents), `Shift+←/→` in-plane grid rotation (`_apply_spin`), **`H` set/move grid origin** (re-anchor the snap lattice, applied in `_plane_basis`), `Z` quick-close / **double-click close**, view-accurate **`knife_project`** for KNIFE mode (`_knife_project_object`, footprint `knife_polygon` fallback), measurement HUD, live 3D cutter cage, Edit-Mode path (v1.3), and **in-draw ops** (v1.4/v1.6: inset `-/=`, rotate `,/.`, array `A`/axis `D`, mirror `M`, bevel-on-cut `B`, **bevelled cutter `C`**, **orient `O`**, stamp `G`, live grid Ctrl+Wheel, live depth PgUp/Dn (**Shift = fine 1/10-cell**)) via `_processed_corner_sets`. **Incremental snapping** (v1.17): holding **Ctrl** while moving forces the world-grid snap on for that move + bypasses geometry snap (`_snap_screen(force_grid=)`). Placement clicks route through a per-session **`CommandManager`** (`_record_placement` = a two-child `base.PlacePointCommand` macro over the screen+world lists; Backspace = undo, reset keys = clear). `_apply_destructive` applies the cutter(s) as an **atomic `MacroCommand`** of `base.BooleanCutCommand`s (multi-target CUT/MAKE + SLICE roll back all-or-nothing on a solver failure) + optional **Fix Shading** (pre-cut `boolean.capture_normal_source` → post-cut `add_normal_transfer`, pref `fix_shading_after_cut`); `_apply_nondestructive` auto-sorts the stack (pref `sort_modifiers_after_cut`). **Cut-to-Trim bridge** (v1.17): `_auto_trim` routes a cyclic pipe / recessed panel line along the drawn boundary (draped onto the ACTIVE target via `snapping.drape_path`, ring cleaned by `transform.dedup_ring`, `build_pipe(closed=True)`) into a "Hardflow Trim" collection; prefs `auto_trim_after_cut`/`auto_trim_radius`/`auto_trim_lift` |
| `operators/hardops.py` | Mesh helpers: edge bevel-weight/crease (Edit), display toggles, random colors, copy material, the boolean-health normal recalc, and the **Smart Sharpen / Init HardSurface** one-shot (`HARDFLOW_OT_edge_weight/display_toggle/random_color/copy_material/recalc_normals/smart_sharpen/sort_modifiers/fix_shading`). `smart_sharpen` = `geometry.mark_sharp_edges` (angle-driven sharp + bevel weight) + a weight-limited `HF_Bevel` + optional angle-limited `HF_MicroBevel` (v1.17 two-tier bevel hierarchy for boolean-cut corners) + a bottom-of-stack `HF_WeightedNormal`, matched by name so a re-run / F9 updates in place; wrapped per-object so one bad mesh can't abort the batch; ends with `sort_modifier_stack`. Module helpers `sort_modifier_stack` (replays `core.modifiers` order via `obj.modifiers.move`), `ensure_smooth_by_angle` (native "Smooth by Angle" GN modifier on 4.1+, legacy `use_auto_smooth` below); `HARDFLOW_OT_sort_modifiers` (hard-surface stack sort), `HARDFLOW_OT_fix_shading` (post-hoc boolean-shading fix: smooth-by-angle + Weighted Normal). The bevel/mirror/clean/symmetrize/dice/array/greeble tool sets were removed in v1.13 |
| `operators/boolean_ops.py` | Boolean from selected objects, active = cutter (`HARDFLOW_OT_boolean`) |
| `operators/cutters.py` | Non-destructive cutter management (`HARDFLOW_OT_apply_cutters/select_cutter/remove_cutter`) + v1.17 **Extract Cutter** (`HARDFLOW_OT_extract_cutter`: Edit-Mode face selection → standalone solidified cutter at the source world transform, via `geometry.extract_faces`) + **Cutter Scroll** (`HARDFLOW_OT_cutter_scroll`: modal wheel/arrow cycle through the stashed HF_Bool cutters on the active object — reveal one, select it, hide the rest; Enter keeps, Esc restores) |
| `operators/pipe.py` | Surface-snapping curve draw on the shared `_CurveDraw` modal (profile cycle via `_PROFILE_CYCLE`, P): pipe (drapes, F toggles; round/square/rect) + free-hanging sagging cable/rope + **Sweep / Follow-Me** (sweeps an L/U/T/I/box structural section along the path); live preview (curve or swept mesh) (`HARDFLOW_OT_pipe/cable/sweep`) |
| `operators/face_tool.py` | **Shared base** `_FaceDragModal` for the face-pick-drag direct-modeling tools (Push/Pull, Offset): hover-pick (maps evaluated-mesh hits past the base mesh — generative modifiers — back to a base face via `geometry.nearest_face_to_point`) + lock + drag/numeric + live preview + snap + HUD frame + cancel/cleanup + shared axis-drag **inference** (`_capture_axis_inference`/`_snap_axis_value`: vertex + edge-midpoint heights → snap). The live preview runs through a per-session **`CommandManager` + `base.MeshSnapshotCommand`** (`_begin_edit` snapshots + applies, base `_refresh_preview` re-applies each frame via `command.reapply`, cancel = `undo_all`, commit = `clear` → one Blender undo step). A plain mixin (not an Operator, not registered); subclasses fill `_lock_face`/`_lock_edit`/`_update_drag`/**`_mutate`** (the edit without the restore)/`_set_value`/`_repeat_last`/`_remember_last`/`_hud_lines`/`_handle_key`. Mirrors `pipe._CurveDraw` |
| `operators/push_pull.py` | Push/Pull (on `face_tool._FaceDragModal`): drag a face along its normal (grid snap + numeric + **vertex/edge inference** via the shared base), bmesh extrude w/ live snapshot/restore; `C` **Copy** (keep starting face, stacked extrude), `R` **repeat** last distance (`HARDFLOW_OT_push_pull`) |
| `operators/offset.py` | Offset (on `face_tool._FaceDragModal`): drag to inset a face's border, bmesh inset w/ live snapshot/restore; **in-plane thickness inference** snaps the border onto a coplanar feature (`_capture_offset_inference`/`_snap_offset` → `offset.inset_inference_candidates`); `E` **chains into extruding** the inner face (recess / raised panel, two-phase `inset_extrude_faces`, depth has vertex/edge inference); `R` **repeat** last thickness (`HARDFLOW_OT_offset`) |
| `operators/edge_tool.py` | Object-Mode edge tools on shared `_EdgePickModal` (raycast → nearest edge, through modifiers; built on `face_tool._FaceDragModal`): **Edge Bevel** (drag width / `[ ]` segments / `L` whole-loop `edge_loop` → `bevel_object_edges`, `R` repeat, **`S` Smart Bevel** → `geometry.smart_bevel_edges` with `-`/`=` tightness: support loops + n-gon clean, non-quad-safe with a live `+N loops, M clamped` HUD readout, EXPERIMENTAL) + **Loop Cut** (`[ ]`/type cuts → `edge_ring` + `loop_cut`; **drag = slide** a single loop along its ring); live snapshot/restore. Edge work without Edit Mode (`HARDFLOW_OT_edge_bevel`, `HARDFLOW_OT_loop_cut`) |
| `operators/base.py` | Operator-layer (bpy-aware) Command-Pattern base over `core/command.py` (`HardFlowCommand` (adds `redo`), `PlacePointCommand` (undoable click), `MeshSnapshotCommand` (the named `snapshot_mesh`/`restore_mesh` preview→commit→rollback flow, mode-aware via injected `restore`), `BooleanCutCommand` (one `robust_boolean` as an atomic command that raises on failure), `boolean_chain` (a `MacroCommand` of cuts → all-or-nothing boolean chain), `LivePreviewCommand` (the non-destructive live-boolean preview: owns the temp `HF_LivePreview` modifier lifecycle via `execute`/`refresh`/`clear` — NOT a mesh snapshot, so the draw preview never bakes a per-frame boolean)) |
| `operators/hardflow_mode.py` | **HardFlow Mode "Shadowing Engine":** shared `_HardflowModeModal` shell (modal-hijack loop + Ghost-Grid snap chain `_snap_screen` + VIEW/**SURFACE**/X/Y/Z plane cycle (`_surface_basis_at`, aligned to the face under the first click) + **`Tab` verb cycle** (`_cycle_verb`) + per-session `CommandManager` + HUD; verbs dispatched by `self._active_verb`, subclasses only set `_START_VERB`). Verbs: **Knife** (score the drawn footprint onto the active mesh, swept along the construction-plane normal — view-projection on the VIEW plane, straight-in on SURFACE/X/Y/Z) + **Extrude** (draw a footprint, PgUp/PgDn depth, `build_prism` → new solid) + **Cut/Add/Slice/Intersect** draw-to-cut booleans (`_build_boolean`: footprint → `build_prism` cutter (`_boolean_cutter_mesh`; Cut/Slice/Intersect use a pierce-through `_pierce_thickness`, Add stands a boss proud of the surface) → atomic `MacroCommand` of `base.BooleanCutCommand` (`robust_boolean` + solver fallback; Slice keeps the intersect duplicate), destructive cutter). Entered from Ctrl+Shift+X + the Edit pie/menu (`mode_knife`/`mode_extrude`/`mode_cut`). Draws the **framed HUD** (verb + live depth) + dashed per-plane axis guide lines through the snapped cursor + a ring snap marker (`_draw_plane_guides`) + held-surface-plane fix (`_surface_hold`). One invocation = one atomic Blender undo step (`HARDFLOW_OT_mode_knife`, `HARDFLOW_OT_mode_extrude`, `HARDFLOW_OT_mode_cut`) |
| `operators/construction.py` | Starter primitives (cube/plane) + guide line + construction-grid object at the 3D cursor + loft/bridge between two profiles (`HARDFLOW_OT_add_primitive/add_guide/add_grid/loft`) |
| `operators/decals.py` | Decal placement/management/bake/library/trim/atlas + v1.7 create/match/retrim/conform/transfer + editable library (`HARDFLOW_OT_place_decal/select_decal/remove_decal/bake_decal/load_decal_image/library_place/load_trim_sheet/atlas_decals/match_decal/retrim_decal/conform_decal/transfer_decal/create_decal/library_rename/library_delete`). `place_decal` also takes a **`region_index`** into the sheet's custom `hardflow_trim` regions (v1.16): a whole-image / equal-grid-cell / custom-region sub-rect all flow through the one `_uv_rect`/`_wh` path, Up/Down cycles regions |
| `operators/trim_editor.py` | **Trim Sheet UV editor (v1.16):** the region data model (`HARDFLOW_TrimRegion`/`HARDFLOW_TrimSheet` PropertyGroups stored on `bpy.types.Image.hardflow_trim`; `Scene.hardflow_trim_image` points at the active sheet) + the interactive modal `HARDFLOW_OT_trim_editor` (draws the sheet as a screen-space canvas, LMB-drag = new region, drag handles = resize, click = select/move, `C`/`Shift+C` = guillotine split, `X` = delete, `A` = add, `Tab` = next, `G`/`[ ]`/wheel = snap, Enter/Esc = confirm/cancel-via-snapshot; all rect math via `core/atlas`) + region-management ops (`HARDFLOW_OT_load_trim_image`/`trim_region_add`/`trim_region_remove`/`trim_grid_regions`/`place_trim_region`/`retrim_region`) + **chroma-key background removal** (`HARDFLOW_OT_trim_chroma_key`: make a key colour transparent — eyedropper or corner-sample, tolerance + edge-softness feather, copy `<name>_cutout` (regions carried) or in-place; numpy fast path + `atlas.chroma_key` fallback) |
| `operators/assets.py` | INSERT placement (auto-scale + insert-grid snap, v1.8) + library + mark + material INSERT + asset-pack export (`HARDFLOW_OT_place_asset/load_asset/asset_library_place/mark_asset/material_insert/export_asset`) |
| `ui/draw.py` | GPU + blf helpers: shapes/points/fills/grid, the **framed HUD** (`draw_hud` with a bordered panel + optional accent `title`/header — every modal tool's premium overlay), the viewport-guide primitives (`draw_rect_outline`, `draw_rect_fill`, `draw_guide_line`, `draw_dashed_line`, `draw_snap_ring`, `draw_mirror_plane`, `fade_color` for translucent / fade-in overlays), plus **`draw_image`** (a GPU texture as a screen-space quad — the trim-editor canvas) and **`draw_text`** (a single blf label — per-region names), and the **v1.16+ Module 2 polish** — **`draw_shortcut_bar`** (a premium translucent bottom bar of `[KEY] Label` chips with a live accent = engaged/current state) + **`draw_alignment_guides`** (dashed full-span guides when the cursor is square with a placed point), both packing/aligning via the pure `core/hud.py` |
| `ui/pie.py` | Categorized pie system: main pie (Cut/Push-Pull/Offset heroes + category openers + Apply Cutters) + Boolean/Build/Edit/Curves sub-pies (`HARDFLOW_MT_pie`, `HARDFLOW_MT_pie_boolean/build/edit/curves`); `_draw`/`_open` helpers. Same Boolean→Build→Edit→Curves category order as the header menu + N-panel |
| `ui/menu.py` | 3D-View header dropdown covering every tool incl. Decals/Assets; data-driven `*_ITEMS` tables + submenus (Boolean/Build/Edit/Curves/Display/Decals/Assets — Edit = Push-Pull/Offset/Edge-Bevel/Loop-Cut) (`HARDFLOW_MT_menu`, `HARDFLOW_MT_menu_*`); `register`/`unregister` add the header hook |
| `ui/panel.py` | N-panel in Boolean→Build→Edit→Curves→Display order (matches the pie + header menu): Boolean draw (Cut/Slice/Make/Intersect/Join/Knife + Circle/N-gon/Slot/Star/Arc shapes + Boolean-Selected + Apply Cutters), Build (cube/plane/cylinder/cone/sphere/tube + sketch faces + grid/guide/loft), Edit (Push/Pull/Offset/Edge-Bevel/Loop-Cut), Curves (pipe/cable/sweep), display + material rows, snap settings, **Cutter Options** (v1.13 prefs-backed inset/bevel/array/live-preview), **modifier-stack manager** (v1.5), **gizmo toggles** (v1.10), cutter list (`HARDFLOW_PT_tools/gizmos/snap/cutter_options/modifiers/cutters`) |
| `gizmos/__init__.py` | Gizmo subsystem registration (v1.10): `HARDFLOW_GizmoSettings` (Scene-stored toggles `show`/`move`/`rotate`/`scale`/`bevel`/`push_pull`) + its own `register`/`unregister` (gizmo classes via `register_class`, Workspace Tools via `tools.register`), called from the add-on `__init__` |
| `gizmos/shapes.py` | Pure custom-gizmo geometry, stdlib math only (`arrow_tris` — +Z shaft+cone triangle soup for the Push/Pull handle) |
| `gizmos/custom.py` | Custom modal Gizmo `HARDFLOW_GT_drag_extrude`: drag a face along its normal to extrude it live (snapshot/restore in invoke/modal/exit, reuses `core.geometry` extrude + `core.raycast.closest_axis_distance` — the gizmo form of `operators/push_pull.py`) |
| `gizmos/groups.py` | GizmoGroups — persistent `HARDFLOW_GGT_persistent` (toggle-gated; hides handles per mode) + per-tool `HARDFLOW_GGT_move/rotate/scale/bevel/push_pull`. Move/Rotate/Scale wrap built-in `transform.translate/rotate/resize` (arrow/dial via `target_set_operator` + `constraint_axis`); Bevel drives an `HF_Bevel` width via `target_set_handler` (`_bevel_get`/`_bevel_set`); shared `_make_*`/`_axis_basis`/`_setup_pushpull` builders |
| `gizmos/tools.py` | Workspace Tools (toolbar T): `HARDFLOW_T_move/rotate/scale/bevel` + `push_pull` (Object, launches the raycast modal) + `push_pull_edit` (Edit Mesh, gizmo); `register`/`unregister` wrap `register_tool` defensively (it can raise headless) |
| `ui/decal_panel.py` | N-panel "Decals" section: place by type + decal list (`HARDFLOW_PT_decals`) |
| `ui/decal_library.py` | N-panel "Decal Library" section: image icon grid (`HARDFLOW_PT_decal_library`, `bpy.utils.previews`) |
| `ui/trim_panel.py` | N-panel "Trim Sheet Editor" section under Decals (v1.16): pick/load the active sheet (`Scene.hardflow_trim_image`), open the editor, seed regions from a grid, and manage the carved regions — place one as a decal / re-trim a placed decal / rename / remove; **Remove Background…** (chroma-key) button (`HARDFLOW_PT_trim`) |
| `ui/asset_panel.py` | N-panel "Assets" + "Asset Library" sections (`HARDFLOW_PT_assets/asset_library`) |
| `tests/test_core.py` | Pure core tests without Blender (`python tests/test_core.py`) |
| `tests/test_blender.py` | Headless runtime tests for bpy-dependent core + non-modal operators (`blender --background --python tests/test_blender.py`) |
| `tests/manual_checklist.md` | Click-through checklist for the modal tools the headless suite can't reach (draw, Push/Pull, Offset, pie + header menu) |

## Registration rule

Every new class must be added to the `_classes` tuple in `__init__.py`,
otherwise it won't be registered. Keymaps live in `keymaps.register_keymaps()`;
users can rebind them from the standard Blender keymap editor in preferences.

**Gizmos are the exception:** `Gizmo`/`GizmoGroup` classes and `WorkSpaceTool`s
register through `gizmos.register()` (called from the add-on `__init__`), *not*
the `_classes` tuple — gizmos use `register_class` but tools use
`register_tool`. Note registered gizmo classes are **not** exposed on
`bpy.types.<Name>`; look them up with
`bpy.types.GizmoGroup.bl_rna_get_subclass_py("HARDFLOW_GGT_…")`.

## Blender API constraints (4.2 LTS+ target)

- 2D drawing shader: `'UNIFORM_COLOR'` / `'POLYLINE_UNIFORM_COLOR'`.
  **DO NOT USE `'2D_UNIFORM_COLOR'`** (removed in 3.x).
- `blf.size(font_id, size)` — no legacy dpi parameter.
- `batch_for_shader` primitives: `LINE_STRIP`, `LINES`, `TRIS`, `POINTS`.
  **Do not use `LINE_LOOP` / `TRI_FAN`** (deprecated).
- For context override, use `with context.temp_override(...)`.

## Development loop

For fast iteration without re-zipping, set up a symlink:

```bash
ln -s "$(pwd)" ~/.config/blender/4.2/extensions/user_default/hardflow
```

To load a change in Blender: `F3 > Reload Scripts` or disable/enable the addon.
Keep the System Console open (Window > Toggle System Console).

Note: `bpy` does not run outside Blender; unit tests run inside Blender's Python
or headless via `blender --background --python test.py`. Most `core/` modules can
be tested with bpy mocked out (a deliberate design choice).

## Conventions

- Class names: `HARDFLOW_OT_*` (operator), `HARDFLOW_MT_*` (menu),
  `HARDFLOW_Preferences`.
- Operator `bl_idname`: `mesh.hardflow_*` or `object.hardflow_*`.
- PEP 8, ~90 character lines.
- License GPLv3 — applies to new files too.
