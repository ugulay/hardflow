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
- [ ] **Live cutter cage:** while drawing (after the first click), a **wireframe
      3D volume** of the cutter is shown through the model (BoxCutter-style depth
      preview), updating as you move. It disappears on commit/cancel — no
      leftover `hf_preview` object in the outliner.
- [ ] **Slice / Make / Face** (`2`/`3`/`4`) also show the live cage; FACE shows
      the flat face outline.
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
- [ ] **Live preview:** while dragging/typing, the **real mesh extrudes live**
      (not just an outline) and follows the distance back and forth.
- [ ] **Click again / `Enter`** → the extrude is kept exactly as previewed. Pull
      (+) and push (−) both work; the side walls are created.
- [ ] `Esc` before confirming cancels with **no geometry change** (the live
      preview is rolled back to the original mesh — verify vert/face counts match).
- [ ] Result survives **Undo** (`Ctrl+Z`) in one step.

Watch for: wrong extrude direction on a **rotated/scaled** object (the world→local
vector transform in `_commit`), and any `IndexError` in the console (should be
guarded).

---

## 4. Offset (modal)

Setup: same as Push/Pull.

- [ ] N-panel ▸ Build ▸ **Offset**. Hover highlights a face (green tint).
- [ ] Click to lock → drag (or type) sets **Thickness**, grid-snapped; `X` toggles snap.
- [ ] **Live preview:** the inset ring appears and resizes live in the real mesh
      as you drag/type.
- [ ] Confirm → the inset is kept; `Esc` rolls the mesh back with no change;
      `Ctrl+Z` reverts in one step.

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
- [ ] Decals: place one on a surface; it sticks (shrinkwrap) and shows its material.
- [ ] Assets: place an INSERT from a `.blend`; mark an object as an asset.
- [ ] **Singular-matrix guard** (hardening, `inverted_safe`): scale an object to
      **0 on one axis** (e.g. `S X 0`), then run **Cut**, **Push/Pull**, **Offset**,
      and **Array** on it. The tools must report/no-op gracefully — **no
      `ValueError: matrix does not have an inverse`** in the console.
- [ ] **Modal handler guard:** if a draw/Push/Pull/Offset/Pipe modal ever fails to
      start, the viewport must not keep drawing a ghost HUD/cage afterwards (no
      orphaned draw handler).

---

## 8. Pipe & Cable ⭐ (burying fix + drape + live preview)

Setup: a cube in Object Mode. The original bug: the tube sank halfway into the
surface and straight segments cut through corners (see the v1.2 screenshot).

- [ ] N-panel/menu ▸ Curves ▸ **Pipe**. As you click points along a face, a
      **real round tube previews live** (not just a 2D line).
- [ ] **Burying fix:** the tube **rests ON the surface** — its lower edge touches
      the face, it does not sink in. `Ctrl+Wheel` adds extra clearance; `Wheel`
      changes radius and the lift tracks it (still never buried).
- [ ] **Drape (follow):** with **Follow ON** (HUD), draw a pipe from the **top
      face across the edge onto a side face** → the tube **wraps the corner and
      hugs the surface** instead of cutting straight through. Press **`F`** to
      toggle Follow OFF → the same path goes straight again (for comparison).
- [ ] `Enter` commits the tube exactly as previewed; `Esc` discards it (no
      leftover `Hardflow_Pipe` object).
- [ ] **Cable:** Curves ▸ **Cable**. Anchors on a vertical face → the rope
      **hangs in a sag** clear of the wall (not buried). `Shift+Wheel` changes
      sag, `Wheel` radius. Live preview + `Enter`/`Esc` behave as above.

---

---

## 9. In-draw operations ⭐ (v1.4 — on the draw modal)

Setup: a cube, Object Mode, `Ctrl+Shift+D`.

- [ ] **`Tab`** cycles the boolean mode (Cut→Slice→Make→Intersect→Face→Knife),
      **Shift+Tab** reverses; the HUD's "Mode" updates. (The number row no longer
      switches mode — it types a size, below.)
- [ ] **Intersect** mode (Tab to it, or menu ▸ Boolean ▸ Intersect): draw a box →
      only the part of the object **inside** the drawn volume remains.
- [ ] **Knife** mode: drawing a box scores the surface (edges added, no boolean /
      no volume cage). In Object Mode it knifes the active mesh; select a face
      first for a contained score.
- [ ] **Numeric size** ⭐ — after the first click, **type a number** → the shape
      locks to that exact size (radius / extent / segment length) in metres; the
      HUD shows `size … m (typing)`. `Backspace` edits, `.` (or numpad `.`) is the
      decimal; moving the mouse rotates the fixed-size shape around the anchor.
      A second click commits at the typed size. Works on the SURFACE/EDGES/XYZ
      planes too (size is measured in the plane's metres).
- [ ] `-` / `=` change **inset** (the loop shrinks/grows before commit); HUD shows
      `inset … m`.
- [ ] `,` / `.` **rotate** the shape in-plane (when not mid-number); HUD shows
      `rot …°`.
- [ ] `A` cycles **array count** (1→6), `D` cycles the **array axis** (X/Y/Z) →
      the cage shows N stamped copies; commit bakes them into one cutter.
- [ ] `M` cycles a live **mirror** across a world axis (off→X→Y→Z).
- [ ] `B` toggles **bevel-on-cut** → after a CUT the cut edge is chamfered
      (an `HF_CutBevel` modifier on the target).
- [ ] `Ctrl+Wheel` changes **grid density** live (the visible grid re-spaces);
      `PgUp`/`PgDn` set an explicit **cutter depth** (HUD `depth … m`, `grid … m`).
- [ ] After a commit, `G` **stamps** the previous shape+params again.

---

## 10. Edit Mode (v1.3)

Setup: enter Edit Mode on a cube.

- [ ] **Push/Pull** with face(s) selected → drags the selection along its averaged
      normal (live extrude in the edit-mesh); `Esc` rolls back.
- [ ] **Offset** with face(s) selected → insets them live; `Esc` rolls back.
- [ ] **Draw** (`Ctrl+Shift+D`): MAKE/FACE adds an n-gon into the mesh;
      CUT/SLICE/KNIFE scores the selected face. Vertex/edge snap tracks the
      *live* edit-mesh.
- [ ] **Edge Weight** (`mesh.hardflow_edge_weight`, via menu/F3) sets bevel
      weight / crease on the selected edges.

---

## 11. Hard Ops parity (v1.5) & Grid Modeler extras (v1.6)

- [ ] N-panel ▸ **Dice** grid-slices the object into panels (redo panel sets X/Y/Z).
- [ ] **Modifier Stack** sub-panel lists modifiers with show/move/apply/remove.
- [ ] Greeble row: **Steps / Taper / Knurl** drop a generated object at the cursor.
- [ ] Display row: **Wire / Sharp / Cutters** toggles; **Random Colors** /
      **Copy Mat** behave.
- [ ] Sharpen redo panel offers **WN / SSharp / CSharp** presets.
- [ ] Pipe: `P` cycles **Round / Square / Rect** cross-section (square/rect build a
      swept mesh tube).
- [ ] Build ▸ **Loft**: select two profile objects (e.g. two FACE shapes with the
      same vertex count) → bridges them into a solid.

---

## 12. DECALmachine (v1.7) & KitOps (v1.8) extras

- [ ] Decal list ▸ per-item **Match** (NODE_MATERIAL icon) tunes the decal to the
      target's material; **Conform** (shrinkwrap icon) trims faces over gaps.
- [ ] Decal ▸ **Create from High-poly**: select a high-poly source + an active
      UV'd plane → bakes a normal map into the library.
- [ ] Decal Library thumbnails have **rename / delete** buttons that edit the file.
- [ ] Assets: enable **Auto Scale** + **Insert Grid Snap**, place an INSERT →
      it fits the target feature size and snaps to the grid / existing anchors.
- [ ] Assets ▸ **Material INSERT** applies a `.blend`'s material to the selection;
      **Export INSERT** writes the selection to the asset-library folder.

---

## 13. Surface-modeling smartness (v1.9 follow-ups)

Setup: Edit Mode on a face whose edges have clearly different lengths (e.g. a
4 × 1 rectangle).

- [ ] **EDGES grid plane — deterministic main axis:** select two edges of
      different length, start a draw (`Ctrl+Shift+D`) → the grid lays on the
      selection with its **main axis along the LONGER edge**, regardless of which
      edge you selected first (`best_edge_pair`). `Shift+←/→` still spins it.
- [ ] **Overlap-accurate knife footprint:** on a single large face, `5` (Knife),
      draw a **thin score that crosses the whole face** → only that face is
      scored; the score does **not** reach distant parts of the mesh, and a
      crossing score is no longer dropped (it used to fall back to slicing every
      face).

> **Pending (not yet implemented — verify in the same pass once added; see
> `ROADMAP.md`):** `Ctrl+Click` to set the 2-edge plane's main edge manually,
> and a pixel-accurate `knife_project` that clips the score to the exact drawn
> outline (today a single large face still scores a full-width line).

---

When every box is ticked, update the live-verification note in `CLAUDE.md`
(FIRST TASK) and the smoke-test memory.
