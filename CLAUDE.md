# CLAUDE.md — Hardflow

This file exists so that Claude Code approaches the project with the right
context in every session.

## What the project is

Hardflow is an **open-source (GPLv3) hard-surface boolean modeling** toolkit for
Blender 4.2+. The goal: deliver the core workflows of Grid Modeler, Boxcutter,
and Hard Ops for free. Currently at **v0.1** — the basic architecture is in
place and a handful of features work. The full roadmap is in `ROADMAP.md`.

## FIRST TASK: smoke test inside Blender

This code **has been written and syntax-verified, but has not yet been run in a
live Blender.** Before developing any feature:

1. Install the addon, enable it, and verify it registers without errors.
2. Select a cube in Object Mode → Ctrl+Shift+D → draw a Box → see the Cut work.
3. Try the pie menu (Alt+Q), bevel, mirror, slice, and make modes one by one.
4. Two especially suspect spots: the `temp_override` + `modifier_apply` call in
   `core/boolean.py`, and the geometry/projection math in `_build_and_apply` in
   `operators/draw_cut.py`. These have not been tested at runtime.

If errors come up, fix these first, then move on to the ROADMAP.

## Architecture — an inviolable rule

Layer dependency is **one-directional**:

```
ui  ─┐
     ├─► core      (core NEVER looks upward)
ops ─┘
```

- `core/` is pure logic: it **does not use** `bpy.ops`, `gpu`, or `blf`. The only
  exception: `modifier_apply` inside `core/boolean.py` (a deliberate
  concession).
- `core` must stay testable. A new feature = a pure function in `core` + a thin
  `operator` that calls it.
- UI drawing is gathered in `ui/draw.py`; operators delegate to it.

## File map

| Path | Responsibility |
|-----|-----------|
| `__init__.py` | Registration orchestration, the `_classes` tuple |
| `keymaps.py` | Shortcut registration + preferences rebind UI (`register_keymaps`, `draw_keymap_prefs`); defaults Alt+Q / Ctrl+Shift+D |
| `preferences.py` | Settings + the `get_prefs(context)` accessor |
| `core/raycast.py` | Screen↔3D projection + plane (u,v) (`screen_to_plane`, `view_direction`, `world_to_plane_uv`, `plane_uv_to_world`, `world_to_screen`) |
| `core/grid.py` | World-scale + angle snap, shape points (`snap_world`, `world_grid_segments`, `snap_angle`, `box_points`, `circle_points`) |
| `core/snap.py` | Vertex/edge geometry snap, pure 2D (`nearest_point`, `closest_point_on_segment`, `nearest_on_segments`) |
| `core/geometry.py` | bmesh generation (`build_prism`, `build_face`, `build_pipe`, `estimate_thickness`, `cleanup_mesh`) |
| `core/boolean.py` | boolean + cutter management (`apply_boolean`, `add_boolean`, `duplicate_object`, `stash_cutter`, `cutter_collection`) |
| `operators/draw_cut.py` | Main modal drawing operator (`HARDFLOW_OT_draw`): cut/slice/make/face, plane rotation, measurement HUD |
| `operators/modifiers.py` | Bevel + mirror + clean (`HARDFLOW_OT_bevel/mirror/clean`) |
| `operators/cutters.py` | Non-destructive cutter management (`HARDFLOW_OT_apply_cutters/select_cutter/remove_cutter`) |
| `operators/pipe.py` | Pipe from a line (`HARDFLOW_OT_pipe`) |
| `ui/draw.py` | GPU + blf helpers |
| `ui/pie.py` | Pie menu (`HARDFLOW_MT_pie`) |
| `ui/panel.py` | N-panel: tools, snap settings, cutter list (`HARDFLOW_PT_*`) |
| `tests/test_core.py` | Pure core tests without Blender (`python tests/test_core.py`) |

## Registration rule

Every new class must be added to the `_classes` tuple in `__init__.py`,
otherwise it won't be registered. Keymaps live in `keymaps.register_keymaps()`;
users can rebind them from the standard Blender keymap editor in preferences.

## Blender API constraints (4.2 LTS+ target)

- 2D drawing shader: `'UNIFORM_COLOR'` / `'POLYLINE_UNIFORM_COLOR'`.
  **DO NOT USE `'2D_UNIFORM_COLOR'`** (removed in 3.x).
- `blf.size(font_id, size)` — no legacy dpi parameter.
- `batch_for_shader` primitives: `LINE_STRIP`, `LINES`, `TRIS`, `POINTS`.
  **Do not use `LINE_LOOP` / `TRI_FAN`** (deprecated).
- For context override, use `with context.temp_override(...)`.

## Development loop

For fast iteration without re-zipping, set up a symlink:

```bash
ln -s "$(pwd)" ~/.config/blender/4.2/extensions/user_default/hardflow
```

To load a change in Blender: `F3 > Reload Scripts` or disable/enable the addon.
Keep the System Console open (Window > Toggle System Console).

Note: `bpy` does not run outside Blender; unit tests run inside Blender's Python
or headless via `blender --background --python test.py`. Most `core/` modules can
be tested with bpy mocked out (a deliberate design choice).

## Conventions

- Class names: `HARDFLOW_OT_*` (operator), `HARDFLOW_MT_*` (menu),
  `HARDFLOW_Preferences`.
- Operator `bl_idname`: `mesh.hardflow_*` or `object.hardflow_*`.
- PEP 8, ~90 character lines.
- License GPLv3 — applies to new files too.
