# Pure high-to-low bake decisions -- stdlib only, no bpy.
#
# The awkward part of a bake is never the bake button: it is pairing the right
# high with the right low, deciding how far the cage has to stand off so it
# encloses the high poly without catching the neighbouring part, and naming the
# output so it is still recognisable three assets later. Those are rules, so
# they live here; operators/bake.py builds the cage, drives Blender's baker and
# puts the engine back.
#
# Deliberately dependency-free (no sibling core imports) so tests/test_core.py
# can execute it standalone.

# Our bake types -> (Blender's bake type, non-color data, filename suffix).
# Only what Blender can actually produce from a high poly: there is no
# curvature bake in Blender, and promising one would be a lie.
BAKE_TYPES = {
    'NORMAL': ('NORMAL', True, 'normal'),
    'AO': ('AO', True, 'ao'),
    'COMBINED': ('COMBINED', False, 'combined'),
    'ROUGHNESS': ('ROUGHNESS', True, 'roughness'),
    'EMIT': ('EMIT', False, 'emit'),
}

LOW_SUFFIX = '_low'
HIGH_SUFFIX = '_high'


def blender_type(bake_type):
    """Blender's bake type id for one of ours ('NORMAL' for anything unknown,
    which is the only bake that is always meaningful)."""
    return BAKE_TYPES.get(bake_type, BAKE_TYPES['NORMAL'])[0]


def is_data(bake_type):
    """True when the result is data rather than colour, i.e. must be written
    non-colour. A normal or AO map read through sRGB is the classic silently
    wrong bake."""
    return BAKE_TYPES.get(bake_type, BAKE_TYPES['NORMAL'])[1]


def suffix(bake_type):
    return BAKE_TYPES.get(bake_type, BAKE_TYPES['NORMAL'])[2]


def strip_duplicate_tail(name):
    """Drop Blender's ``.001`` duplicate tail. Done BEFORE any suffix test,
    because ``panel_high.001`` does not end in ``_high`` until it is gone --
    which is exactly how a duplicated high poly gets orphaned."""
    if len(name) > 4 and name[-4] == '.' and name[-3:].isdigit():
        return name[:-4]
    return name


def base_name(name, low_suffix=LOW_SUFFIX, high_suffix=HIGH_SUFFIX):
    """Strip a _low / _high suffix (case-insensitive) to get the asset's name,
    duplicate tail included."""
    stem = strip_duplicate_tail(name)
    low = stem.lower()
    for suf in (low_suffix, high_suffix):
        if suf and low.endswith(suf.lower()):
            return stem[:-len(suf)]
    return stem


def pair_by_suffix(names, low_suffix=LOW_SUFFIX, high_suffix=HIGH_SUFFIX):
    """Pair ``name_low`` with ``name_high`` across a list of object names.

    Returns ``(pairs, unpaired)`` where pairs is ``[(low, [high, ...]), ...]``
    in the order the lows appear -- several highs can feed one low, which is
    normal when the detail is modelled in pieces. This is the convention every
    game pipeline already uses, so a whole scene can be baked in one press
    without anyone clicking through pairings."""
    lows, highs = [], {}
    for name in names:
        # Classify on the name WITHOUT the duplicate tail, so panel_high.001
        # is a high poly rather than an unrecognised object.
        stem = strip_duplicate_tail(name).lower()
        if low_suffix and stem.endswith(low_suffix.lower()):
            lows.append(name)
        elif high_suffix and stem.endswith(high_suffix.lower()):
            highs.setdefault(base_name(name, low_suffix, high_suffix),
                             []).append(name)
    pairs = []
    matched = set()
    for low in lows:
        key = base_name(low, low_suffix, high_suffix)
        group = highs.get(key, [])
        if group:
            pairs.append((low, list(group)))
            matched.add(key)
    unpaired = [n for n in names
                if n not in [p[0] for p in pairs]
                and n not in [h for _l, g in pairs for h in g]]
    return pairs, unpaired


def suggested_extrusion(low_size, high_size, margin=1.25, minimum=0.001):
    """How far the cage should stand off the low poly, from the two bounding
    box sizes (each an (x, y, z) tuple, in metres).

    The cage has to enclose the high poly everywhere, so the floor is half the
    largest per-axis overhang, times a margin for the places a bounding box
    does not describe well (a spike, a bolt head). Never returns zero: a cage
    flush with the low poly bakes nothing."""
    overhang = 0.0
    for i in range(3):
        diff = float(high_size[i]) - float(low_size[i])
        if diff > overhang:
            overhang = diff
    base = (overhang / 2.0) * margin
    if base < minimum:
        # No measurable overhang (a decimated low of the same silhouette):
        # scale a default off the object rather than hard-coding a metre.
        base = max(max(float(s) for s in low_size) * 0.02, minimum)
    return base


def corrected_extrusion(extrusion, base_size, achieved_size, needed_size,
                        margin=1.05, limit=8.0):
    """Scale a cage standoff up so the cage actually encloses the high poly.

    A cage is pushed along SMOOTH vertex normals (face normals would split it
    at every hard edge, which is where it is most needed), and on a box corner
    that normal is the diagonal -- so a 0.375 m push only grows the box by
    0.217 m per axis. Rather than guess that factor from the shape, measure
    what the first push achieved and scale by the shortfall.

    The scale has to be computed on the GROWTH, not on the total size: a
    dimension is ``base + 2 * d * k`` for some unknown tilt factor k, so only
    the ``- base`` part moves with the standoff. Scaling the totals instead
    under-corrects every time and leaves the cage inside the high poly.

    All three sizes are bounding-box (x, y, z) tuples. Returns the original
    when it already covers; `limit` stops a degenerate measurement from
    inflating the cage without bound."""
    worst = 1.0
    for i in range(3):
        base = float(base_size[i])
        grown = float(achieved_size[i]) - base
        need = float(needed_size[i]) - base
        if need > grown > 1e-9:
            worst = max(worst, need / grown)
    if worst <= 1.0:
        return extrusion
    return extrusion * min(worst * margin, limit)


def image_name(low_name, bake_type, low_suffix=LOW_SUFFIX):
    """``bolt_low`` + NORMAL -> ``bolt_normal``: the asset's name, not the
    low-poly object's, because the map belongs to the asset."""
    return "%s_%s" % (base_name(low_name, low_suffix, ""), suffix(bake_type))


def cage_name(low_name):
    return "%s_cage" % low_name
