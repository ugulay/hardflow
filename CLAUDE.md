# CLAUDE.md — Hardflow

This file exists so that Claude Code approaches the project with the right
context in every session.

## What the project is

Hardflow is an **open-source (GPLv3) hard-surface boolean modeling** toolkit for
Blender 4.2+. The goal: deliver the core workflows of Grid Modeler, Boxcutter,
Hard Ops, DECALmachine, and KitOps for free. **All roadmap features through v1.8
are implemented** — the core boolean/snap/cutter workflows; the full decal
subsystem (placement, PBR material, bake, image library, trim sheets, atlasing,
plus v1.7 create/match/retrim/conform + editable library); the asset/kitbash
system (INSERT placement, boolean INSERTs, .blend library, conform, asset-browser
mark, plus v1.8 auto-scale, insert-grid snap, material INSERTs, KPACK export,
solver fallbacks); the Hard Ops tools (boolean-from-selection, array, radial,
symmetrize, sharpen + presets, dice/panel, edge weights, display toggles,
material helpers, step/taper/knurl greeble); live placement preview; the
SketchUp direct-modeling tools (Push/Pull, Offset, construction grid, cable);
**Edit Mode** for draw/Push-Pull/Offset/snap (v1.3); the Boxcutter-style
**in-draw operations** (knife, inset, array, mirror, bevel-on-cut, in-plane
rotation, stamp/repeat, live grid + depth — v1.4/v1.6); and square/rect pipe
profiles + loft (v1.6). Code is syntax-verified with pure + headless tests; live
Blender verification of the modal tools is still ongoing. Roadmap: `ROADMAP.md`.

## FIRST TASK: smoke test inside Blender

This code **has been written and syntax-verified, but has not yet been run in a
live Blender.** Before developing any feature:

1. Install the addon, enable it, and verify it registers without errors.
2. Select a cube in Object Mode → Ctrl+Shift+D → draw a Box → see the Cut work.
3. Try the pie menu (Alt+Q), bevel, mirror, slice, and make modes one by one.
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
| `core/raycast.py` | Screen↔3D projection + plane (u,v) + surface ray (`screen_to_plane`, `view_direction`, `world_to_plane_uv`, `plane_uv_to_world`, `world_to_screen`, `ray_cast_surface`/`ray_cast_surface_ex` (w/ `ignore` to skip the live preview), `face_edge_tangent` (smart edge-aligned orient), `basis_from_normal`, `closest_axis_distance`) |
| `core/grid.py` | World-scale + angle + scalar snap, shape points, construction grid, 2D rotation (`snap_world`, `snap_scalar`, `world_grid_segments`, `centered_grid_segments`, `snap_angle`, `box_points`, `circle_points`, `ngon_points`, `centroid`, `rotate_2d`, `is_self_intersecting`, `point_in_polygon`, `polygons_overlap` (knife footprint test), `lock_distance` (numeric exact-size entry)) |
| `core/snap.py` | Vertex/edge geometry snap, pure 2D (`nearest_point`, `closest_point_on_segment`, `nearest_on_segments`, `resolve_snap` (nearest-wins disambiguation, vertex priority breaks ties)) |
| `core/snapping.py` | Unified 3D snapping shared by every draw tool (vertex/edge → surface → grid → free) + pipe surface-drape; bpy-data + mathutils, no `bpy.ops`/`gpu`/`blf`; reads the live edit-mesh in Edit Mode (v1.3); delegates picking to `core/snap.py` (`Geo`, `collect_geo`, `geo_snap_3d`, `grid_snap_3d`, `snap_insert_point`, `nearest_surface_point`, `drape_path`) |
| `core/offset.py` | Pure 2D polygon inset/offset math, stdlib only — SketchUp Offset (`signed_area`, `offset_polygon`) |
| `core/geometry.py` | bmesh generation (`build_prism`/`build_prisms` (`apex` = perspective Project taper), `build_face`/`build_faces`, `build_box`/`build_plane`/`build_line` (starter primitives + guide line), `build_pipe`/`build_pipe_mesh`/`profile_points`, `build_loft`, `build_grid_mesh`, `extrude_faces`, `inset_faces`, `knife_polygon` (footprint-restricted via `_knife_footprint_faces`), `bevel_cutter` (chamfer the cutter for bevelled cuts), `estimate_thickness`, `symmetrize_mesh`, `mark_sharp_by_angle`, `dice_mesh`, `set_sharp_edge_weights`, `SHARPEN_PRESETS`, greeble `build_steps`/`build_taper`/`build_knurl`, `cleanup_mesh`) + live-preview snapshot (`snapshot_mesh`, `restore_mesh`, `free_mesh`) + Edit-Mode bridge (v1.3: `flush_edit_mesh`, `restore_edit_mesh`, `edit_extrude_faces`, `edit_inset_faces`, `edit_bevel_edges` (real on-selection edge bevel), `edit_add_face`, `edit_knife_polygon`, `edit_set_edge_weights`, `selected_face_basis`) |
| `core/boolean.py` | boolean + cutter management (`apply_boolean`, `apply_boolean_fallback` (EXACT→FAST), `robust_boolean` (auto-solver + fallback + cutter normal repair + diagnosis), `choose_solver` (health-driven solver pick), `_coerce_solver` (version-safe solver: Manifold→Exact before Blender 4.5), `recalc_normals`, `mesh_health`/`_health_summary`, `add_boolean`, `duplicate_object`, `stash_cutter`, `cutter_collection`) |
| `core/transform.py` | Pure array/radial + cable-sag + dice + fit math, stdlib only (`radial_step_radians`, `radial_angles_deg`, `array_offset_vector`, `mirror_axis_flags`, `cable_points`, `cable_chain`, `dice_coordinates`, `fit_scale`, `adaptive_dimension` (size-scaled bevel/chamfer width), `bevel_segments` (width-scaled segment count)) |
| `core/decal_math.py` | Pure orientation math, no bpy/mathutils (`orientation_basis`, `base_tangent`, `dominant_tangent` (longest-edge alignment), `basis_from_edge`/`basis_from_two_edges` (Grid Modeler grid-on-edges plane), `best_edge_pair` (deterministic longest-edge main + most-perpendicular partner for the 2-edge plane), `rotate_about_axis`) |
| `core/decal_image.py` | Pure decal-library helpers, stdlib only (`scan_library`, `is_image_file`, `aspect_size`) |
| `core/atlas.py` | Pure UV-rect + pixel math for trim sheets + atlasing (`slice_grid`, `cell_rect`, `rect_pixels`, `pack_shelves`, `remap_uv`, `blit_pixels`, `rect_to_uv`, `next_pow2`) |
| `core/decal.py` | Decal build/stick/material (`make_decal`, `make_image_decal`, `build_decal_mesh`, `decal_matrix`, `add_shrinkwrap`, `decal_material`/`image_decal_material` + shared PBR node group `_decal_node_group`/`HF_DecalShader` with base/metallic/roughness/AO/normal/height+depth/emission/alpha, bake helpers `bake_image`/`ensure_material`/`bake_image_node`/`discard_bake_image` (roll back a failed bake), atlas image `atlas_image`, `decal_collection`, `DECAL_TYPES`; v1.7 extras `sample_material`/`match_decal_to_material`/`set_decal_uv_rect`/`conform_trim_decal`/`retarget_decal` (transfer to another surface)/`save_image`) |
| `core/asset_lib.py` | Pure `.blend` kit-library scan, stdlib only (`scan_assets`, `is_asset_file`) |
| `core/asset.py` | INSERT append/orient/bind, bpy-data only (`load_blend_objects`, `asset_matrix`, `place_asset`, `make_asset_cutter`, `bind_cutters`, `flatten_objects`, `conform_asset`, `transfer_shading`, `asset_collection`) + v1.8 KitOps extras (`bound_size`, `surface_feature_size`, `load_blend_materials`, `apply_material`, `write_objects_blend`) |
| `operators/draw_cut.py` | Main modal drawing operator (`HARDFLOW_OT_draw`): cut/slice/make/**join**(add solid, no boolean)/**intersect**/face/**knife** (mode via `Tab`/`Shift+Tab`), per-cut **boolean solver** (Default/Exact/Fast/Manifold), Polyline-Trim **Project/Fixed** extrude orientation (`O`, perspective taper via `_project_apex`), **numeric exact-size entry** (type a dimension -> `_apply_numeric`/`grid.lock_distance`), plane cycling VIEW/SURFACE/**EDGES**(grid on selected edges, longest-edge main via `best_edge_pair`)/X/Y/Z (edge- and face-aligned tangents), `Shift+←/→` in-plane grid rotation (`_apply_spin`), `Z` quick-close / **double-click close**, measurement HUD, live 3D cutter cage, Edit-Mode path (v1.3), and **in-draw ops** (v1.4/v1.6: inset `-/=`, rotate `,/.`, array `A`/axis `D`, mirror `M`, bevel-on-cut `B`, **bevelled cutter `C`**, **orient `O`**, stamp `G`, live grid Ctrl+Wheel, live depth PgUp/Dn) via `_processed_corner_sets` |
| `operators/modifiers.py` | Bevel + mirror + clean + recalc-normals + symmetrize + sharpen (w/ SSharp/CSharp presets) (`HARDFLOW_OT_bevel/mirror/clean/recalc_normals/symmetrize/sharpen`) |
| `operators/hardops.py` | v1.5 Hard Ops parity: dice/panel, edge bevel-weight/crease (Edit), display toggles, random colors, copy material, step/taper/knurl greeble (`HARDFLOW_OT_dice/edge_weight/display_toggle/random_color/copy_material/add_step/add_taper/add_knurl`) |
| `operators/boolean_ops.py` | Boolean from selected objects, active = cutter (`HARDFLOW_OT_boolean`) |
| `operators/array.py` | Linear + radial + along-curve array (`HARDFLOW_OT_array/radial_array/curve_array`) |
| `operators/cutters.py` | Non-destructive cutter management (`HARDFLOW_OT_apply_cutters/select_cutter/remove_cutter`) |
| `operators/pipe.py` | Surface-snapping curve draw: pipe (drapes, F toggles; round/square/rect profile, P cycles — v1.6) + free-hanging sagging cable/rope; live preview (curve or swept mesh); shared `_CurveDraw` modal (`HARDFLOW_OT_pipe/cable`) |
| `operators/push_pull.py` | SketchUp Push/Pull: raycast a face (Object) or selected faces (Edit, v1.3), drag along normal (grid snap + numeric), bmesh extrude w/ live snapshot/restore (`HARDFLOW_OT_push_pull`) |
| `operators/offset.py` | SketchUp Offset: raycast a face (Object) or selected faces (Edit, v1.3), drag to inset, bmesh inset w/ live snapshot/restore (`HARDFLOW_OT_offset`) |
| `operators/construction.py` | Starter primitives (cube/plane) + guide line + construction-grid object at the 3D cursor + loft/bridge between two profiles (`HARDFLOW_OT_add_primitive/add_guide/add_grid/loft`) |
| `operators/decals.py` | Decal placement/management/bake/library/trim/atlas + v1.7 create/match/retrim/conform/transfer + editable library (`HARDFLOW_OT_place_decal/select_decal/remove_decal/bake_decal/load_decal_image/library_place/load_trim_sheet/atlas_decals/match_decal/retrim_decal/conform_decal/transfer_decal/create_decal/library_rename/library_delete`) |
| `operators/assets.py` | INSERT placement (auto-scale + insert-grid snap, v1.8) + library + mark + material INSERT + KPACK export (`HARDFLOW_OT_place_asset/load_asset/asset_library_place/mark_asset/material_insert/export_asset`) |
| `ui/draw.py` | GPU + blf helpers |
| `ui/pie.py` | Categorized pie system: main pie + Build/Boolean/Modify/Curves sub-pies (`HARDFLOW_MT_pie`, `HARDFLOW_MT_pie_build/boolean/modify/curves`); `_draw`/`_open` helpers |
| `ui/menu.py` | 3D-View header dropdown covering every tool incl. Decals/Assets; data-driven `*_ITEMS` tables + submenus (`HARDFLOW_MT_menu`, `HARDFLOW_MT_menu_*`); `register`/`unregister` add the header hook |
| `ui/panel.py` | N-panel: tools, snap settings, **modifier-stack manager** (v1.5), **gizmo toggles** (v1.10), cutter list, greeble + display + material rows (`HARDFLOW_PT_tools/gizmos/snap/modifiers/cutters`) |
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
