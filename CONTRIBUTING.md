# Contributing Guide

## Setup (development)

For a fast iteration loop, link the addon into Blender's extensions folder with a
symbolic link so you don't have to re-zip on every change:

```bash
# Linux/macOS example — adjust the path to your version
ln -s "$(pwd)/hardflow" \
  ~/.config/blender/4.2/extensions/user_default/hardflow
```

To reload inside Blender: with the System Console open, use
`F3 > Reload Scripts`, or disable/enable the addon.

## Testing

`core/grid.py` and `core/snap.py` are deliberately kept free of `bpy`, so the
math layer can run without Blender using plain CPython:

```bash
python tests/test_core.py     # runs standalone, no pytest required
```

For the `bpy`-dependent core (geometry/boolean + bevel/mirror operators), a
headless Blender smoke test:

```bash
blender --background --python tests/test_blender.py
```

When you add a new pure core function, add a test to `tests/test_core.py`; when
you add a `bpy`-dependent building block, add one to `tests/test_blender.py`. The
modal drawing operator (which requires a window/region) is verified by hand, in a
live Blender.

## Architecture rules

1. **Layering is one-directional:** `ui` and `operators` → `core`. `core` never
   depends upward and does not use `bpy.ops`/`gpu`/`blf` (with the sole
   `modifier_apply` exception in boolean.py). This keeps `core` pure and
   testable.
2. **One feature = a pure function in core + a thin operator.** Don't bury the
   logic in the operator.
3. **Add your new class to `_classes` in `__init__.py`.** Otherwise it won't be
   registered.
4. **API compatibility:** the target is Blender 4.2 LTS+. Avoid 3.x-specific
   calls (`2D_UNIFORM_COLOR`, the old dpi signature of `blf.size`, the
   `LINE_LOOP` primitive).

## Project layout

For a feature-by-feature map of which module implements what, see
[docs/features.md](docs/features.md).

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
│   ├── path.py             # freehand-stroke / spline math — RDP, Catmull-Rom (pure)
│   ├── physics.py          # cable gravity-settle relaxation + collision (pure)
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
│   ├── pipe.py             # pipe/cable/sweep — freehand strokes, smooth path, gravity settle, custom profiles, detail along path
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

## PR flow

- One feature/fix = one PR.
- If it maps to an item in ROADMAP.md, check the box.
- If you added a new user action, update the key table in the README.

## Style

- PEP 8, ~90 character lines.
- Operator/class names follow the `HARDFLOW_OT_*`, `HARDFLOW_MT_*` pattern.
- Comments and docstrings must be in English.
