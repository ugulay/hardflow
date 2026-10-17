# Hardflow — full feature matrix

Every shipped feature, grouped by the paid tool whose workflow it brings to
Blender for free. The right column points at the implementing module, so this
doubles as a map of the codebase.

For the short, artist-facing overview see the [README](../README.md); for
per-version history see the [CHANGELOG](../CHANGELOG.md) and for what is next
see the [ROADMAP](../ROADMAP.md).

Every shipped feature through **v1.22**, grouped by the paid tool whose workflow
it brings to Blender for free. The right column points at the implementing module.

> **Super Modeling Mode (v1.14+)** — a SketchUp-fluidity / pro-pipeline
> evolution on three new layers: the **Shadowing Engine** (HardFlow Mode verbs,
> now with a SURFACE plane + `Tab` verb cycle + keymap/pie entry), a **per-modal
> atomic macro** (Command-Pattern undo, now driving the direct-modeling tools and
> the boolean cut chain), and **Smart Topology** (Smart Bevel + boolean n-gon
> cleanup). See the *Super Modeling Mode* subsection at the end of the matrix.

### Boolean & drawing

| Feature | What it does | Where |
|---------|--------------|-------|
| Modal draw-to-cut | Box / Circle / Polygon / N-gon / Slot / Star / Arc / Vent shapes (Slot/Star/Arc v1.13, Vent v1.20), drawn directly in the viewport; keys `Q/W/E/R/T/Y/U/I` | `operators/draw_cut.py`, `core/grid.py slot_points/star_points/arc_points/vent_slats` |
| Cut / Slice / Make / Join / Intersect / Face | DIFFERENCE · split-in-two · UNION · add-as-separate-solid (v1.11) · keep-overlap · create an n-gon surface; `Tab` cycles mode | `operators/draw_cut.py` |
| Vent / grill shape (v1.20) | The drawn rectangle expands into N parallel louvre slots (border ribs = interior ribs; `[ ]` slat count) — works with every mode, array, mirror and the live preview | `core/grid.py vent_slats`, `operators/draw_cut.py` |
| Polyline Trim parity (v1.11) | Point-to-point polygon → boolean: **double-click** closes; per-cut **Solver** (Exact / Fast / Manifold); **Project / Fixed** extrude orientation (`O`, perspective taper) | `operators/draw_cut.py`, `core/geometry.py build_prism` |
| Numeric size entry (v1.10) | Type an exact dimension while drawing to lock the shape's size (radius / extent / segment) | `core/grid.py lock_distance` |
| Knife / zero-depth cut (v1.4) | Score the surface without extruding; restricted to the drawn footprint, not the whole mesh (v1.9) | `core/geometry.py knife_polygon` |
| World-scale grid snap | Camera-independent grid in meters; plane cycles VIEW / SURFACE / EDGES / X / Y / Z; `Shift+←/→` rotates the grid (v1.9) | `core/grid.py`, `core/raycast.py` |
| Grid on selected edges (v1.9) | Edit-Mode draw lays the grid on 1–2 selected edges | `core/decal_math.py basis_from_edge` |
| Live grid density (v1.6) | Adjust grid spacing mid-draw with Ctrl+Wheel + on-screen grid widget | `operators/draw_cut.py`, `ui/draw.py` |
| Live thickness / depth (v1.6) | Drag cutter/extrude depth during the draw with a readout (PgUp/Dn) | `operators/draw_cut.py` |
| Vertex / edge snap | Lock to corner / edge / midpoint of existing geometry; colored cursor | `core/snap.py`, `core/snapping.py` |
| Angle lock | Hold Shift to lock the draw direction to angle steps | `core/grid.py snap_angle` |
| Self-intersection guard | A broken polygon is rejected before the cut | `core/grid.py is_self_intersecting` |
| Multi-object cut | Apply CUT/MAKE to all selected meshes with one cutter | `operators/draw_cut.py` |
| Live boolean preview (v1.13) | Toggle `J` to see the actual Cut/Make/Intersect RESULT on the target while drawing (a temporary modifier, removed on commit/cancel; vertex-capped) | `operators/draw_cut.py` |
| Persistent draw tool (v1.23) | A toolbar Workspace Tool (`Hardflow Draw Cut`) that stays armed, so a row of cuts is one click each; takes its operation from the N-panel Mode dropdown (`use_scene_mode`) | `gizmos/tools.py HARDFLOW_T_draw`, `operators/draw_cut.py` |
| Draw session memory (v1.23) | The in-draw settings (inset / array / mirror / bevel / depth / plane / grid / shape) carry from one draw to the next within the Blender session, so a persistent tool stops resetting them; pref `draw_remember_session`, Ctrl+S still writes the real defaults | `operators/draw_cut.py _store_session/_apply_session` |
| Cutter options (v1.13) | N-panel "Cutter Options" presets the next draw's inset / bevel-on-cut / bevelled cutter / array | `ui/panel.py`, `preferences.py` |

### In-draw operations (v1.4)

| Feature | What it does | Where |
|---------|--------------|-------|
| Inset / extract cut | Offset the drawn loop inward/outward before commit (`-`/`=`) | `core/offset.py offset_polygon` |
| Array during draw | Stamp the in-progress cutter N times along an axis, or spin a **radial (bolt-circle)** set about the grid origin — v1.20 (`A` / `D`) | `operators/draw_cut.py _processed_corner_sets`, `core/grid.py radial_sets` |
| Mirror during draw | Live mirror of the cutter across a world axis (`M`) | `operators/draw_cut.py _processed_corner_sets` |
| Bevel-on-cut | Add an angle-limited bevel to the cut edge at commit (`B`) | `operators/draw_cut.py` |
| Bevelled cutter (v1.10) | Chamfer the cutter so the cut leaves bevelled recess walls (`C`) | `core/geometry.py bevel_cutter` |
| In-plane rotation | Rotate the drawn shape within its plane, live angle in HUD (`,` / `.`) | `core/grid.py rotate_2d` |
| Stamp / repeat | Re-place the previous shape + size with one key (`G`) | `operators/draw_cut.py` |

### Non-destructive workflow

| Feature | What it does | Where |
|---------|--------------|-------|
| Live modifier cut | Leave a boolean modifier instead of applying (`N`) | `core/boolean.py` |
| Cutter collection | Cutters kept in "Hardflow Cutters" (wire, parented, render off) | `core/boolean.py stash_cutter` |
| Cutter manager | Select / show-hide / remove cutters; "Apply Cutters (Bake)" | `operators/cutters.py`, `ui/panel.py` |
| Robust booleans (v1.9) | Every cut auto-picks the solver, retries (EXACT→FAST→normal-repair), and reports *why* it failed | `core/boolean.py robust_boolean/choose_solver/mesh_health` |

### Mesh tools (v1.0 / v1.5)

> **v1.13** removed the bevel / mirror / array / radial / symmetrize / sharpen /
> dice / clean modifier operators and the step / taper / knurl greeble. The
> Object-Mode **Edge Bevel** and **Loop Cut** (Direct modeling section) cover edge work
> without Edit Mode; Blender's own Bevel / Array modifiers cover the rest.
> **Mirror came back in v1.23** — not as a wrapper around the modifier panel,
> but as the one-keystroke decision (axis from the view, keep the visible half,
> sorted stack position) the paid tools are pressed for. The remaining
> mesh-management helpers:

| Feature | What it does | Where |
|---------|--------------|-------|
| Boolean from selection | Boolean selected meshes with the active object as cutter | `operators/boolean_ops.py` |
| Edge weights / crease | Set/clear bevel-weight + crease on selected edges (Edit Mode) | `operators/hardops.py` |
| Display toggles | Wireframe / sharp-edge / cutter-visibility viewport toggles | `operators/hardops.py` |
| Material helpers | Random viewport colors, copy active material to selection | `operators/hardops.py` |
| Recalculate normals | One-click outward-normal fix for booleans that won't cut | `operators/hardops.py recalc_normals` |
| Mirror / symmetry (v1.23) | One press: the axis comes from the view's left-right axis, the half you can see is the one kept, and the live `HF_Mirror` lands in the sorted stack position. Modes: live modifier or Bisect+Mirror (real welded geometry); pivot = object origin / 3D cursor (hidden helper empty) / active object. Alt+X, F9-redoable, refuses to mirror an object away | `operators/mirror.py HARDFLOW_OT_mirror`, `core/mirror.py` |
| Panel Lines (v1.20) | Selected edges → ordered chains swept into a **groove** seam or a raised **weld bead** (Edit Mode); open strips / closed loops / T-X junctions resolve cleanly; destructive or stashed as a live cutter | `operators/hardops.py HARDFLOW_OT_panel_line`, `core/transform.py order_edge_paths` |
| Modifier-stack manager | N-panel list with move / toggle / apply / remove | `ui/panel.py` |

### Decals (v0.7–v0.9 / v1.7)

| Feature | What it does | Where |
|---------|--------------|-------|
| Place on surface | Shrinkwrap-adhered decal aligned to the hit normal; wheel/roll/click | `operators/decals.py`, `core/decal.py` |
| Decal types | Info / Panel / Subset, each driving a shared PBR shader | `core/decal.py DECAL_TYPES` |
| PBR shader | Base / metallic / roughness / AO / normal / height+depth / emission / alpha | `core/decal.py HF_DecalShader` |
| Bake into mesh | Bake Normal / Combined detail into the target's texture | `core/decal.py bake_image` |
| Image library | Folder of PNG/JPG/TGA placed from an icon grid | `core/decal_image.py`, `ui/decal_library.py` |
| Trim sheets | Slice a sheet into a grid; place / cycle individual cells | `core/atlas.py slice_grid` |
| Trim sheet UV editor (v1.16) | Carve a sheet into free, unequal named UV rectangles (draw / resize / move / split) stored on the image; place any region as a decal | `operators/trim_editor.py`, `core/atlas.py`, `ui/trim_panel.py` |
| Background removal / chroma key (v1.17) | Make a picked colour transparent on a trim sheet — knock out a green-screen / flat background so the graphics separate; eyedropper or corner-sample, tolerance + edge-softness feather, copy or in-place | `operators/trim_editor.py HARDFLOW_OT_trim_chroma_key`, `core/atlas.py chroma_key` |
| Heightmap decals (v1.18) | A dedicated grayscale height map (or the color's own luminance) drives depth independently of the albedo — feeding both the Parallax Occlusion UV shift and a normal-relief Bump, with an invert-polarity toggle | `core/decal.py image_decal_material/_wire_height_bump`, `core/parallax.py surface_depth` |
| Atlasing | Pack every image decal into one atlas + one shared material | `core/atlas.py pack_shelves` |
| Create decal (v1.7) | Bake normal/height/alpha out of high-poly source into the library | `operators/decals.py`, `core/decal.py` |
| Material match (v1.7) | Match a decal's blend to the target's active material | `core/decal.py match_decal_to_material` |
| Retrim / conform (v1.7) | Re-drive the trim cell after placement; trim across cuts/edges | `core/decal.py conform_trim_decal` |
| Transfer to surface (v1.10) | Move placed decals onto another object; shrinkwrap + parent re-target, world pose kept | `core/decal.py retarget_decal` |
| Editable library (v1.7) | Rename / delete / re-export library entries from the N-panel | `operators/decals.py` |

### Assets / kitbash (v1.0 / v1.8)

| Feature | What it does | Where |
|---------|--------------|-------|
| INSERT placement | Append a `.blend` part, orient to the surface; wheel/roll/click | `operators/assets.py`, `core/asset.py` |
| Boolean INSERTs | Each mesh becomes a non-destructive CUT/MAKE cutter | `core/asset.py make_asset_cutter` |
| Asset library | `.blend` kit folder shown as an N-panel grid | `core/asset_lib.py`, `ui/asset_panel.py` |
| Conform / shading | Shrinkwrap onto the surface; transfer material + smooth state | `core/asset.py conform_asset/transfer_shading` |
| Asset Browser mark | Mark selection as Blender assets with a preview | `operators/assets.py` |
| Auto / smart scale (v1.8) | Fit the INSERT to the target's local feature size on placement | `core/asset.py`, `core/transform.py fit_scale` |
| Insert-grid snap (v1.8) | Snap repeated INSERTs to a regular grid / existing anchors | `core/snapping.py snap_insert_point` |
| Material INSERTs (v1.8) | Apply a material-only INSERT from a `.blend` | `core/asset.py load_blend_materials` |
| Asset-pack export (v1.8) | Write a selection to a `.blend` in the library with a preview | `operators/assets.py`, `core/asset.py write_objects_blend` |

### Direct modeling & curves (v1.2 / v1.3 / v1.6 / v1.11 / v1.21 / v1.22)

| Feature | What it does | Where |
|---------|--------------|-------|
| Push/Pull | Raycast a face, drag along its normal to extrude; grid-snap + numeric + **vertex/edge inference**; `C` copy/stack, `R` repeat (v1.11) | `operators/push_pull.py` |
| Manifold push (v1.22) | With `D` on, an INWARD Push/Pull **cuts** the volume the face sweeps out of the mesh instead of extruding into it — a clean pocket, or a real hole, with no walls buried in the solid; falls back to the plain extrude (with the reason in the HUD) for an outward pull, Copy, Edit Mode, an open mesh or a failed solver | `operators/push_pull.py _manifold_push`, `core/transform.py push_is_inward/sweep_prism_span` |
| Offset | Raycast a face, drag to inset its border; `E` chains into extruding the inner face — instant recess / raised panel; `R` repeat (v1.11) | `operators/offset.py`, `core/offset.py` |
| Edge Bevel (v1.11) | Object-Mode: pick an edge (or its whole loop, `L`), drag a width, `[ ]` segments — bevel without Edit Mode; `S` **Smart Bevel** adds support loops + n-gon cleanup (`-`/`=` tightness) | `operators/edge_tool.py`, `core/geometry.py bevel_object_edges/smart_bevel_edges` |
| Loop Cut (v1.11) | Object-Mode: pick an edge, insert an edge loop by subdividing its ring; `[ ]` sets how many | `operators/edge_tool.py`, `core/geometry.py edge_ring/loop_cut` |
| Pick through modifiers (v1.11) | The face/edge tools map an evaluated-mesh hit (subdivision / array / mirror) back to a base face | `core/geometry.py nearest_face_to_point` |
| Shared modal base (v1.11) | One mixin owns the hover / lock / drag / preview / numeric / inference / HUD shell for every face-drag tool | `operators/face_tool.py _FaceDragModal` |
| Starter primitives (v1.9 / v1.13) | Add a Cube / Plane / Cylinder / Cone / Sphere / Tube at the 3D cursor to model on | `operators/construction.py`, `core/geometry.py build_box/build_plane/build_cylinder/build_cone/build_uv_sphere/build_tube` |
| Construction grid | Drop a wire reference grid at the 3D cursor on XY / XZ / YZ | `operators/construction.py` |
| Guide line (v1.9) | Drop a snappable wire guide line at the cursor (construction guides) | `operators/construction.py`, `core/geometry.py build_line` |
| Loft / bridge (v1.6) | Bridge two drawn profiles into a solid | `core/geometry.py build_loft` |
| Pipe + profiles (v1.6) | Surface-draping pipe; round / square / rect cross-section (`P`) | `operators/pipe.py`, `core/geometry.py build_pipe` |
| Sweep / Follow-Me (v1.13) | Draw a path and sweep an L / U / T / I / box structural section along it (`P` cycles) | `operators/pipe.py HARDFLOW_OT_sweep`, `core/geometry.py profile_points` |
| Freehand + Smooth Path (v1.21) | Click *or* stroke-draw the path (the ink hugs the surface, reduced to clean anchors on release); `C` interpolates a Catmull-Rom spline through the anchors — a ROUND pipe commits an editable AUTO-handle Bezier | `operators/pipe.py`, `core/path.py rdp_simplify/catmull_rom` |
| CUSTOM cross-sections (v1.21) | The `P` cycle sweeps a flat mesh's boundary outline, or rides a curve object as a native non-destructive bevel profile | `core/geometry.py object_profile_points`, `operators/pipe.py` |
| Sagging cable / rope | A cable that drapes between its points (catenary sag) | `core/transform.py cable_points` |
| Cable gravity settle (v1.21) | `G` relaxes the rope as an anchor-pinned particle chain with real scene collision — it drapes over obstacles and rests on geometry; Shift+Wheel feeds slack | `core/physics.py settle_chain`, `operators/pipe.py` |
| Detail Along Path (v1.21) | Repeat a picked detail mesh along the active curve (Array Fit-Curve + Curve deform) — chain links, cable clips, corrugated hoses | `operators/pipe.py HARDFLOW_OT_path_detail` |

### Edit Mode (v1.3)

| Feature | What it does | Where |
|---------|--------------|-------|
| bmesh edit bridge | Read/write the live edit-mesh via `from_edit_mesh`/`update_edit_mesh` | `core/geometry.py` (`edit_*` helpers) |
| Draw cut into edit mesh | The drawn shape is knifed/inset into the active mesh, no cutter object | `operators/draw_cut.py` |
| Push/Pull & Offset in Edit | Operate on the selected face(s) of the edit-mesh directly | `operators/push_pull.py`, `operators/offset.py` |
| Edit-aware snapping | Vertex/edge snap reads the live, unapplied edit-mesh | `core/snapping.py collect_geo` |

### Tool smartness (v1.9)

| Feature | What it does | Where |
|---------|--------------|-------|
| Self-diagnosing booleans | Auto-solver + retries; on failure says which geometry is broken | `core/boolean.py robust_boolean/mesh_health` |
| Pre-cut health warning | N-panel flags broken geometry before you draw + one-click normal fix | `ui/panel.py`, `operators/hardops.py recalc_normals` |
| Adaptive sizing | Cut chamfer, decal offset, bevel-drag speed scale to the object | `core/transform.py adaptive_dimension`, `core/decal.py adaptive_decal_offset` |
| Smart snapping | Nearest-wins vertex/edge disambiguation; raycast skips the live preview | `core/snap.py resolve_snap`, `core/raycast.py` |
| Edge-aligned orientation | SURFACE drawing aligns to the face edge nearest the click (v1.13 — correct on non-rectangular faces); INSERTs / decals align to the dominant (longest) edge | `core/raycast.py face_edge_tangent`, `core/decal_math.py dominant_tangent` |
| Connected faces | Drawn faces weld onto coincident existing vertices | `core/geometry.py edit_add_face` |

### UX & shared

| Feature | What it does | Where |
|---------|--------------|-------|
| Live placement preview | Decal/asset tools show the real object under the cursor pre-click | `operators/decals.py`, `operators/assets.py` |
| Pie menu | Categorized main pie + Boolean/Build/Edit/Curves sub-pies (Alt+Q) | `ui/pie.py` |
| Header dropdown | 3D-View header menu covering every tool incl. Decals/Assets | `ui/menu.py` |
| N-panel | Tools, snap settings, cutter options, modifier stack, cutter list, display rows | `ui/panel.py` |
| HUD measurement | Drawn shape size in meters (Box W×H, Circle r/d, Poly segments) | `ui/draw.py` |
| Customizable keymap | Rebind shortcuts from the standard Blender keymap editor | `keymaps.py` |

### Super Modeling Mode

*A SketchUp-fluidity / pro hard-surface-pipeline evolution on three foundation
layers, all landed (syntax + pure + headless verified — the headless suite runs
live against a standalone `bpy` build; the modal GUI is in the manual checklist).
Smart Bevel's support-loop placement is **validated** against a live Catmull-Clark
Subdivision pass (Blender 5.1.2, headless) — the holding loop pins the flanking
flat near the bevel and the subdivided fillet stays crisp at radius ≈ the bevel
width — see `docs/hardflow_mode_plan.md`.*

| Feature | What it does | Where |
|---------|--------------|-------|
| Shadowing Engine | HardFlow Mode owns its own modal loop and routes the raw mouse through the core snap chain to bmesh — it never invokes Blender's native modal tools | `operators/hardflow_mode.py _HardflowModeModal` |
| HardFlow Mode: Knife | Draw a snapped polyline on the Ghost Grid, score it onto the active mesh | `operators/hardflow_mode.py HARDFLOW_OT_mode_knife` |
| HardFlow Mode: Extrude | Draw a footprint, PgUp/PgDn depth, build a new prism solid along the plane normal | `operators/hardflow_mode.py HARDFLOW_OT_mode_extrude`, `core/geometry.py build_prism` |
| HardFlow Mode: Cut / Add / Slice / Intersect (v1.17) | Draw a footprint, extrude it into a cutter and boolean it against the active mesh — DIFFERENCE / UNION / split-in-two / keep-overlap — as an atomic solver-fallback chain (Cut/Slice/Intersect auto-pierce; Add stands a boss proud of the surface) | `operators/hardflow_mode.py HARDFLOW_OT_mode_cut/_build_boolean`, `operators/base.py BooleanCutCommand`, `core/boolean.py robust_boolean` |
| Mode plane + verb cycle | The shell cycles VIEW / **SURFACE** (aligned to the face under the first click) / X / Y / Z, and `Tab` cycles the active verb (Knife → Extrude → **Cut → Add → Slice → Intersect**) in-session; enter it from **Ctrl+Shift+X** or the **Edit pie / menu** | `operators/hardflow_mode.py _surface_basis_at/_cycle_verb`, `keymaps.py`, `ui/pie.py` |
| Per-modal atomic macro | A tool session's edits live in a Command journal and commit as **one** Blender undo step; `Backspace` steps back, `Esc` rolls the session back. Now drives the direct-modeling tools' live preview (Push/Pull, Offset, Edge Bevel, Loop Cut) | `core/command.py`, `operators/base.py MeshSnapshotCommand`, `operators/face_tool.py` |
| Atomic boolean chain | N cutters applied as an all-or-nothing MacroCommand — a mid-chain failure rolls the whole chain back (no half-baked cutters, no orphaned slice piece). Wired into the draw-cut destructive apply | `operators/base.py BooleanCutCommand/boolean_chain`, `operators/draw_cut.py _apply_destructive` |
| Smart Bevel & support loops | Bevel + support/holding loops so the edge survives Subdivision (`S` on Edge Bevel, `-`/`=` tightness); a `~r=…` HUD readout shows the fillet radius the bevel settles to. Placement validated against a live Subdivision pass | `core/bevel.py support_loop_positions/beveled_fillet_radius`, `core/geometry.py smart_bevel_edges` |
| Boolean n-gon cleanup | Opt-in: re-quad the n-gons a boolean cut / Apply Cutters leaves (N-panel ▸ Cutter Options ▸ Topology) | `core/geometry.py dissolve_boolean_ngons`, `preferences.py cut_dissolve_ngons` |

