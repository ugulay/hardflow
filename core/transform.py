# Pure transform / sizing helpers, stdlib arithmetic only (span dicing,
# cable-sag points, fit + adaptive sizing). No bpy / mathutils here, so these are
# unit-tested without Blender (mirrors core/grid.py and core/atlas.py).
import math


def fit_scale(insert_size, target_feature, fraction=0.25, default=1.0):
    """Uniform scale that fits an INSERT of size `insert_size` to `fraction` of a
    target's local feature size -- smart scale on placement. Returns
    `default` when either size is non-positive. Pure arithmetic, unit-tested; the
    bbox measurement lives in core/asset.py."""
    if insert_size <= 0.0 or target_feature <= 0.0:
        return default
    return (target_feature * fraction) / insert_size


def adaptive_dimension(max_dimension, fraction=0.02, min_value=0.001,
                       max_value=1.0):
    """A length that scales with an object's size: `fraction` of its largest
    dimension, clamped to [min_value, max_value]. Lets a bevel width / cut
    chamfer read the same on a 5 cm bracket and a 50 m hull instead of a fixed
    value that's invisible on one and huge on the other. Returns `min_value` when
    the dimension is unknown (<= 0). Pure arithmetic, unit-tested."""
    if max_dimension <= 0.0:
        return min_value
    return max(min_value, min(max_value, max_dimension * fraction))


def dedup_ring(points, tol=1e-5):
    """Drop near-duplicate CONSECUTIVE points from a boundary ring (list of
    (x, y, z)), including a trailing point coincident with the first -- the
    Cut-to-Trim footprint loop, which a curve then bevels into a panel line.
    Keeps input order; returns a new list. A ring that collapses below 2 distinct
    points comes back as-is (nothing to clean). Pure arithmetic (3D tuples)."""
    if len(points) < 2:
        return list(points)

    def close(a, b):
        return all(abs(a[i] - b[i]) <= tol for i in range(len(a)))

    out = [tuple(points[0])]
    for p in points[1:]:
        if not close(out[-1], p):
            out.append(tuple(p))
    # Drop a final point that loops back onto the first (the ring is implicitly
    # closed by the caller / the cyclic spline).
    if len(out) > 2 and close(out[-1], out[0]):
        out.pop()
    return out


def dice_coordinates(lo, hi, count):
    """Interior cut positions that slice the span [lo, hi] into `count` equal
    pieces. Returns the `count - 1` evenly spaced interior coordinates (empty for
    count <= 1). Pure arithmetic, unit-tested."""
    count = max(1, int(count))
    if count == 1 or hi <= lo:
        return []
    step = (hi - lo) / count
    return [lo + step * i for i in range(1, count)]


def cable_points(p0, p1, segments=12, sag=0.0, axis=2):
    """Points along one hanging-cable span from p0 to p1 (both endpoints
    included). The span is linearly interpolated, then drooped with a parabolic
    sag: 0 at the ends, `sag` metres at mid-span, pulling along -`axis` (gravity;
    axis 2 = world Z). sag=0 yields a straight segment. `segments` >= 1
    sub-divisions. Pure arithmetic -- no bpy/mathutils -- so the cable shape is
    unit-tested without Blender (the curve build lives in operators/pipe.py)."""
    segments = max(1, int(segments))
    out = []
    for i in range(segments + 1):
        t = i / segments
        p = [p0[k] + (p1[k] - p0[k]) * t for k in range(3)]
        p[axis] -= 4.0 * sag * t * (1.0 - t)
        out.append((p[0], p[1], p[2]))
    return out


def cable_chain(points, segments=12, sag=0.0, axis=2):
    """A sagging cable through a list of >=2 anchor points: each consecutive span
    is drooped with `cable_points` and the spans are joined without duplicating
    the shared anchors. Fewer than 2 points are returned unchanged. Pure
    arithmetic, no bpy."""
    if len(points) < 2:
        return [tuple(p) for p in points]
    out = [tuple(points[0])]
    for a, b in zip(points[:-1], points[1:]):
        out.extend(cable_points(a, b, segments, sag, axis)[1:])
    return out


def order_edge_paths(edges):
    """Order an unordered edge set (vertex-index pairs) into connected vertex
    chains -- the selected-edges -> Panel Line path builder (v1.20). An open run
    comes back as [v0, v1, ..., vn]; a closed loop repeats its first index at
    the end. Verts where more than two edges meet are junctions: chains stop
    there (several chains may share the junction vert), so a T / X selection
    becomes clean strips instead of one zig-zag. Duplicate and self edges are
    ignored. Deterministic: walks start from the lowest vertex index and prefer
    the lowest-index neighbour. Pure stdlib, unit-tested."""
    adj = {}
    unused = set()
    for a, b in edges:
        if a == b:
            continue
        key = (a, b) if a < b else (b, a)
        if key in unused:
            continue
        unused.add(key)
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    for v in adj:
        adj[v].sort()

    def take(a, b):
        key = (a, b) if a < b else (b, a)
        if key in unused:
            unused.remove(key)
            return True
        return False

    def walk(start, nxt):
        chain = [start, nxt]
        cur = nxt
        while len(adj[cur]) == 2:      # junctions / endpoints stop the walk
            step = None
            for n in adj[cur]:
                if take(cur, n):
                    step = n
                    break
            if step is None:
                break                  # closed back onto consumed edges
            chain.append(step)
            cur = step
        return chain

    chains = []
    # Open runs first: start at every vert that is not mid-path (degree != 2).
    for v in sorted(adj):
        if len(adj[v]) == 2:
            continue
        for n in adj[v]:
            if take(v, n):
                chains.append(walk(v, n))
    # Whatever is left is pure cycles; the walk returns to its start vertex.
    while unused:
        a, b = min(unused)
        take(a, b)
        chains.append(walk(a, b))
    return chains
