# Hardflow

An open-source hard-surface boolean modeling toolkit — aiming to deliver the
core workflows of Grid Modeler, Boxcutter, and Hard Ops for free under GPLv3.
Compatible with the Blender 4.2+ extension system.

> Under active development. The core cut loop, world-scale + vertex/edge
> snapping, and the non-destructive flow are all working. See ROADMAP.md for the
> full roadmap (including decals).

## Features

- **Boolean via modal drawing** — Box / Circle / Polygon shapes; Cut, Slice
  (split in two), Make (add), and Face (create a surface) modes.
- **World-scale grid snap** — a camera-independent grid that stays consistent in
  meters (Grid Modeler's "absolute size" logic); plane switches with `←/→`
  between VIEW / X / Y / Z.
- **Multi-object** — apply CUT/MAKE to all selected meshes with a single cutter.
- **Pipe** — a round-profile pipe from a drawn line; mesh cleanup via **Clean**
  (Hard Ops style).
- **Vertex / edge snap** — lock the drawing point to the corner / edge / edge
  midpoint of existing geometry; colored cursor feedback.
- **Angle lock** — hold Shift to lock the drawing direction to 15° (adjustable)
  steps.
- **Non-destructive mode** — instead of applying the boolean, leave a live
  modifier; keep cutters in a separate collection (the Boxcutter spirit).
- **Advanced bevel** — interactive (drag = width, wheel = segments), with profile
  + angle limit + width-type + **Weighted Normal** (clean shading); mirror
  (bisect + clip). The Hard Ops spirit.
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
| Q / W / E | Shape: Box / Circle / Polygon |
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

**Other tools:** Bevel · Mirror · **Clean** (mesh cleanup) · **Pipe** (pipe from
a line) · **Apply Cutters** — all in the N-panel and the pie menu.

**Snap cursor colors:** 🟡 corner · 🟢 edge midpoint · 🔵 on edge.

## Architecture

```
hardflow/
├── blender_manifest.toml   # extension identity (4.2+)
├── __init__.py             # registration orchestration + keymap
├── preferences.py          # settings + get_prefs() accessor
├── core/                   # pure logic (UI-independent, testable)
│   ├── raycast.py          # screen <-> 3D projection, plane (u,v)
│   ├── grid.py             # world-scale + angle snap, shape points
│   ├── snap.py             # vertex/edge geometry snap (pure 2D)
│   ├── geometry.py         # cutter volume generation via bmesh
│   └── boolean.py          # destructive + non-destructive boolean
├── operators/              # user actions
│   ├── draw_cut.py         # main modal drawing operator (cut/slice/make/face)
│   ├── modifiers.py        # smart bevel + mirror + clean
│   ├── cutters.py          # non-destructive cutter management (apply/select/remove)
│   └── pipe.py             # pipe generation from a line
├── ui/                     # GPU drawing, HUD, menus
│   ├── draw.py             # gpu + blf helpers
│   ├── pie.py              # Hard Ops style pie menu
│   └── panel.py            # N-panel: tools, settings, cutter list
└── tests/                  # tests
    ├── test_core.py        # pure core, without Blender (python tests/test_core.py)
    └── test_blender.py     # headless (blender --background --python ...)
```

`core/grid.py` and `core/snap.py` are deliberately kept free of `bpy`, so the
math layer is tested with plain CPython (`python tests/test_core.py`).

Layering rule: `ui` and `operators` → may depend on `core`; `core` **never**
depends on `ui`. A new feature usually means adding a pure function to core plus
a thin operator that calls it.

## License

GPLv3. Every Blender addon distributed with `bpy` is effectively GPL in
practice, and this project is no exception. See the LICENSE file for the full
license text.
