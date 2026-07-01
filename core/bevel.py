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


def safe_support_fraction(offset, flank_length, min_gap=0.02):
    """Clamp one absolute support-loop `offset` (meters, out from the bevel
    shoulder) to a safe split fraction in (0, 1) of a flanking edge of length
    `flank_length`. Keeps at least `min_gap` clearance from *both* ends so the
    edge split never makes a zero-area sliver or lands on/past the far vertex --
    the per-edge clamping barrier `geometry.smart_bevel_edges` needs to survive
    irregular, non-quad flanks a boolean cut leaves.

    Returns a float in [min_gap, 1 - min_gap], or None when there is nothing to
    place (a degenerate flank or a non-positive offset). Pure float, no bpy.

        >>> safe_support_fraction(0.0325, 0.1)   # 0.325 of the flank
        0.325
        >>> safe_support_fraction(0.5, 0.1)      # past the far end -> clamped
        0.98
        >>> safe_support_fraction(0.001, 0.1)    # tiny -> clamped off the near end
        0.02
    """
    if flank_length <= 0.0 or offset <= 0.0:
        return None
    lo = _clamp01(min_gap)
    hi = 1.0 - lo
    if hi <= lo:
        return None
    f = offset / flank_length
    return round(min(hi, max(lo, f)), 6)


def flank_can_support(flank_length, width, min_ratio=1.5):
    """Safety barrier for the Smart Bevel support loop: True only when a flank is
    comfortably larger than the bevel it must hold. A holding loop dropped into a
    flank that is barely wider than the bevel collapses the face -- exactly the
    thin, irregular off-cuts a boolean leaves behind. Gating on
    `flank_length >= min_ratio * width` (both positive) is the non-quad-safe
    check that lets `smart_bevel_edges` skip those flanks instead of breaking
    them.

        >>> flank_can_support(2.0, 0.2)     # a cube face vs a small bevel
        True
        >>> flank_can_support(0.25, 0.2)    # a thin sliver -> skip the loop
        False
    """
    if width <= 0.0 or flank_length <= 0.0 or min_ratio <= 0.0:
        return False
    return flank_length >= min_ratio * width


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
