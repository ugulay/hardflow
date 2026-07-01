# Changelog

Notable changes in this project. Versioning follows [SemVer](https://semver.org)
logic: minor versions add features, patch versions fix bugs.

## [Unreleased]

### Changed
- **`draw_cut` fully adopts the per-modal command layer.** The main draw operator
  now owns a per-session `CommandManager`: each placement click is a two-child
  `MacroCommand` of `base.PlacePointCommand`s (the screen + world anchor lists
  move as one), so `Backspace` = `undo()` and the shape/plane/stamp reset keys =
  `clear()`. The hand-rolled `append`/`pop` history is gone, and `draw_cut` now
  shares the same command vocabulary as `face_tool` / `hardflow_mode` end to end.
  No user-visible change (Backspace behaves as before). Headless
  `test_draw_placement_journal`.
- **`draw_cut`'s live boolean preview adopts the command layer.** The ad-hoc
  `HF_LivePreview` temp-modifier bookkeeping (`_bool_targets`, `_remove_live_mod`,
  the scene-wide cleanup sweep) is replaced by a new
  `operators/base.LivePreviewCommand` — a *named, non-destructive* command that
  owns the temp-modifier lifecycle (`execute`/`refresh`/`clear`). It deliberately
  does **not** subclass `MeshSnapshotCommand`: the live preview never mutates the
  target mesh (it lets the viewport evaluate a temporary Boolean modifier), so a
  snapshot port would force a per-frame boolean bake. Behaviour and cost are
  unchanged; the preview just joins the shared command vocabulary. Headless
  `test_livepreview_command_lifecycle` + `test_draw_cut_uses_livepreview_command`.

## [1.14.0] — 2026-07-01

### Added
- **Super Modeling Mode — three foundation layers toward the SketchUp-fluidity /
  pro hard-surface pipeline.** All respect the one-directional (ui/ops → core)
  rule and stay pure/headless-testable.
  - **Shadowing Engine.** `operators/hardflow_mode.py` grows a shared
    `_HardflowModeModal` shell — the modal-hijack loop + Ghost-Grid snap chain
    (`core/raycast`+`core/snapping`+`core/grid`) + VIEW/**SURFACE**/X/Y/Z plane
    cycle + per-session Command journal + HUD — that the draw *verbs* subclass,
    mirroring `face_tool._FaceDragModal` / `pipe._CurveDraw`. The knife prototype
    moves onto it and a new **Extrude** verb joins it (`HARDFLOW_OT_mode_extrude`:
    draw a snapped footprint, PageUp/PageDown depth, `build_prism` → new solid).
    The tool owns its own modal loop and calls bmesh directly — it never invokes
    Blender's native modal operators. The **SURFACE** plane (promoted from
    `draw_cut._surface_basis_at`) locks to the face under the first click; **`Tab`**
    switches the active verb (Knife ↔ Extrude) in-session, keeping the points
    placed so far. Entered from a **Ctrl+Shift+X** keymap (rebindable) + an **Edit
    pie** slot, and both verbs are in the header-menu Edit submenu. Headless
    `test_mode_shell_verb_and_plane_cycle`.
  - **Per-modal atomic macro.** `operators/base.py` adds `BooleanCutCommand` (one
    `robust_boolean` as an atomic command that raises on solver failure) and
    `boolean_chain` (a `MacroCommand` of cuts) so a cutter chain commits or rolls
    back all-or-nothing — the fix for "undo crashes in long boolean chains." A
    modal session's edits stay in the Command journal and commit as *one* Blender
    undo step. Headless `test_boolean_chain_command_atomic` (success + rollback).
    - **Adopted in the shipping tools.** The shared `operators/face_tool._FaceDragModal`
      (Push/Pull, Offset, Edge Bevel, Loop Cut) now runs its live preview through a
      per-session `CommandManager` + `MeshSnapshotCommand`: `_begin_edit` snapshots
      + applies, the base `_refresh_preview` re-applies each drag frame via
      `command.reapply`, cancel routes through `undo_all`, commit `clear`s the
      journal → one Blender undo step; each tool supplies `_mutate` (the edit
      *without* the restore) instead of its own `_refresh_preview` (a behaviour-
      preserving rename of the old `_base`/`_committed` flow). Added a public
      `MeshSnapshotCommand.snapshot` accessor for inference capture.
      `draw_cut._apply_destructive` now applies the cutter(s) through an atomic
      `MacroCommand` of `BooleanCutCommand`s, so a multi-target Cut/Make or a Slice
      rolls back cleanly on a mid-chain solver failure (no half-cut target, no
      orphaned slice duplicate) while keeping the cleanup / n-gon-dissolve / solver-
      fallback reporting. Headless `test_facetool_command_adoption_structure`,
      `test_facetool_begin_edit_lifecycle`,
      `test_draw_cut_apply_destructive_atomic_chain`,
      `test_mesh_snapshot_command_snapshot_property`.
  - **Smart Topology (Smart Bevel & Support).** New pure `core/bevel.py`
    (`support_loop_positions` — where holding loops sit for a `width`/`tightness`
    bevel) + `geometry.smart_bevel_edges` (bevel + support/holding loops via
    `_flank_support_loop`, topology-preserving) + `geometry.dissolve_boolean_ngons`
    (triangulate + re-quad the n-gons a boolean/bevel leaves). Object-Mode Edge
    Bevel gains an **`S` Smart** toggle with `-`/`=` tightness (EXPERIMENTAL — exact
    holding-loop placement wants a live cube→Subdivision tuning pass, tracked in
    the manual checklist). Pure tests for the placement math + headless
    `test_smart_bevel_edges` / `test_dissolve_boolean_ngons`.
    - **Wired into the boolean pipeline (opt-in).** A new **Re-quad Cut N-gons**
      preference (`cut_dissolve_ngons`, default off) runs `dissolve_boolean_ngons`
      after a destructive draw Cut/Make/Intersect *and* after **Apply Cutters**, so
      the "auto-clean the n-gons a boolean leaves" flow is one toggle. A
      **Smart Edge Bevel** preference (`smart_bevel_default`) makes Edge Bevel start
      in Smart mode. Both live in N-panel ▸ Cutter Options ▸ Topology. Headless
      `test_boolean_cut_ngon_cleanup_pipeline` (real cut → n-gons → clean) +
      `test_topology_prefs_registered`.

### Fixed
- **Decals didn't conform to curved / multi-face surfaces** — `build_decal_mesh`
  made a single flat quad, so the SHRINKWRAP had only 4 corner verts to project:
  on a curved surface the decal's interior clipped through or floated over the
  curvature. It now builds an NxN grid (preference `decal_resolution`, default 12)
  so the shrinkwrap can bend the decal to the surface; `add_shrinkwrap` also
  projects in both Z directions so verts that start inside a curve snap back flush.
  `set_decal_uv_rect` now maps UVs by normalized position (a grid would have
  collapsed onto corners under the old sign-based map). Headless
  `test_decal_mesh_grid_resolution` + updated decal mesh/uv tests.
- **Asset placement leaked orphan data** — cancelling (or a failed commit of) an
  INSERT placement removed the appended objects but left their mesh / material
  data-blocks behind. `assets._discard_objects` now removes the data too, and the
  as-cutter commit drops its non-mesh helper empties/curves in both destructive
  and non-destructive modes (matching `core/asset.make_asset_cutter`).
- **Material INSERT leaked materials** — `material_insert` appended every material
  from the .blend but only used the first; the rest (and the first, when no mesh
  received it) are now purged instead of orphaned.
- **Create-Decal bake clobbered scene state** — the bake set `cage_extrusion`
  without restoring it (and never touched `max_ray_distance`), and never arranged
  the selected-to-active selection it depends on. It now saves/restores both bake
  settings and arranges the source/destination selection like `bake_decal`.
- **Atlas aborted on one bad image** — `atlas_decals` now skips images whose pixel
  buffer is unreadable (unloaded / zero-size / mismatched) and reports the count,
  instead of crashing the whole operator with a traceback.
- **"Match to Surface" accumulated materials** — re-matching a decal left the
  previous single-user material copy as an orphan; the orphan is now removed
  (shared templates keep their other users and are untouched).
- **Pipe/Cable/Sweep confirm could delete the result** — if the selection
  bookkeeping after promoting the preview raised, cleanup deleted the just-created
  object. The commit is marked final the moment the object is promoted.
- **Offset `R` corrupted an in-progress recess** — repeating the last thickness in
  the EXTRUDE phase silently overwrote the locked offset; `R` is now ignored
  outside the OFFSET phase.
- **Draw tool robustness** — the modal is wrapped so a mid-draw exception cleans up
  (GPU handler + temp `HF_LivePreview` modifiers) instead of stranding them; a
  failed SLICE no longer orphans its spare duplicate half; live-boolean cleanup
  sweeps the scene so no preview modifier survives the tool; an edge-on plane no
  longer stores a `None` draw anchor.
- **Face-drag tools** — `_cleanup` always removes the GPU draw handler even if the
  mesh restore raises.
- **Push/Pull gizmo** — dragging a not-yet-populated handle no longer raises
  `AttributeError` (the group-written slots are initialized in `setup`).
- **Add-on registration** — gizmo / Workspace-Tool registration is guarded so a
  headless or edge-context failure can't strand the rest of the add-on
  half-registered; gizmo unregistration is defensive against a partial register.
- **Geometry guards** — `edit_add_face` rejects a zero-area (collinear) footprint
  and fully cleans up its verts on failure; `build_pipe_mesh` returns `None` when
  no side faces build and adds each end cap independently; the radial draw shapes
  (`circle`/`ngon`/`star`/`arc_points`) return no points for a zero-radius drag
  instead of a coincident cluster.
- **Apply Cutters** warns when a boolean sat below a non-Hardflow modifier (applied
  out of stack order, so the result can differ from the preview).
- `snap_to_candidates` ties now resolve deterministically (first candidate wins).
- **FAST solver fallback was dead on Blender 5.x** — Blender 5.0 renamed the
  Boolean modifier's `FAST` solver to `FLOAT`, so every `FAST` request (the broken-
  mesh fast path + the fallback after EXACT) silently coerced all the way back to
  the slow EXACT solver. `_coerce_solver` now maps `FAST → FLOAT` when FLOAT is the
  available fast solver, restoring the intended fast/fallback behaviour on 5.x while
  staying correct on 4.x (real `FAST`). Headless `test_coerce_solver_fast_to_float`.

### Performance
- **Draw preview no longer rebuilds every frame** — the modal regenerated the live
  cutter cage (a fresh bmesh) and re-evaluated the live-boolean modifier on *every*
  event, mouse-move included. `_update_preview` now skips the rebuild when a cheap
  signature of the build inputs (shape/mode/params + snapped cursor + placed points,
  `draw_cut._preview_signature`) is unchanged, so cursor jitter within one snapped
  grid cell costs nothing. Behaviour-preserving: view changes arrive as
  pass-through events that already bypassed the rebuild, and re-anchored screen
  points change the signature after an orbit/zoom.
- **Pre-cut health check is cached** — the N-panel "Cut may fail" warning rebuilt a
  bmesh (`mesh_health`) on every sidebar redraw. `panel._cached_health_summary`
  memoizes it against the object's vert/poly count (Object Mode), recomputing only
  when the mesh actually changes. Headless `test_panel_health_cache`.
- **Manifold-first solver on clean meshes** — `choose_solver` now starts a cut on
  the much faster MANIFOLD solver (Blender 4.5+) when **both** operands are clean
  and watertight (`non_manifold == 0`, no degenerate / loose geometry), instead of
  EXACT. The cutter is checked too (a non-manifold cutter could otherwise produce a
  silently-wrong Manifold result), guarded by the same vert cap. Accuracy is never
  sacrificed: `robust_boolean` now runs an ordered fallback chain
  (`_fallback_chain`) that escalates Manifold → **EXACT** → FAST, so if Manifold
  rejects the input EXACT still runs before the lossy FAST pass. A health-forced
  FAST start (broken target) is unchanged, and the draw tool no longer mislabels the
  Manifold pick as a "fallback". Solver-version safety stays in `_coerce_solver` /
  the new `_solver_available`. Headless `test_solver_fallback_chain_and_message`,
  `test_choose_solver_cutter_gate` + updated `test_choose_solver_from_health`.

## [1.13.0] — 2026-06-30

Tool-set trim plus a Build/Boolean expansion. The **Greeble** (step/taper/knurl)
and the **Modifier** tool set (bevel, mirror, array, radial, symmetrize, sharpen,
clean, dice) were removed to refocus on the boolean / direct-modeling core; the
**Pipe** and **Cable** curve tools were kept (relocated to a "Curves" N-panel
section). In their place: new build primitives, new boolean draw shapes, a
Sweep / Follow-Me tool, and a live boolean preview. Pure logic is unit-tested
(`64/64`); the new bpy paths add headless coverage (`84/84`, live-verified in
Blender 5.1.2). Modal/interactive feel is in
[tests/manual_checklist.md](tests/manual_checklist.md) §18.

### Added
- **Build primitives** — Cylinder / Cone / Sphere / Tube join Cube / Plane on the
  `HARDFLOW_OT_add_primitive` operator and the N-panel Build section
  (`core/geometry.build_cylinder` / `build_cone` / `build_uv_sphere` /
  `build_tube`; radius / height / segments / inner-radius params).
- **Boolean draw shapes** — **Slot** (stadium), **Star** (n-pointed), and **Arc**
  (filled pie sector) join Box / Circle / Polygon / N-gon in the draw tool (keys
  `T` / `Y` / `U`; `[ ]` sets the segment / point count, or the ARC sweep angle).
  Pure math `core/grid.slot_points` / `star_points` / `arc_points`.
- **Surfaced boolean modes** — Intersect / Join / Knife are now first-class
  buttons in the N-panel Boolean Draw section (alongside Cut / Slice / Make), plus
  a Slot / Star / Arc shape row, and Slot/Star/Arc-cut entries in the header menu.
- **Sweep / Follow-Me** — `HARDFLOW_OT_sweep` (`operators/pipe.py`, on the shared
  `_CurveDraw` base): draw a path and sweep an **L / U / T / I / box** structural
  cross-section along it (`P` cycles the profile). New
  `core/geometry.profile_points` sections; `_CurveDraw._PROFILE_CYCLE`.
- **Live boolean preview** — toggle `J` while drawing a Cut / Make / Intersect to
  see the **actual boolean result** on the target (a temporary `HF_LivePreview`
  modifier evaluated by the viewport, stripped before the real cut and on cancel;
  skipped on heavy targets). Preference `live_boolean_preview`
  (`draw_cut._sync_live_boolean` / `_clear_live_boolean`).
- **Cutter Options** — an N-panel section (`HARDFLOW_PT_cutter_options`) +
  preferences (`draw_inset` / `draw_bevel_cut` / `draw_cutter_bevel` /
  `draw_array_count` / `draw_array_axis`) that preset the next boolean draw's
  inset / bevel-on-cut / bevelled-cutter / array, then live-tweak with the modal
  keys.

### Removed
- The **Greeble** generators (`HARDFLOW_OT_add_step` / `add_taper` / `add_knurl`,
  `core/geometry.build_steps` / `build_taper` / `build_knurl`).
- The **Modifier** tool set: `HARDFLOW_OT_bevel`, `HARDFLOW_OT_mirror`,
  `HARDFLOW_OT_clean`, `HARDFLOW_OT_symmetrize`, `HARDFLOW_OT_sharpen`,
  `HARDFLOW_OT_array`, `HARDFLOW_OT_radial_array`, `HARDFLOW_OT_curve_array`,
  `HARDFLOW_OT_dice` — and the now-dead core helpers (`symmetrize_mesh`,
  `mark_sharp_by_angle`, `set_sharp_edge_weights`, `SHARPEN_PRESETS`,
  `edit_bevel_edges`, `dice_mesh`, `transform.bevel_segments`). `operators/
  modifiers.py` and `operators/array.py` were deleted; `recalc_normals` moved to
  `operators/hardops.py`. Object-Mode **Edge Bevel** / **Loop Cut** and Blender's
  own modifiers cover the gap.

### Changed
- N-panel, header menu, and pie restructured: the "Modify" sub-pie/menu and the
  "Greeble" menu are gone; a "Curves" panel section hosts Pipe / Cable / Sweep,
  and a "Display & Mesh" menu hosts the surviving edge-weight / display / material
  / recalc-normals helpers.

### Fixed
- **SURFACE-plane box looked rotated on angled faces** — the on-surface
  construction grid aligned to a face's single *longest* edge, so on
  non-rectangular (e.g. boolean-cut parallelogram) faces the box sat at an odd
  angle to the other edges. It now aligns to the face edge **nearest the click**
  (`raycast.face_edge_tangent` `near_point`), so the box follows the edge you
  start on. Verified in Blender 5.1.2 (axis aligns to the clicked edge within
  ~0.02°); headless `test_face_edge_tangent_near_point`. Decal / asset placement
  keep the longest-edge alignment.

## [1.11.0] — 2026-06-30

Direct-modeling depth: the direct-modeling tools were consolidated onto a shared
modal base and grown to parity (copy/repeat/inference, recess chaining), two new
Object-Mode edge tools landed (Edge Bevel + Loop Cut), the face tools now pick
through generative modifiers, and the draw tool gained Blender's **Polyline Trim**
parity. Pure logic is unit-tested (`61/61`); the new bpy paths add headless
coverage (project taper, keep/clean extrude, inset-extrude, edge pick/loop/ring +
bevel, loop cut, modifier-pick). The modal/interactive feel is checked via
[tests/manual_checklist.md](tests/manual_checklist.md) §3/§4/§15/§16/§17.

### Added
- **Polyline Trim parity** in the draw tool — **double-click** closes a polyline
  (native finish); a **Join** mode adds the drawn shape as a separate solid (no
  boolean); a per-cut **Solver** (Default / Exact / Fast / **Manifold**, the last
  version-safe via `core/boolean._coerce_solver`); and a **Project / Fixed**
  extrude orientation (`O`) that tapers the cut along the camera rays in
  perspective (`core/geometry.build_prism(s)` `apex`). "Polyline Trim / Add / Join"
  entries in the Boolean menu + pie.
- **Push/Pull — Copy & Repeat & inference** — `C` keeps the starting face and
  stacks a new volume on it (Ctrl push/pull); `R` repeats the last
  distance; with snap on, the drag **infers** to a real vertex / edge-midpoint
  height before falling back to the grid (`core/snap.snap_to_candidates`).
- **Offset — Repeat & recess/panel chain** — `R` repeats the last thickness; `E`
  locks the inset and continues into **extruding the inner face** along its normal
  (recess for `-`, raised panel for `+`), one bmesh pass
  (`core/geometry.inset_extrude_faces`); the depth infers too.
- **Edge Bevel (Object Mode)** — `HARDFLOW_OT_edge_bevel`: raycast-pick the nearest
  edge, drag a width, `[ ]` segments, `L` to bevel the whole connected **edge
  loop** — chamfer an edge without entering Edit Mode
  (`core/geometry.nearest_edge_on_face` / `edge_loop` / `bevel_object_edges`).
- **Loop Cut (Object Mode)** — `HARDFLOW_OT_loop_cut`: pick an edge, insert an edge
  loop by subdividing its ring; `[ ]` / type sets how many loops
  (`core/geometry.edge_ring` / `loop_cut`).
- **Pick through generative modifiers** — Push/Pull, Offset and the edge tools map
  an evaluated-mesh raycast hit (subdivision / array / mirror, etc.) back to the
  nearest base face (`core/geometry.nearest_face_to_point`), so they work on
  modified objects (exact for deform-only, best-effort otherwise).

### Changed
- **Shared modal base** — Push/Pull and Offset (and the new edge tools) are built
  on one mixin, `operators/face_tool._FaceDragModal`, that owns the
  hover-pick / lock / drag / live snapshot-preview / numeric / snap+inference / HUD
  / cancel shell (~300 lines of duplication removed; a fix/feature lands once). The
  two edge tools further share `operators/edge_tool._EdgePickModal`. Mirrors the
  existing `operators/pipe._CurveDraw` base.

### Fixed
- **Object-Mode Push/Pull left an interior face** — `core/geometry.extrude_faces`
  now drops the source face by default (clean, manifold extrude, matching Edit
  Mode); `keep_original=True` is the opt-in for the new Copy behavior.

## [1.10.0] — 2026-06-30

A code-review hardening pass over the decal/asset subsystems plus a feature
gap pass over common hard-surface workflows: numeric
exact-size drawing, an Intersect draw mode, a bevelled cutter, mirror across the
3D cursor / active object, array-along-curve, and decal transfer between surfaces.
Pure logic is unit-tested (`60/60`); every new bpy path is verified headless in
Blender 5.1.2 (`77/77`).

### Added
- **Numeric size entry while drawing** — after placing the first point, type an
  exact dimension (radius / extent / segment length, in the plane's metres) to
  lock the shape's size along the cursor direction; the HUD shows
  `size … m (typing)`, `Backspace` edits, `.`/numpad-`.` is the decimal, and
  moving the mouse rotates the fixed-size shape around the anchor (precision
  entry, `core/grid.lock_distance`). The boolean mode now
  cycles with **`Tab` / `Shift+Tab`** (the number row types the size instead).
- **Intersect draw mode** — the draw modal gains an INTERSECT mode (keep only the
  part of the object inside the drawn volume), reached via `Tab` mode-cycle or
  the header Boolean menu.
- **Bevelled cutter** — `C` in the draw modal chamfers the cutter itself, so a
  CUT leaves bevelled recess walls (`core/geometry.bevel_cutter`), distinct from
  `B` bevel-on-cut which chamfers the target's cut edge (bevelled cut).
- **Array along a curve** — `HARDFLOW_OT_curve_array` arrays the active mesh along
  a selected curve (Array fit-curve + Curve deform) so copies follow the path;
  header Modify menu.
- **Transfer decal to another surface** — `HARDFLOW_OT_transfer_decal` moves the
  selected decal(s) onto the active mesh, re-pointing their shrinkwrap and
  re-parenting while preserving world pose (`core/decal.retarget_decal`); Decals
  menu (decal transfer).

### Changed
- **Mirror across the 3D cursor or active object** — `HARDFLOW_OT_mirror` gains a
  "Mirror Across" option (Self / 3D Cursor / Active Object): mirror the selected
  meshes across the active object, or across an empty at the 3D cursor, not only
  the object's own origin.
- **Deterministic main edge for the 2-edge grid plane** — the `EDGES` construction
  plane picked edges by arbitrary bmesh order, so which selected edge became the
  grid's main axis was unpredictable. It now takes the longest selected edge as the
  main axis and its most-perpendicular partner for the plane
  (`core/decal_math.best_edge_pair`, `operators/draw_cut._capture_edges_basis`);
  parallel selections degrade cleanly to a single-edge plane. The manual
  `Ctrl+Click` main-edge override still awaits the modal edge-pick UX.

### Fixed
- **Failed bake no longer pollutes the target material** — a Cycles bake that
  raised (in `HARDFLOW_OT_bake_decal` / `HARDFLOW_OT_create_decal`) left an orphan
  image plus a dangling Image Texture node wired into the target. The error path
  now rolls back exactly what that call created via `core/decal.discard_bake_image`
  (guarded by `image.users == 0`, so a re-bake never deletes a prior good result).
- **Knife footprint is overlap-accurate** — `_knife_footprint_faces` kept only
  faces whose center sat inside the drawn loop (or that held a loop corner) and
  fell back to slicing *every* face when none matched, so a thin score crossing a
  large face sliced the whole mesh. It now uses a full polygon-overlap test
  (vertex-in-either + edge crossings, `core/grid.polygons_overlap`).
- **INSERT export / decal save can't escape the library folder** — a user-typed
  name now passes through `core/decal_image.safe_filename` (strips path separators
  and characters illegal on common filesystems); `HARDFLOW_OT_export_asset` also
  warns before overwriting an existing `.blend` and reports Overwrote vs Exported.
- **Place wrappers report cancellation** — the decal/asset `_invoke_place` helpers
  returned `{'FINISHED'}` even when the spawned modal cancelled immediately (no
  viewport / bad args); they now propagate `{'CANCELLED'}`.
- **Material match writes the active slot** — `core/decal.match_decal_to_material`
  assigned `materials[0]`, wrong when the decal's material is not slot 0; it now
  replaces the single-user copy via `active_material`.
- **`transfer_shading` guards non-mesh targets** — `core/asset.transfer_shading`
  early-returns instead of dereferencing `target.data.polygons` on a non-mesh.

## [1.9.0] — 2026-06-30

Tool smartness + surface-modeling depth. The tools now
reason about the geometry (self-healing booleans, adaptive sizing, smart snapping
and orientation), and the on-surface drawing workflow gains a grid you can lay on
selected edges, rotate freely, and draw connected geometry on. Pure logic is
unit-tested (`56/56`); bpy paths have headless coverage; the modal/interactive
behaviour still awaits a live-Blender pass.

### Added (precision-draw)
- **Rotate the grid plane** — `Shift + ←/→` spins the construction grid's axes
  around its normal in `angle_step` increments while drawing (the plane normal and
  origin stay put), so you can align the grid freely on any plane. Plain `←/→`
  still cycles the plane type.
- **Grid plane on selected edges** — entering the draw tool in Edit Mode with
  edge(s) selected lays the construction grid on that selection (one edge → plane
  along the edge + its face normal; two edges → the plane they span), cycled via
  the new `EDGES` plane in `< >` (`core/decal_math.basis_from_edge`/
  `basis_from_two_edges`, `operators/draw_cut._capture_edges_basis`). Orient your
  grid by any direction / select 2 edges.
- **Connected faces** — `core/geometry.edit_add_face` now welds the drawn face's
  vertices onto coincident existing ones, so created faces connect to the
  surrounding mesh instead of floating as a detached island.
- **`Z` quick-close** — `Z` closes and commits the in-progress polygon
  (quick-close), alongside Enter.
- **Construction guide lines** — `HARDFLOW_OT_add_guide` drops a snappable wire
  guide line at the 3D cursor along X/Y/Z (`core/geometry.build_line`), the
  "construction lines" reference. N-panel Build row.
- **Line-width preference** — the drawn shape outline thickness is now a
  preference (`line_width`), scaled by Blender's UI scale.

### Added (surface-tool review)
- **Smart edge-aligned orientation** — drawing on a surface and placing an INSERT
  now align to the hit face's dominant (longest) edge, so cuts and greeble line up
  with existing panel lines instead of an arbitrary world/view axis
  (`core/decal_math.dominant_tangent`, `core/raycast.face_edge_tangent`,
  `ray_cast_surface_ex`). Falls back to the view-up tangent when no edge is found.
- **Starter primitives** — `HARDFLOW_OT_add_primitive` drops a Cube or Plane at
  the 3D cursor (`core/geometry.build_box`/`build_plane`), so the direct-modeling
  tools have a mesh to act on without leaving Hardflow. N-panel Build row.
- **Edit-Mode edge bevel** — the Bevel tool now does a real on-selection edge
  bevel when run in Edit Mode with edges selected (`core/geometry.edit_bevel_edges`,
  `bmesh.ops.bevel`), instead of only adding a whole-object Bevel modifier.
- **Auto bevel segment count** — an adaptive bevel now scales its segment count to
  the chamfer width (`core/transform.bevel_segments`), so a wide bevel stays smooth
  instead of faceted; manual width-drag or segment-wheel turns the auto off.
- **Polygon draw button** — the Build row exposes the freeform Polygon (POLY +
  FACE) draw tool alongside Rectangle.

### Fixed (surface-tool review)
- **Knife no longer slices the whole object** — `core/geometry.knife_polygon` /
  `edit_knife_polygon` bisected the entire mesh along each loop edge's *infinite*
  plane, so a small score on one face cut lines clear across the model. The score
  is now restricted to the faces under the drawn footprint
  (`core/grid.point_in_polygon` + `_knife_footprint_faces`).
- **Decals/assets no longer stick to their own preview** — `ray_cast_surface`
  gained an `ignore` set; the place modals exclude the live preview object that
  hovers under the cursor, so the ray lands on the real target surface.
- **Decal orientation no longer pops on curved surfaces** — `decal_math.
  orientation_basis` now swaps in a stable surface tangent when the roll tangent
  is near-parallel to the normal, instead of normalizing a tiny unstable residual.
- **On-surface draw grid aligns to the view** — the SURFACE construction plane
  derives its tangent from the view up, so the snap lattice/measure axes match
  how you look at an angled face instead of reading as world-tilted.

### Changed (surface-tool review)
- **Bevel drag scales to object size** — the modal width drag was a fixed
  metres-per-pixel constant (unusable on very large/small objects); it now scales
  to the object's dimensions.
- **Adaptive decal hover offset** — the decal surface gap scales to the target's
  size (`core/decal.adaptive_decal_offset`); the Decal Offset preference now
  defaults to `0` meaning "auto", preventing z-fighting on large meshes and
  visible gaps on small ones.

### Added
- **Auto-solver selection** — `core/boolean.choose_solver` reads the target's
  health and starts a cut with the FAST solver when the target is too broken for
  EXACT to ever succeed, skipping the slow doomed EXACT pass (clean targets keep
  EXACT; guarded by a vertex cap so the scan stays cheap). `robust_boolean` still
  falls back, so this only reorders attempts.
- **Robust, self-diagnosing booleans** — a new `core/boolean.robust_boolean`
  escalation path (auto-solver → FAST → recalculate the cutter's normals → FAST)
  backs every destructive cut: the draw tool (`operators/draw_cut.py`), the
  selected-objects boolean (`operators/boolean_ops.py`), the cutter bake
  (`operators/cutters.py`), and boolean INSERTs (`core/asset.bind_cutters`). When
  a cut still fails it reports *why* via `mesh_health` (non-manifold / zero-area /
  loose geometry) instead of failing silently or with a bare error.
- **Pre-cut health warning** — the Hardflow N-panel flags an active mesh with
  boolean-breaking geometry before you draw and offers a one-click fix
  (`HARDFLOW_OT_recalc_normals`, `ui/panel.py`); capped to light meshes to keep
  the sidebar responsive.
- **Adaptive bevel / chamfer width** — the smart bevel and the in-draw
  bevel-on-cut now scale their width to the active object's size by default
  (`core/transform.adaptive_dimension`), so a chamfer reads the same on a 5 cm
  bracket and a 50 m hull instead of being invisible or enormous. The bevel's
  "Adaptive Width" toggle turns off automatically once you drag to set a width
  manually.

### Fixed
- **Snap disambiguation** — geometry snap (vertex / edge-midpoint / on-edge) now
  locks to the target *closest to the cursor*, with vertex precedence only
  breaking near-ties (`core/snap.resolve_snap`). Previously a vertex anywhere
  within the pixel threshold hijacked the snap even when an edge was far closer;
  fixed in both the draw tool and the shared 3D snap path used by pipe /
  Push-Pull / Offset (`core/snapping.geo_snap_3d`).
- The main draw-cut and selected-boolean paths previously called the bare
  EXACT-only `apply_boolean` with no fallback — the solver fallback added in v1.8
  only covered INSERTs. They now share the robust path.
- Stale docs: `ROADMAP.md` listed surface-aligned grid plane and Edit Mode as
  open limitations though both already shipped (SURFACE plane / v1.3).

## [1.8.0] — 2026-06-29

Asset / kitbash system depth: smart placement and author-side
packaging. Pure logic is unit-tested without Blender (`48/48` passing); the
bpy-dependent paths have headless coverage and still await a live-Blender smoke
test.

### Added
- **Auto / smart scale** — scale an INSERT to the target's local feature size on
  placement (raycast footprint → fit) instead of only manual wheel scale;
  `core/asset.py bound_size`/`surface_feature_size`, `core/transform.fit_scale`.
- **Material INSERTs** — apply a material-only INSERT from a `.blend` to the
  target (`HARDFLOW_OT_material_insert`, `core/asset.load_blend_materials`/
  `apply_material`).
- **Asset-pack export** — mark a selection as an INSERT and write it to a
  `.blend` in the asset library with a generated preview
  (`HARDFLOW_OT_export_asset`, `core/asset.write_objects_blend`).
- **Insert-grid / factory snapping** — snap repeated INSERTs to a regular grid or
  to existing insert anchors (`core/snapping.snap_insert_point`).
- **Boolean-solver fallbacks** — when an insert cutter fails the EXACT solver,
  retry FAST (`core/boolean.apply_boolean_fallback`).

## [1.7.0] — 2026-06-29

Decal subsystem depth: decal authoring and management beyond placement.

### Added
- **Decal creation pipeline** — bake a decal (normal/height/alpha) out of
  high-poly source geometry into the library (`HARDFLOW_OT_create_decal`).
- **Material matching** — match a placed decal's blend to the target's active
  material (`HARDFLOW_OT_match_decal`, `core/decal.sample_material`/
  `match_decal_to_material`).
- **Interactive trim-UV editor** — adjust which trim cell a placed decal uses
  after placement (`HARDFLOW_OT_retrim_decal`, `core/decal.set_decal_uv_rect`).
- **Auto-cut decal to surface** — project + trim a decal that crosses a cut/edge
  so it doesn't float over gaps (`HARDFLOW_OT_conform_decal`,
  `core/decal.conform_trim_decal`).
- **Editable decal library** — rename / delete / re-export library entries from
  the N-panel (`HARDFLOW_OT_library_rename`/`library_delete`, `core/decal.save_image`).

## [1.6.0] — 2026-06-29

Precision-draw extras and pipe profiles.

### Added
- **Live grid density in-modal** — adjust grid spacing during the draw with
  Ctrl+Wheel, with an on-screen grid widget (`operators/draw_cut.py`, `ui/draw.py`).
- **Live thickness / depth drag** — drag the cutter/extrude depth during the draw
  with a measurement readout (PgUp/PgDn).
- **Loft / bridge between two profiles** — bridge two drawn shapes into a solid
  (`HARDFLOW_OT_loft`, `core/geometry.build_loft`).
- **Square / rectangular pipe cross-section** — `core/geometry.build_pipe` gained
  a profile arg (round / square / rect), cycled with `P` while drawing.

## [1.5.0] — 2026-06-29

Modifier & mesh helpers: modifier-stack management, dice/greeble, and mesh
helpers, in a new `operators/hardops.py`.

### Added
- **Modifier-stack manager** — an N-panel section listing the active object's
  modifiers with move / toggle / apply / remove (`ui/panel.py`).
- **Boolean dice / panel** — grid-slice an object into N pieces along axes
  (`HARDFLOW_OT_dice`, `core/geometry.dice_mesh`, `core/transform.dice_coordinates`).
- **Sharpen presets (tiered)** — preset tiers of bevel-weight + crease +
  WN (`core/geometry.SHARPEN_PRESETS`).
- **Edge bevel-weight / crease** — set/clear weight + crease on selected edges in
  Edit Mode (`HARDFLOW_OT_edge_weight`).
- **Mesh display toggles** — wireframe / sharp-edge / cutter-visibility viewport
  toggles (`HARDFLOW_OT_display_toggle`).
- **Material / viewport helpers** — random viewport colors, copy the active
  material to selection (`HARDFLOW_OT_random_color`/`copy_material`).
- **Step / taper / knurl greeble** — parametric detail generators
  (`HARDFLOW_OT_add_step`/`add_taper`/`add_knurl`, `core/geometry.build_steps`/
  `build_taper`/`build_knurl`).

## [1.4.0] — 2026-06-29

In-draw operations: modify the cut *while drawing*. All
hang off the `operators/draw_cut.py` modal via `_processed_corner_sets`.

### Added
- **Knife / zero-depth cut** — a mode (key `5`) that scores the surface without
  extruding (`core/geometry.knife_polygon`).
- **Inset / extract cut** — offset the drawn loop inward/outward before commit
  (`-` / `=`, reuses `core/offset.offset_polygon`).
- **Array during draw** — stamp the in-progress cutter N times along an axis
  (`A` count / `D` axis, `core/transform.array_offset_vector`).
- **Mirror during draw** — live mirror of the cutter across a world axis (`M`,
  `core/transform.mirror_axis_flags`).
- **Bevel-on-cut** — optionally add an angle-limited bevel to the cut edge at
  commit (`B`).
- **In-plane shape rotation** — rotate the drawn shape within its plane (`,` /
  `.`, `core/grid.rotate_2d`), live angle in the HUD.
- **Repeat / stamp last shape** — re-place the previous shape + size with one key
  (`G`).

## [1.3.0] — 2026-06-29

Edit Mode foundation — the biggest single lever, unlocking edit-draw and precise
loops. A `core/geometry.py` bmesh edit-mesh bridge keeps `core` free of `bpy.ops`
while the operator owns the mode.

### Added
- **bmesh edit-mesh bridge** — read/write the active edit-mesh via
  `bmesh.from_edit_mesh` / `update_edit_mesh` (`core/geometry.py` `flush_edit_mesh`,
  `restore_edit_mesh`, `edit_extrude_faces`, `edit_inset_faces`, `edit_add_face`,
  `edit_knife_polygon`, `edit_set_edge_weights`, `selected_face_basis`).
- **Draw cut into edit mesh** — `operators/draw_cut.py` gains an Edit Mode path:
  the drawn shape becomes geometry knifed/inset into the active mesh, no separate
  cutter object.
- **Push/Pull & Offset in Edit Mode** — `operators/push_pull.py` /
  `operators/offset.py` operate on the selected face(s) of the edit-mesh directly.
- **Edit-mode aware snapping** — `core/snapping.collect_geo` reads the live,
  unapplied edit-mesh so vertex/edge snap works mid-edit.

## [1.2.0] — 2026-06-29

The direct-modeling milestone: drag faces in/out (Push/Pull),
inset face borders (Offset), and drop a construction-grid reference object to
model against. Pure logic is unit-tested without Blender (`44/44` passing); the
bpy-dependent paths have headless coverage and still await a live-Blender smoke
test.

### Added
- **Push/Pull** — `HARDFLOW_OT_push_pull` (`operators/push_pull.py`):
  raycast a face, lock it, then drag along its normal to extrude in or out with
  world-grid snap and numeric entry; bmesh extrude, no `bpy.ops`. Reuses
  `core/raycast.py`, `core/grid.py`, and `core/geometry.py`.
- **Offset** — `HARDFLOW_OT_offset` (`operators/offset.py`): raycast a
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
  outline, so you see exactly what you'll get before clicking (the decal / asset
  placement flow).
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

The v1.0 milestone: the asset/kitbash system lands and the mesh
toolset is rounded out (boolean-from-selection, array, radial array,
symmetrize, sharpen). Pure logic is unit-tested without Blender; the
bpy-dependent paths have headless coverage and still await a live-Blender smoke
test.

### Added
- **Asset / kitbash system (v1.0)** — a new subsystem for placing
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
- **Boolean from selection** — `HARDFLOW_OT_boolean`: boolean the
  selected meshes using the active object as the cutter (Difference / Union /
  Intersect / Slice), honouring the non-destructive preference. Reuses
  `core/boolean.py`; no drawing required.
- **Array** — `HARDFLOW_OT_array`: a linear Array modifier along a
  world axis, relative or constant offset (`core/transform.py
  array_offset_vector`, tested).
- **Radial array** — `HARDFLOW_OT_radial_array`: an Array modifier
  driven by a rotated offset Empty parented at the 3D cursor; `count` copies
  evenly around an axis. Pure angle math in `core/transform.py
  radial_step_radians` / `radial_angles_deg` (tested).
- **Symmetrize** — `HARDFLOW_OT_symmetrize` /
  `core/geometry.symmetrize_mesh`: mirror one half of the mesh onto the other
  across an object-local axis (bmesh `symmetrize`, no `bpy.ops`).
- **Sharpen** — `HARDFLOW_OT_sharpen` /
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
- **Decals (v0.7 placement core)** — a new decal subsystem. Stick a
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
- **Clean operator** — remove doubles + coplanar merge + delete loose (mesh
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
- **ROADMAP** — added a decal subsystem (v0.7–v0.9).

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
