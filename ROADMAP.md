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

## v0.6 — UX polish (current release)
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

### v0.9 — Library and performance
- [ ] **Decal library** — load images/presets from disk, an icon grid in the
      N-panel; a user library folder (path in preferences).
- [ ] **Generate decal from image** — PNG/alpha → a ready decal object +
      material.
- [ ] **Trim sheet / trim decal** — UV slices from a single atlas.
- [ ] **Atlasing** — gather the scene's decals into a single atlas texture
      (reduce draw-call and material count); game-ready export.

## v1.0+ — Asset/kitbash system (the KitOps spirit)
After DECALmachine. Non-destructive kitbashing from a ready-part (INSERT)
library: stick hard-surface details onto the surface with boolean/snap. A
separate `assets/` package; it reuses the existing boolean + snap +
cutter-collection core (independent of the decal subsystem).
- [ ] **INSERT placement** — call a part from the library at the cursor/surface
      normal; rotate/scale with the mouse (similar to the Boxcutter placement
      flow).
- [ ] **Boolean INSERTs** — a part automatically becomes a cutter (CUT/MAKE),
      bound non-destructively via `core/boolean.py` + `stash_cutter`.
- [ ] **Asset library** — `.blend`/collection-based INSERTs; an icon grid in the
      N-panel + a user library folder (preference).
- [ ] **Wrap/Conform INSERT** — parts wrapped onto a curved surface via
      shrinkwrap.
- [ ] **Blender Asset Browser integration** — mark INSERTs as assets,
      drag-and-drop; mark-as-asset + catalog.
- [ ] **Material/auto-smooth transfer** — apply the target's shading settings to
      the placed part.

## Known limitations
- The grid plane is perpendicular to the view direction (passing through the
  object origin); it is not yet aligned to the object surface/world axes (see
  v0.2 "rotating the grid plane").
- Object Mode only. There is no Edit Mode flow (`bmesh.from_edit_mesh`) yet.
- Concave polygons work; self-intersecting ones produce a broken cutter.
- The EXACT solver can fail on overlapping/inverted-normal geometry — if a cut
  doesn't happen, fix the target's normals or nudge the cutter slightly.
