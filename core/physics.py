# Pure cable-settle physics, stdlib arithmetic only: a deterministic
# position-based (Jakobsen Verlet) relaxation of a particle chain under
# gravity, with pinned anchors, segment distance constraints and an injected
# collision callback -- the Cable tool's G "gravity" mode. Unlike the parabolic
# sag in core/transform.cable_points, the settled rope reacts to the scene: the
# operator wires `collide` to a nearest-surface query so the cable drapes over
# obstacles and rests on geometry. No bpy / mathutils and no time or
# randomness (fixed iteration counts), so the settle is unit-tested without
# Blender with synthetic colliders.
import math


def _dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
                     + (a[2] - b[2]) ** 2)


def chain_rest_lengths(points, slack=1.0):
    """Per-segment rest lengths for a particle chain: each segment's current
    (straight) length scaled by `slack`. slack 1.0 = taut; > 1.0 gives the
    rope extra length to droop with. Pure arithmetic."""
    s = max(0.0, float(slack))
    return [_dist(a, b) * s for a, b in zip(points[:-1], points[1:])]


def settle_chain(points, pinned=(), gravity=(0.0, 0.0, -1.0), strength=None,
                 slack=1.15, iterations=48, passes=4, damping=0.94,
                 collide=None, collide_every=4):
    """Relax a particle chain into its hanging shape and return the settled
    points (tuples). `points` are the initial particles IN ORDER (build them by
    sub-dividing the anchor spans); `pinned` are indices held exactly fixed --
    pin at least both ends or the chain just falls. `gravity` is a direction
    (normalized here); `strength` is the per-iteration pull in metres, default
    0.3% of the rope's rest length (scale-free). `slack` scales the segment
    rest lengths (1.0 = taut, 1.15 = 15% extra rope). Each of the `iterations`
    steps applies inertia (damped Verlet) + gravity, then `passes` sweeps of
    distance-constraint projection; every `collide_every` iterations (and once
    at the end) free particles are passed through `collide(p) -> corrected
    point or None`, so the rope comes to rest on obstacles instead of passing
    through them. Deterministic: no time step, no randomness. Fewer than 2
    points, or no free particles, come back unchanged."""
    cur = [tuple(p) for p in points]
    n = len(cur)
    pins = {i for i in pinned if -n <= i < n}
    pins = {i % n for i in pins}
    if n < 2 or len(pins) >= n or iterations <= 0:
        return cur

    rest = chain_rest_lengths(cur, slack)
    total = sum(rest)
    if total <= 0.0:
        return cur
    g_len = _dist(gravity, (0.0, 0.0, 0.0))
    if g_len <= 0.0:
        return cur
    if strength is None:
        strength = total * 0.003
    g = tuple(gravity[k] / g_len * strength for k in range(3))

    prev = list(cur)
    for it in range(int(iterations)):
        # Inertia + gravity (pins never move).
        for i in range(n):
            if i in pins:
                continue
            px, py, pz = prev[i]
            x, y, z = cur[i]
            prev[i] = cur[i]
            cur[i] = (x + (x - px) * damping + g[0],
                      y + (y - py) * damping + g[1],
                      z + (z - pz) * damping + g[2])
        # Project the segment length constraints.
        for _ in range(max(1, int(passes))):
            for s in range(n - 1):
                a, b = cur[s], cur[s + 1]
                d = _dist(a, b)
                if d <= 1e-12:
                    continue
                diff = (d - rest[s]) / d
                a_pin, b_pin = s in pins, (s + 1) in pins
                if a_pin and b_pin:
                    continue
                # Split the correction between the free ends.
                wa = 0.0 if a_pin else (1.0 if b_pin else 0.5)
                wb = 0.0 if b_pin else (1.0 if a_pin else 0.5)
                delta = tuple((b[k] - a[k]) * diff for k in range(3))
                if wa:
                    cur[s] = tuple(a[k] + delta[k] * wa for k in range(3))
                if wb:
                    cur[s + 1] = tuple(b[k] - delta[k] * wb for k in range(3))
        # Push free particles out of the scene every few iterations.
        if collide is not None and (it % max(1, int(collide_every))) == 0:
            _collide_free(cur, pins, prev, collide)
    if collide is not None:
        _collide_free(cur, pins, prev, collide)
    return cur


def _collide_free(cur, pins, prev, collide):
    """Apply the collision callback to every free particle; a corrected
    particle also loses its velocity (prev = cur) so it rests instead of
    jittering against the surface."""
    for i in range(len(cur)):
        if i in pins:
            continue
        fixed = collide(cur[i])
        if fixed is not None:
            cur[i] = tuple(fixed)
            prev[i] = cur[i]
