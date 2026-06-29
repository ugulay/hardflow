# Roadmap

The features of competing tools and where/how they fit into Hardflow. Each item
is isolated to a single module as much as possible, so that contributors can make
progress without colliding with one another.

## v0.1 — Initial release (core loop working)
- [x] Modal drawing operator (Box / Circle / Polygon)
- [x] Cut / Slice / Make modes (boolean DIFFERENCE / INTERSECT / UNION)
- [x] Screen-space grid snap + live GPU drawing + HUD
- [x] Smart bevel and mirror operators
- [x] Pie menu, preferences, keymap

## v0.2 — Snapping and precision (highest value)
This is where Grid Modeler's real power lies.
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
      the plane normal. World-aligned grid = Grid Modeler aligned drawing.

## v0.3 — Non-destructive workflow (the Boxcutter spirit)
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
- [x] Dead-vertex cleanup after bevel — `HARDFLOW_OT_clean` (Hard Ops "clean").
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

## v0.5 — Pipe and profile (Grid Modeler "pipes")
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

## v0.7+ — Decals (the DECALmachine spirit)
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

### v0.9 — Library and performance (current release)
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

## v1.0 — Asset/kitbash system (the KitOps spirit) + modeling tools
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

## v1.0 — Hard Ops modeling tools
Round out the Hard Ops feature parity beyond bevel/mirror/clean.
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
- [x] **Sharpen (SSharp)** — `HARDFLOW_OT_sharpen` / `geometry.mark_sharp_by_angle`:
      mark edges sharp by angle and clean shading with a Weighted Normal modifier
      (+ optional angle-limited bevel).

## v1.1 — Live placement preview
- [x] **Live decal/asset preview** — the decal and asset placement tools show the
      **real** object under the cursor (not a wireframe outline) before commit, so
      you see exactly what you'll get; the preview *is* the final object on click,
      and Esc discards it. New `core/asset.py` helpers `bind_cutters` /
      `flatten_objects` support the reuse.

## v1.2 — SketchUp-style direct modeling
Direct push/pull/offset on existing faces plus a construction reference plane —
the SketchUp spirit, fitting the existing architecture (pure math in `core`, a
thin modal operator on top).
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

## v1.3+ — Feature-parity gap with the referenced tools

Everything above is implemented. The sections below (v1.3–v1.8) close the
remaining gaps between Hardflow and the five tools it tracks (Grid Modeler,
Boxcutter, Hard Ops, DECALmachine, KitOps). Each item is scoped to a single
module wherever possible so contributors don't collide. These are now
**implemented** (syntax-verified + pure/headless tests added; live Blender
verification of the modal tools is still ongoing — see `tests/manual_checklist.md`).

Where it landed, by section:
- **v1.3** Edit Mode — `core/geometry.py` bridge (`edit_extrude_faces`,
  `edit_inset_faces`, `edit_add_face`, `edit_knife_polygon`, `restore_edit_mesh`,
  `selected_face_basis`, `flush_edit_mesh`); `core/snapping.py collect_geo` reads
  the live edit-mesh; draw/Push-Pull/Offset branch on `EDIT_MESH`.
- **v1.4** In-draw — all on `operators/draw_cut.py`: KNIFE mode, inset (`-`/`=`),
  in-plane rotate (`,`/`.`, `core/grid.rotate_2d`), array (`A`/`D`), mirror (`M`),
  bevel-on-cut (`B`), stamp/repeat (`G`); `core/geometry.build_prisms/build_faces/
  knife_polygon`.
- **v1.5** Hard Ops — `operators/hardops.py` (dice, edge weight, display toggles,
  random colors, copy material, step/taper/knurl) + `core/geometry.py` builders,
  `core/transform.dice_coordinates`, sharpen presets, modifier-stack panel.
- **v1.6** Grid Modeler — live grid density (Ctrl+Wheel) + live depth (PgUp/Dn) in
  draw, square/rect pipe (`build_pipe_mesh` + `P`), loft (`build_loft` /
  `HARDFLOW_OT_loft`).
- **v1.7** DECALmachine — `operators/decals.py` create/match/retrim/conform +
  editable library; `core/decal.py` `sample_material`, `match_decal_to_material`,
  `set_decal_uv_rect`, `conform_trim_decal`, `save_image`.
- **v1.8** KitOps — auto-scale + insert-grid snap in the place modal, material
  INSERT + KPACK export; `core/asset.py` `bound_size`/`surface_feature_size`/
  `load_blend_materials`/`write_objects_blend`, `core/transform.fit_scale`,
  `core/boolean.apply_boolean_fallback`, `core/snapping.snap_insert_point`.

### v1.3 — Edit Mode foundation (the biggest single lever)
Object Mode only is the most-felt limitation: it blocks Grid Modeler-style
edit-draw and most precise Hard Ops loops. This unlocks several later sections.
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

### v1.4 — In-draw operations (the Boxcutter spirit)
Boxcutter's signature is modifying the cut *while drawing* instead of as separate
ops. All of these hang off the existing `operators/draw_cut.py` modal.
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
      key, Boxcutter "lazorcut" style, for repetitive panel cuts.

### v1.5 — Hard Ops parity (modifier & mesh management)
Hard Ops is more than bevel/mirror/clean; the gap is mostly non-destructive
stack management and dice/greeble helpers.
- [x] **Modifier stack manager** — an N-panel section (`ui/panel.py`) listing the
      active object's modifiers with move/toggle/apply/remove, the Hard Ops "Q"
      mod-list equivalent, so non-destructive edits stay navigable.
- [x] **Boolean dice / split / panel** — grid-slice an object into N pieces along
      one or more axes (`core/geometry.py` cut-plane generation + boolean SLICE),
      the basis for greebling and panel breaks.
- [x] **Sharpen presets (SSharp / CSharp tiers)** — extend `HARDFLOW_OT_sharpen`
      with preset levels (bevel-weight + crease + WN combinations), not a single
      angle pass; presets table in `core/geometry.py`.
- [x] **Edge bevel-weight / crease workflow** — operators to set/clear bevel
      weight and crease on selected edges (Edit Mode; depends on v1.3) so the
      bevel modifier can be weight-limited.
- [x] **Mesh display toggles** — quick wireframe / sharp-edge / cutter-visibility
      viewport toggles (`ui/panel.py` + `operators/`), the Hard Ops display menu.
- [x] **Material / viewport helpers** — assign random viewport colors, copy the
      active material to selection (`operators/`), for fast block-out readability.
- [x] **Step / taper / knurl helpers** — parametric detail generators
      (`core/geometry.py` pure builders + thin operators) for recurring greeble.

### v1.6 — Grid Modeler extras
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

### v1.7 — DECALmachine extras
The decal subsystem is broad already; the gaps are authoring and management.
- [x] **Decal creation pipeline** — bake a decal (normal/height/alpha) out of
      high-poly source geometry into the library, the DM "create decal" flow;
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

### v1.8 — KitOps extras
The INSERT system covers placement; authoring and smart-scale are missing.
- [x] **Auto / smart scale** — scale the INSERT to the target's local feature size
      on placement (raycast footprint → fit), not only manual wheel scale;
      `core/asset.py` fit helper.
- [x] **Material INSERTs** — apply a material-only INSERT from a `.blend` to the
      target (KitOps material kpack equivalent); `core/asset.py` material-append
      path + op in `operators/assets.py`.
- [x] **KPACK-style packaging / export** — author side: mark a selection as an
      INSERT and write it to a `.blend` in the asset library with a generated
      preview (`operators/assets.py`, reuse `mark_asset` + write path).
- [x] **Insert grid / factory snapping** — snap repeated INSERTs to a regular grid
      or to existing insert anchors for clean greeble arrays
      (`core/snapping.py` + `operators/assets.py`).
- [x] **Boolean-solver fallbacks for inserts** — when an insert cutter fails the
      EXACT solver, retry FAST / nudge / report, so boolean INSERTs are robust on
      messy targets (`core/boolean.py`).

## Known limitations
- The grid plane is perpendicular to the view direction (passing through the
  object origin); it is not yet aligned to the object surface/world axes (see
  v0.2 "rotating the grid plane").
- Object Mode only. There is no Edit Mode flow (`bmesh.from_edit_mesh`) yet.
- Concave polygons work; self-intersecting ones produce a broken cutter.
- The EXACT solver can fail on overlapping/inverted-normal geometry — if a cut
  doesn't happen, fix the target's normals or nudge the cutter slightly.
