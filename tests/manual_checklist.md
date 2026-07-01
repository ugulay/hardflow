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
      3D volume** of the cutter is shown through the model (non-destructive depth
      preview), updating as you move. It disappears on commit/cancel — no
      leftover `hf_preview` object in the outliner.
- [ ] **Cage dirty-check (perf, regression):** the cage must still update when it
      *should*, now that redundant rebuilds are skipped (`_preview_signature`).
      Confirm the cage tracks the cursor while dragging, and refreshes on each of:
      `[`/`]` sides, `-`/`=` inset, `,`/`.` rotate, `A`/`D` array, `M` mirror,
      `PgUp`/`PgDn` depth, `O` orient, `C` bevelled cutter, and **after an
      orbit/zoom**. With `J` live-boolean on, the real cut result must update too.
- [ ] **Slice / Make / Face** (`2`/`3`/`4`) also show the live cage; FACE shows
      the flat face outline.
- [ ] HUD snap state toggles with `X` (grid) and `V` (vertex/edge).
- [ ] `< >` cycles the projection plane (VIEW / X / Y / Z); the grid re-orients.
- [ ] `Esc` / right-click cancels cleanly (no leftover cutter, no console spam).

---

## 2. Build ▸ sketch a face (the draw-then-pull loop)

These reuse the draw operator in **FACE** mode — they make real geometry, not a
boolean.

- [ ] N-panel ▸ **Build** ▸ **Rectangle** → two clicks → a new flat
      face object appears (it becomes the active object).
- [ ] **Line** → click several points → `Enter` closes them into a face.
- [ ] **Circle** and **N-gon** likewise produce a face ( `[` `]` change N-gon sides).

---

## 3. Push/Pull ⭐ (modal — the highest-risk new path)

Setup: select a mesh with clean faces (a cube, or the face from step 2). Object
Mode. Generative modifiers (subdivision, etc.) now work **best-effort** — the hit
maps to the nearest base face (`geometry.nearest_face_to_point`); exact for
deform-only modifiers, approximate for array/mirror (the base face can sit away
from the visible copy).

- [ ] **Pick through a modifier** ⭐ — add a **Subdivision Surface** modifier to a
      cube, run Push/Pull, hover the rounded surface → a base face still
      highlights and push/pull works (the extrude feeds back through the modifier).

> Push/Pull and Offset now share `operators/face_tool._FaceDragModal`. Behavior
> is unchanged, so re-running §3 and §4 in full is the regression check for that
> refactor — watch for any console error on invoke (a registration / MRO issue).

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
- [ ] **Clean extrude (fix):** push/pull a cube's top face out in **Object Mode**,
      then check Edit Mode — there is **no leftover interior face** at the old
      level (object-mode extrude used to leave one). Headless:
      `test_extrude_keep_original_vs_clean`.
- [ ] **`C` Copy** ⭐ — press `C` while locked (HUD shows `(copy)` / `C copy ON`):
      the extrude now **keeps the starting face**, stacking a new volume on it
      (Ctrl push/pull copy). Press `C` again → back to clean extrude. Works in
      Object and Edit Mode.
- [ ] **`R` repeat** ⭐ — after one push/pull, run the tool again, lock another
      face, press `R` → it re-applies the **last distance** (HUD shows
      `R repeat <m>`). `Enter` keeps it.
- [ ] **Vertex/edge inference** ⭐ — with snap ON (`X`), drag a face until its
      height lines up with **another feature's vertex or edge-midpoint** (e.g. push
      a boss down to the base level): the distance **snaps to that height** and the
      HUD shows `-> on geometry`. Off-feature, it falls back to the grid. Skipped on
      meshes over 50k verts. Core covered by `test_snap_to_candidates`.

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
- [ ] **`R` repeat** ⭐ — after one offset, run the tool again, lock another face,
      press `R` → it re-applies the **last thickness** (HUD shows `R repeat <m>`).
- [ ] **`E` → extrude (recess/panel)** ⭐ — with an inset set, press `E`: the HUD
      switches to **Depth** and dragging now extrudes the **inner** face along the
      normal — drag **in** for a recessed panel, **out** for a raised one (the
      outer border stays put). Numeric + `X` snap work; the depth also has
      **vertex/edge inference** (HUD `-> on geometry`). `Enter` keeps both; `Esc`
      before confirming rolls back to the original mesh. Headless:
      `test_inset_extrude_faces_recess`.

---

## 5. Construction grid (non-modal, but visual)

- [ ] N-panel ▸ Build ▸ **Construction Grid** → a wire grid appears at the 3D
      cursor, drawn in front, hidden from render.
- [ ] The redo panel (bottom-left) changes **Plane** (XY/XZ/YZ), **Half Extent**,
      **Spacing** live.

---

## 6. Menu system (pie + header dropdown)

- [ ] `Alt+Q` → main pie. The category slots (**Build ▸ / Boolean ▸ / Curves ▸**)
      open their sub-pie; the sub-pie's **◂ Back** returns to the main pie.
- [ ] The direct slots (Cut / Push/Pull / Offset / Apply Cutters / Edge Bevel)
      fire immediately.
- [ ] Header ▸ **Hardflow** dropdown lists every category (Build / Boolean /
      Curves / Display & Mesh, **plus Decals and Assets**); submenus open and the
      entries run.
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
- [ ] `C` toggles **bevelled cutter** → the CUT leaves chamfered *recess walls*
      (the cutter mesh itself is bevelled, distinct from `B`'s target-edge bevel).
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

## 11. Mesh-editing parity (v1.5) & modeling extras (v1.6)

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

## 12. Decal (v1.7) & asset/insert (v1.8) extras

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

## 14. Gizmos ⭐ (v1.10 — viewport handles)

Registration is covered headless (`test_gizmos_registered`, plus a live GUI
check that the 6 tools land in the right toolbar mode-lists); the **drag
interactions** below need a real viewport.

### Always-on persistent gizmos (N-panel toggle)

Setup: a mesh in Object Mode. N-panel ▸ Hardflow ▸ **Gizmos** sub-panel.

- [ ] **Always-On Gizmos** off by default → no Hardflow handles in the viewport.
- [ ] Tick **Always-On Gizmos** → the per-kind toggles activate; **Move** (arrows)
      and **Rotate** (dials) show on the active object by default; **Scale** off.
- [ ] **Move** arrows drag the object along world X/Y/Z (wraps `transform.translate`
      — snapping, numeric entry, `Shift`/`Ctrl` all work as in the native gizmo).
- [ ] **Rotate** dials spin about world X/Y/Z (`transform.rotate`); the angle HUD shows.
- [ ] **Scale** (tick it) — box-tipped arrows resize per axis (`transform.resize`).
- [ ] Handles **follow the active object** when you select a different mesh and
      stay put as you orbit (placed at the object origin).
- [ ] **Bevel Width** (tick it, Object Mode): a cyan arrow; drag it → an `HF_Bevel`
      modifier appears and its **width tracks the drag** (drag from zero creates it;
      drag again only adjusts — no duplicate modifier). Header shows the value.
- [ ] **Push/Pull** (tick it) shows **only in Edit Mode** with face(s) selected:
      an orange arrow on the selection's average normal. Drag → the faces **extrude
      live** along the normal (grid-snapped; `Ctrl` inverts snap). Release keeps it;
      right-click/Esc mid-drag rolls the mesh back. The arrow does **not** drift
      while dragging (axis is frozen at grab).

### Workspace Tools (toolbar, press `T`)

- [ ] Below the built-in transform tools, a Hardflow group appears: **Move /
      Rotate / Scale / Push/Pull / Bevel** (Object Mode).
- [ ] Picking **Hardflow Move/Rotate/Scale/Bevel** shows that single gizmo set
      (same behaviour as the toggles above) without enabling the always-on panel.
- [ ] **Hardflow Push/Pull** (Object Mode tool): click-drag a face runs the
      raycast modal `mesh.hardflow_push_pull` (hover-pick + drag, as in section 3).
- [ ] In **Edit Mode** the toolbar shows **Hardflow Push/Pull** with the drag-arrow
      gizmo (selected faces).
- [ ] Disable/re-enable the addon → tools and gizmos unregister with no console
      errors and no orphaned toolbar entries.

---

## 15. Polyline Trim parity ⭐ (new — Blender native Polyline Trim workflow)

Setup: a cube, Object Mode, selected/active.

- [ ] **Double-click to close** — `Ctrl+Shift+D`, press `E` (Polygon), click ≥3
      points, then **double-click** → the polyline closes and the cut commits
      (previously needed `Enter`/`Z`). The triggering second click must not leave a
      stray extra point.
- [ ] **Menu/pie entry** — N-panel/header ▸ Boolean ▸ **Polyline Trim** starts the
      draw already in POLY + Cut; **Polyline Add** starts POLY + Make. `Alt+Q` ▸
      Boolean ▸ has a **Polyline Trim** slot (replaced the old Circle Cut slot;
      circle is still reachable in the header menu / by pressing `W` mid-draw).
- [ ] **Join mode** — `Tab` to **Join** (between Make and Intersect), draw a shape →
      a **separate solid object** (`Hardflow_Solid`) is created, with **no boolean**
      on the target (the target is untouched). In Edit Mode, Join adds an n-gon face
      into the active mesh (documented best-effort).
- [ ] **Solver choice** — the draw operator exposes a **Solver** property
      (Default / Exact / Fast / Manifold; Default defers to the preference). The
      reliable global control is Preferences ▸ **Boolean Solver**, which now lists
      **Manifold**. Set it to each value and confirm a cut still succeeds.
- [ ] **Manifold safety** — set the preference (or op) solver to **Manifold** on a
      Blender **< 4.5**: the cut must fall back to **Exact silently** (no error) —
      `core/boolean._coerce_solver`. On 4.5+ the Manifold solver runs.
- [ ] **Project orientation** — in a **perspective** view, press **`O`** mid-draw
      (HUD shows `project`) and cut a polyline through a tall object: the cut
      **tapers along the camera rays** (a frustum), not a straight prism. Press `O`
      again → `Fixed` → straight cut. In an **orthographic** view the two are
      identical (parallel rays). The headless suite covers the taper geometry
      (`test_build_prism_project_taper`).

---

## 16. Edge Bevel ⭐ (object-mode, new — bevel an edge without Edit Mode)

Setup: a cube in Object Mode, selected/active.

- [ ] Build menu ▸ **Edge Bevel** (or F3 → "Hardflow Edge Bevel").
- [ ] **Hover** near an edge → that **edge highlights** (a line; the HUD says
      "Hover an edge…"). Moving to a different edge of the face re-picks the
      nearest one.
- [ ] **Click** an edge → it locks (orange), HUD switches to "Width … Segments 2".
- [ ] **Drag right** → the edge **bevels live**, wider with distance (grid-snapped;
      `X` toggles snap). **Type a number** for an exact width.
- [ ] **`[` / `]`** decrease / increase **segments** (1–12) → a chamfer becomes a
      rounded bevel; the preview updates.
- [ ] **`L` loop** ⭐ — on a **subdivided / grid** mesh (a plain cube has no loops),
      lock an edge and press `L`: the bevel expands to the whole **edge loop** (HUD
      shows `loop xN`). On a plain cube it stays a single edge. Core covered by
      `test_edge_loop`.
- [ ] **Enter / click** keeps the bevel; **Esc** rolls the mesh back to the
      original (no change). `Ctrl+Z` reverts in one step.
- [ ] **`R` repeat** — run again on another edge, press `R` → last width.
- [ ] **`S` Smart Bevel** ⭐ (EXPERIMENTAL) — lock an edge, drag a width, press
      `S`: the HUD shows `SMART t=0.5` and the preview adds **support / holding
      loops** flanking the bevel; **`-` / `=`** lower / raise **tightness** (loops
      hug the bevel harder). Add a **Subdivision** modifier and confirm the bevel
      stays crisp (vs. soft with Smart off). Watch for: support loops landing in
      the wrong spot or a T-junction on a non-quad flank — this is the "tune live"
      caveat; headless only checks that Smart never *removes* geometry
      (`test_smart_bevel_edges`).
- [ ] **N-panel ▸ Cutter Options ▸ Topology** — enabling **Smart Edge Bevel**
      makes the tool start with `SMART` already on; enabling **Re-quad Cut N-gons**
      then drawing a **Cut** (§1) leaves the cut faces re-quadded (no 5+-gons) and
      **Apply Cutters** does the same when baking live booleans. Both default off,
      so the normal cut/bevel result is unchanged until toggled
      (`test_boolean_cut_ngon_cleanup_pipeline`).
- [ ] Headless geometry is covered by `test_nearest_edge_on_face` +
      `test_bevel_object_edges` (+ `test_smart_bevel_edges`); the modal/raycast
      pick needs this GUI pass.

Watch for: picking the wrong edge (the raycast→nearest-edge mapping), and any
console error on a non-manifold/curved face.

## 17. Loop Cut ⭐ (object-mode, new — insert an edge loop without Edit Mode)

Setup: a **subdivided / grid** mesh in Object Mode (a plain cube only has band
loops — still works, but a grid shows it best).

- [ ] Build menu ▸ **Loop Cut** (or F3 → "Hardflow Loop Cut").
- [ ] **Hover** an edge → it highlights; HUD says "Hover an edge…".
- [ ] **Click** → an **edge loop is inserted** through that edge's ring (live), HUD
      shows "Loop Cut  Cuts 1".
- [ ] **`[` / `]`** (or type a number) → **more loops** at once (evenly spaced);
      the preview updates.
- [ ] With **Cuts 1**, **drag left/right** → the loop **slides along its ring**
      (HUD shows `slide ±NN%`); the whole loop moves together (no zig-zag). Setting
      Cuts > 1 clears the slide. Headless `test_loop_cut_slide`; the slide math is
      live-verified in Blender 5.1.2.
- [ ] **Enter / click** keeps the loop(s); **Esc** rolls the mesh back. `Ctrl+Z`
      reverts in one step.
- [ ] On a **plain cube**, clicking a top edge inserts a band loop around the cube
      (no crash). Headless: `test_loop_cut` (+ `edge_ring`).

Watch for: a ring that stops early on non-quad faces (expected), and any console
error on n-gons / triangles.

---

## 18. v1.12 / trailing-v1.9 completions ⭐ (new)

**Offset in-plane thickness inference** (Object Mode; §4 setup, but on a face that
has a *coplanar* feature — e.g. a face with an interior vertex/hole, or run Offset
once then Offset again so the prior inset edge is a coplanar reference):
- [ ] Lock a face, drag the inset → as the border passes a coplanar vertex/edge the
      thickness **snaps to it** and the HUD shows `-> on geometry`; grid snap is the
      fallback. Pure `test_inset_inference_candidates` + headless
      `test_offset_inference_projection`.

**Draw tool ▸ Ctrl+Click set main edge** (Edit Mode, EDGES plane):
- [ ] Select 2+ edges, launch the draw tool → it starts on **EDGES**; the grid main
      axis follows the longest edge. HUD plane reads `EDGES (Ctrl+Click = set main)`.
- [ ] **Ctrl+Click** a different selected edge → the grid **re-orients** so that edge
      is the main axis (HUD bit `main edge set`). Headless
      `test_capture_edges_basis_forced_main`.

**Draw tool ▸ `H` move grid origin** (any non-VIEW plane):
- [ ] Press **`H`** over a point → the visible snap grid **re-anchors** there (HUD bit
      `grid origin set`); snapping now falls on the new lattice. **`H`** again reverts.
      Cycling the plane (`←/→`) also clears it.

**Draw tool ▸ KNIFE = pixel-accurate `knife_project`** (Object Mode):
- [ ] KNIFE mode, draw a shape over a face → the score follows the **exact drawn
      outline** (not a full-width line across the face). The temporary
      `HF_KnifeCutter` is removed and the object stays active in Object Mode.
      Live-verified in Blender 5.1.2 (`_knife_project_object`).
- [ ] Draw with the plane **edge-on** to the view (or in a context with no region) →
      it **falls back** to the footprint knife without error.

## 19. v1.13 build/boolean expansion ⭐ (new)

**Build primitives** (Object Mode, N-panel ▸ Build):
- [ ] **Cylinder / Cone / Sphere / Tube** each drop a clean solid at the 3D cursor,
      selected + active. The redo panel exposes radius / height / segments (Tube also
      inner-radius); changing them rebuilds the primitive.

**Draw tool ▸ new shapes** (`Q/W/E/R/T/Y/U`):
- [ ] **`T` Slot** draws a stadium (rounded-rectangle) from two corners; the caps sit
      on the short sides; HUD reads `Slot: W x H m`.
- [ ] **`Y` Star** draws an n-pointed star from a center drag; `[ ]` changes the point
      count; HUD reads `Star: N points`.
- [ ] **`U` Arc** draws a filled pie sector; `[ ]` grows/shrinks the **sweep angle**
      (15° steps); HUD reads `Arc: D deg`. Each shape commits a valid boolean cutter.

**Draw tool ▸ SURFACE plane on angled faces** (fix):
- [ ] On a **non-rectangular angled face** (e.g. a boolean-cut slope), `←/→` to the
      SURFACE plane and start a Box near one of the face's edges → the box's edges
      line up with the **edge you clicked near** (not rotated at an odd angle).
- [ ] Start the box near a **different** edge of the same face → the box now follows
      **that** edge instead. Decal / asset placement still align to the longest edge.

**N-panel ▸ Boolean Draw** — Intersect / Join / Knife buttons and the
Circle / N-gon / Slot / Star / Arc shape rows each launch the draw tool in the
right mode/shape.

**Live boolean preview** (`J`, Cut/Make/Intersect):
- [ ] Enable **Cutter Options ▸ Live Boolean Preview** (or press **`J`** while drawing)
      → the target shows the **actual cut result** live as you move/draw, not just the
      wire cage (HUD bit `live boolean`).
- [ ] **Commit** → the temporary `HF_LivePreview` modifier is gone and the real cut is
      applied exactly once (no double boolean). **Cancel (Esc)** → the target is back to
      its original mesh, no leftover modifier.
- [ ] On a **heavy** target (> ~8k verts) the live boolean is skipped (only the wire
      cage shows), staying responsive.

**Cutter Options** (N-panel section): presetting inset / bevel-on-cut / bevelled
cutter / array there seeds the next draw (then `-`/`=`, `B`, `C`, `A`/`D` live-tweak).

**Sweep / Follow-Me** (N-panel ▸ Curves ▸ Sweep):
- [ ] Draw a path on a surface → an **L** section is swept along it; **`P`** cycles
      L → U → T → I → Square → Rect; Enter commits the swept solid, Esc discards.

**Removed tools** — confirm the N-panel no longer shows the **Modifier** (bevel/
mirror/array/radial/symmetrize/sharpen/clean/dice) or **Greeble** (steps/taper/
knurl) sections, the pie has no **Modify** slice, and the header menu has no
**Greeble** submenu; **Pipe/Cable** still work (now under "Curves").

---

## 20. HardFlow Mode ⭐ (Shadowing Engine — shared shell, Knife + Extrude verbs)

Architecture: `docs/hardflow_mode_plan.md` + `docs/command_refactor.md`. The pure
command journal (`core/command.py`) and the bpy-aware command layer
(`operators/base.py`, incl. `MeshSnapshotCommand`, `BooleanCutCommand`,
`boolean_chain`) are headless-verified (`tests/test_core.py`,
`tests/test_blender.py`); only the modal verbs below need a viewport. Both verbs
run on the shared `_HardflowModeModal` shell, so the snap/plane/undo checks below
apply to each — verify them once on Knife, then spot-check on Extrude.

**Entry points:**
- [ ] **`Ctrl+Shift+X`** (rebindable in Preferences ▸ Keymap) enters HardFlow Mode
      on the **Knife** verb; **pie ▸ Edit ▸ HardFlow Mode** does the same.

**Shared shell (either verb):**
- [ ] **`←` / `→`** cycles the construction **plane** (VIEW → **SURFACE** → X → Y →
      Z; the HUD shows `plane …`). Drawn points snap onto the chosen plane through
      the object origin (or the 3D cursor when nothing is active).
- [ ] **SURFACE plane**: cycle to it, then the **first click** locks the plane to
      the face under the cursor (aligned to the nearest face edge); the rest of the
      footprint stays on that plane. When the ray misses geometry the HUD shows
      `SURFACE(miss)` and it falls back to a view-facing plane.
- [ ] **`Tab`** switches the active **verb** in-session (Knife ↔ Extrude) without
      losing the points placed so far; the HUD label + help line update (Extrude
      gains the `depth … (PgUp/PgDn)` readout).

**HardFlow Mode Knife** (`mesh.hardflow_mode_knife`, F3 → "HardFlow Mode Knife"):

Setup: a mesh in Object Mode, selected/active.
- [ ] Moving the mouse shows a **snap marker** that recolors by target: **yellow**
      vertex, **green** midpoint, **blue** on-edge, **white** grid.
- [ ] **`X`** toggles the Ghost Grid snap (marker white ↔ geometry colors / free).
- [ ] **Click** places points; the rubber-band segment follows the snapped cursor.
- [ ] **`Backspace`** removes the last point (Command `undo()`); repeated presses
      walk back through every placement.
- [ ] **`Z` / `Enter` / double-click** with ≥3 points scores the drawn footprint
      onto the active mesh; the info bar reports the knife ran.
- [ ] **`Esc`** before committing rolls the whole session back (`undo_all()`) and
      leaves the mesh untouched — no leftover `hf_mode_knife` snapshot in the
      .blend's orphan mesh data.
- [ ] After a commit, a **single `Ctrl+Z`** reverts the knife (one atomic undo
      step — the modal never pushes its own per-step undo).

**HardFlow Mode Extrude** (`mesh.hardflow_mode_extrude`, header menu ▸ Edit ▸
"HardFlow Mode: Extrude", or F3):

Setup: any scene (an active object sets the plane origin; else the 3D cursor).
- [ ] Same snap marker / `X` snap / `←`/`→` plane / `Backspace` undo behaviour as
      Knife (shared shell).
- [ ] **PageUp / PageDown** change the extrude **depth** (HUD shows `depth … m`).
- [ ] **`Z` / `Enter` / double-click** with ≥3 points builds a **new solid**
      (prism) from the footprint, extruded along the plane normal; it becomes the
      active/selected object and the info bar reports the n-gon + depth.
- [ ] **`Esc`** before committing discards with no new object created.
- [ ] After a commit, a **single `Ctrl+Z`** removes the whole solid (one atomic
      undo step). Watch for: a degenerate (self-crossing / collinear) footprint —
      it should report "degenerate footprint", not crash.

**Command adoption spot-check** — the `_FaceDragModal` tools (Push/Pull, Offset,
Edge Bevel, Loop Cut) now run their live preview through
`base.MeshSnapshotCommand` + a per-session `CommandManager`, and
`draw_cut._apply_destructive` applies its cutter(s) through `base.boolean_chain`.
For each direct-modeling tool verify its **Esc-cancel** restores the mesh exactly
and a **commit** leaves no `hf_*` snapshot mesh orphaned in the file (Blender ▸
Outliner ▸ Blender File ▸ Meshes), and that a **single `Ctrl+Z`** reverts the whole
edit. For the boolean chain: a multi-object **Cut** across several selected meshes,
or a **Slice**, must commit every piece or (on a forced solver failure) leave every
target **unchanged** — never half-cut, never an orphaned slice duplicate.

## 22. v1.15 Polish & Performance

**Smart Bevel topology safety** (Object Mode ▸ Edge Bevel, `S` = Smart on):
- [ ] Bevel a **clean cube** edge with Smart on — the HUD shows `SMART t=…
      (+N loops)` and support/holding loops appear on the flanking faces. Add a
      **Subdivision** modifier: the bevel stays crisp.
- [ ] Boolean-cut a shape into a face first (leaving **n-gons**), then Smart-bevel
      one of the resulting irregular edges — loops still land on the n-gon flanks
      and the mesh does **not** collapse.
- [ ] Bevel a **very small / thin** feature with a wide width — the HUD shows
      `M clamped` and the too-small flanks are **skipped** (no face collapse,
      no NaN geometry). `-` / `=` re-tunes tightness live.

**Premium HUD + viewport guides:**
- [ ] Every modal tool's HUD now has a **bordered panel + accent header** (tool
      title). Edge Bevel / Loop Cut show their title; HardFlow Mode shows
      `HardFlow Mode · Knife/Extrude`.
- [ ] In **HardFlow Mode**, dashed **axis guide lines** run through the snapped
      cursor along the plane's two in-plane axes (colored per X/Y/Z plane, accent
      for VIEW/SURFACE), and the snap marker is a **ring** colored by snap kind.

**High-poly live boolean preview** (`J` on):
- [ ] With a **heavy** target (raise its poly count) and `live_preview_max_verts`
      left at its default, the wire cage still draws but the live RESULT is skipped
      — the viewport stays responsive. Lower/raise the preference to change the cap.
- [ ] With **two** targets where the cutter cage only overlaps one, only the
      **overlapping** target shows the live cut result; the far one is untouched.
- [ ] Holding the mouse **still** mid-draw does not re-stutter (the boolean isn't
      re-evaluated every frame); moving it resumes the live update immediately.

## §21 — Trim Sheet UV editor (v1.16)

Setup: N-panel ▸ Hardflow ▸ Decals ▸ **Trim Sheet Editor**. Click **Load Sheet…**
and pick any image (or set an already-loaded one via the datablock picker).

- [ ] **Open Editor** shows the sheet as a centered canvas over the viewport with
      a dark backdrop; one whole-sheet region ("R0") exists to start.
- [ ] **LMB drag on empty canvas** rubber-bands a **new** rectangle; releasing
      keeps it (a click with no drag adds nothing). It becomes the active region
      (accent outline + yellow handles + its name label).
- [ ] **Drag a corner / edge handle** of the active region resizes it; dragging an
      edge past its opposite **flips cleanly** (no inversion).
- [ ] **Click inside** another region selects it; **drag inside** moves it, and it
      **stops at the sheet border** (never leaves [0,1], size preserved).
- [ ] **`C`** splits the active region into left/right at the cursor; **`Shift+C`**
      into top/bottom. The two pieces exactly tile the original.
- [ ] **`X` / Del** deletes the active region; **`A`** adds a centered one;
      **`Tab`** cycles which region is active.
- [ ] **`G`** toggles snap; **`[` / `]` / wheel** change the density (grid lines
      appear); new/resized edges land on the lattice. HUD shows the active
      region's **pixel size** (`W × H px`).
- [ ] **Enter** applies (HUD reports the region count); **Esc** cancels and the
      regions **revert** to how they were on entry.
- [ ] Back in the panel, each region row: **place** (⟶ decal place tool, Up/Down
      cycles regions live), **apply-to-decal** (re-trims the selected decal's UVs),
      rename, and remove all work. **From Grid** fills an equal grid to then tweak.
- [ ] A decal placed from a **custom (unequal) region** carries that region's
      aspect ratio and shows only that slice of the sheet.

---

## Decal depth — Parallax Occlusion Mapping + Normal Transfer (Module 1)

Enable **Preferences → Parallax Occlusion** (and set a **Parallax Depth**, e.g.
0.08) before placing.

- [ ] Place an **image decal** with a bit of tonal contrast (a panel/grunge PNG)
      on a flat face. Orbit to a **grazing angle**: the dark areas should
      **recess** and slide behind their lip (view-dependent), not stay a flat
      print. Head-on there is little/no shift (correct).
- [ ] Raise **Parallax Depth** → the apparent recess deepens; raise **Parallax
      Layers** → the grazing-angle silhouette gets smoother (more nodes).
- [ ] The decal's node tree contains an **`HF_Parallax_<image>_<N>`** group feeding
      the base-color image's **Vector** input; deleting/disabling it falls back to
      a flat decal (no crash).
- [ ] With a **bad/one-pixel image** or on an odd Blender build, placement still
      succeeds as a flat decal and the console logs `parallax wiring skipped`
      (graceful degrade).
- [ ] Enable **Decal Normal Transfer**, place a decal across a **curved / bevelled
      edge**: it should shade as part of the surface (an `HF_NormalTransfer` Data
      Transfer modifier sits after `HF_Shrinkwrap`), not catch flat sticker
      lighting. On a build without the modifier it logs `normal transfer skipped`.

---

## Viewport polish — shortcut bar + alignment guides (Module 2)

- [ ] Start **Draw Cut** (Ctrl+Shift+D). A **premium translucent shortcut bar**
      sits centered along the bottom: chips like `[Tab] Cut`, `[B] Bevel`,
      `[J] Live Bool`, `[V] Vertex`, `[Enter] Apply`. Toggling **B / C / J / M /
      V / N** flips the matching chip's key box to the **accent (ON)** color live;
      **Tab** updates the mode chip label.
- [ ] Place a first point, then move the cursor so it is roughly **above** or
      **level with** that point: a **dashed full-span guide line** snaps on
      (vertical when square in X, horizontal when square in Y) and disappears when
      you move off. With several points placed, guides appear for whichever ones
      you line up with (near-duplicates collapse to one line).
- [ ] The top-left HUD is now shorter (status + one hint line) since the bar
      carries the toggles — nothing important was lost.
- [ ] Enter **HardFlow Mode** (Ctrl+Shift+X). Same bottom bar (`[Tab] Knife`,
      `[←/→] Plane: …`, `[X] Snap`, `[Enter] Commit`); the **Depth** chip is
      accent-lit only on the **Extrude** verb. Alignment guides also light up
      against placed points, alongside the existing per-plane axis guides.
- [ ] At a **narrow viewport width** the bar left-anchors instead of sliding its
      first chips off-screen (never clipped on the left).

---

## Topology & SubD stability (Module 4)

- [ ] Cut a boolean into a cube, then add a **Subdivision Surface** modifier.
      Toggle **Preferences → Re-quad Cut N-gons** on and re-cut: the cut border
      should subdivide **without pinches / dark sliver artifacts** (the
      `_clean_boolean_slivers` pass dissolved the near-zero-area faces + redundant
      cut-line verts). The N-gon count around the cut drops vs. the old behavior.
- [ ] **Edge Bevel → `S` (Smart)** on a cube edge, raise **segments** with `[ ]`:
      the support/holding loop now sits **tighter** on a rounder bevel (seg-aware
      placement) and the beveled edge holds its radius under Subdivision instead
      of ballooning. HUD still reports `+N loops, M clamped`.
- [ ] Smart Bevel on an **irregular boolean off-cut** still never collapses a thin
      flank (the `flank_can_support` barrier), it just adds fewer loops.

---

When every box is ticked, update the live-verification note in `CLAUDE.md`
(FIRST TASK) and the smoke-test memory.
