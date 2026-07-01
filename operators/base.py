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
