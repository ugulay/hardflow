# Roadmap

The hard-surface modeling features and where/how they fit into Hardflow. Each item
is isolated to a single module as much as possible, so that contributors can make
progress without colliding with one another.

## v0.1 — Initial release (core loop working)
- [x] Modal drawing operator (Box / Circle / Polygon)
- [x] Cut / Slice / Make modes (boolean DIFFERENCE / INTERSECT / UNION)
- [x] Screen-space grid snap + live GPU drawing + HUD
- [x] Smart bevel and mirror operators
- [x] Pie menu, preferences, keymap

## v0.2 — Snapping and precision (highest value)
This is the precision core.
- [x] **World-scale grid** — `core/grid.py` `snap_world` + `world_grid_segments`,
      `core/raycast.py` `world_to_plane_uv`/`plane_uv_to_world`/`world_to_screen`.
      Snap now operates on the projection plane's local (u,v) meter axes;
      preference `grid_world` (meters). Core math tested without bpy.
- [x] **Vertex / edge snap** — `core/snap.py` (pure 2D, tested): project the
      target's world corners to the screen and lock to the nearest
      vertex/midpoint/edge. `V` toggle in the operator, preferences
      `geo_snap`+`snap_pixels`, colored cursor (yellow=corner, green=midpoint,
      blue=edge). Disables automatically on dense meshes.
- [x] **Angle lock** — while Shift is held, lock the drawing direction to the
      `angle_step` step (`core/grid.py snap_angle`, tested).
- [x] **Rotating the grid plane** — `←/→` cycles the plane between VIEW / world
      X / Y / Z (`core/raycast.py ray_to_plane`); the cutter is extruded along
      the plane normal. World-aligned grid = aligned drawing.

## v0.3 — Non-destructive workflow
- [x] Leave a live modifier instead of applying booleans — toggle with `N` in
      the operator, preference `non_destructive`. CUT/SLICE/MAKE are all
      supported.
- [x] Keep cutter objects in a separate "Hardflow Cutters" collection (WIRE
      display, render disabled, parented to the target) — `core/boolean.py
      stash_cutter`.
- [x] Cutter hide/collection toggle UI — N-panel "Cutters" section:
      collection- and object-level show/hide.
- [x] "Recut" foundation — select a cutter from the N-panel (make it visible +
      active) to edit its mesh; "Apply Cutters (Bake)" applies them all
      destructively (`operators/cutters.py`).

## v0.4 — Geometry quality
- [x] Self-intersection detection and warning for polygons — `core/grid.py`
      `is_self_intersecting`; a broken poly is rejected at commit (tested).
- [x] Post-cut cleanup — preference `cleanup_after_cut`; `core/geometry.py
      cleanup_mesh` (remove doubles + limited dissolve + delete loose).
- [x] Dead-vertex cleanup after bevel — `HARDFLOW_OT_clean` (mesh "clean").
- [x] Create face — `FACE` mode in the drawing operator (key `4`): a single
      n-gon surface object from the drawn shape (`geometry.build_face`). Extrude
      with native `E`.
- [x] **N-gon draw shape** — regular-polygon primitive (shape key `R`); side
      count from the `ngon_sides` preference, live `[`/`]` adjust. Pure-core
      `core/grid.py ngon_points` (tested). Later: rotation handle, star/slot.
- [x] **Advanced bevel** — `HARDFLOW_OT_bevel` modal/interactive (drag = width,
      wheel = segments) + profile, angle limit, width-type, and **Weighted
      Normal** modifier (clean hard-surface shading). Later: custom profile
      curve, bevel presets, vertex bevel.

## v0.5 — Pipe and profile (pipes)
- [x] Pipe generation with a curve + bevel along the drawn line —
      `HARDFLOW_OT_pipe` modal + `core/geometry.py build_pipe`; radius preference
      `pipe_radius`. Profile is round for now; square/custom cross-sections
      later.

## v0.6 — UX polish
- [x] N-panel: tools + settings + active cutter list (`ui/panel.py`).
- [x] HUD measurement display — the drawn shape's size in meters (Box W×H,
      Circle radius/diameter, Poly point count + last segment).
- [x] Theme/color live preview — line/grid color in the N-panel (applies
      instantly).
- [x] Multi-object support — `multi_object` preference; CUT/MAKE is applied to
      all selected meshes with a single cutter.

## v0.7+ — Decals (the decal subsystem)
A new subsystem; surface-adhering detail passes (panel lines, logos,
screw/warning marks) make hard-surface look "finished". A separate `decals/`
package that fits the architecture: pure logic in `core/decal*.py`, actions in
`operators/decal*.py`, interface in `ui/decal_panel.py`. Decals are not booleans
but a **shrinkwrap + material** layer; they can progress independently of the
existing cut core.

### v0.7 — Decal placement core
- [x] **Decal object** — a thin UV-mapped plane that adheres to the target via a
      `SHRINKWRAP` (PROJECT, ABOVE_SURFACE) modifier + `parent`, following the
      surface (`core/decal.py make_decal` / `add_shrinkwrap`).
- [x] **Place on surface** — `HARDFLOW_OT_place_decal` (modal): raycasts the
      surface under the cursor (`core/raycast.py ray_cast_surface`), aligns the
      decal to the hit normal + a rollable tangent; wheel scales, `[`/`]` roll,
      click places. Orientation math in `core/decal_math.py` (pure, tested).
- [x] **Decal types** — Info (emissive accent), Panel (dark recessed), Subset
      (masked patch); each is a reusable material template
      (`core/decal.py decal_material`, `DECAL_TYPES`). Full PBR node groups in
      v0.8.
- [x] **Decal collection** — gathered under `Hardflow Decals`; N-panel "Decals"
      section lists them with show/hide, select, delete (mirrors the cutter
      collection). `ui/decal_panel.py`, `operators/decals.py`.

### v0.8 — Decal material and appearance
- [x] **PBR material setup** — a shared `HF_DecalShader` node group
      (`core/decal.py _decal_node_group`) exposing base color / metallic /
      roughness / AO / normal / emission / alpha channels wired into a Principled
      BSDF, blending into the surface with alpha (Eevee + Cycles compatible).
      Per-type materials instance the group and tune its inputs; v0.9's image
      library plugs textures into the same sockets. Curvature-driven edge wear
      lands with parallax below.
- [x] **Parallax decal** — fake depth: the `HF_DecalShader` group gained Height +
      Depth channels feeding a Bump node that recesses panel lines (Depth = bump
      strength; PANEL preset enables it). No-op until a height map is plugged in
      (v0.9). View-dependent parallax-occlusion UV offset is deferred to v0.9, as
      it needs a UV-sampled height texture to act on.
- [x] **Bake decal into mesh** — `HARDFLOW_OT_bake_decal` bakes the decal's
      Normal or Combined detail into an image on the target via Cycles
      selected-to-active (`core/decal.py bake_image`/`ensure_material`/
      `bake_image_node`; `bake_size` preference; N-panel + per-decal button).
      Requires the target to be UV-unwrapped.

### v0.9 — Library and performance
- [x] **Decal library** — `core/decal_image.py` `scan_library` (pure, tested)
      finds image files in the `decal_library_path` preference folder;
      `ui/decal_library.py` `HARDFLOW_PT_decal_library` shows them as an icon
      grid (thumbnails via a `bpy.utils.previews` collection). Clicking a
      thumbnail runs `HARDFLOW_OT_library_place` → place tool with that image.
- [x] **Generate decal from image** — `HARDFLOW_OT_load_decal_image` picks any
      image; `core/decal.py image_decal_material` plugs its Color+Alpha into the
      shared `HF_DecalShader` group; `make_image_decal` sizes the quad to the
      image aspect (`core/decal_image.py aspect_size`, tested). Reuses the modal
      place tool via an `image_name` property on `HARDFLOW_OT_place_decal`.
- [x] **Trim sheet / trim decal** — place one cell of a grid-sliced sheet as a
      decal. `core/atlas.py slice_grid`/`cell_rect`/`rect_pixels` (pure, tested)
      map the cell to a UV sub-rect; `core/decal.py build_decal_mesh` gained a
      `uv_rect` arg, `make_image_decal` passes it through.
      `HARDFLOW_OT_load_trim_sheet` (file browser, Columns/Rows) starts the place
      tool with trim params; Up/Down cycle the cell, the quad is sized to the
      cell aspect. N-panel: a grid button next to "Decal from Image".
- [x] **Atlasing** — `HARDFLOW_OT_atlas_decals` packs every image decal's texture
      into one `HF_Decal_Atlas` image, retargets each decal's UVs into its slot,
      and swaps them all to a single shared material (fewer materials/draw calls).
      Pure core in `core/atlas.py`: `pack_shelves` (shelf packing), `blit_pixels`
      (RGBA block copy), `remap_uv`, `rect_to_uv`, `next_pow2` (all tested). No
      `bpy.ops` — pixel + UV data only — so it is verified headless
      (`tests/test_blender.py test_atlas_decals`); the blit/UV y-flip composition
      is checked end-to-end. Preference `atlas_max_width`.

## v1.0 — Asset/kitbash system + modeling tools
Non-destructive kitbashing from a ready-part (INSERT) library: stick hard-surface
details onto the surface with boolean/snap. Pure logic in `core/asset*.py`,
actions in `operators/assets.py`, interface in `ui/asset_panel.py`; it reuses the
existing boolean + cutter-collection + orientation core (independent of the decal
subsystem).
- [x] **INSERT placement** — `HARDFLOW_OT_place_asset` (modal): raycasts the
      surface under the cursor, previews the part footprint aligned to the hit
      normal; wheel scales, `[`/`]` roll, click places. The part is appended from
      a `.blend` (`core/asset.py load_blend_objects`) and parented under an
      oriented Empty (`place_asset`), reusing the shared `decal_math` basis.
- [x] **Boolean INSERTs** — when "Asset as Cutter" is on, each mesh of the part
      becomes a CUT/MAKE cutter on the surface object, bound non-destructively via
      `core/boolean.py` + `stash_cutter` (`asset.make_asset_cutter`).
- [x] **Asset library** — `.blend` INSERTs in the `asset_library_path` folder
      (`core/asset_lib.py scan_assets`, pure + tested); an N-panel "Asset Library"
      grid (`ui/asset_panel.py`) places one with `HARDFLOW_OT_asset_library_place`.
- [x] **Wrap/Conform INSERT** — `asset.conform_asset` adds a SHRINKWRAP
      (NEAREST_SURFACEPOINT) toward the surface; preference `asset_conform`.
- [x] **Blender Asset Browser integration** — `HARDFLOW_OT_mark_asset` marks the
      selected objects as assets (`asset_mark` + `asset_generate_preview`) for
      drag-and-drop from the Asset Browser.
- [x] **Material/auto-smooth transfer** — `asset.transfer_shading` gives the
      placed part the surface object's active material + smooth-shading state;
      preference `asset_transfer_shading`.

## v1.0 — Mesh tools
Round out the modifier & mesh helpers beyond bevel/mirror/clean.
- [x] **Boolean from selection** — `HARDFLOW_OT_boolean`: boolean the selected
      meshes using the active object as the cutter (Difference / Union /
      Intersect / Slice), honouring the non-destructive preference. No drawing
      needed; reuses `core/boolean.py`.
- [x] **Array** — `HARDFLOW_OT_array`: a linear Array modifier along a world axis
      (relative or constant offset). `core/transform.py array_offset_vector`.
- [x] **Radial array** — `HARDFLOW_OT_radial_array`: an Array modifier driven by a
      rotated offset Empty at the 3D cursor (count copies around an axis).
      `core/transform.py radial_step_radians` (pure, tested).
- [x] **Symmetrize** — `HARDFLOW_OT_symmetrize` / `geometry.symmetrize_mesh`:
      mirror one half of the mesh onto the other across an object-local axis.
- [x] **Sharpen** — `HARDFLOW_OT_sharpen` / `geometry.mark_sharp_by_angle`:
      mark edges sharp by angle and clean shading with a Weighted Normal modifier
      (+ optional angle-limited bevel).

## v1.1 — Live placement preview
- [x] **Live decal/asset preview** — the decal and asset placement tools show the
      **real** object under the cursor (not a wireframe outline) before commit, so
      you see exactly what you'll get; the preview *is* the final object on click,
      and Esc discards it. New `core/asset.py` helpers `bind_cutters` /
      `flatten_objects` support the reuse.

## v1.2 — Direct modeling
Direct push/pull/offset on existing faces plus a construction reference plane,
fitting the existing architecture (pure math in `core`, a thin modal operator on
top).
- [x] **Push/Pull** — `HARDFLOW_OT_push_pull` (`operators/push_pull.py`): raycast a
      face, lock it, then drag along its normal to extrude in or out with
      world-grid snap and numeric entry; bmesh extrude, no `bpy.ops`. Reuses
      `core/raycast.py`, `core/grid.py`, `core/geometry.py`.
- [x] **Offset** — `HARDFLOW_OT_offset` (`operators/offset.py`): raycast a face and
      drag to inset its border inward by a measured distance (grid-snapped,
      numeric entry), committing a bmesh inset. Pure 2D inset/offset math in
      `core/offset.py` (`signed_area`, `offset_polygon`), stdlib only + tested.
- [x] **Construction grid** — `HARDFLOW_OT_add_grid` (`operators/construction.py`):
      drops a wire reference grid at the 3D cursor on the XY / XZ / YZ plane to
      model against; built from `core/grid.py centered_grid_segments` +
      `core/geometry.py build_grid_mesh`.
- [x] **Sagging cable / rope** — `HARDFLOW_OT_cable` (`operators/pipe.py`): a
      cable that drapes between its points; pure catenary-style sag math in
      `core/transform.py` (`cable_points`, `cable_chain`, tested).

## v1.3+ — Feature gap pass with common hard-surface workflows

Everything above is implemented. The sections below (v1.3–v1.8) close the
remaining gaps between Hardflow and the common hard-surface workflows. Each item
is scoped to a single module wherever possible so contributors don't collide.
These are now **implemented** (syntax-verified + pure/headless tests added; live
Blender verification of the modal tools is still ongoing — see
`tests/manual_checklist.md`).

Where it landed, by section:
- **v1.3** Edit Mode — `core/geometry.py` bridge (`edit_extrude_faces`,
  `edit_inset_faces`, `edit_add_face`, `edit_knife_polygon`, `restore_edit_mesh`,
  `selected_face_basis`, `flush_edit_mesh`); `core/snapping.py collect_geo` reads
  the live edit-mesh; draw/Push-Pull/Offset branch on `EDIT_MESH`.
- **v1.4** In-draw — all on `operators/draw_cut.py`: KNIFE mode, inset (`-`/`=`),
  in-plane rotate (`,`/`.`, `core/grid.rotate_2d`), array (`A`/`D`), mirror (`M`),
  bevel-on-cut (`B`), stamp/repeat (`G`); `core/geometry.build_prisms/build_faces/
  knife_polygon`.
- **v1.5** Mesh tools — `operators/hardops.py` (dice, edge weight, display toggles,
  random colors, copy material, step/taper/knurl) + `core/geometry.py` builders,
  `core/transform.dice_coordinates`, sharpen presets, modifier-stack panel.
- **v1.6** Precision-draw extras — live grid density (Ctrl+Wheel) + live depth
  (PgUp/Dn) in draw, square/rect pipe (`build_pipe_mesh` + `P`), loft (`build_loft` /
  `HARDFLOW_OT_loft`).
- **v1.7** Decal subsystem — `operators/decals.py` create/match/retrim/conform +
  editable library; `core/decal.py` `sample_material`, `match_decal_to_material`,
  `set_decal_uv_rect`, `conform_trim_decal`, `save_image`.
- **v1.8** Asset / kitbash system — auto-scale + insert-grid snap in the place
  modal, material INSERT + asset pack export; `core/asset.py`
  `bound_size`/`surface_feature_size`/`load_blend_materials`/`write_objects_blend`,
  `core/transform.fit_scale`, `core/boolean.apply_boolean_fallback`,
  `core/snapping.snap_insert_point`.

### v1.3 — Edit Mode foundation (the biggest single lever)
Object Mode only is the most-felt limitation: it blocks edit-draw and most precise
mesh loops. This unlocks several later sections.
- [x] **bmesh edit-mesh bridge** — `core/geometry.py` helpers that read/write the
      active edit-mesh via `bmesh.from_edit_mesh` / `update_edit_mesh` instead of
      object data, so the existing pure builders can target an in-edit bmesh.
      Keep `core` free of `bpy.ops`; the operator owns the mode.
- [x] **Draw cut into edit mesh** — `operators/draw_cut.py` gains an Edit Mode
      path: the drawn shape becomes new geometry knifed/inset into the active
      mesh (no separate cutter object), honouring the same snap/grid pipeline.
- [x] **Push/Pull & Offset in Edit Mode** — `operators/push_pull.py` /
      `operators/offset.py` operate on the selected face(s) of the edit-mesh
      directly, not only on a raycast-picked object face.
- [x] **Edit-mode aware snapping** — `core/snapping.py` `collect_geo` reads the
      edit-mesh bmesh (live, unapplied) so vertex/edge snap works mid-edit.

### v1.4 — In-draw operations
The signature is modifying the cut *while drawing* instead of as separate ops. All
of these hang off the existing `operators/draw_cut.py` modal.
- [x] **Knife / zero-depth cut** — a CUT variant that only scores the surface
      (project the shape onto the face, split edges, no extrude/boolean). New mode
      key alongside Cut/Slice/Make; surface projection in `core/geometry.py`.
- [x] **Inset / extract cut** — offset the drawn loop inward/outward before commit
      (reuse `core/offset.py offset_polygon`); live `[`/`]` or drag to set inset.
- [x] **Array during draw** — stamp the in-progress cutter N times along an axis
      before commit, driven by `core/transform.py array_offset_vector`; live count
      adjust in the modal, baked into one cutter on commit.
- [x] **Mirror / symmetry during draw** — toggle a live mirror of the cutter
      across a world axis while drawing (`core/transform.py mirror_axis_flags`).
- [x] **Bevel-on-cut** — optionally add an angle-limited bevel to the cut edge at
      commit, reusing the `HARDFLOW_OT_bevel` modifier path so the cut reads as
      chamfered without a second operator.
- [x] **In-plane shape rotation handle** — rotate the drawn shape within its plane
      (distinct from the existing `←/→` plane cycle); live angle in the HUD.
- [x] **Repeat / stamp last shape** — re-place the previous shape+size with one
      key, repeat / stamp style, for repetitive panel cuts.

### v1.5 — Modifier & mesh helpers (stack management)
There is more than bevel/mirror/clean; the gap is mostly non-destructive
stack management and dice/greeble helpers.
- [x] **Modifier stack manager** — an N-panel section (`ui/panel.py`) listing the
      active object's modifiers with move/toggle/apply/remove, so non-destructive
      edits stay navigable.
- [x] **Boolean dice / split / panel** — grid-slice an object into N pieces along
      one or more axes (`core/geometry.py` cut-plane generation + boolean SLICE),
      the basis for greebling and panel breaks.
- [x] **Sharpen presets (tiered)** — extend `HARDFLOW_OT_sharpen`
      with preset levels (bevel-weight + crease + WN combinations), not a single
      angle pass; presets table in `core/geometry.py`.
- [x] **Edge bevel-weight / crease workflow** — operators to set/clear bevel
      weight and crease on selected edges (Edit Mode; depends on v1.3) so the
      bevel modifier can be weight-limited.
- [x] **Mesh display toggles** — quick wireframe / sharp-edge / cutter-visibility
      viewport toggles (`ui/panel.py` + `operators/`), the display menu.
- [x] **Material / viewport helpers** — assign random viewport colors, copy the
      active material to selection (`operators/`), for fast block-out readability.
- [x] **Step / taper / knurl helpers** — parametric detail generators
      (`core/geometry.py` pure builders + thin operators) for recurring greeble.

### v1.6 — Precision-draw extras
Precision-draw features beyond the world grid already shipped.
- [x] **Live grid density in-modal** — adjust grid spacing with a hotkey during
      the draw (`operators/draw_cut.py`), not only via the `grid_world` preference.
- [x] **On-screen grid widget / HUD** — draw the active snap grid in the viewport
      (`ui/draw.py`) so the snap lattice is visible while drawing.
- [x] **Solidify / live thickness drag** — drag to set the cutter/extrude depth
      during the draw with a measurement readout, instead of a fixed depth.
- [x] **Bridge / loft between two profiles** — draw two shapes and bridge them
      into a solid (`core/geometry.py` loft builder), for tapered ducts/tubes.
- [x] **Square / custom pipe cross-section** — `core/geometry.py build_pipe` gains
      a profile arg (square, rectangular, custom) beyond the current round tube.

### v1.7 — Decal subsystem extras
The decal subsystem is broad already; the gaps are authoring and management.
- [x] **Decal creation pipeline** — bake a decal (normal/height/alpha) out of
      high-poly source geometry into the library, the "create decal" flow;
      pure baking helpers extend `core/decal.py` bake path, op in
      `operators/decals.py`.
- [x] **Material matching** — match a placed decal's blend to the target's active
      material (sample base/roughness/metallic) so it reads as the same surface;
      `core/decal.py` material-sample helper.
- [x] **Editable decal library** — beyond the read-only scan: move/rename/re-export
      and repack library entries from the N-panel (`ui/decal_library.py` +
      `operators/decals.py`); keep the file IO out of `core`.
- [x] **Interactive trim-UV editor** — adjust which trim cell / sub-rect a decal
      uses after placement (re-drive `build_decal_mesh` `uv_rect`), not only at
      placement time.
- [x] **Auto-cut decal to surface** — when a decal crosses a boolean cut or edge,
      project + trim its mesh to the surface boundary so it doesn't float over
      gaps (`core/decal.py` projection/trim helper).

### v1.8 — Asset / kitbash extras
The INSERT system covers placement; authoring and smart-scale are missing.
- [x] **Auto / smart scale** — scale the INSERT to the target's local feature size
      on placement (raycast footprint → fit), not only manual wheel scale;
      `core/asset.py` fit helper.
- [x] **Material INSERTs** — apply a material-only INSERT from a `.blend` to the
      target (material asset pack equivalent); `core/asset.py` material-append
      path + op in `operators/assets.py`.
- [x] **Asset-pack packaging / export** — author side: mark a selection as an
      INSERT and write it to a `.blend` in the asset library with a generated
      preview (`operators/assets.py`, reuse `mark_asset` + write path).
- [x] **Insert grid / factory snapping** — snap repeated INSERTs to a regular grid
      or to existing insert anchors for clean greeble arrays
      (`core/snapping.py` + `operators/assets.py`).
- [x] **Boolean-solver fallbacks for inserts** — when an insert cutter fails the
      EXACT solver, retry FAST / nudge / report, so boolean INSERTs are robust on
      messy targets (`core/boolean.py`).

## v1.9 — Tool smartness + surface modeling
Make the tools *reason* about the geometry, and bring the on-surface drawing /
editing workflow forward. Pure math is unit-tested
(`tests/test_core.py`); bpy paths have headless coverage; the modal/interactive
behaviour still awaits a live-Blender pass.

### Tool smartness
- [x] **Robust, self-diagnosing booleans** — every destructive cut (draw,
      selected-boolean, cutter-bake, INSERT) runs through `core/boolean.robust_boolean`
      (auto-solver → FAST → cutter normal repair) and reports *why* it failed via
      `mesh_health` instead of failing silently.
- [x] **Health-driven solver choice** — `core/boolean.choose_solver` starts a cut
      with FAST on visibly-broken targets, skipping a doomed EXACT pass.
- [x] **Pre-cut health warning** — the N-panel flags boolean-breaking geometry
      before you draw, with a one-click `HARDFLOW_OT_recalc_normals` fix.
- [x] **Adaptive sizing** — bevel width + segment count, cut chamfer, decal hover
      offset, and bevel drag speed all scale to the object's size
      (`core/transform.adaptive_dimension`/`bevel_segments`, `decal.adaptive_decal_offset`).
- [x] **Smart snapping** — nearest-wins vertex/edge/midpoint disambiguation
      (`core/snap.resolve_snap`); the placement raycast skips the live preview
      (`raycast.ray_cast_surface` `ignore`); stable decal orientation on curves.
- [x] **Edge-aligned orientation** — drawing on a surface / placing an INSERT
      aligns to the hit face's dominant edge (`raycast.face_edge_tangent`,
      `decal_math.dominant_tangent`). *Refined in v1.13:* SURFACE drawing now
      aligns to the edge **nearest the click** (`near_point`), not the single
      longest edge, so the box reads correctly on non-rectangular (boolean-cut)
      faces; INSERT / decal placement keep the longest-edge rule.

### Surface modeling
- [x] **Grid plane on selected edges** — Edit-Mode draw with 1–2 edges selected
      lays the construction grid on them (`decal_math.basis_from_edge`/
      `basis_from_two_edges`, draw tool `EDGES` plane).
- [x] **Rotate the grid plane** — `Shift + ←/→` spins the grid in place.
- [x] **Connected faces** — drawn faces weld onto coincident existing vertices
      (`geometry.edit_add_face`).
- [x] **Edit-Mode edge bevel** — real on-selection bevel (`geometry.edit_bevel_edges`),
      not only a whole-object modifier.
- [x] **Starter primitives + guide lines** — Add Cube/Plane and a snappable guide
      line at the cursor (`geometry.build_box`/`build_plane`/`build_line`).
- [x] **Local knife** — the knife score is restricted to the drawn footprint
      (`geometry.knife_polygon`), not infinite planes across the whole mesh. The
      footprint test is a full polygon-overlap check (vertex-in-either + edge
      crossings, `core/grid.polygons_overlap`), so a thin score that merely
      crosses a large face is still localised instead of falling back to slicing
      every face.
- [x] **`Z` quick-close** + **line-width preference** (UI-scaled).
- [x] **Set / move the grid origin** — `H` in the draw tool re-anchors the snap
      lattice (and the visible grid) to the point under the cursor on the current
      plane; press again to revert (`draw_cut` `grid_origin`, applied in
      `_plane_basis`). A movable grid origin.
- [x] **Deterministic main edge** — the 2-edge grid plane uses the longest
      selected edge as the main axis and its most-perpendicular partner for the
      plane (`core/decal_math.best_edge_pair`), so the grid no longer depends on
      bmesh selection order; parallel selections degrade to a clean single-edge
      plane.
- [x] **`Ctrl+Click` set main edge** — on the EDGES plane, Ctrl+Click the
      selected edge under the cursor to force it as the grid's main axis,
      overriding the automatic longest-edge pick (`draw_cut._pick_selected_edge` →
      `decal_math.best_edge_pair` `forced_main`). Headless
      `test_capture_edges_basis_forced_main` + pure `test_best_edge_pair`.
- [x] **Pixel-accurate knife** (`knife_project`) — KNIFE mode now builds a wire
      cutter from the drawn loop(s) and projects it along the current view onto the
      active mesh (`draw_cut._knife_project_object` → `bpy.ops.mesh.knife_project`),
      clipping the score to the exact drawn outline; falls back to the
      footprint-restricted object knife when the viewport operator can't run.
      Live-verified in Blender 5.1.2 (the modal/viewport path is in
      `tests/manual_checklist.md`).
- **`X` start-from-edge-vertex** — *not planned (redundant):* `X` is the snap
  toggle, and vertex snap (`V`) already starts a draw from an existing vertex.

## v1.10 — Viewport gizmos (interactive handles)
On-object handles for the common transforms, so the hard-surface loop doesn't
have to lean on keyboard shortcuts. Two surfaces, sharing one set of gizmo
groups (`gizmos/`): an **always-on persistent** widget toggled from the N-panel
and a set of **Workspace Tools** in the toolbar (T, like Blender's native
Move/Rotate/Scale).
- [x] **Move / Rotate / Scale** — wrap the built-in `transform.translate` /
      `transform.rotate` / `transform.resize` via `target_set_operator`
      (arrow + dial gizmos, world-axis constrained), so snapping / numeric entry
      / axis constraints come for free (`gizmos/groups.py`).
- [x] **Bevel width** — a drag handle bound to an `HF_Bevel` modifier's width
      through `target_set_handler` (`_bevel_get`/`_bevel_set`); dragging from
      zero adds the modifier, dragging again only adjusts it.
- [x] **Push/Pull** — custom modal gizmo `HARDFLOW_GT_drag_extrude`
      (`gizmos/custom.py`): drag the selected faces' average normal to extrude
      live, reusing the operator's snapshot/restore path. Edit-Mesh gizmo;
      Object Mode keeps the raycast hover-pick modal (toolbar tool launches it).
- [x] **N-panel toggles** — `HARDFLOW_PT_gizmos` + Scene-stored
      `HARDFLOW_GizmoSettings` (master `show` + per-kind switches).
- [x] **Workspace Tools** — `hardflow.move/rotate/scale/bevel/push_pull`
      (Object) + `push_pull` gizmo in Edit Mesh (`gizmos/tools.py`).
- Registration + tool placement live-verified in Blender 5.1.2; the drag
  interactions themselves are in `tests/manual_checklist.md` §14 (need a
  viewport). Possible follow-ups: GLOBAL/LOCAL orientation toggle, a uniform
  centre scale handle, an Offset gizmo to mirror Push/Pull.

## v1.11 — Polyline Trim parity (Blender native)
Match Blender's Sculpt-mode **Polyline Trim** workflow (draw a point-to-point
polygon → extrude through the mesh → boolean) in the draw tool, which already had
the core pipeline (POLY shape + Cut/Make/Intersect). All on
`operators/draw_cut.py` + `core/`; the modal/draw-time paths are in
`tests/manual_checklist.md` §15 (need a viewport).
- [x] **Double-click to close** a polyline — parity with the native finish, in
      addition to `Enter` / `Z` / click-start (`operators/draw_cut.py` modal).
- [x] **Join mode** — add the drawn shape as a *separate solid* object with no
      boolean on the target (native "Join"); `_build_solid` +
      `geometry.build_prisms`. (Cut = Difference and Make = Union already shipped.)
- [x] **Project / Fixed orientation** (`O`) — Fixed extrudes straight along the
      drawing-plane normal; Project extrudes each corner along its own camera ray
      so the cut tapers with perspective (`geometry.build_prism(s)` `apex`,
      `draw_cut._project_apex`). Equal in an orthographic view. Headless taper test
      `test_build_prism_project_taper`.
- [x] **Per-cut boolean solver** — Default / Exact / Fast / **Manifold** exposed
      on the operator + preferences; `core/boolean._coerce_solver` makes Manifold
      safe (falls back to Exact before Blender 4.5).
- [x] **Discoverability** — "Polyline Trim" / "Polyline Add" / "Join (Add Solid)"
      in the header Boolean menu, and a "Polyline Trim" pie slot (`ui/menu.py`,
      `ui/pie.py`).
- [x] **Project verify** — the perspective taper is built, unit-checked, and
      live-verified in Blender 5.1.2: Fixed keeps both caps equal (straight prism),
      Project narrows the cap nearer the camera apex (frustum taper). A side-by-side
      visual A/B against the native Sculpt tool remains a manual nicety.

## v1.12 — Direct-modeling tool improvements
Push/Pull and Offset were minimal (hover → lock → drag/type → apply). Bring them
up to better ergonomics and fix an extrude bug. All on `operators/push_pull.py`
/ `operators/offset.py` + `core/geometry.py`; interactions in
`tests/manual_checklist.md` §3/§4.
- [x] **Shared modal base** — `operators/face_tool._FaceDragModal` factors the
      identical hover-pick / lock / drag / snapshot-preview / numeric / HUD /
      cancel shell out of Push/Pull + Offset (~300 lines of duplication removed),
      so a direct-modeling fix or feature lands once. Tools keep their own
      entries; mirrors the existing `pipe._CurveDraw` base.
- [x] **Clean object-mode extrude (fix)** — `geometry.extrude_faces` now drops the
      source face by default (object-mode push/pull used to leave an interior
      divider, unlike Edit Mode); `keep_original` opt-in preserves it. Headless
      `test_extrude_keep_original_vs_clean`.
- [x] **Push/Pull "Copy"** (`C`) — keep the starting face and stack a new volume on
      it (Ctrl push/pull), Object + Edit Mode (`extrude_faces`/
      `edit_extrude_faces` `keep_original`).
- [x] **Repeat last** (`R`) — re-apply the last committed distance (Push/Pull) /
      thickness (Offset) on the newly locked face; remembered across runs.
- [x] **Push/Pull vertex inference** — snap the drag distance to a real vertex
      height (`core/snap.snap_to_candidates`, candidates captured at lock from the
      object's verts projected onto the drag axis); HUD shows `-> on geometry`,
      grid is the fallback. Headless `test_snap_to_candidates`.
- [x] **Edge-midpoint + extrude inference** — inference moved into the shared
      `_FaceDragModal._capture_axis_inference` / `_snap_axis_value`; candidates now
      include edge mid-points (not just vertices), and the Offset EXTRUDE depth
      drag uses it too (not only Push/Pull). Reuses the tested
      `snap.snap_to_candidates`.
- [x] **In-plane offset-thickness inference** — the Offset drag snaps the inset
      *thickness* so the border lines up with a coplanar feature inside the face:
      every other vertex coplanar with the locked face and inside its boundary
      becomes a candidate (its distance to the nearest boundary edge), and the
      thickness snaps to it before grid (`offset.inset_inference_candidates` +
      `offset._capture_offset_inference`/`_snap_offset`; HUD `-> on geometry`).
      Pure `test_inset_inference_candidates` + headless `test_offset_inference_projection`.
- [x] **Offset → auto Push/Pull** — press `E` mid-Offset to lock the inset and
      chain into extruding the inner face along its normal (recess for `-`, raised
      panel for `+`), one bmesh pass `geometry.inset_extrude_faces` /
      `edit_inset_extrude_faces`. Headless `test_inset_extrude_faces_recess`.
- [x] **Interactive edge bevel** — Object-Mode `HARDFLOW_OT_edge_bevel`
      (`operators/edge_tool.py`, on the shared `_FaceDragModal`): raycast → pick the
      nearest edge (`geometry.nearest_edge_on_face`) → drag width, `[ ]` segments →
      `geometry.bevel_object_edges`, live snapshot/restore. Bevel an edge without
      Edit Mode. Headless `test_nearest_edge_on_face` + `test_bevel_object_edges`.
- [x] **Edge-loop bevel** — `L` in the Edge Bevel tool expands the picked edge to
      its connected loop (`geometry.edge_loop`, valence-4 quad walk) and bevels the
      whole loop. Headless `test_edge_loop`.
- [x] **Loop cut** — `HARDFLOW_OT_loop_cut` (`operators/edge_tool.py`, on the
      shared `_EdgePickModal`): pick an edge → insert an edge loop by subdividing
      its ring (`geometry.edge_ring` + `loop_cut`); `[ ]` / type sets how many
      loops. Inserted at the ring midpoints. Headless `test_loop_cut`.
- [x] **Loop-cut slide** — drag to position a single inserted loop along its ring
      (slide -1..1, 0 = midpoint), not only the midpoint (`geometry.loop_cut`
      `slide` via `_oriented_ring` for a zig-zag-free slide; `edge_tool` loop-cut
      drag). Headless `test_loop_cut_slide` + live-verified in Blender 5.1.2.
- [x] **Hover-pick through modifiers** — when the raycast hits geometry a
      generative modifier added (evaluated face index past the base mesh), map the
      hit point back to the nearest base face (`geometry.nearest_face_to_point`) so
      Push/Pull, Offset and Edge Bevel work on modified objects. Exact for
      deform-only modifiers; best-effort nearest-pick for subdivision/array/mirror
      (the base face can sit away from the visible copy). Headless
      `test_nearest_face_to_point`.

## v1.13 — Build/Boolean expansion + tool-set trim
Refocus the toolkit on its boolean / direct-modeling core: drop the secondary
modifier wrappers and greeble, and deepen the Build and Boolean draw
tools instead. All pure math is unit-tested; the bpy paths add headless coverage
(64 pure + 84 headless), live-verified in Blender 5.1.2; modal feel in
`tests/manual_checklist.md` §19.
- [x] **Removed the Greeble + Modifier tool sets** — `HARDFLOW_OT_add_step`/
      `add_taper`/`add_knurl` and `HARDFLOW_OT_bevel`/`mirror`/`clean`/`symmetrize`/
      `sharpen`/`array`/`radial_array`/`curve_array`/`dice`, plus their now-dead core
      builders. `operators/modifiers.py` + `operators/array.py` deleted;
      `recalc_normals` moved to `operators/hardops.py`. **Pipe/Cable kept** (moved to
      a "Curves" N-panel section). The Object-Mode Edge Bevel / Loop Cut and
      Blender's own modifiers cover the gap.
- [x] **Build primitives** — Cylinder / Cone / Sphere / Tube join Cube / Plane
      (`core/geometry.build_cylinder`/`build_cone`/`build_uv_sphere`/`build_tube`,
      `HARDFLOW_OT_add_primitive`). Headless `test_build_primitives`.
- [x] **New boolean draw shapes** — Slot (stadium) / Star (n-pointed) / Arc (filled
      pie sector), keys `T`/`Y`/`U`, with `[ ]` count or ARC sweep
      (`core/grid.slot_points`/`star_points`/`arc_points`, pure-tested). Intersect /
      Join / Knife and the shape rows surfaced as N-panel buttons.
- [x] **Sweep / Follow-Me** — `HARDFLOW_OT_sweep` sweeps an L/U/T/I/box structural
      section along a drawn path (`core/geometry.profile_points` sections, `P`
      cycles via `_CurveDraw._PROFILE_CYCLE`). Headless `test_sweep_profiles`.
- [x] **Live boolean preview** — `J` shows the real Cut/Make/Intersect result on the
      target via a temporary `HF_LivePreview` modifier (stripped before the real cut /
      on cancel, vertex-capped). Preference `live_boolean_preview`. Headless
      `test_live_boolean_preview_and_cutter_options`.
- [x] **Cutter Options in the N-panel** — prefs-backed inset / bevel-on-cut /
      bevelled-cutter / array defaults (`HARDFLOW_PT_cutter_options`) that seed the
      next draw, then live-tweak with the modal keys.
- [x] **SURFACE box orientation on angled faces (fix)** — the on-surface grid now
      aligns to the face edge **nearest the click** (`raycast.face_edge_tangent`
      `near_point`) instead of the single longest edge, so a box reads correctly on
      non-rectangular (boolean-cut parallelogram) faces. Live-verified in Blender
      5.1.2 (axis aligns to the clicked edge within ~0.02deg); headless
      `test_face_edge_tangent_near_point`.

## Feature gap pass (pre-publish)
A feature audit of common hard-surface workflows. Closed in this pass:
- [x] **Numeric exact-size entry** in the draw tool — type a dimension to lock
      the shape's size (`core/grid.lock_distance`, `_apply_numeric`); the boolean
      mode moved to `Tab`/`Shift+Tab`. Precision entry.
- [x] **INTERSECT draw mode** — keep only what's inside the drawn volume.
- [x] **Bevelled cutter** (`C`) — chamfered recess walls (`geometry.bevel_cutter`),
      distinct from `B` bevel-on-cut (target edge).
- [x] **Mirror across the 3D cursor / active object** — `HARDFLOW_OT_mirror`
      "Mirror Across" pivot (Self / 3D Cursor / Active Object).
- [x] **Array along a curve** — `HARDFLOW_OT_curve_array` (Array fit-curve +
      Curve deform).
- [x] **Decal transfer between surfaces** — `HARDFLOW_OT_transfer_decal`
      (`decal.retarget_decal`).

Closed in a later pass (now implemented + verified):
- [x] `Ctrl+Click` set main edge, pixel-accurate `knife_project`, and set/move the
      grid origin (`H`) — all landed; see the v1.9 list above. The modal/viewport
      interactions are live-verified in Blender 5.1.2 (`tests/manual_checklist.md`).

Not separately planned (covered by an existing tool):
- **EXTRACT** — *covered by Slice*, which already keeps both the object and the
  carved piece, so it is not implemented separately.

## Known limitations
- Concave polygons work; self-intersecting ones produce a broken cutter.
- The EXACT solver can still fail on badly broken targets. The draw tool and the
  selected-boolean operator now retry automatically (EXACT → FAST → recalculate
  the cutter's normals → FAST) via `core/boolean.robust_boolean`, and on a
  hard failure report *why* (`mesh_health`: non-manifold / zero-area / loose
  geometry) so you know what to repair. For target-side normal problems, run
  Mesh > Normals > Recalculate Outside.

## Resolved (previously listed as limitations)
- ~~Grid plane perpendicular to view only~~ — the draw tool has VIEW / **SURFACE**
  (aligned to the face under the cursor) / world X / Y / Z planes, cycled with
  `←/→` (`operators/draw_cut.py` `_plane_basis`, `core/raycast.basis_from_normal`).
- ~~Object Mode only~~ — Edit Mode draw / Push-Pull / Offset / snap landed in v1.3.
- ~~No manual main-edge / movable grid origin / pixel-accurate knife~~ — the draw
  tool gained `Ctrl+Click` set-main-edge on the EDGES plane, `H` set/move grid
  origin, and a view-accurate `knife_project` KNIFE path (footprint fallback);
  loop cut gained slide and Offset gained in-plane thickness inference (all v1.9 /
  v1.12, live-verified in Blender 5.1.2).
