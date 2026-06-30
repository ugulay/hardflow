<div align="center">

# Hardflow

**A free, open-source hard-surface boolean modeling toolkit for Blender.**

Hardflow brings the core workflows of Grid Modeler, Boxcutter, Hard Ops,
DECALmachine, and KitOps together in one GPLv3 add-on — draw-to-cut booleans,
world-scale snapping, a full decal pipeline, a kitbash/asset system, and
SketchUp-style direct modeling — all without a price tag.

[![tests](https://github.com/ugulay/hardflow/actions/workflows/tests.yml/badge.svg)](https://github.com/ugulay/hardflow/actions/workflows/tests.yml)
[![Blender 4.2+](https://img.shields.io/badge/Blender-4.2%2B-EA7600?logo=blender&logoColor=white)](https://www.blender.org/)
[![Extension](https://img.shields.io/badge/Blender-Extension-orange?logo=blender&logoColor=white)](https://extensions.blender.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.10.0-brightgreen.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

</div>

> **Status — under active development.** **Every roadmap feature through v1.10 is
> implemented** — the boolean cut loop (Cut / Slice / Make / Intersect / Knife),
> world-scale + vertex/edge snapping, the non-destructive flow, the full decal
> subsystem, the asset/kitbash system, the Hard Ops modeling tools, the
> SketchUp-style direct-modeling tools, **Edit Mode** for draw/Push-Pull/Offset/snap
> (v1.3), the Boxcutter-style **in-draw operations** (knife, inset, array, mirror,
> bevel-on-cut, bevelled cutter, in-plane rotation, stamp, live grid + depth —
> v1.4/v1.6), square/rect pipe profiles + loft (v1.6), and the v1.9–v1.10
> reference-tool gap pass: **numeric exact-size drawing**, the **Intersect** draw
> mode, **mirror across the cursor / active object**, **array-along-curve**, and
> **decal transfer between surfaces**. The pure-logic core is unit-tested
> (`60/60`, no Blender required) and every bpy path is verified headless in
> Blender 5.1.2 (`77/77`); the modal tools' interactive feel is checked via
> [tests/manual_checklist.md](tests/manual_checklist.md). See
> [ROADMAP.md](ROADMAP.md) for the full roadmap and [CHANGELOG.md](CHANGELOG.md)
> for the per-version history.

## Features

- **Boolean via modal drawing** — Box / Circle / Polygon / N-gon shapes; Cut,
  Slice (split in two), Make (add), Intersect (keep the overlap), Face (create a
  surface), and Knife (score) modes (`Tab` cycles mode).
- **Numeric precision** — type an exact dimension while drawing to lock the
  shape's size (radius / extent / segment), Grid Modeler / Boxcutter style.
- **World-scale grid snap** — a camera-independent grid that stays consistent in
  meters (Grid Modeler's "absolute size" logic); plane switches with `←/→`
  between VIEW / SURFACE / EDGES / X / Y / Z, and `Shift+←/→` rotates the grid.
- **Multi-object** — apply CUT/MAKE to all selected meshes with a single cutter.
- **Pipe & Cable** — a round-profile pipe from a drawn line, or a sagging
  cable/rope that drapes between its points; mesh cleanup via **Clean** (Hard Ops
  style).
- **Vertex / edge snap** — lock the drawing point to the corner / edge / edge
  midpoint of existing geometry; colored cursor feedback.
- **Angle lock** — hold Shift to lock the drawing direction to 15° (adjustable)
  steps.
- **Non-destructive mode** — instead of applying the boolean, leave a live
  modifier; keep cutters in a separate collection (the Boxcutter spirit).
- **Advanced bevel** — interactive (drag = width, wheel = segments), with profile
  + angle limit + width-type + **Weighted Normal** (clean shading); mirror
  (bisect + clip) across the object, the 3D cursor, or the active object. The
  Hard Ops spirit.
- **Boolean from selection** — boolean the selected meshes using the active
  object as the cutter (Difference / Union / Intersect / Slice), no drawing
  needed; respects the non-destructive flow.
- **Array, Radial & Curve array** — a linear Array along a world axis, a radial
  array of N copies around the 3D cursor (a rotated offset empty drives the
  modifier), or an array deformed along a selected curve.
- **Symmetrize & Sharpen** — mirror one half of the mesh onto the other, and
  mark sharp edges by angle + Weighted Normal (Hard Ops SSharp).
- **Push/Pull (SketchUp spirit)** — raycast a face, then drag it along its normal
  to extrude in or out, with world-grid snap and numeric entry; click or Enter to
  apply.
- **Offset (SketchUp spirit)** — raycast a face and drag to inset its border
  inward by a measured distance (grid-snapped, numeric entry), then commit a
  bmesh inset.
- **Construction grid** — drop a wire reference grid at the 3D cursor on the
  XY / XZ / YZ plane to model against (SketchUp's construction plane); spacing
  follows the same world grid as the snap tools.
- **Assets / kitbash (KitOps spirit)** — place ready-made parts ("INSERTs") from
  a `.blend` library onto a surface: wheel scales, `[ ]` roll, click places. A
  part can be a plain decoration, a boolean cutter, conformed to the surface
  (shrinkwrap), and/or given the surface's material/shading. Browse a kit folder
  as a grid, and mark objects as Blender assets for the Asset Browser.
- **Live placement preview** — both the decal and asset tools show the **real**
  object under the cursor (not just a wireframe outline) before you click, so you
  see exactly what you'll get; Esc discards it.
- **Decals** — stick Info / Panel / Subset decals onto any surface; they adhere
  via shrinkwrap and follow the target (the DECALmachine spirit). Wheel scales,
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

Every roadmap feature through **v1.10**, grouped by the paid tool whose workflow
it brings to Blender for free. The right column points at the implementing module.

### Boolean & drawing (Grid Modeler · Boxcutter)

| Feature | What it does | Where |
|---------|--------------|-------|
| Modal draw-to-cut | Box / Circle / Polygon / N-gon shapes, drawn directly in the viewport | `operators/draw_cut.py` |
| Cut / Slice / Make / Intersect / Face | DIFFERENCE · split-in-two · UNION · keep-overlap (v1.10) · create an n-gon surface; `Tab` cycles mode | `operators/draw_cut.py` |
| Numeric size entry (v1.10) | Type an exact dimension while drawing to lock the shape's size (radius / extent / segment) | `core/grid.py lock_distance` |
| Knife / zero-depth cut (v1.4) | Score the surface without extruding; restricted to the drawn footprint, not the whole mesh (v1.9) | `core/geometry.py knife_polygon` |
| World-scale grid snap | Camera-independent grid in meters; plane cycles VIEW / SURFACE / EDGES / X / Y / Z; `Shift+←/→` rotates the grid (v1.9) | `core/grid.py`, `core/raycast.py` |
| Grid on selected edges (v1.9) | Edit-Mode draw lays the grid on 1–2 selected edges (Grid Modeler) | `core/decal_math.py basis_from_edge` |
| Live grid density (v1.6) | Adjust grid spacing mid-draw with Ctrl+Wheel + on-screen grid widget | `operators/draw_cut.py`, `ui/draw.py` |
| Live thickness / depth (v1.6) | Drag cutter/extrude depth during the draw with a readout (PgUp/Dn) | `operators/draw_cut.py` |
| Vertex / edge snap | Lock to corner / edge / midpoint of existing geometry; colored cursor | `core/snap.py`, `core/snapping.py` |
| Angle lock | Hold Shift to lock the draw direction to angle steps | `core/grid.py snap_angle` |
| Self-intersection guard | A broken polygon is rejected before the cut | `core/grid.py is_self_intersecting` |
| Multi-object cut | Apply CUT/MAKE to all selected meshes with one cutter | `operators/draw_cut.py` |

### In-draw operations (Boxcutter — v1.4)

| Feature | What it does | Where |
|---------|--------------|-------|
| Inset / extract cut | Offset the drawn loop inward/outward before commit (`-`/`=`) | `core/offset.py offset_polygon` |
| Array during draw | Stamp the in-progress cutter N times along an axis (`A` / `D`) | `core/transform.py array_offset_vector` |
| Mirror during draw | Live mirror of the cutter across a world axis (`M`) | `core/transform.py mirror_axis_flags` |
| Bevel-on-cut | Add an angle-limited bevel to the cut edge at commit (`B`) | `operators/draw_cut.py` |
| Bevelled cutter (v1.10) | Chamfer the cutter so the cut leaves bevelled recess walls (`C`) | `core/geometry.py bevel_cutter` |
| In-plane rotation | Rotate the drawn shape within its plane, live angle in HUD (`,` / `.`) | `core/grid.py rotate_2d` |
| Stamp / repeat | Re-place the previous shape + size with one key (`G`) | `operators/draw_cut.py` |

### Non-destructive workflow (Boxcutter)

| Feature | What it does | Where |
|---------|--------------|-------|
| Live modifier cut | Leave a boolean modifier instead of applying (`N`) | `core/boolean.py` |
| Cutter collection | Cutters kept in "Hardflow Cutters" (wire, parented, render off) | `core/boolean.py stash_cutter` |
| Cutter manager | Select / show-hide / remove cutters; "Apply Cutters (Bake)" | `operators/cutters.py`, `ui/panel.py` |
| Robust booleans (v1.9) | Every cut auto-picks the solver, retries (EXACT→FAST→normal-repair), and reports *why* it failed | `core/boolean.py robust_boolean/choose_solver/mesh_health` |

### Hard Ops tools (Hard Ops — v1.0 / v1.5)

| Feature | What it does | Where |
|---------|--------------|-------|
| Advanced bevel | Interactive (drag = width, wheel = segments) + Weighted Normal; adaptive width + segment count scale to the object (v1.9) | `operators/modifiers.py` |
| Edit-Mode edge bevel (v1.9) | A real on-selection edge bevel when run in Edit Mode, not just a modifier | `core/geometry.py edit_bevel_edges` |
| Mirror | Bisect + clip across the object, the 3D cursor, or the active object (v1.10) | `operators/modifiers.py` |
| Array / Radial / Curve array | Linear array on an axis; N copies around the 3D cursor; array deformed along a selected curve (v1.10) | `operators/array.py`, `core/transform.py` |
| Symmetrize | Mirror one half of the mesh onto the other | `core/geometry.py symmetrize_mesh` |
| Sharpen + presets | Mark sharp by angle + WN; SSharp / CSharp preset tiers | `core/geometry.py SHARPEN_PRESETS` |
| Boolean from selection | Boolean selected meshes with the active object as cutter | `operators/boolean_ops.py` |
| Dice / panel | Grid-slice an object into N pieces along axes | `core/geometry.py dice_mesh` |
| Edge weights / crease | Set/clear bevel-weight + crease on selected edges (Edit Mode) | `operators/hardops.py` |
| Display toggles | Wireframe / sharp-edge / cutter-visibility viewport toggles | `operators/hardops.py` |
| Material helpers | Random viewport colors, copy active material to selection | `operators/hardops.py` |
| Step / taper / knurl | Parametric greeble generators | `core/geometry.py build_steps/build_taper/build_knurl` |
| Modifier-stack manager | N-panel list with move / toggle / apply / remove | `ui/panel.py` |
| Clean | Remove doubles + limited dissolve + delete loose | `core/geometry.py cleanup_mesh` |

### Decals (DECALmachine — v0.7–v0.9 / v1.7)

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

### Assets / kitbash (KitOps — v1.0 / v1.8)

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
| KPACK export (v1.8) | Write a selection to a `.blend` in the library with a preview | `operators/assets.py`, `core/asset.py write_objects_blend` |

### SketchUp-style direct modeling (v1.2 / v1.3 / v1.6)

| Feature | What it does | Where |
|---------|--------------|-------|
| Push/Pull | Raycast a face, drag along its normal to extrude; grid-snap + numeric | `operators/push_pull.py` |
| Offset | Raycast a face, drag to inset its border by a measured distance | `operators/offset.py`, `core/offset.py` |
| Starter primitives (v1.9) | Add a Cube / Plane at the 3D cursor to model on | `operators/construction.py`, `core/geometry.py build_box/build_plane` |
| Construction grid | Drop a wire reference grid at the 3D cursor on XY / XZ / YZ | `operators/construction.py` |
| Guide line (v1.9) | Drop a snappable wire guide line at the cursor (SketchUp guides) | `operators/construction.py`, `core/geometry.py build_line` |
| Loft / bridge (v1.6) | Bridge two drawn profiles into a solid | `core/geometry.py build_loft` |
| Pipe + profiles (v1.6) | Surface-draping pipe; round / square / rect cross-section (`P`) | `operators/pipe.py`, `core/geometry.py build_pipe` |
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
| Pre-cut health warning | N-panel flags broken geometry before you draw + one-click normal fix | `ui/panel.py`, `operators/modifiers.py recalc_normals` |
| Adaptive sizing | Bevel width + segments, cut chamfer, decal offset, drag speed scale to the object | `core/transform.py adaptive_dimension/bevel_segments`, `core/decal.py adaptive_decal_offset` |
| Smart snapping | Nearest-wins vertex/edge disambiguation; raycast skips the live preview | `core/snap.py resolve_snap`, `core/raycast.py` |
| Edge-aligned orientation | Drawing / INSERTs align to the hit face's dominant edge | `core/raycast.py face_edge_tangent`, `core/decal_math.py dominant_tangent` |
| Connected faces | Drawn faces weld onto coincident existing vertices | `core/geometry.py edit_add_face` |

### UX & shared

| Feature | What it does | Where |
|---------|--------------|-------|
| Live placement preview | Decal/asset tools show the real object under the cursor pre-click | `operators/decals.py`, `operators/assets.py` |
| Pie menu | Categorized main pie + Build/Boolean/Modify/Curves sub-pies (Alt+Q) | `ui/pie.py` |
| Header dropdown | 3D-View header menu covering every tool incl. Decals/Assets | `ui/menu.py` |
| N-panel | Tools, snap settings, modifier stack, cutter list, greeble/display rows | `ui/panel.py` |
| HUD measurement | Drawn shape size in meters (Box W×H, Circle r/d, Poly segments) | `ui/draw.py` |
| Customizable keymap | Rebind shortcuts from the standard Blender keymap editor | `keymaps.py` |

## Installation

Blender 4.2+: **Edit > Preferences > Get Extensions > (top-right ⌄) > Install
from Disk** → select the `hardflow` zip.

## Usage

Select a mesh in Object Mode:

- **Alt+Q** → pie menu (all tools)
- **Ctrl+Shift+D** → direct drawing tool

In drawing mode:

| Key | Function |
|-----|-----------|
| Left click | Place point / start-finish shape |
| Enter | Close the POLY shape and apply |
| Backspace | Delete the last POLY point |
| Q / W / E / R | Shape: Box / Circle / Polygon / N-gon |
| [ / ] | Decrease / increase N-gon side count |
| 1 / 2 / 3 / 4 / 5 | Mode: Cut / Slice / Make / Face / Knife |
| ← / → | Drawing plane: VIEW / X / Y / Z |
| X | Toggle world-scale grid snap |
| V | Toggle vertex/edge snap |
| Shift (held) | Lock drawing direction to angle steps |
| N | Toggle non-destructive (live modifier) |
| **- / =** | In-draw inset / extract (offset the loop) |
| **, / .** | In-draw in-plane rotation |
| **A / D** | In-draw array count / array axis |
| **M** | In-draw mirror across a world axis |
| **B** | Toggle bevel-on-cut |
| **G** | Stamp / repeat the previous shape |
| **Ctrl+Wheel** | Live grid density |
| **PgUp / PgDn** | Live cutter / extrude depth |
| Right click / Esc | Cancel |

**Modes:** Cut = boolean DIFFERENCE · Slice = split the object in two · Make =
add geometry (UNION) · Face = create a surface from the drawn shape (not a
boolean) · Knife = score the surface without extruding (zero-depth cut).

**Other tools:** Bevel · Mirror · **Array** · **Radial** · **Symmetrize** ·
**Sharpen** (+ SSharp/CSharp presets) · **Boolean (Selected)** · **Dice/Panel** ·
**Edge Weights** · **Display Toggles** · **Step/Taper/Knurl** greeble ·
**Push/Pull** · **Offset** · **Construction Grid** · **Loft** · **Clean** (mesh
cleanup) · **Pipe** (round/square/rect) / **Cable** (from a line) · **Apply
Cutters** · a **modifier-stack manager** — all in the N-panel. Push/Pull, Offset,
the draw tool, and snapping also work in **Edit Mode** (v1.3).

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
│   ├── offset.py           # polygon inset/offset math, SketchUp Offset (pure 2D)
│   ├── geometry.py         # bmesh build/dice/greeble/loft + Edit-Mode bridge
│   ├── boolean.py          # destructive + non-destructive boolean + fallbacks
│   ├── transform.py        # array / radial / cable-sag / dice / fit math (pure)
│   ├── decal*.py / atlas.py# decal orientation, image library, trim/atlas math
│   ├── asset_lib.py        # .blend kit-library scan (pure)
│   └── asset.py            # append / orient / bind INSERTs + KitOps extras
├── operators/              # user actions
│   ├── draw_cut.py         # main modal draw (cut/slice/make/face/knife + in-draw)
│   ├── modifiers.py        # bevel + mirror + clean + symmetrize + sharpen
│   ├── hardops.py          # dice / edge-weight / display / greeble (Hard Ops v1.5)
│   ├── boolean_ops.py      # boolean from selected objects
│   ├── array.py            # linear + radial array
│   ├── cutters.py          # non-destructive cutter management (apply/select/remove)
│   ├── pipe.py             # pipe (round/square/rect) + sagging cable/rope
│   ├── push_pull.py        # SketchUp Push/Pull (Object + Edit Mode)
│   ├── offset.py           # SketchUp Offset (Object + Edit Mode)
│   ├── construction.py     # wire construction grid + loft/bridge
│   ├── decals.py           # decal placement + library + trim + atlas + bake + v1.7
│   └── assets.py           # INSERT placement + library + mark + material + export
├── ui/                     # GPU drawing, HUD, menus
│   ├── draw.py             # gpu + blf helpers
│   ├── pie.py              # categorized pie (main + Build/Boolean/Modify/Curves)
│   ├── menu.py             # 3D-View header dropdown covering every tool
│   ├── panel.py            # N-panel: tools, settings, modifier stack, cutters
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
