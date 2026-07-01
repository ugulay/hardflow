<div align="center">

# Hardflow

**A free, open-source hard-surface boolean modeling toolkit for Blender.**

One GPLv3 add-on covering the whole hard-surface modeling loop — draw-to-cut
booleans, world-scale snapping, a full decal pipeline, a kitbash/asset system, and
direct modeling (Push/Pull, Offset, edge tools, profile sweeps) — all without a
price tag.

[![tests](https://github.com/ugulay/hardflow/actions/workflows/tests.yml/badge.svg)](https://github.com/ugulay/hardflow/actions/workflows/tests.yml)
[![Blender 4.2+](https://img.shields.io/badge/Blender-4.2%2B-EA7600?logo=blender&logoColor=white)](https://www.blender.org/)
[![Extension](https://img.shields.io/badge/Blender-Extension-orange?logo=blender&logoColor=white)](https://extensions.blender.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.15.0-brightgreen.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

</div>

> **Status — under active development.** **Every roadmap feature through v1.15 is
> implemented** — the boolean cut loop (Cut / Slice / Make / Join / Intersect /
> Knife) with Box / Circle / Polygon / N-gon / Slot / Star / Arc shapes,
> world-scale + vertex/edge snapping, the non-destructive flow, the full decal
> subsystem, the asset/kitbash system, mesh helpers (edge weights, display toggles,
> recalc normals), the direct-modeling tools, **Edit Mode** for
> draw/Push-Pull/Offset/snap (v1.3), the **in-draw operations** (knife, inset,
> array, mirror, bevel-on-cut, bevelled cutter, in-plane rotation, stamp, live grid
> + depth, **live boolean preview** — v1.4/v1.6/v1.13), pipe/cable/Follow-Me sweep
> profiles + loft, the v1.10 **viewport gizmos**, the **v1.11 direct-modeling
> depth** (Blender **Polyline Trim** parity, Push/Pull Copy/Repeat/inference, an
> Offset recess/panel chain, Object-Mode **Edge Bevel + Loop Cut**, and picking
> **through generative modifiers**), and the **v1.13 build/boolean expansion**
> (Cylinder/Cone/Sphere/Tube primitives, Slot/Star/Arc cut shapes, the Follow-Me
> sweep, live boolean preview + cutter options), and the **v1.14 Super Modeling
> Mode** (HardFlow Mode shadowing shell — Knife + Extrude verbs with a SURFACE
> plane + `Tab` verb cycle, a per-modal Command-Pattern undo now driving the
> direct-modeling tools' live preview + an all-or-nothing boolean cut chain, and
> Smart Bevel + boolean n-gon cleanup), and the **v1.15 Polish & Performance**
> pass (topology-safe Smart Bevel on irregular post-boolean meshes, a framed
> "premium" HUD with translucent viewport guide lines, and a high-poly live
> boolean preview that culls non-intersecting targets + gates idle re-evaluation
> via the new pure `core/preview_cache`). The pure-logic core is unit-tested
> (`76/76`, no Blender required) and bpy paths add headless coverage (run live
> against a standalone `bpy` build + verified in Blender 5.1.2); the modal
> tools' interactive feel is checked via
> [tests/manual_checklist.md](tests/manual_checklist.md). See
> [ROADMAP.md](ROADMAP.md) for the full roadmap and [CHANGELOG.md](CHANGELOG.md)
> for the per-version history.

## Features

- **Boolean via modal drawing** — Box / Circle / Polygon / N-gon / Slot / Star /
  Arc shapes; Cut, Slice (split in two), Make (add), Join (add as a separate
  solid), Intersect (keep the overlap), Face (create a surface), and Knife
  (score) modes (`Tab` cycles mode). Toggle `J` for a **live boolean preview** of
  the real result while you draw.
- **Numeric precision** — type an exact dimension while drawing to lock the
  shape's size (radius / extent / segment) for precise drawing.
- **World-scale grid snap** — a camera-independent grid that stays consistent in
  meters (an "absolute size" world grid); plane switches with `←/→`
  between VIEW / SURFACE / EDGES / X / Y / Z, and `Shift+←/→` rotates the grid.
- **Multi-object** — apply CUT/MAKE to all selected meshes with a single cutter.
- **Pipe, Cable & Sweep** — a round-profile pipe from a drawn line, a sagging
  cable/rope that drapes between its points, or a **Sweep / Follow-Me** that
  pushes an L / U / T / I / box structural section along the drawn path.
- **Vertex / edge snap** — lock the drawing point to the corner / edge / edge
  midpoint of existing geometry; colored cursor feedback.
- **Angle lock** — hold Shift to lock the drawing direction to 15° (adjustable)
  steps.
- **Non-destructive mode** — instead of applying the boolean, leave a live
  modifier; keep cutters in a separate collection (non-destructive).
- **Boolean from selection** — boolean the selected meshes using the active
  object as the cutter (Difference / Union / Intersect / Slice), no drawing
  needed; respects the non-destructive flow.
- **Build primitives** — drop a Cube / Plane / Cylinder / Cone / Sphere / Tube at
  the 3D cursor to model on with the direct-modeling tools.
- **Push/Pull** — raycast a face, then drag it along its normal
  to extrude in or out, with world-grid snap, numeric entry and **vertex/edge
  inference**; `C` keeps the starting face (copy/stack), `R` repeats the last
  distance; click or Enter to apply.
- **Offset** — raycast a face and drag to inset its border
  inward by a measured distance (grid-snapped, numeric entry); `E` continues into
  **extruding the inner face** for an instant recess or raised panel; `R` repeats.
- **Edge tools (Object Mode)** — **Edge Bevel** (pick an edge or its whole loop,
  drag a width, `[ ]` segments; `S` toggles **Smart Bevel** — support/holding
  loops + n-gon cleanup so the bevel survives Subdivision, `-`/`=` tightness) and
  **Loop Cut** (pick an edge, insert an edge loop) — edge work without entering
  Edit Mode. All the direct-modeling tools also pick **through generative
  modifiers** (subdivision, etc.).
- **HardFlow Mode** (**Ctrl+Shift+X**) — a streamlined "shadowing" draw mode that
  owns its own modal loop (it never invokes Blender's native tools): draw a snapped
  polyline on the Ghost Grid, then **Knife** it onto a mesh or **Extrude** it into a
  new solid, with **`Tab`** switching verb in-session. `←/→` cycle the construction
  plane (VIEW / **SURFACE** / X / Y / Z), Backspace steps a point back, and the
  whole session commits as a **single atomic undo step** (a per-modal Command-
  Pattern journal); Esc rolls the entire session back.
- **Construction grid** — drop a wire reference grid at the 3D cursor on the
  XY / XZ / YZ plane to model against (a construction plane); spacing
  follows the same world grid as the snap tools.
- **Assets / kitbash** — place ready-made parts ("INSERTs") from
  a `.blend` library onto a surface: wheel scales, `[ ]` roll, click places. A
  part can be a plain decoration, a boolean cutter, conformed to the surface
  (shrinkwrap), and/or given the surface's material/shading. Browse a kit folder
  as a grid, and mark objects as Blender assets for the Asset Browser.
- **Live placement preview** — both the decal and asset tools show the **real**
  object under the cursor (not just a wireframe outline) before you click, so you
  see exactly what you'll get; Esc discards it.
- **Decals** — stick Info / Panel / Subset decals onto any surface; they adhere
  via shrinkwrap and follow the target (surface-adhering detail). Wheel scales,
  `[ ]` roll, click places; managed from the N-panel "Decals" section. Each type
  drives a shared PBR shader (base/metallic/roughness/AO/normal/emission/alpha +
  parallax depth), and detail can be **baked** into the target's texture.
- **Decal image library** — point a folder of PNG/JPG/TGA images and place any of
  them as a decal from an icon grid; images are sized to their aspect ratio.
- **Trim sheets** — slice one sheet into a grid and place individual cells
  (cycle cells with Up/Down while placing).
- **Decal transfer** — move placed decals onto a different surface object; their
  shrinkwrap and parent re-target while the world pose is preserved.
- **Atlasing** — pack every image decal's texture into a single atlas image and
  collapse them onto one shared material (fewer materials / draw calls).
- **Pie menu**, preferences panel, customizable snap settings.

## Feature matrix

Every roadmap feature through **v1.13**, grouped by the paid tool whose workflow
it brings to Blender for free. The right column points at the implementing module.

> **Super Modeling Mode (Unreleased)** — a SketchUp-fluidity / pro-pipeline
> evolution on three new layers: the **Shadowing Engine** (HardFlow Mode verbs,
> now with a SURFACE plane + `Tab` verb cycle + keymap/pie entry), a **per-modal
> atomic macro** (Command-Pattern undo, now driving the direct-modeling tools and
> the boolean cut chain), and **Smart Topology** (Smart Bevel + boolean n-gon
> cleanup). See the *Super Modeling Mode* subsection at the end of the matrix.

### Boolean & drawing

| Feature | What it does | Where |
|---------|--------------|-------|
| Modal draw-to-cut | Box / Circle / Polygon / N-gon / Slot / Star / Arc shapes (Slot/Star/Arc v1.13), drawn directly in the viewport; keys `Q/W/E/R/T/Y/U` | `operators/draw_cut.py`, `core/grid.py slot_points/star_points/arc_points` |
| Cut / Slice / Make / Join / Intersect / Face | DIFFERENCE · split-in-two · UNION · add-as-separate-solid (v1.11) · keep-overlap · create an n-gon surface; `Tab` cycles mode | `operators/draw_cut.py` |
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
| Cutter options (v1.13) | N-panel "Cutter Options" presets the next draw's inset / bevel-on-cut / bevelled cutter / array | `ui/panel.py`, `preferences.py` |

### In-draw operations (v1.4)

| Feature | What it does | Where |
|---------|--------------|-------|
| Inset / extract cut | Offset the drawn loop inward/outward before commit (`-`/`=`) | `core/offset.py offset_polygon` |
| Array during draw | Stamp the in-progress cutter N times along an axis (`A` / `D`) | `operators/draw_cut.py _processed_corner_sets` |
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
> without Edit Mode; Blender's own Bevel / Mirror / Array / Symmetrize modifiers
> cover the rest. The remaining mesh-management helpers:

| Feature | What it does | Where |
|---------|--------------|-------|
| Boolean from selection | Boolean selected meshes with the active object as cutter | `operators/boolean_ops.py` |
| Edge weights / crease | Set/clear bevel-weight + crease on selected edges (Edit Mode) | `operators/hardops.py` |
| Display toggles | Wireframe / sharp-edge / cutter-visibility viewport toggles | `operators/hardops.py` |
| Material helpers | Random viewport colors, copy active material to selection | `operators/hardops.py` |
| Recalculate normals | One-click outward-normal fix for booleans that won't cut | `operators/hardops.py recalc_normals` |
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

### Direct modeling (v1.2 / v1.3 / v1.6 / v1.11)

| Feature | What it does | Where |
|---------|--------------|-------|
| Push/Pull | Raycast a face, drag along its normal to extrude; grid-snap + numeric + **vertex/edge inference**; `C` copy/stack, `R` repeat (v1.11) | `operators/push_pull.py` |
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
| Sagging cable / rope | A cable that drapes between its points (catenary sag) | `core/transform.py cable_points` |

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
Only Smart Bevel's exact support-loop placement is still EXPERIMENTAL, pending a
live subdivision-tuning pass — see `docs/hardflow_mode_plan.md`.*

| Feature | What it does | Where |
|---------|--------------|-------|
| Shadowing Engine | HardFlow Mode owns its own modal loop and routes the raw mouse through the core snap chain to bmesh — it never invokes Blender's native modal tools | `operators/hardflow_mode.py _HardflowModeModal` |
| HardFlow Mode: Knife | Draw a snapped polyline on the Ghost Grid, score it onto the active mesh | `operators/hardflow_mode.py HARDFLOW_OT_mode_knife` |
| HardFlow Mode: Extrude | Draw a footprint, PgUp/PgDn depth, build a new prism solid along the plane normal | `operators/hardflow_mode.py HARDFLOW_OT_mode_extrude`, `core/geometry.py build_prism` |
| Mode plane + verb cycle | The shell cycles VIEW / **SURFACE** (aligned to the face under the first click) / X / Y / Z, and `Tab` switches the active verb (Knife ↔ Extrude) in-session; enter it from **Ctrl+Shift+X** or the **Edit pie** | `operators/hardflow_mode.py _surface_basis_at/_cycle_verb`, `keymaps.py`, `ui/pie.py` |
| Per-modal atomic macro | A tool session's edits live in a Command journal and commit as **one** Blender undo step; `Backspace` steps back, `Esc` rolls the session back. Now drives the direct-modeling tools' live preview (Push/Pull, Offset, Edge Bevel, Loop Cut) | `core/command.py`, `operators/base.py MeshSnapshotCommand`, `operators/face_tool.py` |
| Atomic boolean chain | N cutters applied as an all-or-nothing MacroCommand — a mid-chain failure rolls the whole chain back (no half-baked cutters, no orphaned slice piece). Wired into the draw-cut destructive apply | `operators/base.py BooleanCutCommand/boolean_chain`, `operators/draw_cut.py _apply_destructive` |
| Smart Bevel & support loops | Bevel + support/holding loops so the edge survives Subdivision (`S` on Edge Bevel, `-`/`=` tightness) — EXPERIMENTAL | `core/bevel.py support_loop_positions`, `core/geometry.py smart_bevel_edges` |
| Boolean n-gon cleanup | Opt-in: re-quad the n-gons a boolean cut / Apply Cutters leaves (N-panel ▸ Cutter Options ▸ Topology) | `core/geometry.py dissolve_boolean_ngons`, `preferences.py cut_dissolve_ngons` |

## Installation

Blender 4.2+: **Edit > Preferences > Get Extensions > (top-right ⌄) > Install
from Disk** → select the `hardflow` zip.

## Usage

Select a mesh in Object Mode:

- **Alt+Q** → pie menu (all tools)
- **Ctrl+Shift+D** → direct drawing tool
- **Ctrl+Shift+X** → HardFlow Mode (Knife verb; `Tab` switches to Extrude)

In drawing mode:

| Key | Function |
|-----|-----------|
| Left click | Place point / start-finish shape |
| Enter / double-click | Close the POLY shape and apply |
| Backspace | Delete the last POLY point |
| Q / W / E / R / T / Y / U | Shape: Box / Circle / Polygon / N-gon / Slot / Star / Arc |
| [ / ] | N-gon / star / slot segment count (ARC: sweep angle) |
| **Tab / Shift+Tab** | Cycle mode (Cut / Slice / Make / Join / Intersect / Face / Knife) |
| 0–9 / . / - | Type an exact size (radius / extent / segment) |
| ← / → | Drawing plane: VIEW / SURFACE / EDGES / X / Y / Z |
| **O** | Project / Fixed extrude orientation (perspective taper) |
| X | Toggle world-scale grid snap |
| V | Toggle vertex/edge snap |
| Shift (held) | Lock drawing direction to angle steps |
| N | Toggle non-destructive (live modifier) |
| **- / =** | In-draw inset / extract (offset the loop) |
| **, / .** | In-draw in-plane rotation |
| **A / D** | In-draw array count / array axis |
| **M** | In-draw mirror across a world axis |
| **B** / **C** | Toggle bevel-on-cut / bevelled cutter |
| **J** | Toggle live boolean preview (real result on the target) |
| **G** | Stamp / repeat the previous shape |
| **Ctrl+Wheel** | Live grid density |
| **PgUp / PgDn** | Live cutter / extrude depth |
| Right click / Esc | Cancel |

**Modes:** Cut = boolean DIFFERENCE · Slice = split the object in two · Make =
add geometry (UNION) · Join = add the drawn shape as a separate solid (no boolean)
· Intersect = keep only the overlap · Face = create a surface from the drawn shape
(not a boolean) · Knife = score the surface without extruding (zero-depth cut).

**Other tools:** **Build primitives** (Cube / Plane / Cylinder / Cone / Sphere /
Tube) · **Boolean (Selected)** · **Edge Weights** · **Display Toggles** ·
**Random Colors / Copy Material** · **Recalculate Normals** · **Push/Pull** ·
**Offset** · **Edge Bevel** · **Loop Cut** · **Construction Grid** · **Loft** ·
**Pipe** (round/square/rect) / **Cable** / **Sweep** (L/U/T/I/box sections) ·
**Apply Cutters** · a **modifier-stack manager** — all in the N-panel. Push/Pull,
Offset, the draw tool, and snapping also work in **Edit Mode** (v1.3).

> **v1.13** removed the bevel / mirror / array / radial / symmetrize / sharpen /
> dice / clean modifier tools and the step / taper / knurl greeble; use the
> Object-Mode Edge Bevel / Loop Cut and Blender's own modifiers instead.

**HardFlow Mode:** **Ctrl+Shift+X**, pie ▸ Edit ▸ **HardFlow Mode**, or header
menu ▸ Edit ▸ **"HardFlow Mode: Knife"** / **"…: Extrude"** (or F3). Click to place
snapped points; `←/→` cycle the construction plane (VIEW / **SURFACE** — locked to
the face under the first click / X / Y / Z), **`Tab`** switches the active verb
(Knife ↔ Extrude) without leaving the session, Backspace steps back, `Z` / Enter /
double-click commit, Esc cancels. In Extrude, **PgUp / PgDn** set the depth. The
whole session is one undo step.

**Smart Bevel & topology (Super Modeling Mode):** in **Edge Bevel** press `S` to
add support/holding loops so the bevel survives Subdivision (`-` / `=` adjust how
tightly they hug the bevel). Enable **N-panel ▸ Cutter Options ▸ Topology ▸
Re-quad Cut N-gons** to auto-clean the n-gons a boolean cut / Apply Cutters leaves,
and **Smart Edge Bevel** to start Edge Bevel in Smart mode. (Both default off;
Smart Bevel is EXPERIMENTAL.)

**Assets:** N-panel "Assets" → "Asset from .blend" (or the "Asset Library" grid)
starts the placement tool: wheel = scale, `[ ]` = roll, left click = place, Esc =
cancel. Toggle "Asset as Cutter", "Conform", and "Transfer Shading" there.

**Decals:** N-panel "Decals" → Info / Panel / Subset. In the placement tool:
wheel = scale, `[ ]` = roll, left click = place, Esc = cancel.

**Snap cursor colors:** 🟡 corner · 🟢 edge midpoint · 🔵 on edge.

## Architecture

```
hardflow/
├── blender_manifest.toml   # extension identity (4.2+)
├── __init__.py             # registration orchestration + keymap
├── preferences.py          # settings + get_prefs() accessor
├── core/                   # pure logic (UI-independent, testable)
│   ├── raycast.py          # screen <-> 3D projection, plane (u,v), surface ray
│   ├── grid.py             # world-scale + angle snap, shape + grid pts, rotate_2d
│   ├── snap.py             # vertex/edge geometry snap (pure 2D)
│   ├── snapping.py         # unified 3D snapping for every draw tool (bpy-data)
│   ├── offset.py           # polygon inset/offset math, Offset tool (pure 2D)
│   ├── bevel.py            # Smart Bevel support-loop placement math (pure)
│   ├── geometry.py         # bmesh build (primitives/prisms/pipe/loft) + smart bevel + n-gon clean + Edit-Mode bridge
│   ├── boolean.py          # destructive + non-destructive boolean + fallbacks
│   ├── command.py          # pure Command-Pattern journal (per-modal atomic undo)
│   ├── transform.py        # cable-sag / fit / adaptive sizing math (pure)
│   ├── decal*.py / atlas.py# decal orientation, image library, trim/atlas math
│   ├── asset_lib.py        # .blend kit-library scan (pure)
│   └── asset.py            # append / orient / bind INSERTs + asset extras
├── operators/              # user actions
│   ├── draw_cut.py         # main modal draw (box/circle/poly/ngon/slot/star/arc; live boolean)
│   ├── hardflow_mode.py    # HardFlow Mode shell (Shadowing Engine) — Knife + Extrude verbs
│   ├── base.py             # operator-layer Command-Pattern (MeshSnapshotCommand / BooleanCutCommand)
│   ├── hardops.py          # edge-weight / display / material / recalc-normals helpers
│   ├── boolean_ops.py      # boolean from selected objects
│   ├── cutters.py          # non-destructive cutter management (apply/select/remove)
│   ├── pipe.py             # pipe (round/square/rect) + cable/rope + sweep (L/U/T/I)
│   ├── face_tool.py        # shared modal base for the face-drag tools (_FaceDragModal, command-backed preview)
│   ├── push_pull.py        # Push/Pull — copy/repeat/inference (Object + Edit)
│   ├── offset.py           # Offset — repeat + recess/panel chain (Object + Edit)
│   ├── edge_tool.py        # Object-Mode Edge Bevel + Loop Cut (shared _EdgePickModal)
│   ├── construction.py     # wire construction grid + loft/bridge
│   ├── decals.py           # decal placement + library + trim + atlas + bake + v1.7
│   └── assets.py           # INSERT placement + library + mark + material + export
├── ui/                     # GPU drawing, HUD, menus
│   ├── draw.py             # gpu + blf helpers
│   ├── pie.py              # categorized pie (main + Boolean/Build/Edit/Curves)
│   ├── menu.py             # 3D-View header dropdown covering every tool
│   ├── panel.py            # N-panel: tools, settings, cutter options, modifier stack, cutters
│   ├── decal_panel.py / decal_library.py   # decal sections
│   └── asset_panel.py      # asset + asset-library sections
└── tests/                  # tests
    ├── test_core.py        # pure core, without Blender (python tests/test_core.py)
    ├── test_blender.py     # headless (blender --background --python ...)
    └── manual_checklist.md # click-through checklist for the modal tools
```

`core/grid.py` and `core/snap.py` are deliberately kept free of `bpy`, so the
math layer is tested with plain CPython (`python tests/test_core.py`).

Layering rule: `ui` and `operators` → may depend on `core`; `core` **never**
depends on `ui`. A new feature usually means adding a pure function to core plus
a thin operator that calls it.

## Contributing

Contributions are very welcome — the architecture is built so features stay
isolated and easy to add. Start with [CONTRIBUTING.md](CONTRIBUTING.md) for the
setup, testing, and layering rules, and please report bugs with your **System
Console** output (Window → Toggle System Console).

- 🐛 [Open an issue](https://github.com/ugulay/hardflow/issues/new/choose)
  (bug or feature request)
- 💬 [Discussions](https://github.com/ugulay/hardflow/discussions) for questions
  and sharing builds
- 🔒 Security issues: see [SECURITY.md](SECURITY.md) (please report privately)
- 🤝 By participating you agree to the
  [Code of Conduct](CODE_OF_CONDUCT.md)
- 🗺️ Want to pick something up? The [ROADMAP.md](ROADMAP.md) tracks what's done
  and what's next.

## License

GPLv3. Every Blender addon distributed with `bpy` is effectively GPL in
practice, and this project is no exception. See the [LICENSE](LICENSE) file for
the full license text.
