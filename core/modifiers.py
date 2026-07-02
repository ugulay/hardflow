# Pure hard-surface modifier-stack ordering (the "Sorting Engine").
#
# Booleans carve the base form first, so they sit at the TOP of the stack; the
# rounding Bevel goes below them, and the shading fixers (Weighted Normal,
# Triangulate) sit at the very BOTTOM so they run last. A Mirror can sit just
# below the booleans (default) or above them (mirror the raw form first) -- the
# one-key toggle the operator exposes.
#
# Everything here is stdlib-only and works on lightweight (name, type) tuples so
# it is unit-testable without Blender; operators/hardops.sort_modifier_stack
# applies the resulting order to a real object's modifier stack.

# Stack priority: a SMALLER number is HIGHER in the stack (evaluated earlier).
_PRIORITY = {
    'BOOLEAN': 10,
    'MIRROR': 15,          # overridden by the mirror_after_boolean toggle below
    'SOLIDIFY': 40,
    'ARRAY': 45,
    'SCREW': 45,
    'BEVEL': 60,
    'SUBSURF': 70,
    'MULTIRES': 70,
    'WEIGHTED_NORMAL': 90,
    'TRIANGULATE': 95,
}
# Unknown modifiers land in the middle band and keep their input order, so a
# stack with exotic modifiers is never scrambled -- only the known ones anchor.
_DEFAULT_PRIORITY = 50


def modifier_priority(mtype, mirror_after_boolean=True):
    """Stack rank for a modifier type. Smaller = higher in the stack. The Mirror
    rank flips around the boolean band with the toggle: just below the booleans
    (default, booleans stay on top) or just above them (mirror the raw form)."""
    if mtype == 'MIRROR':
        return 15 if mirror_after_boolean else 5
    return _PRIORITY.get(mtype, _DEFAULT_PRIORITY)


def _is_pinned(mod):
    """True when a (name, type[, pinned]) tuple carries a truthy pinned flag.
    Blender 4.3+ pins the "Smooth by Angle" node modifier to the bottom of the
    stack (use_pin_to_last) and silently refuses any move off it, so a pinned
    modifier must be held last regardless of its type priority."""
    return len(mod) > 2 and bool(mod[2])


def sorted_order(mods, mirror_after_boolean=True):
    """Modifier names in hard-surface stack order. `mods` is a list of
    (name, type) or (name, type, pinned). Stable: equal-priority modifiers keep
    their input order, so re-runs are idempotent and unknown modifiers don't jump
    around each other. Pinned-to-last modifiers are held at the very bottom in
    their input order (moving them is impossible), so the sort never fights a pin
    it can't win -- which is what made the previous version non-idempotent."""
    indexed = list(enumerate(mods))
    free = [it for it in indexed if not _is_pinned(it[1])]
    pinned = [it for it in indexed if _is_pinned(it[1])]
    free.sort(key=lambda it: (
        modifier_priority(it[1][1], mirror_after_boolean), it[0]))
    return [mod[0] for _i, mod in free] + [mod[0] for _i, mod in pinned]


def reorder_moves(current, desired):
    """A selection-sort move plan turning the `current` name list into `desired`:
    a list of (from_index, to_index) applied in order. Each move pops the item at
    from_index and re-inserts it at to_index -- exactly Blender's
    ``obj.modifiers.move(from, to)`` semantics -- so the operator can replay them
    verbatim. Only the moves actually needed are emitted (empty when already
    sorted). `desired` must be a permutation of `current`."""
    work = list(current)
    moves = []
    for target in range(len(desired)):
        name = desired[target]
        cur = work.index(name)
        if cur == target:
            continue
        work.insert(target, work.pop(cur))
        moves.append((cur, target))
    return moves


def is_sorted(mods, mirror_after_boolean=True):
    """True when `mods` (list of (name, type[, pinned])) is already in hard-surface
    order -- lets the operator stay quiet / skip work when there's nothing to do."""
    names = [mod[0] for mod in mods]
    return names == sorted_order(mods, mirror_after_boolean)
