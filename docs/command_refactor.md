# Command Pattern Refactor — `operators/base.py` + `draw_cut` proposal

*Follow-up to `docs/hardflow_mode_plan.md`. This is the concrete "how": the named
Command abstraction over the existing `_base` / `_committed` snapshot flow, and a
step-by-step refactoring proposal for the modal tools — without breaking the
working machinery.*

Status: `operators/base.py` and `core/geometry.bisect_plane` are **landed and
tested** (pure + headless). The `_FaceDragModal` adoption (§3 Q1) and the
`draw_cut` boolean-chain step (§4 Step 1) are **now landed and verified** against a
standalone `bpy` build — the shared preview runs through a per-session
`CommandManager` + `MeshSnapshotCommand`, and `draw_cut._apply_destructive` applies
its cutter(s) as an atomic `MacroCommand`.

**Audit (v1.14, 2026-07):** the three-layer command architecture is now complete
and consistent across **every** modal tool — `hardflow_mode`, `face_tool`
(Push/Pull, Offset, Edge Bevel, Loop Cut) and `draw_cut` (both its destructive
path *and* its interactive shell). All three `draw_cut` follow-up steps have
landed:

- **Step 1 — the boolean chain — landed.** `draw_cut._apply_destructive` applies
  its cutter(s) as an atomic `MacroCommand` of `base.BooleanCutCommand`s.
- **Step 2 — placement journaling — landed.** `draw_cut` now owns a per-session
  `CommandManager`; each placement click is a two-child `MacroCommand` of
  `PlacePointCommand`s (the screen + world point lists move together), so
  `Backspace` = `undo()` and the shape/plane/stamp reset keys = `clear()`. The
  append/pop bookkeeping is gone. Headless `test_draw_placement_journal`.
- **Step 3 — the live boolean preview — landed.** `draw_cut`'s
  `_sync_live_boolean` / `_clear_live_boolean` / `_bool_targets` bookkeeping is
  replaced by a single `base.LivePreviewCommand` (§4 Step 3, corrected). It owns
  the temp-`HF_LivePreview`-modifier lifecycle — *not* a mesh snapshot, so the
  preview stays non-destructive and per-frame cheap. Held directly (not journaled),
  so `Backspace` never strips the preview. Headless
  `test_livepreview_command_lifecycle` + `test_draw_cut_uses_livepreview_command`.

Everything above is verified against a standalone `bpy` build (Blender 5.0.1) —
the full headless suite runs green. The modal *event routing* itself still can't
be driven without a viewport, so the placement/preview commands are exercised on
stand-in `self` objects (as `test_facetool_begin_edit_lifecycle` does); GUI
click-through remains tracked in `tests/manual_checklist.md`.

---

## 1. Architectural summary

Two layers, one rule (`ui/ops → core`, core never looks up):

```
core/command.py     PURE sequencing. Command / CallbackCommand / MacroCommand /
                    CommandManager. No bpy -> unit-tested in tests/test_core.py.
                        │  (subclassed by)
operators/base.py   BPY-AWARE commands. HardFlowCommand (adds redo) +
                    MeshSnapshotCommand (the named _base/_committed flow) +
                    PlacePointCommand. Drives core.geometry; touches bpy data,
                    so it lives in operators/, not core/.
                        │  (used by)
operators/*.py      Modal tools build concrete commands and feed a
                    CommandManager; commit = clear() + free(), Blender records
                    ONE undo step for the invocation.
```

Why two layers instead of one `HardFlowCommand` doing everything? Because the
*sequencing* (do/undo/redo stacks, atomic macro rollback) has zero Blender
dependencies and is the part most worth unit-testing. Keeping it in `core`
means the undo semantics are proven on plain CPython; `base.py` only has to get
the mesh snapshot/restore right, which the headless suite covers.

### The undo model, stated once more (it is the crux)

- The CommandManager is a **per-modal-session journal**. `Backspace` →
  `undo()`, `Esc` → `undo_all()`, commit → `clear()`.
- You **never** call `bpy.ops.ed.undo_push()` yourself. An operator with
  `bl_options={'REGISTER','UNDO'}` already produces exactly **one** Blender undo
  step per invocation, capturing the net mesh change on `FINISHED`. *That* is the
  "atomic macro commit to Blender's stack" — Blender does it for you. Your job is
  only to make sure the mesh is in the right final state when you return
  `{'FINISHED'}`, and fully restored when you return `{'CANCELLED'}`.
- `MacroCommand` is for grouping **within** one commit — a boolean chain of N
  cutters — so a mid-chain failure rolls the already-applied ones back and the
  invocation fails cleanly instead of leaving half the cutters baked.

---

## 2. `operators/base.py` walkthrough

### `HardFlowCommand`
Subclasses the pure `core.command.Command` (inheriting idempotent
`execute`/`undo`) and adds `redo()`. Two-level redo, on purpose:

- `command.redo()` — re-apply **this** command after its own undo (`redo ==
  execute`; `execute()` no-ops while still applied, so it only fires post-undo).
- `CommandManager.redo()` — walk the session's redo **stack**.

### `MeshSnapshotCommand` — the named `_base` / `_committed`
The mapping is one-to-one, so adopting it changes names, not behaviour:

| Today (ad-hoc, in `_FaceDragModal`) | Named command |
|---|---|
| `self._base = geometry.snapshot_mesh(obj, name)` | `cmd._ensure_snapshot()` (lazy, on first `execute`) |
| per-frame `restore_mesh(obj, self._base)` + re-edit | `cmd.reapply(mutate)` |
| commit: keep mesh, `_committed = True` | manager `clear()` (keep mesh) |
| `free_mesh(self._base)` | `cmd.free()` |
| cancel: `restore_mesh(obj, self._base)` | `cmd.undo()` |

`mutate(obj)` is any bmesh edit — extrude, inset, knife, **bisect** — always run
against the freshly-restored "before" state, which is why it is safe to call
every drag frame.

### `PlacePointCommand`
Append-on-execute / pop-on-undo. Every click in a polyline modal becomes a
journal entry, so `Backspace` and `Esc` fall out of the manager for free.

---

## 3. Answering the two direct questions

### Q1 — "How do I pull `_base`/`_committed` into a named Command Pattern **without breaking it**?"

You don't rewrite the modal; you swap the three touch-points for method calls on
one `MeshSnapshotCommand`. Here is the `_FaceDragModal` lock / preview / commit /
cancel cycle, before and after — behaviour is identical:

**Before (today):**
```python
def _lock_face(self, context, co):
    ...
    self._base = geometry.snapshot_mesh(self.obj, self._snapshot_name)

def _refresh_preview(self):
    geometry.restore_mesh(self.obj, self._base)
    # ... re-apply the current drag value (extrude/inset) ...

def _commit(self, context):
    self._refresh_preview()
    self._remember_last()
    self._committed = True
    self._cleanup(context)          # frees self._base, keeps the mesh

def _cleanup(self, context):
    if self._base is not None and not self._committed:
        geometry.restore_mesh(self.obj, self._base)   # cancel path
    geometry.free_mesh(self._base)
```

**After (named command, same effect):**
```python
from . import base
from ..core import command

def _init_tool(self, context, event):
    self._commands = command.CommandManager()
    self._edit = None               # the live MeshSnapshotCommand

def _lock_face(self, context, co):          # Object Mode
    ...
    self._edit = base.MeshSnapshotCommand(
        self.obj, self._mutate, snapshot_name=self._snapshot_name)
    self._commands.do(self._edit)   # snapshot 'before' + first apply

def _lock_edit(self, context, event):       # Edit Mode: same command, mode-aware
    ...
    self._edit = base.MeshSnapshotCommand(
        self.obj, self._mutate, snapshot_name=self._snapshot_name,
        restore=geometry.restore_edit_mesh)   # the ONLY Object/Edit difference
    self._commands.do(self._edit)
    return True

def _refresh_preview(self):
    self._edit.reapply(self._mutate)     # restore + re-edit with current value

def _commit(self, context):
    self._refresh_preview()
    self._remember_last()
    self._commands.clear()          # hand net change to Blender's undo
    self._edit.free()               # == free_mesh(self._base)
    self._cleanup(context)

def _cleanup(self, context):        # cancel path
    if self._edit is not None and not self._committed:
        self._commands.undo_all()   # == restore_mesh(obj, self._base)
    if self._edit is not None:
        self._edit.free()
```

`self._mutate` is a small method the subclass already effectively has — for
Push/Pull it wraps `geometry.extrude_faces(...)`, for Offset
`geometry.inset_faces(...)`. Nothing about the drag/numeric/HUD shell changes.
The payoff: cancel, commit and preview now go through one object with a tested
contract, and that same object drops into a `MacroCommand` the day a tool needs a
chain.

### Q2 — "How do I sync mouse moves with `core/grid.py`, and wrap `bmesh.ops.bisect_plane` in the snapshot logic?"

**Mouse → grid** is the composition already isolated in
`operators/hardflow_mode.py::_snap_screen` (read it as the reference). The shape:

```python
def _snap_screen(self, context, screen_co):
    region, rv3d = context.region, context.region_data
    # 1) geometry snap (vertex/edge/midpoint) -- precision beats the grid
    if self.geo and self.geo.enabled:
        hit = snapping.geo_snap_3d(region, rv3d, screen_co, self.geo, self._snap_px)
        if hit is not None:
            return hit[0]
    # 2) project onto the plane, round the (u,v) METERS to the Ghost Grid
    origin, right, up, normal = self._basis
    world = raycast.ray_to_plane(region, rv3d, screen_co, origin, normal)
    if world is None:
        return None
    u, v = raycast.world_to_plane_uv(world, origin, right, up)
    if self.snap:
        u, v = grid.snap_world(u, v, self._grid, True)   # core/grid.py
    return raycast.plane_uv_to_world(u, v, origin, right, up)
```

**Wrapping `bisect_plane` in snapshot logic** — the mutation is just a closure
handed to a `MeshSnapshotCommand`. `core/geometry.bisect_plane` (landed, headless
-tested) is the bmesh op; the command owns the snapshot/restore:

```python
# a Slice verb: drag a plane point, live-preview the guillotine cut, commit once.
def _lock(self, context, world_pt):
    obj = context.active_object
    mw_inv = obj.matrix_world.inverted_safe()
    self._plane_no = mw_inv.to_3x3() @ raycast.view_direction(context.region_data)

    def _mutate(o):
        # plane_co follows the live snapped cursor; object-local.
        co = obj.matrix_world.inverted_safe() @ self._cursor
        geometry.bisect_plane(o, co, self._plane_no)

    self._edit = base.MeshSnapshotCommand(obj, _mutate, label="Slice")
    self._commands.do(self._edit)          # snapshot + first cut

def _on_mousemove(self, context, co):
    self._cursor = self._snap_screen(context, co)   # grid-locked plane point
    self._edit.reapply()                            # restore + re-cut live

def _commit(self, context):
    self._commands.clear()
    self._edit.free()
    return {'FINISHED'}                     # Blender records one undo step
```

Every `MOUSEMOVE` restores the pre-cut mesh and re-bisects at the new
grid-snapped point — no accumulation, no leaked geometry, and `Esc` (undo_all)
puts the mesh back exactly.

---

## 4. `draw_cut.py` refactoring proposal (incremental, non-breaking)

`draw_cut` is ~1500 lines; do **not** big-bang it. Three isolated steps, each
shippable and green on its own:

**Step 1 — the boolean chain becomes a `MacroCommand`.**
The array-of-cutters loop in `_build_and_apply` is where "undo crashes in
boolean chains" actually bites. Wrap each cutter's destructive
`robust_boolean` in a `MeshSnapshotCommand` and run the set as one macro:

```python
from ..core import command
from . import base

def _build_and_apply(self, context):
    target = context.active_object
    cutters = self._make_cutters(context)          # existing footprint → prisms
    mesh_cmds = [
        base.MeshSnapshotCommand(
            target, lambda o, c=cut: boolean.robust_boolean(
                context, o, c, self._operation, self._solver))
        for cut in cutters
    ]
    chain = command.MacroCommand(mesh_cmds, label="Boolean chain")
    try:
        chain.execute()          # atomic: a failing cutter rolls the rest back
    except Exception as ex:
        self.report({'ERROR'}, "Hardflow: %s" % ex)
        return {'CANCELLED'}     # target untouched, no half-applied cutters
    for c in mesh_cmds:          # keep the mutated target, free the snapshots
        c.free()
    return {'FINISHED'}
```

Caveat, stated honestly: `draw_cut._apply_destructive` is *already* effectively
atomic — `robust_boolean` cleans up its own half-added modifiers and never
raises on a solver failure (it returns `(ok, used, msg)`), and the whole
`execute` is one Blender undo step. So the `MacroCommand` here buys **explicit,
inspectable** rollback of a genuinely raising chain (and a uniform vocabulary
with the modal tools), not a fix for a currently-crashing path. Treat it as a
clarity/robustness upgrade, and validate it against a deliberately-broken cutter
before shipping. The real per-step undo win is in the **modal** tools (§3 Q1),
where Blender gives you no intra-session undo at all.

**Step 2 — placements become `PlacePointCommand` (landed v1.14).**
`self.points` / `self.world_points` `append`/`pop` (and the `BACK_SPACE` handler)
now route through a per-session `CommandManager`, so undo-during-draw is uniform
with the mesh edits instead of a second hand-rolled history. Because `draw_cut`
keeps two parallel lists (screen + world anchor), one click is recorded as a
two-child `MacroCommand` of `PlacePointCommand`s (`_record_placement`), so `undo`
pops both together; the shape/plane/stamp reset keys and teardown `clear()` the
journal (placements never touch mesh data, so cancel needs `clear`, not
`undo_all`). Headless `test_draw_placement_journal`.

**Step 3 — the live cutter preview becomes a `LivePreviewCommand`
(corrected).** The original proposal said "fold `_sync_live_boolean` /
`_clear_live_boolean` onto a `MeshSnapshotCommand`, it is the same
snapshot-shaped lifecycle." The v1.14 audit found that wrong: the live boolean
preview **never mutates the target mesh**. It hangs a temporary `HF_LivePreview`
Boolean *modifier* on each target pointing at the live cutter cage and lets
Blender's viewport evaluate the result (hence the `live_preview_max_verts` cap —
a preference since v1.15, previously the `_LIVE_BOOL_MAX_VERTS` constant — plus
the v1.15 `core/preview_cache` bounding-box target culling + idle-frame distance
gate, and the `FAST` solver). Porting it to `MeshSnapshotCommand` would force a real
per-frame boolean *bake* on every `MOUSEMOVE` — a regression, not a cleanup.

The right named form is a lightweight `LivePreviewCommand(HardFlowCommand)` that
owns the temp-modifier lifecycle instead of a mesh snapshot: `execute()`/`refresh()`
attach + retarget the `HF_LivePreview` modifier on the wanted targets;
`undo()`/`free()` strip every one back off (folding in today's scene-wide safety
sweep). That collapses the scattered `_bool_targets` bookkeeping under one named
owner **without** changing behaviour or cost — the preview stays non-destructive
and just as cheap.

**Landed in v1.14, standalone.** `draw_cut` holds the `LivePreviewCommand`
directly (`self._live_cmd`), driven by `execute()`/`refresh()`/`clear()` — *not*
in a `CommandManager` journal. That is deliberate: the journal (Step 2) is for
`Backspace`-undoable placements, and the live preview is a continuously-refreshed
side-effect you never `Backspace`, so putting it in the same journal would make
`Backspace` strip the preview instead of the last point. The command needs no
journal to be the single named owner, so Step 3 shipped without waiting on Step 2.

After all three, `draw_cut` and `hardflow_mode` share the same command
vocabulary, and a future extraction of `_HardflowModeModal` (Phase 1 of the main
plan) has a clean seam to cut along.

---

## 5. What landed with this document

| File | Change | Verified |
|---|---|---|
| `operators/base.py` | **New.** `HardFlowCommand` / `MeshSnapshotCommand` (mode-aware: injectable `snapshot`/`restore`, so Object + Edit share one command) / `PlacePointCommand`. | headless (`test_place_point_command_*`, `test_mesh_snapshot_command_*`) |
| `core/geometry.py` | **New** `bisect_plane` bmesh primitive (Slice verb + the Q2 example). | headless (`test_bisect_plane_slices_cube`) |
| `operators/hardflow_mode.py` | Refactored to consume `base.PlacePointCommand` + `MeshSnapshotCommand` (the knife now snapshots + is macro-committed). | compiles; live smoke test pending |
| `operators/base.py` | **New** `LivePreviewCommand` (v1.14): the temp-`HF_LivePreview`-modifier lifecycle as a named non-destructive command. | headless (`test_livepreview_command_lifecycle`) |
| `operators/draw_cut.py` | Live boolean preview adopts `LivePreviewCommand`; placements adopt a per-session `CommandManager` + `PlacePointCommand` macro (`_record_placement`); the ad-hoc `_bool_targets` / `_remove_live_mod` / `append`/`pop` bookkeeping is gone. | headless (`test_draw_cut_uses_livepreview_command`, `test_draw_placement_journal`) |
| `tests/test_blender.py` | +4 headless tests (bisect, place-point redo, snapshot preview/commit/undo, macro rollback on a real mesh), +2 for the live preview command, +1 for the placement journal. | `blender --background` **or** a standalone `bpy` build (full suite green on 5.0.1) |

With Steps 1–3 landed, `draw_cut` and `hardflow_mode` share the same command
vocabulary end to end, and the future extraction of `_HardflowModeModal` has a
clean seam to cut along — the original goal of this refactor.
