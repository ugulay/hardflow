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
`core/atlas.py`); and the **v1.18 Heightmap decals** — an image decal can carry a
**dedicated grayscale height map** (`decal_height_image`) that drives depth
independently of the albedo, feeding both the POM UV shift and a new normal-relief
**Bump** (`decal_bump_strength`, `_wire_height_bump`); an **Invert Height** toggle
flips the polarity (pinned in the pure `core/parallax.surface_depth`), with a
`HARDFLOW_OT_load_height_map` loader + an N-panel "Depth (Image Decals)" section;
and the **v1.20 Competitive Edge** — radial (bolt-circle) in-draw array, the
**VENT/grill** draw shape, and **Panel Lines** from selected edges (groove /
weld bead), described below.
Code is syntax-verified with pure +
headless tests (129 pure + 138 headless, run live against a standalone `bpy`
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
support loops and clean boolean n-gons (Smart Bevel's holding-loop placement is
now **validated** against a live Catmull-Clark Subdivision pass — Blender 5.1.2,
headless, cross-section circle fit — the loop pins the flanking flat near the
bevel and the subdivided fillet stays crisp at radius ≈ the bevel width; the `S`
toggle is the opt-in). Design + status: `docs/hardflow_mode_plan.md`,
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

**UX/UI Overhaul.** A four-phase pass (each its own commit) taking the interface
to parity with the code, keeping the one-directional rule: (P0) **unify the
premium viewport overlay** — the framed HUD header, bottom shortcut bar,
alignment guides and ring snap marker were wired into only Draw Cut + HardFlow
Mode; now every modal tool has them, mostly via the shared bases
(`face_tool._FaceDragModal` gains `_hud_title` + a `_shortcut_chips`/`_tool_chips`
hook + an inference snap marker; `pipe._CurveDraw` gains the title + guides + bar;
the new pure `ui/draw.draw_snap_marker` is the one shared snap hint). (P1) **group
the settings** — `preferences.draw` is seven foldable, icon-headed boxed sections
(the ~60-prop wall, via `_section` + `ui_show_*` collapse bools; heavy sections
start folded), and the N-panel snap sub-panel is boxed groups + a Grid/Vertex/
Surface toggle row. (P2) **onboarding** — a dismissible **Quick Start** card
(`show_quickstart` pref) + a **Help & Shortcuts** cheat-sheet sub-panel. (P3)
**collapsible tool sections** — Build/Edit/Curves/Display are foldable
`bl_parent_id` sub-panels (Boolean stays the always-visible hero). GUI verification
tracked in `tests/manual_checklist.md` (Module 2 + the P0–P3 items).

**UX Tracks 1–4.** A follow-up pass (each its own commit) closing the remaining
native-feel gaps, still one-directional: (T1) **native-feel HUD** — `ui/draw.py`
multiplies every HUD / shortcut-bar / snap-marker size by
`preferences.system.ui_scale` (constant physical size on hiDPI) and pulls
background/text/border from the active theme (`_theme_hud_colors`/
`_theme_bar_colors`, hardcoded palette kept as the headless fallback; active-key
glyph via `_contrast_text`); new `draw_cursor_label` shows the live size/distance
in a pill **at the cursor** (Draw Cut + the shared `face_tool._cursor_label` hook →
Push/Pull distance, Offset thickness/depth); `draw_shortcut_bar` gains an `accent`
arg the tools pass. (T2) **status bar + F9 redo** — every modal tool writes a
native `workspace.status_text_set` hint on invoke and clears it on cleanup (shared
`face_tool._set_status` covers the four face-drag tools; Draw Cut, Pipe/Cable/Sweep,
HardFlow Mode add their own); **Push/Pull + Offset gain real bpy properties +
`execute()` + a redo `draw()`** so "Adjust Last Operation" (F9) re-applies
non-modally and the tools are scriptable (`EXEC_DEFAULT`) — the interactive
`invoke()` modal path is unchanged. (T3) **panel** — a persistent
`Scene.hardflow_draw_mode` EnumProperty (registered by `ui/panel.register()`) drives
a **Mode dropdown + hero Draw button + 3×2 shape grid** so every operation × shape
is one click (was CUT-only shapes / BOX-only modes); a "Boolean & Edit need an
active mesh" hint explains the poll-greyed buttons. (T4) **i18n** — new
`translations.py` registers a `bpy.app.translations` **tr_TR** catalog (~70 UI
strings; guarded double-register). Custom brand icons were intentionally **not**
faked — they need real artwork (wire via the decal library's `bpy.utils.previews`
once assets exist). Tests: +5 headless (push/pull + offset execute, draw-mode Scene
prop, translations catalog); GUI items in `tests/manual_checklist.md` §0b.

**Competitive Edge (v1.20).** A competitive-gap pass shipping the features the
paid incumbents are bought for, still one-directional (decision logic in pure
core): (1) **Radial (bolt-circle) array in-draw** — `D`'s axis cycle gains a
RADIAL stop that spins the array copies about the construction-plane / grid
origin (`H` re-anchors the pivot) in plane (u, v) space via the pure
`grid.radial_sets`; works with every shape, mode, mirror and the live preview
(Fluent-parity, BoxCutter has no radial). (2) **VENT/grill draw shape** (key
`I`) — the drawn rectangle expands into N parallel louvre slots via the pure
`grid.vent_slats` (pitch chosen so border ribs equal the interior ribs; count
from `[ ]`, open fraction from the `draw_vent_ratio` pref); the expansion rides
the multi-prism cutter path so all modes / arrays / mirror / preview work
unchanged — enabled by `_processed_corner_sets` now processing a LIST of uv
outlines (Fluent Power Trip's marquee feature, free). (3) **Panel Lines from
edge selection** — `HARDFLOW_OT_panel_line` (Edit Mode): selected edges are
ordered into chains by the pure `transform.order_edge_paths` (open strips,
closed loops, T/X junctions split cleanly), each chain swept into a solid tube
(`build_pipe_mesh(closed=)` seam-bridging + `round_profile`) and booleaned —
GROOVE recesses a seam, BEAD raises a weld line; F9-redoable, and
Non-Destructive stashes the swept line as a live HF cutter (DecalMachine's
signature workflow with real geometry). Tests: +5 pure / +3 headless.

## Agent role

Claude Code works on Hardflow as a **product engineer for competitive
differentiation**: the mission is not parity with the paid incumbents
(BoxCutter, HardOps, Fluent, DecalMachine, MeshMachine, KIT OPS) but beating
them — SketchUp-grade fluidity, precision snapping, and free/GPLv3 as the
wedge. Concretely, every session:

1. **Guard the architecture** — one-directional (ui/ops → core); a new feature
   is a pure `core/` function + a thin operator, with pure + headless tests.
   Both suites must be green before a release commit.
2. **Verify live when it matters** — the local Blender 5.1.2 runs the headless
   suite (`blender --background --python tests/test_blender.py`); modal /
   viewport interactions get an entry in `tests/manual_checklist.md`.
3. **Ship competitive edges, not checklists** — prefer features that close a
   gap the incumbents charge for (vents, radial arrays, panel lines) or that
   nobody has (Cut-to-Trim, trim-sheet editor, heightmap POM decals). One
   feature = one commit on `main`, documented in CLAUDE.md + ROADMAP.md.

## Verification status

The add-on **is live-verified**: registered, drawn and cut in Blender 5.1.2
(2026-07), with the full pure suite (`python tests/test_core.py`) and headless
suite green. The once-suspect spots (`temp_override` + `modifier_apply` in
`core/boolean.py`, the projection math in `operators/draw_cut.py`) are covered
by the headless suite. What still needs a human: the modal/viewport
interactions listed in `tests/manual_checklist.md`.

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
| `translations.py` | UI localization: a `bpy.app.translations` **tr_TR** catalog (`TRANSLATIONS`, ~70 strings) with guarded `register`/`unregister` (double-register safe), wired into `__init__` — the interface shows Turkish when Blender's language + Translate-Interface are on. Add a language = one more top-level dict |
| `core/raycast.py` | Screen↔3D projection + plane (u,v) + surface ray (`screen_to_plane`, `view_direction`, `world_to_plane_uv`, `plane_uv_to_world`, `world_to_screen`, `ray_cast_surface`/`ray_cast_surface_ex` (w/ `ignore` to skip the live preview), `face_edge_tangent` (smart edge-aligned orient; `near_point` aligns to the edge nearest the click for the SURFACE grid), `basis_from_normal`, `view_basis`/`surface_basis_at` (the shared VIEW + on-face SURFACE construction basis; draw_cut and the HardFlow Mode shell both delegate), `closest_axis_distance`) |
| `core/grid.py` | World-scale + angle + scalar snap, shape points, construction grid, 2D rotation (`snap_world`, `snap_scalar`, `world_grid_segments`, `centered_grid_segments`, `snap_angle`, `box_points`, `circle_points`, `ngon_points`, `slot_points` (stadium), `star_points` (n-pointed star), `arc_points` (pie sector), `centroid`, `rotate_2d`, `radial_sets` (spin N copies about a pivot — the bolt-circle radial array, v1.20), `vent_slats` (rect → N louvre slot rectangles, border ribs = interior ribs — the VENT shape, v1.20), `is_self_intersecting`, `point_in_polygon`, `polygons_overlap` (knife footprint test), `lock_distance` (numeric exact-size entry)) |
| `core/snap.py` | Vertex/edge geometry snap, pure 2D (`nearest_point`, `closest_point_on_segment`, `nearest_on_segments`, `resolve_snap` (nearest-wins disambiguation, vertex priority breaks ties), `snap_to_candidates` (1-D inference: snap a scalar to the nearest feature value)) |
| `core/snapping.py` | Unified 3D snapping shared by every draw tool (vertex/edge → surface → grid → free) + pipe surface-drape; bpy-data + mathutils, no `bpy.ops`/`gpu`/`blf`; reads the live edit-mesh in Edit Mode (v1.3); delegates picking to `core/snap.py` (`Geo`, `collect_geo`, `geo_snap_3d`, `grid_snap_3d`, `snap_insert_point`, `nearest_surface_point`, `drape_path`) |
| `core/offset.py` | Pure 2D polygon inset/offset math, stdlib only — the Offset tool (`signed_area`, `offset_polygon`, `inset_inference_candidates` (in-plane thickness inference: distances at which the inset border hits a coplanar feature)) |
| `core/bevel.py` | Pure Smart Bevel support-loop placement + clamping math, stdlib only (`holding_loop_factor`, `seg_factor` (v1.16 bevel-exact: tightens the offset for a rounded multi-segment bevel by 2/(segments+1); 1.0 for a chamfer), `subdiv_fillet_radius`/`support_offset_for_radius` (the lone-loop offset↔subdivided-radius relation, inverses), `beveled_fillet_radius` (the *measured* beveled-fillet radius ≈ bevel width × (1+0.3/segments); from the live Blender 5.1.2 subdivision pass — drives the Edge Bevel `~r=…` HUD readout), `support_loop_positions`/`support_loop_fractions` (absolute offsets / (0,1) flank fractions from the bevel border; `tightness` 0..1 hug + segment-aware), `safe_support_fraction` (clamp one split off both ends of a flank — the per-edge safety barrier), `flank_can_support` (skip a flank too small to hold a loop; the non-quad-safe gate)) |
| `core/topology.py` | Pure post-boolean cleanup predicates, stdlib only — the Module 4 (MeshMachine parity / SubD stability) anchor (`triangle_area`, `polygon_area` (Newell cross-sum, translation-invariant), `is_sliver` (near-zero-area face), `collinear`/`redundant_vertex` (a mid-edge valence-2 vert removable from a straight run)). `core/geometry._clean_boolean_slivers` applies them in bmesh |
| `core/preview_cache.py` | Pure live-boolean-preview caching / culling math, stdlib only — the high-poly guard (`moved_enough`/`PreviewGate` distance gate so an idle mouse doesn't re-evaluate the boolean, AABB math `aabb`/`expand_aabb`/`boxes_overlap`/`point_in_box` so only targets the cutter box actually reaches carry the temp modifier). No bpy; consumed by `operators/draw_cut._sync_live_boolean` |
| `core/hud.py` | Pure HUD-layout + viewport-guide math, stdlib only — the Module 2 (BoxCutter-parity) anchor (`shortcut_bar_layout` (centered / margin-anchored chip packing for the bottom shortcut bar), `axis_alignment` + `alignment_guides` (dynamic full-span alignment guides when the cursor is square with a placed point, deduped)). No gpu/blf; `ui/draw.draw_shortcut_bar`/`draw_alignment_guides` render what it returns |
| `core/command.py` | Pure Command-Pattern journal, stdlib only — the per-modal-session undo layer (`Command` (idempotent `execute`/`undo`), `CallbackCommand`, `MacroCommand` (atomic all-or-nothing chain; rolls applied children back on a failing child), `CommandManager` (`do`/`undo`/`redo`/`undo_all`/`clear` journal)) |
| `core/geometry.py` | bmesh generation (`build_prism`/`build_prisms` (`apex` = perspective Project taper), `build_face`/`build_faces`, `build_box`/`build_plane`/`build_line`/`build_cylinder`/`build_cone`/`build_uv_sphere`/`build_tube` (starter primitives + guide line), `extract_faces` (selected faces → new re-indexed mesh, optionally solidified into a closed cutter volume — the Extract Cutter core), `build_pipe` (round pipe curve; `closed` = cyclic spline for the Cut-to-Trim ring; `spline_type='BEZIER'` = editable AUTO-handle smooth pipe, v1.20)/`build_pipe_mesh` (mesh sweep; v1.20 `closed` bridges the seam ring for cyclic Panel-Line loops)/`round_profile` (circular mesh-sweep section)/`profile_points` (round/square/rect + L/U/T/I structural sections for the Sweep tool), `build_loft`, `build_grid_mesh`, `extrude_faces`/`edit_extrude_faces` (clean extrude or `keep_original` copy), `inset_faces`/`inset_extrude_faces` (offset→push/pull recess/panel combo), `knife_polygon` (footprint-restricted via `_knife_footprint_faces`), `bevel_cutter` (chamfer the cutter for bevelled cuts), `nearest_edge_on_face`/`edge_loop`/`edge_ring`/`bevel_object_edges`/`loop_cut` (Object-Mode edge pick + loop/ring walk + bevel + loop cut; `loop_cut` `slide` positions a single loop along its ring via `_oriented_ring`), `nearest_face_to_point` (map an evaluated-mesh hit to a base face -> pick through generative modifiers), `estimate_thickness`, `cleanup_mesh`, `mark_sharp_edges` (Object-Mode: clear + re-mark hard edges — angle-driven sharp + bevel weight + optional crease + shade-smooth, idempotent; the Smart Sharpen bmesh pass), `smart_bevel_edges` (Smart Bevel: bevel + support/holding loops via `_flank_support_loop` — now **non-quad-safe** (n-gon flanks + a `bevel.flank_can_support` safety barrier that skips too-small flanks, reported as a `skipped` count), topology-preserving), `dissolve_boolean_ngons` (triangulate + re-quad the n-gons a boolean/bevel leaves; v1.16 `clean_slivers` first runs `_clean_boolean_slivers` — merge doubles → `dissolve_degenerate` near-zero-area faces/edges → dissolve redundant collinear valence-2 verts via `core/topology`, the SubD-stabilizing pass)) + live-preview snapshot (`snapshot_mesh`, `restore_mesh`, `free_mesh`) + Edit-Mode bridge (v1.3: `flush_edit_mesh`, `restore_edit_mesh`, `edit_extrude_faces`, `edit_inset_faces`, `edit_add_face`, `edit_knife_polygon`, `edit_set_edge_weights`, `selected_face_basis`) |
| `core/boolean.py` | boolean + cutter management (`apply_boolean`, `apply_boolean_fallback` (EXACT→FAST), `robust_boolean` (auto-solver + ordered Manifold→Exact→Fast fallback chain + cutter normal repair + diagnosis), `choose_solver` (health-driven solver pick; Manifold-first on clean watertight meshes), `_coerce_solver`/`_solver_available` (version-safe solver: Manifold→Exact before Blender 4.5, Fast→Float on Blender 5.0+), `recalc_normals`, `mesh_health`/`_health_summary`, `add_boolean`, `duplicate_object`, `stash_cutter`, `cutter_collection`; **shading fix** `helper_collection`, `capture_normal_source` (hidden pre-cut clean-normal snapshot), `add_normal_transfer` (NEAREST_POLYNOR Data Transfer reflecting those normals onto the boolean n-gons)) |
| `core/modifiers.py` | Pure hard-surface modifier-stack ordering, stdlib only — the Sorting Engine (`modifier_priority` (Booleans top, Bevel mid, Weighted Normal/Triangulate bottom; Mirror above/below booleans by the `mirror_after_boolean` toggle), `sorted_order` (stable so re-runs are idempotent + unknown modifiers stay in the middle band), `reorder_moves` (selection-sort (from,to) plan matching bpy `modifiers.move`), `is_sorted`). Applied by `operators/hardops.sort_modifier_stack` |
| `core/transform.py` | Pure cable-sag + sizing math, stdlib only (`cable_points`, `cable_chain`, `dice_coordinates` (split a span into equal pieces), `fit_scale`, `adaptive_dimension` (size-scaled bevel/chamfer width), `dedup_ring` (drop consecutive/closing duplicate points from a Cut-to-Trim boundary loop), `order_edge_paths` (unordered edge pairs → ordered open/closed vertex chains, T/X junctions split — the Panel Line path builder, v1.20)) |
| `core/path.py` | Pure poly-line / freehand-stroke math, stdlib only — the Curves-upgrade anchor (v1.20) (`path_length`, `dedup_points`, `rdp_simplify` (Ramer–Douglas–Peucker stroke → clean anchors; segment-distance so doubled-back strokes survive), `chaikin_smooth` (corner cutting, open endpoints kept / closed wrap), `catmull_rom` (centripetal Catmull-Rom THROUGH the anchors, open ghost-endpoint / closed; the Smooth Path spline), `resample_path` (even arc-length re-sampling, open keeps endpoints / closed drops the seam — feeds the cable-settle particles)). Consumed by `operators/pipe.py` |
| `core/hardsurface.py` | Pure Smart-Sharpen decision math, stdlib only — the Module 3 (HardOps parity) anchor (`dihedral_angle` (face-normal fold, matches bmesh `calc_face_angle`), `should_sharpen`/`sharp_edges` (which edges are "hard" at a threshold), `adaptive_bevel_width` (bevel width scaled to the smallest side)). `core/geometry.mark_sharp_edges` does the bmesh marking; `operators/hardops.HARDFLOW_OT_smart_sharpen` drives it |
| `core/decal_math.py` | Pure orientation math, no bpy/mathutils (`orientation_basis`, `base_tangent`, `dominant_tangent` (longest-edge alignment), `basis_from_edge`/`basis_from_two_edges` (grid-on-edges plane), `best_edge_pair` (deterministic longest-edge main + most-perpendicular partner for the 2-edge plane; `forced_main` overrides the main for Ctrl+Click set-main-edge), `rotate_about_axis`) |
| `core/decal_image.py` | Pure decal-library helpers, stdlib only (`scan_library`, `is_image_file`, `aspect_size`, `safe_filename`) |
| `core/parallax.py` | Pure Parallax Occlusion Mapping math, stdlib only — the depth-decal (Decal-Machine parity) anchor (`luminance` (Rec.709), `surface_depth` (height→depth polarity `1 − luminance`, `invert` for bright-is-deep maps — the tested convention the shader graph + bump both wire), `tangent_space_view` (world view → (T,B,N)), `dynamic_layer_count` (grazing-aware layer count), `parallax_delta_uv`/`steep_parallax_uv`/`parallax_occlusion_uv` (offset-limiting steep ray-march + occlusion refinement; constant-depth closed form `uv0 − d·P`)). `core/decal._parallax_uv_group` unrolls exactly this march as a shader-node network |
| `core/atlas.py` | Pure UV-rect + pixel math for trim sheets + atlasing (`slice_grid`, `cell_rect`, `rect_pixels`, `pack_shelves`, `remap_uv`, `blit_pixels`, `rect_to_uv`, `next_pow2`) + the **free-rectangle trim editor** math (`normalize_rect`, `rect_area`, `rect_contains`, `rect_at_point` (top-most hit-test), `snap_value`/`snap_rect`, `rect_handle_points`/`nearest_handle` (8-handle pick), `resize_rect`, `move_rect` (unit-clamped), `guillotine_split` (custom-size cut)) + **chroma-key background removal** (`color_distance`, `pixel_rgb`, `chroma_key` — alpha cutout by colour with a feathered edge band, mutates a flat RGBA list) |
| `core/decal.py` | Decal build/stick/material (`make_decal`, `make_image_decal`, `build_decal_mesh` (NxN grid so the shrinkwrap conforms to curved/multi-face surfaces; pref `decal_resolution`), `decal_matrix`, `add_shrinkwrap` (PROJECT both Z dirs), `decal_material`/`image_decal_material` + shared PBR node group `_decal_node_group`/`HF_DecalShader` with base/metallic/roughness/AO/normal/height+depth/emission/alpha, bake helpers `bake_image`/`ensure_material`/`bake_image_node`/`discard_bake_image` (roll back a failed bake), atlas image `atlas_image`, `decal_collection`, `DECAL_TYPES`; v1.7 extras `sample_material`/`match_decal_to_material`/`set_decal_uv_rect`/`conform_trim_decal`/`retarget_decal` (transfer to another surface)/`save_image`; v1.16+ depth extras `_parallax_uv_group`/`_wire_parallax` (per-image POM node graph driven by Camera Vector → tangent-space view, luminance-as-height, `invert` polarity; prefs `decal_parallax`/`decal_parallax_depth`/`decal_parallax_layers`) + **heightmap-decal extras** `_wire_height_bump` (a dedicated/color-luminance height map drives the shared group's Height/Depth Bump for real normal-relief shading, sampled at the parallax-corrected UV when POM is on) — `image_decal_material`/`make_image_decal` take `height_image` (separate grayscale height source), `bump_strength`, `height_invert`; prefs `decal_height_image`/`decal_bump_strength`/`decal_height_invert`, loader `HARDFLOW_OT_load_height_map`; material cached per structure (image, height source, POM+layers, bump on/off, invert) — + `add_normal_transfer` (Data Transfer of the target's normals so a decal shades into a curved surface; pref `decal_normal_transfer`), all wrapped so a node/API mismatch degrades to the flat decal) |
| `core/asset_lib.py` | Pure `.blend` kit-library scan, stdlib only (`scan_assets`, `is_asset_file`) |
| `core/asset.py` | INSERT append/orient/bind, bpy-data only (`load_blend_objects`, `asset_matrix`, `place_asset`, `make_asset_cutter`, `bind_cutters`, `flatten_objects`, `conform_asset`, `transfer_shading`, `asset_collection`) + v1.8 asset extras (`bound_size`, `surface_feature_size`, `load_blend_materials`, `apply_material`, `write_objects_blend`) |
| `operators/draw_cut.py` | Main modal drawing operator (`HARDFLOW_OT_draw`): shapes box/circle/poly/ngon/**slot**/**star**/**arc**/**vent** (keys `Q/W/E/R/T/Y/U/I`; `[ ]` = sides / ARC sweep / VENT slat count; VENT expands the drawn rect into `grid.vent_slats` louvre slots, ratio from pref `draw_vent_ratio`), cut/slice/make/**join**(add solid, no boolean)/**intersect**/face/**knife** (mode via `Tab`/`Shift+Tab`), **live boolean preview** (`J` -> temp `HF_LivePreview` modifier shows the real result via `base.LivePreviewCommand`; `_sync_live_boolean`/`_clear_live_boolean`, non-destructive + vertex-capped) + prefs-seeded **cutter options**, per-cut **boolean solver** (Default/Exact/Fast/Manifold), Polyline-Trim **Project/Fixed** extrude orientation (`O`, perspective taper via `_project_apex`), **numeric exact-size entry** (type a dimension -> `_apply_numeric`/`grid.lock_distance`), plane cycling VIEW/SURFACE/**EDGES**(grid on selected edges, longest-edge main via `best_edge_pair`, **Ctrl+Click** sets the main edge via `_pick_selected_edge`)/X/Y/Z (edge- and face-aligned tangents), `Shift+←/→` in-plane grid rotation (`_apply_spin`), **`H` set/move grid origin** (re-anchor the snap lattice, applied in `_plane_basis`), `Z` quick-close / **double-click close**, view-accurate **`knife_project`** for KNIFE mode (`_knife_project_object`, footprint `knife_polygon` fallback), measurement HUD, live 3D cutter cage, Edit-Mode path (v1.3), and **in-draw ops** (v1.4/v1.6: inset `-/=`, rotate `,/.`, array `A`/axis `D` (X/Y/Z/**RADIAL** — spin about the plane/grid origin via `grid.radial_sets`, v1.20), mirror `M`, bevel-on-cut `B`, **bevelled cutter `C`**, **orient `O`**, stamp `G`, live grid Ctrl+Wheel, live depth PgUp/Dn (**Shift = fine 1/10-cell**)) via `_processed_corner_sets`. **Incremental snapping** (v1.17): holding **Ctrl** while moving forces the world-grid snap on for that move + bypasses geometry snap (`_snap_screen(force_grid=)`). Placement clicks route through a per-session **`CommandManager`** (`_record_placement` = a two-child `base.PlacePointCommand` macro over the screen+world lists; Backspace = undo, reset keys = clear). `_apply_destructive` applies the cutter(s) as an **atomic `MacroCommand`** of `base.BooleanCutCommand`s (multi-target CUT/MAKE + SLICE roll back all-or-nothing on a solver failure) + optional **Fix Shading** (pre-cut `boolean.capture_normal_source` → post-cut `add_normal_transfer`, pref `fix_shading_after_cut`); `_apply_nondestructive` auto-sorts the stack (pref `sort_modifiers_after_cut`). **Cut-to-Trim bridge** (v1.17): `_auto_trim` routes a cyclic pipe / recessed panel line along the drawn boundary (draped onto the ACTIVE target via `snapping.drape_path`, ring cleaned by `transform.dedup_ring`, `build_pipe(closed=True)`) into a "Hardflow Trim" collection; prefs `auto_trim_after_cut`/`auto_trim_radius`/`auto_trim_lift` |
| `operators/hardops.py` | Mesh helpers: edge bevel-weight/crease (Edit), display toggles, random colors, copy material, the boolean-health normal recalc, and the **Smart Sharpen / Init HardSurface** one-shot (`HARDFLOW_OT_edge_weight/display_toggle/random_color/copy_material/recalc_normals/smart_sharpen/sort_modifiers/fix_shading/panel_line`). **Panel Line** (v1.20): Edit-Mode selected edges → `transform.order_edge_paths` chains → swept tube cutter (`round_profile` + `build_pipe_mesh(closed=)`) → GROOVE (difference) / BEAD (union) boolean; F9-redoable (style/radius/segments), `non_destructive` stashes the swept line as a live HF cutter. `smart_sharpen` = `geometry.mark_sharp_edges` (angle-driven sharp + bevel weight) + a weight-limited `HF_Bevel` + optional angle-limited `HF_MicroBevel` (v1.17 two-tier bevel hierarchy for boolean-cut corners) + a bottom-of-stack `HF_WeightedNormal`, matched by name so a re-run / F9 updates in place; wrapped per-object so one bad mesh can't abort the batch; ends with `sort_modifier_stack`. Module helpers `sort_modifier_stack` (replays `core.modifiers` order via `obj.modifiers.move`), `ensure_smooth_by_angle` (native "Smooth by Angle" GN modifier on 4.1+, legacy `use_auto_smooth` below); `HARDFLOW_OT_sort_modifiers` (hard-surface stack sort), `HARDFLOW_OT_fix_shading` (post-hoc boolean-shading fix: smooth-by-angle + Weighted Normal). The bevel/mirror/clean/symmetrize/dice/array/greeble tool sets were removed in v1.13 |
| `operators/boolean_ops.py` | Boolean from selected objects, active = cutter (`HARDFLOW_OT_boolean`) |
| `operators/cutters.py` | Non-destructive cutter management (`HARDFLOW_OT_apply_cutters/select_cutter/remove_cutter`) + v1.17 **Extract Cutter** (`HARDFLOW_OT_extract_cutter`: Edit-Mode face selection → standalone solidified cutter at the source world transform, via `geometry.extract_faces`) + **Cutter Scroll** (`HARDFLOW_OT_cutter_scroll`: modal wheel/arrow cycle through the stashed HF_Bool cutters on the active object — reveal one, select it, hide the rest; Enter keeps, Esc restores) |
| `operators/pipe.py` | Surface-snapping curve draw on the shared `_CurveDraw` modal (profile cycle via `_PROFILE_CYCLE`, P): pipe (drapes, F toggles; round/square/rect) + free-hanging sagging cable/rope + **Sweep / Follow-Me** (sweeps an L/U/T/I/box structural section along the path); live preview (curve or swept mesh). **v1.20 input upgrade:** implicit **click-or-stroke** (LMB drag past a px gate = freehand stroke sampled through the snap chain, reduced to anchors on release via `path.rdp_simplify`; Backspace undoes a whole stroke via `_groups`) + **`C` Smooth Path** (`path.catmull_rom` through the anchors; ROUND + Follow-off commits an editable AUTO-handle **Bezier** via `build_pipe(spline_type='BEZIER')`; smoothed/stroke paths drape with `segments=1` since they are already dense; pref `pipe_smooth`) (`HARDFLOW_OT_pipe/cable/sweep`) |
| `operators/face_tool.py` | **Shared base** `_FaceDragModal` for the face-pick-drag direct-modeling tools (Push/Pull, Offset): hover-pick (maps evaluated-mesh hits past the base mesh — generative modifiers — back to a base face via `geometry.nearest_face_to_point`) + lock + drag/numeric + live preview + snap + HUD frame + cancel/cleanup + shared axis-drag **inference** (`_capture_axis_inference`/`_snap_axis_value`: vertex + edge-midpoint heights → snap). The live preview runs through a per-session **`CommandManager` + `base.MeshSnapshotCommand`** (`_begin_edit` snapshots + applies, base `_refresh_preview` re-applies each frame via `command.reapply`, cancel = `undo_all`, commit = `clear` → one Blender undo step). A plain mixin (not an Operator, not registered); subclasses fill `_lock_face`/`_lock_edit`/`_update_drag`/**`_mutate`** (the edit without the restore)/`_set_value`/`_repeat_last`/`_remember_last`/`_hud_lines`/`_handle_key`. Mirrors `pipe._CurveDraw` |
| `operators/push_pull.py` | Push/Pull (on `face_tool._FaceDragModal`): drag a face along its normal (grid snap + numeric + **vertex/edge inference** via the shared base), bmesh extrude w/ live snapshot/restore; `C` **Copy** (keep starting face, stacked extrude), `R` **repeat** last distance (`HARDFLOW_OT_push_pull`) |
| `operators/offset.py` | Offset (on `face_tool._FaceDragModal`): drag to inset a face's border, bmesh inset w/ live snapshot/restore; **in-plane thickness inference** snaps the border onto a coplanar feature (`_capture_offset_inference`/`_snap_offset` → `offset.inset_inference_candidates`); `E` **chains into extruding** the inner face (recess / raised panel, two-phase `inset_extrude_faces`, depth has vertex/edge inference); `R` **repeat** last thickness (`HARDFLOW_OT_offset`) |
| `operators/edge_tool.py` | Object-Mode edge tools on shared `_EdgePickModal` (raycast → nearest edge, through modifiers; built on `face_tool._FaceDragModal`): **Edge Bevel** (drag width / `[ ]` segments / `L` whole-loop `edge_loop` → `bevel_object_edges`, `R` repeat, **`S` Smart Bevel** → `geometry.smart_bevel_edges` with `-`/`=` tightness: support loops + n-gon clean, non-quad-safe with a live `+N loops, M clamped` + `~r=…` expected-subdiv-radius HUD readout; placement validated against a live Subdivision pass) + **Loop Cut** (`[ ]`/type cuts → `edge_ring` + `loop_cut`; **drag = slide** a single loop along its ring); live snapshot/restore. Edge work without Edit Mode (`HARDFLOW_OT_edge_bevel`, `HARDFLOW_OT_loop_cut`) |
| `operators/base.py` | Operator-layer (bpy-aware) Command-Pattern base over `core/command.py` (`HardFlowCommand` (adds `redo`), `PlacePointCommand` (undoable click), `MeshSnapshotCommand` (the named `snapshot_mesh`/`restore_mesh` preview→commit→rollback flow, mode-aware via injected `restore`), `BooleanCutCommand` (one `robust_boolean` as an atomic command that raises on failure), `boolean_chain` (a `MacroCommand` of cuts → all-or-nothing boolean chain), `LivePreviewCommand` (the non-destructive live-boolean preview: owns the temp `HF_LivePreview` modifier lifecycle via `execute`/`refresh`/`clear` — NOT a mesh snapshot, so the draw preview never bakes a per-frame boolean)) |
| `operators/hardflow_mode.py` | **HardFlow Mode "Shadowing Engine":** shared `_HardflowModeModal` shell (modal-hijack loop + Ghost-Grid snap chain `_snap_screen` + VIEW/**SURFACE**/X/Y/Z plane cycle (`_surface_basis_at`, aligned to the face under the first click) + **`Tab` verb cycle** (`_cycle_verb`) + per-session `CommandManager` + HUD; verbs dispatched by `self._active_verb`, subclasses only set `_START_VERB`). Verbs: **Knife** (score the drawn footprint onto the active mesh, swept along the construction-plane normal — view-projection on the VIEW plane, straight-in on SURFACE/X/Y/Z) + **Extrude** (draw a footprint, PgUp/PgDn depth, `build_prism` → new solid) + **Cut/Add/Slice/Intersect** draw-to-cut booleans (`_build_boolean`: footprint → `build_prism` cutter (`_boolean_cutter_mesh`; Cut/Slice/Intersect use a pierce-through `_pierce_thickness`, Add stands a boss proud of the surface) → atomic `MacroCommand` of `base.BooleanCutCommand` (`robust_boolean` + solver fallback; Slice keeps the intersect duplicate), destructive cutter). Entered from Ctrl+Shift+X + the Edit pie/menu (`mode_knife`/`mode_extrude`/`mode_cut`). Draws the **framed HUD** (verb + live depth) + dashed per-plane axis guide lines through the snapped cursor + a ring snap marker (`_draw_plane_guides`) + held-surface-plane fix (`_surface_hold`). One invocation = one atomic Blender undo step (`HARDFLOW_OT_mode_knife`, `HARDFLOW_OT_mode_extrude`, `HARDFLOW_OT_mode_cut`) |
| `operators/construction.py` | Starter primitives (cube/plane) + guide line + construction-grid object at the 3D cursor + loft/bridge between two profiles (`HARDFLOW_OT_add_primitive/add_guide/add_grid/loft`) |
| `operators/decals.py` | Decal placement/management/bake/library/trim/atlas + v1.7 create/match/retrim/conform/transfer + editable library (`HARDFLOW_OT_place_decal/select_decal/remove_decal/bake_decal/load_decal_image/load_height_map/library_place/load_trim_sheet/atlas_decals/match_decal/retrim_decal/conform_decal/transfer_decal/create_decal/library_rename/library_delete`). `place_decal` also takes a **`region_index`** into the sheet's custom `hardflow_trim` regions (v1.16): a whole-image / equal-grid-cell / custom-region sub-rect all flow through the one `_uv_rect`/`_wh` path, Up/Down cycles regions; its `_build_decal` threads the height-map prefs (`decal_height_image`/`decal_bump_strength`/`decal_height_invert`) into `make_image_decal`. `load_height_map` loads a grayscale image and points `decal_height_image` at it |
| `operators/trim_editor.py` | **Trim Sheet UV editor (v1.16):** the region data model (`HARDFLOW_TrimRegion`/`HARDFLOW_TrimSheet` PropertyGroups stored on `bpy.types.Image.hardflow_trim`; `Scene.hardflow_trim_image` points at the active sheet) + the interactive modal `HARDFLOW_OT_trim_editor` (draws the sheet as a screen-space canvas, LMB-drag = new region, drag handles = resize, click = select/move, `C`/`Shift+C` = guillotine split, `X` = delete, `A` = add, `Tab` = next, `G`/`[ ]`/wheel = snap, Enter/Esc = confirm/cancel-via-snapshot; all rect math via `core/atlas`) + region-management ops (`HARDFLOW_OT_load_trim_image`/`trim_region_add`/`trim_region_remove`/`trim_grid_regions`/`place_trim_region`/`retrim_region`) + **chroma-key background removal** (`HARDFLOW_OT_trim_chroma_key`: make a key colour transparent — eyedropper or corner-sample, tolerance + edge-softness feather, copy `<name>_cutout` (regions carried) or in-place; numpy fast path + `atlas.chroma_key` fallback) |
| `operators/assets.py` | INSERT placement (auto-scale + insert-grid snap, v1.8) + library + mark + material INSERT + asset-pack export (`HARDFLOW_OT_place_asset/load_asset/asset_library_place/mark_asset/material_insert/export_asset`) |
| `ui/draw.py` | GPU + blf helpers: shapes/points/fills/grid, the **framed HUD** (`draw_hud` with a bordered panel + optional accent `title`/header — every modal tool's premium overlay), the viewport-guide primitives (`draw_rect_outline`, `draw_rect_fill`, `draw_guide_line`, `draw_dashed_line`, `draw_snap_ring`, `draw_mirror_plane`, `fade_color` for translucent / fade-in overlays), plus **`draw_image`** (a GPU texture as a screen-space quad — the trim-editor canvas) and **`draw_text`** (a single blf label — per-region names), and the **v1.16+ Module 2 polish** — **`draw_shortcut_bar`** (a premium translucent bottom bar of `[KEY] Label` chips with a live accent = engaged/current state) + **`draw_alignment_guides`** (dashed full-span guides when the cursor is square with a placed point), both packing/aligning via the pure `core/hud.py`; **`draw_snap_marker`** (the shared ring + faded-dot "snapped here" marker — the UX-overhaul unification every draw tool now uses instead of a bare dot); and the **UX-Track-1 native-feel pass** — `_ui_scale` multiplies every size/pad by `preferences.system.ui_scale` (hiDPI-constant), `_theme_hud_colors`/`_theme_bar_colors` pull the panel/bar colors from the active theme (`_contrast_text` picks a legible active-key glyph; hardcoded palette kept as the headless fallback), and **`draw_cursor_label`** renders the live size/distance in a pill at the cursor (`draw_shortcut_bar` gained an `accent` arg) |
| `ui/pie.py` | Categorized pie system: main pie (Cut/Push-Pull/Offset heroes + category openers + Apply Cutters) + Boolean/Build/Edit/Curves sub-pies (`HARDFLOW_MT_pie`, `HARDFLOW_MT_pie_boolean/build/edit/curves`); `_draw`/`_open` helpers. Same Boolean→Build→Edit→Curves category order as the header menu + N-panel |
| `ui/menu.py` | 3D-View header dropdown covering every tool incl. Decals/Assets; data-driven `*_ITEMS` tables + submenus (Boolean/Build/Edit/Curves/Display/Decals/Assets — Edit = Push-Pull/Offset/Edge-Bevel/Loop-Cut) (`HARDFLOW_MT_menu`, `HARDFLOW_MT_menu_*`); `register`/`unregister` add the header hook |
| `ui/panel.py` | N-panel in Boolean→Build→Edit→Curves→Display order (matches the pie + header menu): Boolean draw (Cut/Slice/Make/Intersect/Join/Knife + Circle/N-gon/Slot/Star/Arc shapes + Boolean-Selected + Apply Cutters), Build (cube/plane/cylinder/cone/sphere/tube + sketch faces + grid/guide/loft), Edit (Push/Pull/Offset/Edge-Bevel/Loop-Cut), Curves (pipe/cable/sweep), display + material rows, snap settings, **Cutter Options** (v1.13 prefs-backed inset/bevel/array/live-preview), **modifier-stack manager** (v1.5), **gizmo toggles** (v1.10), cutter list. The **UX/UI overhaul** made Build/Edit/Curves/Display their own **foldable sub-panels** (Boolean Draw stays the always-visible hero), added a dismissible **Quick Start** onboarding card (`_draw_quickstart`, `show_quickstart` pref) + a **Help & Shortcuts** cheat-sheet panel, a premium **Grid/Vertex/Surface** snap toggle row + boxed groups in the snap panel, and a readable Cutter-Options live-keys legend (`HARDFLOW_PT_tools/build/edit/curves/display/help/gizmos/snap/cutter_options/modifiers/cutters`). **UX Track 3** reworked the Boolean section into a persistent **Mode dropdown + hero Draw button + 3×2 shape grid** (`DRAW_MODE_ITEMS`/`DRAW_SHAPE_ITEMS`, the `Scene.hardflow_draw_mode` prop registered by module-level `register`/`unregister`) so any operation × shape is one click, plus a "Boolean & Edit need an active mesh" poll hint |
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

**Non-class registrations** (Scene/Image properties, translation catalogs,
header hooks, previews) live in their own module's `register`/`unregister`, all
called from `__init__.register()`/`unregister()`: `menu`, `decal_library`,
`panel` (the `Scene.hardflow_draw_mode` prop), `translations` (the tr_TR
`bpy.app.translations` catalog), plus the `Image.hardflow_trim` /
`Scene.hardflow_trim_image` pointers set inline in `__init__`.

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
