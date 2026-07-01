# Pure support-loop placement math for the Smart Bevel tool -- stdlib only.
#
# core/geometry.smart_bevel_edges does the bmesh work (bevel + insert the holding
# loops); this module answers the one question that is pure and worth
# unit-testing on plain CPython: *where* do the support / holding loops sit
# relative to a `width` bevel so it stays crisp under a Subdivision modifier?
#
# Layer rule: no bpy / bpy.ops / gpu / blf here (same discipline as core/grid.py).


def _clamp01(x):
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def holding_loop_factor(tightness=0.5):
    """The fraction of the bevel `width` at which the first holding loop sits,
    measured out from the new bevel border across the flanking face.

    `tightness` in [0, 1] -- how hard the loop hugs the bevel:
        0.0 (loose)  -> ~0.60 * width   (soft shoulder, rounder under subdiv)
        0.5 (default)-> ~0.325 * width  (standard hard-surface holding loop)
        1.0 (tight)  -> ~0.05 * width   (razor-crisp edge under subdiv)

    Linear between the loose and tight anchors, clamped. Pure float."""
    t = _clamp01(tightness)
    loose, tight = 0.60, 0.05
    return loose + (tight - loose) * t


def support_loop_positions(width, tightness=0.5, count=1):
    """Absolute offset distances (in `width`'s units, i.e. meters) from the new
    bevel border at which to drop holding / support loops on each flanking face,
    so a bevel of size `width` survives Subdivision without softening.

    Returns a list of `count` offsets, nearest-to-the-bevel first. `count` loops
    per side fan outward, each `holding_loop_factor` further than the last. An
    empty list for a non-positive width or count (nothing to support).

    The caller (geometry.smart_bevel_edges) clamps these against the real
    flanking-face size before splitting -- this function is deliberately unaware
    of the mesh so it stays pure and testable.

        >>> support_loop_positions(0.1, tightness=0.5)
        [0.0325]
        >>> support_loop_positions(0.1, tightness=1.0)   # tighter -> closer
        [0.005]
        >>> support_loop_positions(0.1, tightness=0.5, count=2)
        [0.0325, 0.065]
    """
    if width <= 0.0 or count < 1:
        return []
    base = width * holding_loop_factor(tightness)
    return [round(base * (i + 1), 6) for i in range(int(count))]


def support_loop_fractions(width, flank_length, tightness=0.5, count=1):
    """The same holding-loop offsets expressed as fractions in (0, 1) of a
    flanking face of length `flank_length` -- the form a face-local edge split
    consumes (split at fraction `f` from the bevel border). Offsets that would
    fall on or past the far edge are clamped just inside it (0.98) so the split
    never produces a zero-area sliver. Empty list when there is nothing to place
    or the flank is degenerate."""
    if flank_length <= 0.0:
        return []
    fracs = []
    for off in support_loop_positions(width, tightness, count):
        f = off / flank_length
        fracs.append(round(min(0.98, max(0.02, f)), 6))
    # Deduplicate collapsed clamps while preserving order (two loops that both
    # clamp to 0.98 would otherwise make a degenerate second cut).
    seen, out = set(), []
    for f in fracs:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out
