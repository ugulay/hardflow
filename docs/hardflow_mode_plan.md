# HardFlow Mode — Implementation Plan

*Modal "hijack" context, Smart Bevel + edge flow, and a Command-Pattern undo
journal — designed to fit Hardflow's existing one-directional (ui/ops → core)
architecture without a big-bang rewrite.*

Status: **design + reference prototype landed.** This document is the plan; the
pure `core/command.py` module, the `operators/hardflow_mode.py` prototype, and
their unit tests are committed alongside it so the pattern is runnable, not just
described. Everything here respects the inviolable rule from `CLAUDE.md`: *core
never looks upward, and never touches `bpy.ops` / `gpu` / `blf`.*

---

## 1. Executive summary (and three honest corrections)

The goal — redefine Extrude / Knife / Bevel inside a smart "HardFlow Mode" that
snaps everything to a Ghost Grid, with robust undo for boolean chains — is
sound and achievable. But three assumptions in the brief need correcting up
front, because the whole design depends on them:

1. **"Hijack Blender's native operators" is not literally possible — and you are
   already doing the thing that works instead.** A modal operator cannot wrap
   `bpy.ops.mesh.knife_tool('INVOKE_DEFAULT')` and intercept its mouse events;
   the child modal owns the event stream, not the parent. The realistic pattern
   — which `draw_cut.py`, `push_pull.py`, `offset.py`, and `edge_tool.py` **all
   already use** — is to *shadow* the native tool: own your own modal loop, read
   the raw mouse, route it through `core/raycast` + `core/snapping` + `core/grid`,
   and call bmesh directly. That is the hijack. "HardFlow Mode" is the umbrella
   that makes it feel like one coherent mode instead of separate operators.

2. **A CommandManager is not a replacement for Blender's global Ctrl+Z.** Fighting
   Blender's undo stack from an add-on is a classic footgun. The correct, useful
   scope is a **per-session (per modal) undo journal**: it sequences the several
   sub-steps of *one* tool session (place point, place point, knife, bevel…) so
   they can be stepped back individually while the modal is live, then flushed to
   a **single** Blender undo push on commit. The "undo crashes in long boolean
   chains" symptom comes from partially-applied intermediate states owned by
   nobody; a single owner of `execute`/`undo` with all-or-nothing macros removes
   that. This is the scope `core/command.py` implements.

3. **You already have a proto-Command Pattern — we are formalising it, not
   inventing it.** `geometry.snapshot_mesh` / `restore_mesh` / `free_mesh` plus
   the `_base` / `_committed` bookkeeping in `operators/face_tool._FaceDragModal`
   are exactly *execute = mutate the mesh, undo = restore the snapshot*. The plan
   is to lift that into a named, testable abstraction and reuse it everywhere,
   **not** to rip out the working machinery.

The result: no new dependency, no core-layer violation, and each piece is a pure
function in `core` + a thin operator — the same recipe the rest of the toolkit
follows.

---

## 2. What "the flow feeling" actually is, mechanically

SketchUp's "everything snaps to a grid" feel is one function composition, run on
every `MOUSEMOVE`, that turns a raw pixel coordinate into a locked 3D point:

```
raw mouse (px)
  → core/snapping.geo_snap_3d   # 1. nearest vertex / midpoint / on-edge  (precision)
  → core/raycast.ray_to_plane   # 2a. project onto the construction plane
  → core/raycast.world_to_plane_uv
  → core/grid.snap_world        # 2b. round the (u,v) meters to the Ghost Grid
  → core/raycast.plane_uv_to_world
  → locked 3D world point
```

This exists today, scattered inside `draw_cut._snap_screen`. The plan's first
move is to make it the **single shared entry point** of HardFlow Mode. The
prototype (`operators/hardflow_mode.py::_snap_screen`) is the minimal, isolated
copy of exactly this chain — read it as the reference for step 2. Geometry snap
overrides the grid (precision beats the lattice), which is what makes a draw
"click onto" a real vertex instead of the nearest grid line.

---

## 3. Layer discipline (non-negotiable)

Every feature below is split so `core/` stays pure and unit-testable:

| Feature | Pure `core/` (no bpy.ops/gpu/blf) | Thin `operators/` (owns bpy/modal) |
|---|---|---|
| Ghost Grid snap | `snapping`, `raycast`, `grid`, `snap` (exist) | `hardflow_mode.py` composes them |
| Command / undo | `command.py` — sequencing only (**new, pure**) | operators build concrete Commands |
| Smart Bevel | `geometry.smart_bevel_edges` + support-loop math (**new**) | `edge_tool` drives it |

If a piece needs `bpy.ops`, it belongs in an operator, full stop. The one
sanctioned exception in the codebase (`modifier_apply` in `core/boolean.py`)
is not extended by this plan.

---

## 4. Feature A — HardFlow Mode modal hijack

### 4.1 Design

One modal shell, several tool "verbs" (Knife / Extrude / Bevel), all sharing:

- **the snap chain** of §2 (the Ghost Grid),
- **the plane basis** cycle already proven in `draw_cut._plane_basis`
  (VIEW / SURFACE / EDGES / X / Y / Z),
- **the CommandManager** of §5 for in-modal undo,
- **the HUD** helpers in `ui/draw.py`.

The verbs differ only in what they do on commit — the same way `push_pull` and
`offset` differ only in how they turn the drag value into a bmesh op. So the
production form of HardFlow Mode is a **mixin base**, mirroring the existing
`face_tool._FaceDragModal` and `pipe._CurveDraw` bases:

```
operators/hardflow_mode.py
  _HardflowModeModal            # shell: snap chain, plane basis, command mgr, HUD
    HARDFLOW_OT_mode_knife      # commit → geometry.knife_polygon        (prototype today)
    HARDFLOW_OT_mode_extrude    # commit → geometry.build_prism / extrude (Phase 2)
    HARDFLOW_OT_mode_bevel      # commit → geometry.smart_bevel_edges     (Phase 3)
```

### 4.2 Why not reuse `draw_cut.py` directly?

`draw_cut.HARDFLOW_OT_draw` is ~1500 lines and already carries the full feature
matrix (shapes, in-draw ops, live boolean preview, Edit Mode). Bolting "Mode"
onto it risks the exact thing the brief warns against ("without complicating my
code"). The prototype is intentionally ~230 lines: it isolates the *architecture*
so you can validate the hijack + snap + command loop in a live Blender before
deciding how much of `draw_cut` to fold in. Recommended path: keep `draw_cut` as
the power tool, grow `hardflow_mode` as the streamlined "mode," and share logic
by extracting `_snap_screen` / `_plane_basis` into the mixin (or a small
`core`-side helper) once both need them.

**Update (v1.14.1) — the shared plane-basis seam landed.** The part of
`_plane_basis` both tools built identically — the on-face SURFACE basis
(`ray_cast_surface_ex` → `face_edge_tangent` → `basis_from_normal`) and the VIEW
basis — is now `core/raycast.surface_basis_at` / `core/raycast.view_basis`, and
both `draw_cut._surface_basis_at`/`_view_basis` and the shell's delegate to it.
The *rest* of each `_plane_basis` / `_snap_screen` stays per-tool on purpose:
`draw_cut` carries EDGES, the `H` movable grid origin and `Shift+←/→` grid spin
and returns a *screen* point; the shell returns a *world* point from a simpler
VIEW/SURFACE/X/Y/Z cycle. Forcing those two different contracts into one function
would add branches, not remove them — so only the genuinely-identical basis pick
is shared, which is the clean seam this section called for.

### 4.3 Steps

1. **Prototype (done).** `HARDFLOW_OT_mode_knife` — snap chain + command undo +
   knife commit. Smoke-test it in Blender (see §7).
2. **Extract the shell** into `_HardflowModeModal` once the knife feels right.
3. **Add the plane cycle** (`←/→`) by copying `draw_cut._plane_basis` — or, better,
   promote that method to the shared base so both tools use one implementation.
4. **Add Extrude and Bevel verbs** as subclasses (Phases 2–3).
5. **Single keymap + pie slot** to enter the mode (`keymaps.py`, `ui/pie.py`),
   with `Tab` cycling the active verb the way `draw_cut` cycles boolean modes.

---

## 5. Feature B — Command Pattern (`core/command.py`, landed)

### 5.1 What shipped

A pure, stdlib-only module (unit-tested in `tests/test_core.py`):

- `Command` — abstract; subclasses implement `_apply` / `_revert`. Public
  `execute` / `undo` are **idempotent** guards (never apply or revert twice —
  the source of many undo crashes).
- `CallbackCommand(do, undo, label)` — wrap an existing apply/restore pair. This
  is the bridge to today's code: `CallbackCommand(lambda: knife(...),
  lambda: geometry.restore_mesh(obj, snap))`.
- `MacroCommand` — compose N commands into one atomic unit. **Rolls back
  already-applied children if a later child raises** — directly the fix for a
  boolean chain leaving half its cutters applied when the third solver fails.
- `CommandManager` — per-session `do` / `undo` / `redo` / `undo_all` / `clear`
  journal with standard linear-history semantics (a fresh `do` forks history).

### 5.2 How it relates to Blender undo (read this before wiring it in)

- **Inside a modal:** the CommandManager is the source of truth. `Backspace`
  → `undo()`, `Esc` → `undo_all()`, commit → `clear()`. Blender never sees the
  intermediate steps.
- **At commit:** the operator performs the *net* change once. Because the
  operator has `bl_options={'REGISTER','UNDO'}`, Blender records that as one undo
  step. Do **not** also call `bpy.ops.ed.undo_push()` per sub-step — that is what
  desynchronises the two stacks.
- **Never** try to intercept a global Ctrl+Z to replay Commands. The journal's
  lifetime is the modal session.

### 5.3 Migration path (incremental, low-risk)

The existing snapshot/restore tools become the first adopters, one at a time:

1. `edge_tool` / `push_pull` / `offset` already do snapshot→edit→(restore on
   cancel). Wrap that pair in a `CallbackCommand` so cancel routes through the
   manager. Behaviour identical; the plumbing is now uniform and testable.
2. The boolean chain in `draw_cut._build_and_apply` (array of cutters →
   `robust_boolean` per cutter) becomes a `MacroCommand`, gaining atomic rollback
   for free.
3. New HardFlow Mode verbs use the manager from day one.

No operator is forced to migrate; the manager is additive.

---

## 6. Feature C — Smart Bevel & edge flow

### 6.1 Goal

Move beyond `geometry.bevel_object_edges` (plain chamfer) to a bevel that (a)
follows the selected **edge flow**, (b) drops **support / holding loops** beside
the new bevel so it survives a Subdivision modifier, and (c) preserves topology
(quad-friendly). This is the "hard-surface bevel" hard-surface modelers expect.

### 6.2 What already exists to build on

- `geometry.edge_loop(obj, key)` — valence-4 quad-walk to expand a picked edge to
  its whole loop (the edge-flow analysis primitive).
- `geometry.edge_ring(obj, key)` + `geometry.loop_cut(obj, key, cuts, slide)` —
  insert loops along a ring, with slide positioning.
- `geometry.bevel_object_edges(obj, keys, width, segments)` — the chamfer.
- `transform.adaptive_dimension` — size-scaled widths.

Smart Bevel is largely a **composition** of these, plus a small amount of new
pure math and one new bmesh routine.

### 6.3 Design

**Pure side (`core`)** — a new helper (in `core/geometry.py` for the bmesh op, and
a pure placement function that can live in `core/transform.py` or a new
`core/bevel.py` so it is unit-testable without bpy):

```python
# pure, testable: where do the holding loops sit relative to the bevel?
def support_loop_positions(width, segments, tightness=0.5):
    """Return the fractional offsets (0..1 across the flanking face) at which to
    insert holding loops so a `width`/`segments` bevel stays crisp under
    subdivision. `tightness` → how close the loop hugs the bevel (0.5 = default
    hard-surface). Pure floats; no bpy."""
```

**bmesh side (`core/geometry.py`)**:

```python
def smart_bevel_edges(obj, keys, width, segments, support=True, tightness=0.5):
    """Bevel `keys` (or their loop) then, when support, insert holding loops
    flanking the new bevel using support_loop_positions(). Returns a summary
    (beveled edge count, support loops added). bmesh only — no bpy.ops."""
```

**Operator side** — extend `edge_tool.HARDFLOW_OT_edge_bevel` with an `S` toggle
("Smart") and a `tightness` live-adjust, reusing the existing drag/`[ ]`/`L`/`R`
HUD. When Smart is on, `_refresh_preview` calls `smart_bevel_edges` instead of
`bevel_object_edges`. The snapshot/restore live-preview path is unchanged.

### 6.4 The honest risk

The hard part is **identifying the new bevel's flanking loops in bmesh after the
bevel op**, so the support loop cut lands in the right place. `bmesh.ops.bevel`
returns the created geometry (`'faces'` / `'edges'`), which is the correct handle
— but wiring that into `loop_cut`'s ring walk needs live-Blender iteration; it is
not verified by headless tests alone. **Recommendation:** ship `support_loop_
positions` (pure, tested) and the `smart_bevel_edges` skeleton first, then tune
the loop-identification against a live cube→subdiv in Blender before exposing the
`S` toggle in the UI. Mark it experimental until that pass is done (consistent
with `tests/manual_checklist.md` discipline).

**Update (v1.15) — topology safety landed.** The original skeleton only handled
clean quad flanks; a boolean off-cut leaves **n-gon** flanks, which is exactly
where a naïve support loop collapses a face. v1.15 closed that gap in the pure
core: `geometry._flank_support_loop` now inserts holding loops on non-quad flanks
too, `core/bevel.flank_can_support` is a safety barrier that **skips** any flank
too small to hold a loop (instead of forcing one in), and
`core/bevel.safe_support_fraction` clamps every split off both ends of a flank.
`smart_bevel_edges` returns a `skipped` count, surfaced live in the Edge Bevel
HUD (`+N loops, M clamped`). What remains deferred is only the **live
subdivision-tuning pass** for the exact holding-loop position, so Smart Bevel
stays `S`-gated / EXPERIMENTAL — the topology *safety* is no longer the open
risk, the loop *placement feel* is.

**Update (v1.16, Module 4) — bevel-exact placement landed.** The holding-loop
offset is no longer segment-blind. `core/bevel.seg_factor(segments)` tightens the
offset for a rounded (multi-segment) bevel — which already braces the edge along
its own profile — by `2/(segments+1)` (1.0 for a chamfer, so the single-segment
default is unchanged); `smart_bevel_edges` now passes its `segments` through, so
the support loop is placed to preserve the *modeled* radius instead of letting
Subdivision balloon it. The pure `subdiv_fillet_radius` / `support_offset_for_radius`
pair (unit-tested) expose the offset↔subdivided-radius relationship so a caller
can target a specific fillet radius. The near-degenerate cut result is also
stabilized before re-quadding: `dissolve_boolean_ngons(clean_slivers=True)` runs a
`_clean_boolean_slivers` pass (merge doubles → `dissolve_degenerate` on
near-zero-area faces/edges → dissolve redundant collinear valence-2 verts via the
pure `core/topology` predicates), removing the garbage that pinches a Subdivision
surface. The one remaining item — the *live subdivision pass* on the loop position
— is closed by the v1.19 update below.

**Update (v1.19) — live subdivision pass done, placement validated.** The
"tune the exact holding-loop position against a live cube→Subdivision" item — the
last thing keeping Smart Bevel `EXPERIMENTAL` — is complete. A headless probe
(Blender 5.1.2) bevels a cube edge, hangs a Catmull-Clark Subdivision modifier,
evaluates the mesh and circle-fits the corner cross-section. Two findings settle
the tuning:

1. **The holding loop does its job — it pins the flanking flat.** On an uncreased
   cube, the near-shoulder top-face height recovers markedly *with* a loop vs a
   plain bevel: **+0.11 for a chamfer**, +0.02 for a 2-segment bevel, +0.017 for a
   3-segment bevel (subdiv level 3). The loop's biggest win is on the chamfer —
   exactly where a modeler needs it — which is *why* it is kept for all segment
   counts.
2. **The subdivided fillet radius tracks the bevel WIDTH, not the loop offset.**
   Measured radius/width ≈ 1.05 (3 seg) → 1.2 (2 seg) → 1.3 (chamfer), and is
   essentially flat across the whole holding-loop offset range (an isolated,
   crease-pinned circle fit). So the placement is sound at every `tightness`, and
   the pure `subdiv_fillet_radius(offset)` "radius ≈ offset" relation was modeling
   the wrong scenario (a lone loop on a sharp edge, not a beveled fillet). New
   pure `core/bevel.beveled_fillet_radius(width, segments)` captures the measured
   width-driven relation and drives the Edge Bevel `~r=…` HUD readout.

No placement math changed — the pass *validated* the existing
`support_loop_positions` output. Smart Bevel is de-experimentalised (the `S`
toggle is now just the opt-in). Locked by headless
`test_smart_bevel_subdivision_quality` + pure `test_beveled_fillet_radius`.

---

## 7. Reference prototype (this change)

Files added:

| File | Role |
|---|---|
| `core/command.py` | Pure `Command` / `CallbackCommand` / `MacroCommand` / `CommandManager`. No bpy. |
| `operators/hardflow_mode.py` | `HARDFLOW_OT_mode_knife` — the minimal modal-hijack + Ghost-Grid-snap + command-undo template. |
| `tests/test_core.py` | +6 pure tests for the command core (idempotent do/undo, redo fork, macro atomic rollback). |
| `__init__.py` | Registers `HARDFLOW_OT_mode_knife`. |

**Smoke test (the CLAUDE.md FIRST TASK ritual):**

1. Reload scripts / re-enable the add-on.
2. Object Mode, select a mesh, `F3` → "HardFlow Mode Knife".
3. Click to place ≥3 points — watch the snap marker recolor (yellow=vertex,
   green=midpoint, blue=edge, white=grid). `Backspace` steps a point back
   (Command undo); `X` toggles the Ghost Grid; `Z`/`Enter`/double-click scores
   the footprint onto the mesh; `Esc` rolls the whole session back.
4. Two spots to watch at runtime (untested in headless): the
   `geometry.knife_polygon` sweep on non-planar targets, and `ray_to_plane`
   returning `None` when the plane goes edge-on (the prototype guards it).

What it proves: the mouse never reaches Blender's native knife; it flows through
`core/snapping` → `core/grid`; placements are reversible Commands; the commit is a
single Blender undo step.

---

## 8. Phased rollout

| Phase | Scope | Files | Verified by |
|---|---|---|---|
| **0 (done)** | Command core + Knife prototype + tests | `core/command.py`, `operators/hardflow_mode.py`, `tests/test_core.py` | pure tests green; live smoke test pending |
| **1 (done)** | Extract `_HardflowModeModal` shell (Knife moved onto it) | `operators/hardflow_mode.py` | headless + manual checklist |
| **2 (done)** | Extrude verb + VIEW/SURFACE/X/Y/Z plane cycle + `Tab` verb cycle + keymap/pie entry on the shell | `operators/hardflow_mode.py`, `keymaps.py`, `ui/pie.py` | headless (`test_mode_shell_verb_and_plane_cycle`) + manual checklist |
| **3 (done, validated)** | `support_loop_positions` (pure) + `smart_bevel_edges` / `dissolve_boolean_ngons` (bmesh) + `S` toggle; **v1.15** non-quad-safe flanks + `flank_can_support` / `safe_support_fraction` barrier + `skipped` HUD readout; **v1.19** live subdivision pass → placement validated + `beveled_fillet_radius` HUD | `core/bevel.py`, `core/geometry.py`, `operators/edge_tool.py` | pure tests + headless (`test_smart_bevel_subdivision_quality`) |
| **4 (done)** | Boolean chain → `MacroCommand` (`base.BooleanCutCommand` / `boolean_chain`, atomic rollback), adopted in `draw_cut._apply_destructive` + the `_FaceDragModal` live preview | `operators/base.py`, `operators/draw_cut.py`, `operators/face_tool.py` (+ push_pull/offset/edge_tool) | headless (`test_boolean_chain_command_atomic`, `test_draw_cut_apply_destructive_atomic_chain`, `test_facetool_*`) |

Each phase is independently shippable and leaves the tree green.

**Landed in the Super Modeling Mode change:** Phases 1–3 and the Phase-4 boolean
facility are now committed and green (pure + headless + syntax). The follow-ups
below were subsequently landed and verified live against a standalone `bpy`
build:

- **CommandManager adoption in `push_pull`/`offset`/`edge_tool`** — *done.* The
  shared `_FaceDragModal` runs its live preview through a per-session
  `CommandManager` + `base.MeshSnapshotCommand`: `_begin_edit` snapshots + applies
  the edit as one journal entry, the base `_refresh_preview` re-applies it each
  drag frame via `command.reapply`, cancel routes through `undo_all`, and commit
  `clear`s the journal so the net change is Blender's single undo step. Each tool
  now supplies `_mutate` (the edit *without* the restore) instead of its own
  `_refresh_preview` — the 1:1 rename from `command_refactor.md` §3 Q1. Headless
  `test_facetool_command_adoption_structure`, `test_facetool_begin_edit_lifecycle`.
- **`draw_cut` boolean chain → atomic `MacroCommand`** — *done.* `_apply_destructive`
  applies the cutter(s) through a `MacroCommand` of `base.BooleanCutCommand`s, so a
  multi-target CUT/MAKE or the SLICE dual-cut rolls back all-or-nothing on a
  mid-chain solver failure (no half-cut target, no orphaned slice duplicate),
  while preserving the cleanup / n-gon-dissolve / solver-fallback reporting.
  Headless `test_draw_cut_apply_destructive_atomic_chain`.
- **SURFACE plane + Tab verb cycle on the mode shell** — *done.* The shell cycles
  VIEW/**SURFACE**/X/Y/Z (SURFACE promoted from `draw_cut._surface_basis_at`,
  aligned to the face under the first click; EDGES stays Edit-Mode-only and so
  does not apply to this Object-Mode shell), `Tab` switches the active verb
  (Knife ↔ Extrude) in-session, and the mode is entered from a Ctrl+Shift+X
  keymap + an Edit pie slot. Headless `test_mode_shell_verb_and_plane_cycle`.
- **Full `draw_cut` command adoption + shared plane-basis seam (v1.14.1)** —
  *done.* `draw_cut` gained its own per-session `CommandManager`: placements are
  a two-child `PlacePointCommand` macro (`_record_placement`; Backspace = `undo`),
  and the live boolean preview is a `base.LivePreviewCommand` (non-destructive
  temp-modifier lifecycle, deliberately not a `MeshSnapshotCommand`). The on-face
  SURFACE basis and the VIEW basis it shared with the mode shell are lifted into
  `core/raycast.surface_basis_at` / `view_basis`; both tools delegate (§4.2
  update). Headless `test_draw_placement_journal`,
  `test_livepreview_command_lifecycle`, `test_draw_cut_uses_livepreview_command`,
  `test_surface_basis_shared_helper`. With this, the three-layer command
  architecture is consistent across **every** modal tool.

**Landed in the Polish & Performance change (v1.15):** Smart Bevel topology
safety — non-quad flank support + the `flank_can_support` / `safe_support_fraction`
barrier + the `skipped` HUD count (§6.4 update) — plus a framed "premium" HUD with
translucent viewport guide lines (`ui/draw.py` `draw_hud` accent header +
`draw_guide_line` / `draw_dashed_line` / `draw_snap_ring` / `draw_mirror_plane` /
`fade_color`; the mode shell now draws dashed per-plane axis guides + a ring snap
marker) and a high-poly live boolean preview gated by the new pure
`core/preview_cache` (AABB target culling + idle-frame distance gate, capped by
the `live_preview_max_verts` preference).

Previously pending, now closed:

- **Smart Bevel live tuning — done (v1.19).** The support-loop placement was
  the last deferred item; a headless live cube→Catmull-Clark Subdivision pass
  (Blender 5.1.2) *validated* it — the loop pins the flanking flat near the bevel
  and the subdivided fillet stays crisp at radius ≈ the bevel width, across the
  full `tightness` range (see the §6.4 "live subdivision pass done" update). Smart
  Bevel is de-experimentalised; no placement math changed. With this, **nothing in
  the Super Modeling Mode plan remains deferred.**

---

## 9. Testing strategy

- **Pure (`tests/test_core.py`, `python tests/test_core.py`):** command journal
  semantics (done); `support_loop_positions` (Phase 3). No Blender needed.
- **Headless (`tests/test_blender.py`, `blender --background`):** `smart_bevel_
  edges` edge/loop counts; boolean `MacroCommand` rollback on a forced solver
  failure.
- **Manual (`tests/manual_checklist.md`):** every modal interaction — snap
  marker colors, `Backspace` undo, plane cycle, Smart Bevel under subdivision.
  Add a "§HardFlow Mode" section mirroring the existing draw/push-pull entries.

---

## 10. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Trying to wrap native modal operators | — | Ruled out; we shadow, not wrap (§1.1). |
| CommandManager desyncs with Blender undo | Med | Journal is per-session only; one undo push at commit; never `undo_push` per sub-step (§5.2). |
| Smart Bevel support loops land wrong post-bevel | Closed (was High) | Pure math + skeleton shipped; v1.15 added non-quad-safe flanks + a `flank_can_support` skip barrier; v1.16 (Module 4) made the offset **bevel-exact** (`seg_factor`, segment-aware) + added the `_clean_boolean_slivers` SubD-stabilizing pass; **v1.19** the live cube→Subdivision pass *validated* the placement (loop pins the flat, fillet radius ≈ width) and de-experimentalised it (§6.4). |
| Feature creep bloats `draw_cut` | Med | New `hardflow_mode.py` stays lean; share via mixin/core, don't grow the monolith (§4.2). |
| Core layer violation creeps in | Low | Table in §3; `command.py`/`bevel.py` stay bpy-free and unit-tested. |

---

*This plan is intentionally incremental: Phase 0 is real and testable today, and
nothing after it requires discarding working code. The architecture the brief
asks for is already latent in Hardflow — the work is to name it, share it, and
make the undo story explicit.*
