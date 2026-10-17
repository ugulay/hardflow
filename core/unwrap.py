# Pure hard-surface UV seam decision -- stdlib only, no bpy.
#
# Where a seam belongs on a hard-surface model is not a mystery: it belongs on
# the hard edges, which on a boolean model are exactly the cut boundaries. The
# useful part is that Hardflow already knows which edges those are -- Smart
# Sharpen marks every boolean-cut edge sharp and bevel-weighted (see
# core/geometry.mark_sharp_edges) -- so "seam along the cuts" is not a guess
# from geometry alone, it is reading marks the add-on itself made while
# cutting. That is the whole idea behind "cut-aware": the modelling history is
# already written into the mesh, and the unwrapper can just read it.
#
# This module decides, per edge, whether it is a seam. The bmesh marking and
# the actual unwrap/pack live in operators/unwrap.py -- which measures the
# dihedral angle with bmesh's own edge.calc_face_angle, exactly as
# core/geometry.mark_sharp_edges does, so the two passes agree by construction.
# Deliberately dependency-free (not even a sibling core import), so
# tests/test_core.py can execute it standalone.

# Why an edge became a seam, for the operator's report (and so a user can tell
# "it followed my cuts" from "it fell back to the angle rule").
BY_SHARP = 'sharp'
BY_BEVEL = 'bevel'
BY_ANGLE = 'angle'
BY_BOUNDARY = 'boundary'
BY_NON_MANIFOLD = 'non_manifold'


def should_seam(angle=0.0, sharp=False, bevel_weight=0.0, boundary=False,
                non_manifold=False, angle_limit=1.0472, use_sharp=True,
                use_bevel_weight=True, use_angle=True, weight_threshold=0.01):
    """Whether one edge should carry a UV seam, and why.

    Returns ``(seam, reason)`` -- reason is "" when it is not a seam. Order
    matters: an explicit mark beats the angle rule, because a mark is a
    decision somebody (or Smart Sharpen, on a cut) already made, while the
    angle is only an inference.

    A boundary edge is always a seam -- the island has to end somewhere -- and
    so is a non-manifold edge, which no unwrapper can lay flat across.
    """
    if boundary:
        return (True, BY_BOUNDARY)
    if non_manifold:
        return (True, BY_NON_MANIFOLD)
    if use_sharp and sharp:
        return (True, BY_SHARP)
    if use_bevel_weight and bevel_weight >= weight_threshold:
        return (True, BY_BEVEL)
    if use_angle and angle >= angle_limit:
        return (True, BY_ANGLE)
    return (False, "")


def seam_edges(edges, **rules):
    """Run `should_seam` over an iterable of edge dicts and return
    ``(keys, counts)``: the keys to mark, and how many came from each reason.

    Each edge is a dict with any of: ``key``, ``angle``, ``sharp``,
    ``bevel_weight``, ``boundary``, ``non_manifold``. Missing fields take the
    predicate's defaults, so a caller can measure only what it has."""
    keys = []
    counts = {}
    for e in edges:
        seam, reason = should_seam(
            angle=e.get('angle', 0.0),
            sharp=e.get('sharp', False),
            bevel_weight=e.get('bevel_weight', 0.0),
            boundary=e.get('boundary', False),
            non_manifold=e.get('non_manifold', False),
            **rules)
        if seam:
            keys.append(e.get('key'))
            counts[reason] = counts.get(reason, 0) + 1
    return keys, counts


def pack_margin(padding_px, texture_size):
    """UV-space island margin for a padding given in PIXELS.

    Game artists specify padding in pixels (4 px at 1k, 8 px at 4k) because
    that is what stops bleeding in the baked texture, while Blender's packer
    wants a fraction of the 0-1 square. Clamped to a sane range so a silly
    input cannot pack every island onto itself. Returns 0.0 when there is
    nothing meaningful to compute."""
    if padding_px <= 0.0 or texture_size <= 0:
        return 0.0
    margin = float(padding_px) / float(texture_size)
    return min(margin, 0.25)


def describe(counts):
    """One-line summary of a seam_edges count dict, in a stable order, for the
    operator's report: "42 seam(s): 30 sharp, 8 angle, 4 boundary"."""
    total = sum(counts.values())
    if not total:
        return "no seams"
    order = (BY_SHARP, BY_BEVEL, BY_ANGLE, BY_BOUNDARY, BY_NON_MANIFOLD)
    parts = ["%d %s" % (counts[r], r) for r in order if counts.get(r)]
    return "%d seam(s): %s" % (total, ", ".join(parts))
