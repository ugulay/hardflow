# Command Pattern core -- a transactional journal of reversible operations.
#
# This is the "logic" layer for the HardFlow Mode undo/redo work: it is pure
# Python (no bpy / bpy.ops / gpu / blf) so it stays unit-testable in plain
# CPython, exactly like core/grid.py and core/snap.py. Operators build concrete
# Commands whose _apply/_revert touch bpy data; this module only sequences them.
#
# Scope, stated plainly: a CommandManager is a *per-session* (per modal
# operator) undo journal, NOT a replacement for Blender's global Ctrl+Z. It lets
# the several sub-steps of ONE tool session (place point, place point, knife,
# bevel...) be stepped back individually while the modal is live, then flushed to
# a single Blender undo push on commit. The "undo crashes in long boolean chains"
# problem comes from partially-applied intermediate states owned by nobody; a
# single owner of execute/undo, with all-or-nothing macros, removes that.


class Command:
    """Abstract reversible operation.

    Subclasses implement `_apply` (do the work) and `_revert` (undo it). The
    public `execute`/`undo` are idempotent guards around them so a command is
    never applied or reverted twice. `label` is a short human-readable name for
    the HUD / undo list."""

    label = "Command"

    def __init__(self, label=None):
        if label is not None:
            self.label = label
        self._done = False

    @property
    def done(self):
        return self._done

    def execute(self):
        if self._done:
            return
        self._apply()
        self._done = True

    def undo(self):
        if not self._done:
            return
        self._revert()
        self._done = False

    # --- subclass hooks ---------------------------------------------------

    def _apply(self):
        raise NotImplementedError

    def _revert(self):
        raise NotImplementedError


class CallbackCommand(Command):
    """Wrap a do/undo pair of thunks as a Command -- the lightweight path for
    operators that already have an apply function and a matching restore. E.g.
    the live-preview tools pair a mesh edit with `geometry.restore_mesh(snap)`:

        CallbackCommand(lambda: geometry.knife_polygon(obj, corners, vd),
                        lambda: geometry.restore_mesh(obj, snap),
                        label="Knife")
    """

    def __init__(self, do, undo, label="Command"):
        super().__init__(label)
        self._do = do
        self._undo = undo

    def _apply(self):
        self._do()

    def _revert(self):
        self._undo()


class MacroCommand(Command):
    """Compose several commands into ONE reversible unit -- e.g. a whole boolean
    chain committed or rolled back atomically. Children execute in order and undo
    in reverse. If a child raises mid-execute, the already-executed children are
    rolled back so the macro is all-or-nothing (this is what stops a boolean
    chain from leaving half its cutters applied when the third one fails)."""

    def __init__(self, commands=(), label="Macro"):
        super().__init__(label)
        self._commands = list(commands)

    def add(self, command):
        """Append a child. Only legal before the macro has been executed."""
        if self._done:
            raise RuntimeError("cannot extend an executed MacroCommand")
        self._commands.append(command)
        return command

    def _apply(self):
        applied = []
        try:
            for cmd in self._commands:
                cmd.execute()
                applied.append(cmd)
        except Exception:
            for cmd in reversed(applied):
                cmd.undo()
            raise

    def _revert(self):
        for cmd in reversed(self._commands):
            cmd.undo()

    def __len__(self):
        return len(self._commands)


class CommandManager:
    """Per-session undo/redo journal. `do(cmd)` executes and records; `undo`/
    `redo` walk the two stacks. A fresh `do` after an undo clears the redo stack
    (standard linear-history semantics). `undo_all` rolls the whole session back
    for a modal cancel (Esc), `clear` drops the history on commit so the tool's
    single change hands off cleanly to Blender's own undo step."""

    def __init__(self):
        self._undo = []
        self._redo = []

    def do(self, command):
        command.execute()
        self._undo.append(command)
        self._redo.clear()
        return command

    def undo(self):
        if not self._undo:
            return None
        command = self._undo.pop()
        command.undo()
        self._redo.append(command)
        return command

    def redo(self):
        if not self._redo:
            return None
        command = self._redo.pop()
        command.execute()
        self._undo.append(command)
        return command

    def undo_all(self):
        """Roll every recorded command back, most-recent first (modal cancel)."""
        while self._undo:
            self.undo()

    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def clear(self):
        self._undo.clear()
        self._redo.clear()

    def labels(self):
        """The undo stack as a list of labels, oldest first -- for a HUD list."""
        return [c.label for c in self._undo]

    def __len__(self):
        return len(self._undo)
