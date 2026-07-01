# Pure Parallax Occlusion Mapping (POM) math -- stdlib only, no bpy / gpu / blf.
#
# A plain decal is a flat, textured quad: its height map can only perturb the
# *normal* (a Bump node), so at a grazing angle it still reads as a sticker.
# POM makes the height map read as real geometry by shifting, per fragment, the
# UV that gets sampled ALONG THE VIEW RAY -- so recessed panel lines slide behind
# their lip and raised rivets self-occlude, exactly like the commercial decal
# tools. The shader-node network in core/decal.py unrolls the very algorithm
# implemented (and unit-tested) here, so this module is the correctness anchor
# for a node graph that can only be verified live inside Blender.
#
# Coordinate convention -- everything is in *tangent space* (T, B, N):
#   * the view vector points FROM the surface TOWARD the camera,
#   * +Z (its N component) is out of the surface,
#   * a "depth" value d in [0, 1] describes the height field: d = 0 is the outer
#     (flush) surface and d = 1 is the deepest recess. We march the ray from the
#     surface (layer depth 0) inward until it first sinks below the sampled
#     surface, then refine to the exact crossing.
#
# Layer rule: stdlib only (mirrors core/decal_math.py, core/grid.py) so it runs
# under plain CPython and is covered by tests/test_core.py.


def luminance(rgb):
    """Rec. 709 relative luminance of an (r, g, b) triple in [0, 1].

    The node graph converts the height/color texture to a single depth channel
    with a Color->BW node, which uses these exact weights; a decal with no
    dedicated height map drives POM from its color's luminance, so this is the
    shared definition. Pure float."""
    r, g, b = rgb[0], rgb[1], rgb[2]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def tangent_space_view(view_world, tangent, bitangent, normal):
    """Express a world-space view direction in the surface's tangent basis.

    POM steps the UV in the plane of the surface, so the world view vector has to
    be resolved onto (T, B, N): the result is (V.T, V.B, V.N) -- its X/Y drive the
    lateral UV shift and its Z (the cosine to the normal) drives how grazing the
    angle is. Pure dot products; returns a 3-tuple."""
    def dot(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
    return (dot(view_world, tangent),
            dot(view_world, bitangent),
            dot(view_world, normal))


def dynamic_layer_count(view_ts, min_layers=8, max_layers=32):
    """Number of ray-march layers to use for this view: fewer head-on (cheap, the
    ray barely shifts) and more at grazing angles (where under-sampling shows as
    stair-stepping). Linear in |cos| between the two anchors, where cos is the
    normalized N-component of the tangent-space view.

        head-on  (|cos| = 1) -> min_layers
        grazing  (|cos| = 0) -> max_layers

    Returns an int clamped to [min_layers, max_layers]. Pure."""
    lo, hi = int(min_layers), int(max_layers)
    if hi < lo:
        lo, hi = hi, lo
    vx, vy, vz = view_ts
    length = (vx * vx + vy * vy + vz * vz) ** 0.5
    cos = abs(vz / length) if length > 1e-9 else 1.0
    n = hi + (lo - hi) * cos
    n = int(round(n))
    return lo if n < lo else hi if n > hi else n


def _view_xy_scaled(view_ts, scale):
    """The full-depth ("offset-limiting") UV displacement P = scale * view.xy.

    Offset limiting drops the classic 1/view.z divide, which is what stops the
    texture "swimming" at grazing angles -- P stays bounded by `scale` instead of
    exploding as view.z -> 0. The view is normalized first so `scale` is a true
    UV-space depth. Returns (px, py)."""
    vx, vy, vz = view_ts
    length = (vx * vx + vy * vy + vz * vz) ** 0.5
    if length < 1e-9:
        return (0.0, 0.0)
    return (scale * vx / length, scale * vy / length)


def parallax_delta_uv(view_ts, scale, num_layers):
    """Per-layer UV step of the ray-march: the total offset-limiting displacement
    P (see _view_xy_scaled) divided into `num_layers` equal pieces. The marched UV
    moves by -deltaUV each layer. Returns (dux, duy)."""
    n = max(1, int(num_layers))
    px, py = _view_xy_scaled(view_ts, scale)
    return (px / n, py / n)


def steep_parallax_uv(sample_depth, uv0, view_ts, scale, num_layers):
    """Steep Parallax Mapping: step the UV along the view ray one layer at a time
    until the ray's running depth (0, 1/N, 2/N, ...) first meets or passes the
    sampled surface depth, and return that layer's UV plus the state needed to
    refine it.

    `sample_depth(uv)` returns the surface depth d in [0, 1] at `uv` (0 flush,
    1 deepest). Returns (uv, prev_uv, layer_depth, depth_here) where `uv` is the
    first below-surface layer, `prev_uv` the last above-surface layer, and the
    two depths bracket the true crossing for parallax_occlusion_uv. A flat field
    (depth 0) returns uv0 immediately -- no shift. Pure."""
    n = max(1, int(num_layers))
    dux, duy = parallax_delta_uv(view_ts, scale, n)
    layer_step = 1.0 / n
    u, v = uv0[0], uv0[1]
    cur_layer = 0.0
    depth_here = sample_depth((u, v))
    steps = 0
    # March while the ray is still above the surface (layer shallower than the
    # sampled recess). Cap at n steps so a pathological field can't loop forever.
    while cur_layer < depth_here and steps < n:
        u -= dux
        v -= duy
        depth_here = sample_depth((u, v))
        cur_layer += layer_step
        steps += 1
    prev_uv = (u + dux, v + duy)
    return (u, v), prev_uv, cur_layer, depth_here


def parallax_occlusion_uv(sample_depth, uv0, view_ts, scale, num_layers):
    """Full Parallax Occlusion Mapping: run the steep march, then linearly
    interpolate between the last two layers by where the ray actually crosses the
    height field, for a smooth sub-layer intersection instead of a quantized one.

    The refinement weight is the classic POM triangle-similarity blend:
        after  = depth(cur)  - layer(cur)         (<= 0, ray below surface)
        before = depth(prev) - layer(prev)        (>= 0, ray above surface)
        weight = after / (after - before)
    so the returned UV is `prev*weight + cur*(1-weight)`. For a constant-depth
    field d this collapses to the exact closed form uv0 - d * P, where
    P = scale * view.xy (see _view_xy_scaled) -- the invariant the unit tests
    pin. Returns the parallax-corrected (u, v) tuple. Pure, no bpy."""
    n = max(1, int(num_layers))
    layer_step = 1.0 / n
    (u, v), (pu, pv), cur_layer, depth_here = steep_parallax_uv(
        sample_depth, uv0, view_ts, scale, n)
    after = depth_here - cur_layer
    before = sample_depth((pu, pv)) - (cur_layer - layer_step)
    denom = after - before
    weight = (after / denom) if abs(denom) > 1e-9 else 0.0
    fu = pu * weight + u * (1.0 - weight)
    fv = pv * weight + v * (1.0 - weight)
    return (fu, fv)
