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
[![Version](https://img.shields.io/badge/version-1.2.0-brightgreen.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)

</div>

> **Status — under active development.** The boolean cut loop, world-scale +
> vertex/edge snapping, the non-destructive flow, the decal subsystem, the
> asset/kitbash system, the Hard Ops modeling tools, and the SketchUp-style
> direct-modeling tools are all implemented. The pure-logic core is unit-tested
> (`44/44` passing, no Blender required); live in-Blender verification is
> ongoing. See [ROADMAP.md](ROADMAP.md) for the full roadmap.

## Features

- **Boolean via modal drawing** — Box / Circle / Polygon / N-gon shapes; Cut,
  Slice (split in two), Make (add), and Face (create a surface) modes.
- **World-scale grid snap** — a camera-independent grid that stays consistent in
  meters (Grid Modeler's "absolute size" logic); plane switches with `←/→`
  between VIEW / X / Y / Z.
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
  (bisect + clip). The Hard Ops spirit.
- **Boolean from selection** — boolean the selected meshes using the active
  object as the cutter (Difference / Union / Intersect / Slice), no drawing
  needed; respects the non-destructive flow.
- **Array & Radial array** — a linear Array along a world axis, or a radial array
  of N copies around the 3D cursor (a rotated offset empty drives the modifier).
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
- **Atlasing** — pack every image decal's texture into a single atlas image and
  collapse them onto one shared material (fewer materials / draw calls).
- **Pie menu**, preferences panel, customizable snap settings.

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
| 1 / 2 / 3 / 4 | Mode: Cut / Slice / Make / Face |
| ← / → | Drawing plane: VIEW / X / Y / Z |
| X | Toggle world-scale grid snap |
| V | Toggle vertex/edge snap |
| Shift (held) | Lock drawing direction to angle steps |
| N | Toggle non-destructive (live modifier) |
| Right click / Esc | Cancel |

**Modes:** Cut = boolean DIFFERENCE · Slice = split the object in two · Make =
add geometry (UNION) · Face = create a surface from the drawn shape (not a
boolean).

**Other tools:** Bevel · Mirror · **Array** · **Radial** · **Symmetrize** ·
**Sharpen** · **Boolean (Selected)** · **Push/Pull** · **Offset** ·
**Construction Grid** · **Clean** (mesh cleanup) · **Pipe** / **Cable** (from a
line) · **Apply Cutters** — all in the N-panel.

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
│   ├── raycast.py          # screen <-> 3D projection, plane (u,v)
│   ├── grid.py             # world-scale + angle snap, shape + grid points
│   ├── snap.py             # vertex/edge geometry snap (pure 2D)
│   ├── offset.py           # polygon inset/offset math, SketchUp Offset (pure 2D)
│   ├── geometry.py         # cutter volume, symmetrize, sharpen, cleanup (bmesh)
│   ├── boolean.py          # destructive + non-destructive boolean
│   ├── transform.py        # array / radial-array + cable-sag math (pure)
│   ├── decal*.py / atlas.py# decal orientation, image library, trim/atlas math
│   ├── asset_lib.py        # .blend kit-library scan (pure)
│   └── asset.py            # append / orient / bind INSERTs (bpy-data only)
├── operators/              # user actions
│   ├── draw_cut.py         # main modal drawing operator (cut/slice/make/face)
│   ├── modifiers.py        # bevel + mirror + clean + symmetrize + sharpen
│   ├── boolean_ops.py      # boolean from selected objects
│   ├── array.py            # linear + radial array
│   ├── cutters.py          # non-destructive cutter management (apply/select/remove)
│   ├── pipe.py             # pipe + sagging cable/rope from a line
│   ├── push_pull.py        # SketchUp Push/Pull (drag a face along its normal)
│   ├── offset.py           # SketchUp Offset (inset a face's border)
│   ├── construction.py     # wire construction grid at the 3D cursor
│   ├── decals.py           # decal placement + library + trim + atlas + bake
│   └── assets.py           # INSERT placement + library + mark-as-asset
├── ui/                     # GPU drawing, HUD, menus
│   ├── draw.py             # gpu + blf helpers
│   ├── pie.py              # Hard Ops style pie menu
│   ├── panel.py            # N-panel: tools, settings, cutter list
│   ├── decal_panel.py / decal_library.py   # decal sections
│   └── asset_panel.py      # asset + asset-library sections
└── tests/                  # tests
    ├── test_core.py        # pure core, without Blender (python tests/test_core.py)
    └── test_blender.py     # headless (blender --background --python ...)
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
