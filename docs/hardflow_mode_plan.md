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
| **2 (done)** | Extrude verb + VIEW/X/Y/Z plane cycle on the shell | `operators/hardflow_mode.py` | manual checklist |
| **3 (done, experimental)** | `support_loop_positions` (pure) + `smart_bevel_edges` / `dissolve_boolean_ngons` (bmesh) + `S` toggle | `core/bevel.py`, `core/geometry.py`, `operators/edge_tool.py` | pure tests + headless; live subdiv tuning pending |
| **4 (facility landed)** | Boolean chain → `MacroCommand` (`base.BooleanCutCommand` / `boolean_chain`, atomic rollback) | `operators/base.py` (+ future `draw_cut` adoption) | headless (`test_boolean_chain_command_atomic`) |

Each phase is independently shippable and leaves the tree green.

**Landed in the Super Modeling Mode change:** Phases 1–3 and the Phase-4 boolean
facility are now committed and green (pure + headless + syntax). Still pending and
deliberately deferred (each is a self-contained, low-risk follow-up):

- **CommandManager adoption in `push_pull`/`offset`/`edge_tool`** — the shared
  `_FaceDragModal` still uses the ad-hoc `_base`/`_committed` snapshot bookkeeping.
  The named `MeshSnapshotCommand` maps onto it 1:1 (see `command_refactor.md` §3
  Q1); it is a rename, not a behaviour change, but touches four interdependent
  modal files, so it wants a live pass before landing.
- **`draw_cut` boolean chain → `base.boolean_chain`** — the `MacroCommand` facility
  exists and is tested; wiring it into `_apply_destructive` (esp. the SLICE
  dual-cut) buys explicit atomic rollback. `draw_cut` stays untouched until that
  is validated against a deliberately-broken cutter live.
- **Smart Bevel live tuning** — the support-loop placement is deterministic and
  count-tested, but the exact holding-loop position and non-quad-flank handling
  need a live cube→Subdivision pass (kept EXPERIMENTAL / `S`-gated until then).
- **SURFACE / EDGES planes on the mode shell** — the shell cycles VIEW/X/Y/Z; the
  richer plane set from `draw_cut._plane_basis` can be promoted to the shared base.

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
| Smart Bevel support loops land wrong post-bevel | High | Ship pure math + skeleton first; tune loop-ID live; keep experimental (§6.4). |
| Feature creep bloats `draw_cut` | Med | New `hardflow_mode.py` stays lean; share via mixin/core, don't grow the monolith (§4.2). |
| Core layer violation creeps in | Low | Table in §3; `command.py`/`bevel.py` stay bpy-free and unit-tested. |

---

*This plan is intentionally incremental: Phase 0 is real and testable today, and
nothing after it requires discarding working code. The architecture the brief
asks for is already latent in Hardflow — the work is to name it, share it, and
make the undo story explicit.*
