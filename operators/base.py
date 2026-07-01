# operators/base.py -- the operator-layer (bpy-aware) Command Pattern base.
#
# core/command.py holds the PURE sequencing machinery (Command / CallbackCommand
# / MacroCommand / CommandManager) -- stdlib only, unit-tested. This module adds
# the concrete, bpy-touching commands the modal tools build: the *named* form of
# the existing snapshot_mesh / restore_mesh / _base / _committed flow. It lives in
# operators/ (not core/) precisely because it drives bpy data via core.geometry;
# the one-directional layer rule (ops -> core) is intact.
from ..core import command as _command
from ..core import geometry
from ..core import boolean


class HardFlowCommand(_command.Command):
    """Base for every reversible operator action. Subclasses the pure
    core.command.Command, so it inherits the idempotent execute() / undo() guards
    and drops straight into a MacroCommand / CommandManager -- but is allowed to
    touch bpy data. Adds redo() to complete the execute / undo / redo trio.

    Two-level redo, on purpose:
      * command.redo()  -- re-apply THIS command after its own undo (redo ==
        execute; execute() no-ops while still applied, so it only fires post-undo).
      * CommandManager.redo() -- walk the session's redo STACK, re-applying the
        last-undone command. The manager is the journal; the command is one entry.
    """

    def redo(self):
        self.execute()


class PlacePointCommand(HardFlowCommand):
    """Append one (already snapped) point to a list; undo pops it. The trivial
    reversible action behind every click in a draw / knife / polyline modal, so
    Backspace = manager.undo() and Esc = manager.undo_all() come for free."""

    label = "Place point"

    def __init__(self, points, point):
        super().__init__()
        self._points = points
        self._point = point

    def _apply(self):
        self._points.append(self._point)

    def _revert(self):
        self._points.pop()


class MeshSnapshotCommand(HardFlowCommand):
    """The named form of the _base / _committed pattern: a mesh edit that can
    preview, commit and roll back through ONE snapshot.

        cmd = MeshSnapshotCommand(obj, lambda o: geometry.knife_polygon(o, ...))
        cmd.execute()             # snapshot 'before' once, then apply the edit
        cmd.reapply(new_mutate)   # live-preview frame: restore + re-apply (drag)
        cmd.undo()                # restore the 'before' snapshot
        cmd.free()                # drop the snapshot datablock (commit / discard)

    The mapping from the current ad-hoc bookkeeping is exact:
      * `self._base`        -> `self._snap`   (the snapshot datablock)
      * per-frame restore+re-edit in `_refresh_preview` -> `reapply()`
      * `_committed = True` + `free_mesh(self._base)`   -> `free()` after the
        manager `clear()` on commit (Blender then owns the net change).

    `mutate(obj)` is any bmesh edit -- extrude, inset, knife, bisect... -- always
    run against the restored 'before' state, so it is safe to call every frame.

    Mode-aware: `restore` defaults to geometry.restore_mesh (Object Mode). Pass
    `restore=geometry.restore_edit_mesh` for an Edit-Mode tool -- both share the
    same (obj, snapshot) signature and the same snapshot_mesh capture, so the
    _FaceDragModal Object/Edit split collapses to one injected callable."""

    def __init__(self, obj, mutate, label="Mesh edit",
                 snapshot_name="hf_command", snapshot=None, restore=None):
        super().__init__(label)
        self.obj = obj
        self._mutate = mutate
        self._snapshot_name = snapshot_name
        self._snapshot = snapshot or geometry.snapshot_mesh
        self._restore = restore or geometry.restore_mesh
        self._snap = None

    @property
    def snapshot(self):
        """The captured 'before' mesh datablock (None until the first execute).
        Exposed so a modal tool can read the pre-edit geometry -- e.g. to build
        drag inference candidates -- from the same snapshot the command owns,
        instead of keeping a second copy."""
        return self._snap

    def _ensure_snapshot(self):
        if self._snap is None:
            self._snap = self._snapshot(self.obj, self._snapshot_name)

    def _apply(self):
        # Snapshot the 'before' once, reset to it, then run the edit. Resetting
        # first keeps _apply re-runnable: the mutation always builds from the
        # clean pre-edit state, never stacked on top of a previous apply.
        self._ensure_snapshot()
        self._restore(self.obj, self._snap)
        self._mutate(self.obj)

    def _revert(self):
        if self._snap is not None:
            self._restore(self.obj, self._snap)

    def reapply(self, mutate=None):
        """Live-preview frame during a drag: restore to the snapshot and run the
        (optionally updated) mutation again, WITHOUT touching the _done guard so
        the command stays 'applied'. This is exactly _FaceDragModal's per-frame
        restore_mesh + re-edit loop, named."""
        if mutate is not None:
            self._mutate = mutate
        self._ensure_snapshot()
        self._restore(self.obj, self._snap)
        self._mutate(self.obj)

    def free(self):
        """Discard the snapshot datablock -- call on commit (after the manager
        clear()) or when the command is dropped. Mirrors free_mesh(self._base).
        Idempotent: a second call is a no-op."""
        geometry.free_mesh(self._snap)
        self._snap = None


class BooleanCutCommand(MeshSnapshotCommand):
    """One destructive boolean step as an atomic, reversible command: snapshot the
    target, run `core.boolean.robust_boolean`, and RAISE when the solver
    ultimately fails so a MacroCommand of several cuts rolls the whole chain back
    (never leaving half the cutters baked). This is the operator-layer answer to
    "undo crashes in long boolean chains" -- the intermediate states are owned by
    one command, and N of them commit or roll back all-or-nothing.

    The last successful cut's outcome is kept on `.message` / `.solver_used` so
    the operator can still report a solver fallback after the macro commits."""

    label = "Boolean cut"

    def __init__(self, context, target, cutter, operation='DIFFERENCE',
                 solver='EXACT', label=None, snapshot_name="hf_boolean"):
        self.context = context
        self.cutter = cutter
        self.operation = operation
        self.solver = solver
        self.message = ""
        self.solver_used = None
        super().__init__(target, self._mutate_boolean,
                         label=label or self.label, snapshot_name=snapshot_name)

    def _mutate_boolean(self, target):
        ok, used, msg = boolean.robust_boolean(
            self.context, target, self.cutter, self.operation, self.solver)
        self.message = msg
        self.solver_used = used
        if not ok:
            # robust_boolean already cleaned up its own half-added modifier and
            # reported (False, ...) rather than raising; we escalate to an
            # exception so the enclosing MacroCommand triggers atomic rollback.
            raise RuntimeError(msg)


class LivePreviewCommand(HardFlowCommand):
    """Non-destructive live boolean preview as a named, reversible command.

    Unlike MeshSnapshotCommand (which mutates + restores the real mesh every
    frame), this NEVER edits target geometry: it hangs a temporary
    'HF_LivePreview' Boolean modifier on each target pointing at the live cutter
    cage, so Blender's viewport evaluates the real subtraction/union while the
    shape is drawn; undo()/free() strip every one back off. That keeps the
    preview cheap (no per-frame boolean bake) AND reversible through the same
    vocabulary as every other tool step -- the named form of draw_cut's
    _sync_live_boolean / _clear_live_boolean / _bool_targets bookkeeping.

    Porting the draw preview to MeshSnapshotCommand instead would force a real
    boolean bake on every mouse-move (a regression); the modifier lifecycle is
    the right shape here, so the command owns *that*, not a mesh snapshot.

    execute() only arms the (empty) preview; refresh() does the per-frame work
    (add the modifier to new targets, retarget existing ones, strip the ones that
    left), kept outside the _done guard exactly like MeshSnapshotCommand.reapply.
    """

    label = "Live boolean preview"
    MOD_NAME = "HF_LivePreview"

    def __init__(self, cutter, operation, solver='FAST'):
        super().__init__()
        self.cutter = cutter          # the live wire cutter cage object
        self.operation = operation    # 'DIFFERENCE' / 'UNION' / 'INTERSECT'
        self.solver = solver          # snappy preview; commit uses the real solver
        self._targets = []            # objects currently carrying the temp mod

    def _apply(self):
        pass                          # arm only; refresh() attaches the modifiers

    def _revert(self):
        self.clear()

    def refresh(self, targets):
        """Point the temp modifier at `targets`: add it to new ones, retarget the
        existing, strip the ones that left the set. Idempotent per frame."""
        wanted = set(targets)
        for t in list(self._targets):
            if t not in wanted:
                self._strip(t)
                self._targets.remove(t)
        for t in targets:
            mod = t.modifiers.get(self.MOD_NAME)
            if mod is None:
                mod = t.modifiers.new(self.MOD_NAME, 'BOOLEAN')
                mod.show_render = False
                self._targets.append(t)
            mod.operation = self.operation
            mod.object = self.cutter
            try:
                mod.solver = self.solver
            except (TypeError, AttributeError):
                pass

    def clear(self, context=None):
        """Strip every temp modifier this command added. The optional scene sweep
        catches a target that left the tracked set mid-draw (active/selection
        changed) -- the safety net that keeps a preview modifier from surviving
        the tool."""
        for t in self._targets:
            self._strip(t)
        self._targets = []
        scene = getattr(context, "scene", None) if context is not None else None
        if scene is not None:
            for ob in scene.objects:
                if (ob.type == 'MESH'
                        and ob.modifiers.get(self.MOD_NAME) is not None):
                    self._strip(ob)

    def free(self):
        """Drop the preview (== clear). Idempotent; call on commit and cancel."""
        self.clear()

    @classmethod
    def _strip(cls, obj):
        """Remove the temp modifier from obj, ignoring a deleted object / missing
        modifier (mirrors the old draw_cut._remove_live_mod)."""
        try:
            mod = obj.modifiers.get(cls.MOD_NAME)
            if mod is not None:
                obj.modifiers.remove(mod)
        except (ReferenceError, RuntimeError, AttributeError):
            pass


def boolean_chain(context, target, cutters, operation='DIFFERENCE',
                  solver='EXACT', label="Boolean chain"):
    """Build (but do not execute) a MacroCommand that applies each cutter to
    `target` as an atomic BooleanCutCommand. `.execute()` commits every cut or, on
    the first solver failure, rolls the whole chain back and re-raises -- the
    all-or-nothing boolean chain the modal tools can adopt so a mid-chain failure
    never strands a partially-cut mesh. Each cut snapshots under a distinct name
    so their rollbacks don't collide."""
    cmds = [BooleanCutCommand(context, target, cut, operation, solver,
                              snapshot_name="hf_boolean_%d" % i)
            for i, cut in enumerate(cutters)]
    return _command.MacroCommand(cmds, label=label)
