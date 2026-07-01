# CLAUDE.md — Hardflow

This file exists so that Claude Code approaches the project with the right
context in every session.

## What the project is

Hardflow is an **open-source (GPLv3) hard-surface boolean modeling** toolkit for
Blender 4.2+. The goal: cover the whole hard-surface modeling loop —
draw-to-cut booleans, precise snapping, decals, kitbash assets, and direct
modeling — in one free add-on. **Every roadmap feature is now
implemented** (through v1.14 — the v1.14 line is the **Super Modeling Mode**
described below) — the core
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
**Cutter Options**. Code is syntax-verified with pure + headless tests (70 pure +
105 headless, run live against a standalone `bpy` build); the new bpy paths are
also live-verified in Blender 5.1.2, and full GUI verification of the modal
interactions is tracked in `tests/manual_checklist.md`. Roadmap: `ROADMAP.md`.

**Super Modeling Mode.** The SketchUp-fluidity / pro-pipeline evolution runs on
three layers: (1) the **Shadowing Engine** — `operators/hardflow_mode.py` shadows
native tools on the shared `_HardflowModeModal` shell (own modal loop →
`core/raycast`+`core/snapping`+`core/grid` → bmesh, never `bpy.ops`), with a
VIEW/**SURFACE**/X/Y/Z plane cycle, **`Tab` verb cycle** (Knife ↔ Extrude), and a
Ctrl+Shift+X keymap + Edit-pie entry; (2) the **per-modal atomic macro** —
`core/command.py` + `operators/base.py` give every tool session a Command journal
that commits as one Blender undo step: **adopted** in the `_FaceDragModal` tools
(Push/Pull, Offset, Edge Bevel, Loop Cut — live preview via
`MeshSnapshotCommand`) and in `draw_cut._apply_destructive` (cutter chains are an
all-or-nothing `boolean_chain` MacroCommand); (3) **Smart Topology** —
`core/bevel.py` + `geometry.smart_bevel_edges` / `dissolve_boolean_ngons` add
support loops and clean boolean n-gons (Smart Bevel still EXPERIMENTAL, pending a
live subdivision-tuning pass). Design + status: `docs/hardflow_mode_plan.md`,
`docs/command_refactor.md`.

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
| `core/bevel.py` | Pure Smart Bevel support-loop placement math, stdlib only (`holding_loop_factor`, `support_loop_positions` (absolute offsets from the bevel border; `tightness` 0..1 = how hard the holding loops hug the bevel), `support_loop_fractions` (the same as (0,1) fractions of a flanking face, clamped + deduped)) |
| `core/command.py` | Pure Command-Pattern journal, stdlib only — the per-modal-session undo layer (`Command` (idempotent `execute`/`undo`), `CallbackCommand`, `MacroCommand` (atomic all-or-nothing chain; rolls applied children back on a failing child), `CommandManager` (`do`/`undo`/`redo`/`undo_all`/`clear` journal)) |
| `core/geometry.py` | bmesh generation (`build_prism`/`build_prisms` (`apex` = perspective Project taper), `build_face`/`build_faces`, `build_box`/`build_plane`/`build_line`/`build_cylinder`/`build_cone`/`build_uv_sphere`/`build_tube` (starter primitives + guide line), `build_pipe`/`build_pipe_mesh`/`profile_points` (round/square/rect + L/U/T/I structural sections for the Sweep tool), `build_loft`, `build_grid_mesh`, `extrude_faces`/`edit_extrude_faces` (clean extrude or `keep_original` copy), `inset_faces`/`inset_extrude_faces` (offset→push/pull recess/panel combo), `knife_polygon` (footprint-restricted via `_knife_footprint_faces`), `bevel_cutter` (chamfer the cutter for bevelled cuts), `nearest_edge_on_face`/`edge_loop`/`edge_ring`/`bevel_object_edges`/`loop_cut` (Object-Mode edge pick + loop/ring walk + bevel + loop cut; `loop_cut` `slide` positions a single loop along its ring via `_oriented_ring`), `nearest_face_to_point` (map an evaluated-mesh hit to a base face -> pick through generative modifiers), `estimate_thickness`, `cleanup_mesh`, `smart_bevel_edges` (Smart Bevel: bevel + support/holding loops via `_flank_support_loop`, topology-preserving), `dissolve_boolean_ngons` (triangulate + re-quad the n-gons a boolean/bevel leaves)) + live-preview snapshot (`snapshot_mesh`, `restore_mesh`, `free_mesh`) + Edit-Mode bridge (v1.3: `flush_edit_mesh`, `restore_edit_mesh`, `edit_extrude_faces`, `edit_inset_faces`, `edit_add_face`, `edit_knife_polygon`, `edit_set_edge_weights`, `selected_face_basis`) |
| `core/boolean.py` | boolean + cutter management (`apply_boolean`, `apply_boolean_fallback` (EXACT→FAST), `robust_boolean` (auto-solver + ordered Manifold→Exact→Fast fallback chain + cutter normal repair + diagnosis), `choose_solver` (health-driven solver pick; Manifold-first on clean watertight meshes), `_coerce_solver`/`_solver_available` (version-safe solver: Manifold→Exact before Blender 4.5, Fast→Float on Blender 5.0+), `recalc_normals`, `mesh_health`/`_health_summary`, `add_boolean`, `duplicate_object`, `stash_cutter`, `cutter_collection`) |
| `core/transform.py` | Pure cable-sag + sizing math, stdlib only (`cable_points`, `cable_chain`, `dice_coordinates` (split a span into equal pieces), `fit_scale`, `adaptive_dimension` (size-scaled bevel/chamfer width)) |
| `core/decal_math.py` | Pure orientation math, no bpy/mathutils (`orientation_basis`, `base_tangent`, `dominant_tangent` (longest-edge alignment), `basis_from_edge`/`basis_from_two_edges` (grid-on-edges plane), `best_edge_pair` (deterministic longest-edge main + most-perpendicular partner for the 2-edge plane; `forced_main` overrides the main for Ctrl+Click set-main-edge), `rotate_about_axis`) |
| `core/decal_image.py` | Pure decal-library helpers, stdlib only (`scan_library`, `is_image_file`, `aspect_size`) |
| `core/atlas.py` | Pure UV-rect + pixel math for trim sheets + atlasing (`slice_grid`, `cell_rect`, `rect_pixels`, `pack_shelves`, `remap_uv`, `blit_pixels`, `rect_to_uv`, `next_pow2`) |
| `core/decal.py` | Decal build/stick/material (`make_decal`, `make_image_decal`, `build_decal_mesh` (NxN grid so the shrinkwrap conforms to curved/multi-face surfaces; pref `decal_resolution`), `decal_matrix`, `add_shrinkwrap` (PROJECT both Z dirs), `decal_material`/`image_decal_material` + shared PBR node group `_decal_node_group`/`HF_DecalShader` with base/metallic/roughness/AO/normal/height+depth/emission/alpha, bake helpers `bake_image`/`ensure_material`/`bake_image_node`/`discard_bake_image` (roll back a failed bake), atlas image `atlas_image`, `decal_collection`, `DECAL_TYPES`; v1.7 extras `sample_material`/`match_decal_to_material`/`set_decal_uv_rect`/`conform_trim_decal`/`retarget_decal` (transfer to another surface)/`save_image`) |
| `core/asset_lib.py` | Pure `.blend` kit-library scan, stdlib only (`scan_assets`, `is_asset_file`) |
| `core/asset.py` | INSERT append/orient/bind, bpy-data only (`load_blend_objects`, `asset_matrix`, `place_asset`, `make_asset_cutter`, `bind_cutters`, `flatten_objects`, `conform_asset`, `transfer_shading`, `asset_collection`) + v1.8 asset extras (`bound_size`, `surface_feature_size`, `load_blend_materials`, `apply_material`, `write_objects_blend`) |
| `operators/draw_cut.py` | Main modal drawing operator (`HARDFLOW_OT_draw`): shapes box/circle/poly/ngon/**slot**/**star**/**arc** (keys `Q/W/E/R/T/Y/U`; `[ ]` = sides, or ARC sweep), cut/slice/make/**join**(add solid, no boolean)/**intersect**/face/**knife** (mode via `Tab`/`Shift+Tab`), **live boolean preview** (`J` -> temp `HF_LivePreview` modifier shows the real result via `base.LivePreviewCommand`; `_sync_live_boolean`/`_clear_live_boolean`, non-destructive + vertex-capped) + prefs-seeded **cutter options**, per-cut **boolean solver** (Default/Exact/Fast/Manifold), Polyline-Trim **Project/Fixed** extrude orientation (`O`, perspective taper via `_project_apex`), **numeric exact-size entry** (type a dimension -> `_apply_numeric`/`grid.lock_distance`), plane cycling VIEW/SURFACE/**EDGES**(grid on selected edges, longest-edge main via `best_edge_pair`, **Ctrl+Click** sets the main edge via `_pick_selected_edge`)/X/Y/Z (edge- and face-aligned tangents), `Shift+←/→` in-plane grid rotation (`_apply_spin`), **`H` set/move grid origin** (re-anchor the snap lattice, applied in `_plane_basis`), `Z` quick-close / **double-click close**, view-accurate **`knife_project`** for KNIFE mode (`_knife_project_object`, footprint `knife_polygon` fallback), measurement HUD, live 3D cutter cage, Edit-Mode path (v1.3), and **in-draw ops** (v1.4/v1.6: inset `-/=`, rotate `,/.`, array `A`/axis `D`, mirror `M`, bevel-on-cut `B`, **bevelled cutter `C`**, **orient `O`**, stamp `G`, live grid Ctrl+Wheel, live depth PgUp/Dn) via `_processed_corner_sets`. Placement clicks route through a per-session **`CommandManager`** (`_record_placement` = a two-child `base.PlacePointCommand` macro over the screen+world lists; Backspace = undo, reset keys = clear). `_apply_destructive` applies the cutter(s) as an **atomic `MacroCommand`** of `base.BooleanCutCommand`s (multi-target CUT/MAKE + SLICE roll back all-or-nothing on a solver failure) |
| `operators/hardops.py` | Mesh helpers: edge bevel-weight/crease (Edit), display toggles, random colors, copy material, and the boolean-health normal recalc (`HARDFLOW_OT_edge_weight/display_toggle/random_color/copy_material/recalc_normals`). The bevel/mirror/clean/symmetrize/sharpen/dice/array/greeble tool sets were removed in v1.13 |
| `operators/boolean_ops.py` | Boolean from selected objects, active = cutter (`HARDFLOW_OT_boolean`) |
| `operators/cutters.py` | Non-destructive cutter management (`HARDFLOW_OT_apply_cutters/select_cutter/remove_cutter`) |
| `operators/pipe.py` | Surface-snapping curve draw on the shared `_CurveDraw` modal (profile cycle via `_PROFILE_CYCLE`, P): pipe (drapes, F toggles; round/square/rect) + free-hanging sagging cable/rope + **Sweep / Follow-Me** (sweeps an L/U/T/I/box structural section along the path); live preview (curve or swept mesh) (`HARDFLOW_OT_pipe/cable/sweep`) |
| `operators/face_tool.py` | **Shared base** `_FaceDragModal` for the face-pick-drag direct-modeling tools (Push/Pull, Offset): hover-pick (maps evaluated-mesh hits past the base mesh — generative modifiers — back to a base face via `geometry.nearest_face_to_point`) + lock + drag/numeric + live preview + snap + HUD frame + cancel/cleanup + shared axis-drag **inference** (`_capture_axis_inference`/`_snap_axis_value`: vertex + edge-midpoint heights → snap). The live preview runs through a per-session **`CommandManager` + `base.MeshSnapshotCommand`** (`_begin_edit` snapshots + applies, base `_refresh_preview` re-applies each frame via `command.reapply`, cancel = `undo_all`, commit = `clear` → one Blender undo step). A plain mixin (not an Operator, not registered); subclasses fill `_lock_face`/`_lock_edit`/`_update_drag`/**`_mutate`** (the edit without the restore)/`_set_value`/`_repeat_last`/`_remember_last`/`_hud_lines`/`_handle_key`. Mirrors `pipe._CurveDraw` |
| `operators/push_pull.py` | Push/Pull (on `face_tool._FaceDragModal`): drag a face along its normal (grid snap + numeric + **vertex/edge inference** via the shared base), bmesh extrude w/ live snapshot/restore; `C` **Copy** (keep starting face, stacked extrude), `R` **repeat** last distance (`HARDFLOW_OT_push_pull`) |
| `operators/offset.py` | Offset (on `face_tool._FaceDragModal`): drag to inset a face's border, bmesh inset w/ live snapshot/restore; **in-plane thickness inference** snaps the border onto a coplanar feature (`_capture_offset_inference`/`_snap_offset` → `offset.inset_inference_candidates`); `E` **chains into extruding** the inner face (recess / raised panel, two-phase `inset_extrude_faces`, depth has vertex/edge inference); `R` **repeat** last thickness (`HARDFLOW_OT_offset`) |
| `operators/edge_tool.py` | Object-Mode edge tools on shared `_EdgePickModal` (raycast → nearest edge, through modifiers; built on `face_tool._FaceDragModal`): **Edge Bevel** (drag width / `[ ]` segments / `L` whole-loop `edge_loop` → `bevel_object_edges`, `R` repeat, **`S` Smart Bevel** → `geometry.smart_bevel_edges` with `-`/`=` tightness: support loops + n-gon clean, EXPERIMENTAL) + **Loop Cut** (`[ ]`/type cuts → `edge_ring` + `loop_cut`; **drag = slide** a single loop along its ring); live snapshot/restore. Edge work without Edit Mode (`HARDFLOW_OT_edge_bevel`, `HARDFLOW_OT_loop_cut`) |
| `operators/base.py` | Operator-layer (bpy-aware) Command-Pattern base over `core/command.py` (`HardFlowCommand` (adds `redo`), `PlacePointCommand` (undoable click), `MeshSnapshotCommand` (the named `snapshot_mesh`/`restore_mesh` preview→commit→rollback flow, mode-aware via injected `restore`), `BooleanCutCommand` (one `robust_boolean` as an atomic command that raises on failure), `boolean_chain` (a `MacroCommand` of cuts → all-or-nothing boolean chain), `LivePreviewCommand` (the non-destructive live-boolean preview: owns the temp `HF_LivePreview` modifier lifecycle via `execute`/`refresh`/`clear` — NOT a mesh snapshot, so the draw preview never bakes a per-frame boolean)) |
| `operators/hardflow_mode.py` | **HardFlow Mode "Shadowing Engine":** shared `_HardflowModeModal` shell (modal-hijack loop + Ghost-Grid snap chain `_snap_screen` + VIEW/**SURFACE**/X/Y/Z plane cycle (`_surface_basis_at`, aligned to the face under the first click) + **`Tab` verb cycle** (`_cycle_verb`) + per-session `CommandManager` + HUD; verbs dispatched by `self._active_verb`, subclasses only set `_START_VERB`). Verbs: **Knife** (score the drawn footprint onto the active mesh) + **Extrude** (draw a footprint, PgUp/PgDn depth, `build_prism` → new solid). Entered from Ctrl+Shift+X + the Edit pie. One invocation = one atomic Blender undo step (`HARDFLOW_OT_mode_knife`, `HARDFLOW_OT_mode_extrude`) |
| `operators/construction.py` | Starter primitives (cube/plane) + guide line + construction-grid object at the 3D cursor + loft/bridge between two profiles (`HARDFLOW_OT_add_primitive/add_guide/add_grid/loft`) |
| `operators/decals.py` | Decal placement/management/bake/library/trim/atlas + v1.7 create/match/retrim/conform/transfer + editable library (`HARDFLOW_OT_place_decal/select_decal/remove_decal/bake_decal/load_decal_image/library_place/load_trim_sheet/atlas_decals/match_decal/retrim_decal/conform_decal/transfer_decal/create_decal/library_rename/library_delete`) |
| `operators/assets.py` | INSERT placement (auto-scale + insert-grid snap, v1.8) + library + mark + material INSERT + asset-pack export (`HARDFLOW_OT_place_asset/load_asset/asset_library_place/mark_asset/material_insert/export_asset`) |
| `ui/draw.py` | GPU + blf helpers |
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
