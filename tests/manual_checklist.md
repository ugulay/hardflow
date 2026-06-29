# Manual interaction checklist — Hardflow

The headless suite (`blender --background --python tests/test_blender.py`) covers
every *non-modal* code path: the bmesh builders, the boolean/modifier operators,
decals, assets, and registration. What it **cannot** cover is the modal tools,
which need a real viewport region (mouse, draw handler, HUD). This file is the
click-through checklist for those — run it once after installing the addon.

Pure math: `python tests/test_core.py`. Headless runtime: the command above.
Everything here is what's left: **the interactive tools.**

---

## 0. Install & register

- [ ] Install the addon (or symlink — see `CLAUDE.md` → Development loop) and enable it.
- [ ] No errors in the System Console on enable (`Window ▸ Toggle System Console`).
- [ ] N-panel shows a **Hardflow** tab; the 3D-View header shows a **Hardflow** menu.
- [ ] `Alt+Q` opens the pie; `Ctrl+Shift+D` starts a draw.

> Suspect spots flagged in `CLAUDE.md`: the `temp_override` + `modifier_apply`
> in `core/boolean.py`, and the projection math in `_build_and_apply`
> (`operators/draw_cut.py`). If a cut misbehaves, look there first.

---

## 1. Boolean draw (baseline — confirms projection works)

Setup: add a default cube, stay in Object Mode, keep it selected/active.

- [ ] `Ctrl+Shift+D` → draw a **Box** → the rectangle previews on the grid, the
      HUD shows a live size in metres, and on the second click the cube is **cut**.
- [ ] HUD snap state toggles with `X` (grid) and `V` (vertex/edge).
- [ ] `< >` cycles the projection plane (VIEW / X / Y / Z); the grid re-orients.
- [ ] `Esc` / right-click cancels cleanly (no leftover cutter, no console spam).

---

## 2. Build ▸ sketch a face (the SketchUp draw-then-pull loop)

These reuse the draw operator in **FACE** mode — they make real geometry, not a
boolean.

- [ ] N-panel ▸ **Build (SketchUp)** ▸ **Rectangle** → two clicks → a new flat
      face object appears (it becomes the active object).
- [ ] **Line** → click several points → `Enter` closes them into a face.
- [ ] **Circle** and **N-gon** likewise produce a face ( `[` `]` change N-gon sides).

---

## 3. Push/Pull ⭐ (modal — the highest-risk new path)

Setup: select a mesh with clean faces (a cube, or the face from step 2). Object
Mode. **No generative modifiers** (documented limitation — index targets the base
mesh).

- [ ] N-panel ▸ Build ▸ **Push/Pull** (or pie ▸ Build ▸ Push/Pull).
- [ ] Hovering a face **highlights** it (orange fill + outline); the HUD says
      "Hover a face…".
- [ ] **Click** a face → it locks (fill turns orange-committed), HUD switches to
      "Distance: … m".
- [ ] **Drag** → the distance updates and **snaps to the grid** (`grid_world`);
      toggling `X` turns snap off → free distance.
- [ ] **Type a number** (top row or numpad), `.` for decimals, `-` to flip
      direction → HUD shows `[typing …]`; `Backspace` edits.
- [ ] **Click again / `Enter`** → the face extrudes by that amount. Pull (+) and
      push (−) both work; the side walls are created.
- [ ] `Esc` before confirming cancels with no geometry change.
- [ ] Result survives **Undo** (`Ctrl+Z`) in one step.

Watch for: wrong extrude direction on a **rotated/scaled** object (the world→local
vector transform in `_commit`), and any `IndexError` in the console (should be
guarded).

---

## 4. Offset (modal)

Setup: same as Push/Pull.

- [ ] N-panel ▸ Build ▸ **Offset**. Hover highlights a face (green tint).
- [ ] Click to lock → drag (or type) sets **Thickness**, grid-snapped; `X` toggles snap.
- [ ] Confirm → an inset ring of faces appears inside the picked face.
- [ ] `Esc` cancels; `Ctrl+Z` reverts in one step.

---

## 5. Construction grid (non-modal, but visual)

- [ ] N-panel ▸ Build ▸ **Construction Grid** → a wire grid appears at the 3D
      cursor, drawn in front, hidden from render.
- [ ] The redo panel (bottom-left) changes **Plane** (XY/XZ/YZ), **Half Extent**,
      **Spacing** live.

---

## 6. Menu system (pie + header dropdown)

- [ ] `Alt+Q` → main pie. Each category slot (**Build ▸ / Boolean ▸ / Modify ▸ /
      Curves ▸**) opens its sub-pie; the sub-pie's **◂ Back** returns to the main pie.
- [ ] Direct slots (Cut / Bevel / Mirror / Clean) fire immediately.
- [ ] Header ▸ **Hardflow** dropdown lists every category **including Decals and
      Assets**; submenus open and the entries run.
- [ ] Header ▸ Hardflow ▸ **Pie Menu** opens the pie.
- [ ] Disable then re-enable the addon → no duplicate "Hardflow" entry in the
      header (the hook is removed on unregister).

---

## 7. Regression sweep (existing tools, quick)

- [ ] Bevel, Mirror, Array, Radial, Symmetrize, Sharpen, Clean each add the
      expected modifier / change.
- [ ] Pipe and Cable draw along a surface.
- [ ] Decals: place one on a surface; it sticks (shrinkwrap) and shows its material.
- [ ] Assets: place an INSERT from a `.blend`; mark an object as an asset.

---

When every box is ticked, update the live-verification note in `CLAUDE.md`
(FIRST TASK) and the smoke-test memory.
