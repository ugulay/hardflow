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

## PR flow

- One feature/fix = one PR.
- If it maps to an item in ROADMAP.md, check the box.
- If you added a new user action, update the key table in the README.

## Style

- PEP 8, ~90 character lines.
- Operator/class names follow the `HARDFLOW_OT_*`, `HARDFLOW_MT_*` pattern.
- Comments and docstrings must be in English.
