# Screen (2D) <-> world (3D) conversions.
from bpy_extras import view3d_utils
from mathutils import Vector
from mathutils.geometry import intersect_line_plane


def screen_to_plane(region, rv3d, coord, plane_co):
    """Project a 2D screen coordinate onto the plane passing through plane_co and
    facing the camera."""
    return view3d_utils.region_2d_to_location_3d(
        region, rv3d, Vector((coord[0], coord[1])), plane_co
    )


def ray_to_plane(region, rv3d, coord, plane_co, plane_no):
    """Intersect the mouse ray with an arbitrary plane defined by (plane_co,
    plane_no). Returns None if the plane normal is perpendicular to the view
    (edge-on). For the VIEW plane, passing plane_no = view_direction gives the
    same result as screen_to_plane."""
    co = Vector((coord[0], coord[1]))
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, co)
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, co)
    return intersect_line_plane(origin, origin + direction, plane_co, plane_no)


def view_direction(rv3d):
    """Unit vector pointing into the screen."""
    return (rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))).normalized()


def view_right_up(rv3d):
    """The screen's right and up axes (in world space) for aligning the grid
    correctly."""
    right = (rv3d.view_rotation @ Vector((1.0, 0.0, 0.0))).normalized()
    up = (rv3d.view_rotation @ Vector((0.0, 1.0, 0.0))).normalized()
    return right, up


def world_to_plane_uv(point, origin, right, up):
    """Project a 3D world point onto the local 2D (u, v) meter coordinate of the
    (right, up) plane passing through origin."""
    d = point - origin
    return (d.dot(right), d.dot(up))


def plane_uv_to_world(u, v, origin, right, up):
    """Convert a plane (u, v) meter coordinate back to a 3D world point."""
    return origin + right * u + up * v


def world_to_screen(region, rv3d, point):
    """Project a 3D world point onto a 2D screen (region) coordinate.
    Returns None if the point is behind the camera."""
    return view3d_utils.location_3d_to_region_2d(region, rv3d, point)


def basis_from_normal(normal, up_hint=Vector((0.0, 0.0, 1.0))):
    """Orthonormal (right, up, normal) basis for a construction plane facing
    `normal` -- the SketchUp construction plane derived from a picked face.
    Picks a stable tangent: world up, unless the normal is (near) vertical, in
    which case world +Y is used instead. Right-handed."""
    n = Vector(normal).normalized()
    up = Vector(up_hint).normalized()
    if abs(n.dot(up)) > 0.999:
        up = Vector((0.0, 1.0, 0.0))
    right = up.cross(n).normalized()
    up2 = n.cross(right).normalized()
    return right, up2, n


def closest_axis_distance(region, rv3d, coord, axis_co, axis_dir):
    """Signed distance along the axis line (axis_co + t*axis_dir) of the point
    on that axis nearest to the mouse ray through `coord`. Drives the Push/Pull
    drag: how far along the face normal the cursor reaches. Returns 0.0 when the
    ray is parallel to the axis."""
    co = Vector((coord[0], coord[1]))
    ray_d = view3d_utils.region_2d_to_vector_3d(region, rv3d, co)
    ray_o = view3d_utils.region_2d_to_origin_3d(region, rv3d, co)
    d = Vector(axis_dir).normalized()
    w0 = Vector(axis_co) - ray_o
    a = d.dot(d)                 # = 1 (d is unit)
    b = d.dot(ray_d)
    c = ray_d.dot(ray_d)
    e = d.dot(w0)
    f = ray_d.dot(w0)
    denom = a * c - b * b
    if abs(denom) < 1e-9:
        return 0.0               # ray parallel to the axis
    return (b * f - c * e) / denom


def ray_cast_surface_ex(context, region, rv3d, coord, ignore=None):
    """Shoot the mouse ray into the scene and return the first non-ignored hit as
    (location, normal, object, face_index, matrix_world) in world space, or None
    if nothing is hit. The extended form also gives the hit face index + the
    object's world matrix, for callers that need the face's geometry (e.g. an
    edge-aligned construction tangent).

    `ignore` is an optional set/list of objects to skip -- crucially the live
    placement preview itself, which otherwise sits under the cursor and steals the
    hit. The ray is restarted just past each ignored hit until it reaches a real
    surface."""
    co = Vector((coord[0], coord[1]))
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, co)
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, co)
    depsgraph = context.evaluated_depsgraph_get()
    ignore = set(ignore or ())
    for _ in range(16):     # bounded: skip at most 16 ignored layers
        hit, location, normal, index, obj, matrix = context.scene.ray_cast(
            depsgraph, origin, direction)
        if not hit:
            return None
        if obj not in ignore:
            return location, normal, obj, index, matrix
        origin = location + direction * 1e-4   # step past the ignored hit
    return None


def ray_cast_surface(context, region, rv3d, coord, ignore=None):
    """Shoot the mouse ray into the scene and return the first surface hit as
    (location, normal, object) in world space, or None if nothing is hit. Used
    by decal/asset placement to stick onto whatever is under the cursor. See
    ray_cast_surface_ex for the face index + matrix and the `ignore` behaviour."""
    hit = ray_cast_surface_ex(context, region, rv3d, coord, ignore)
    if hit is None:
        return None
    location, normal, obj, _index, _matrix = hit
    return location, normal, obj


def face_edge_tangent(obj, index, matrix, normal, near_point=None):
    """World-space tangent aligned to an edge of obj's face `index`, projected
    onto the surface plane, or None when the face can't be read (bad index /
    generative modifiers). Uses the base mesh, matching the Push/Pull index clamp.
    The shared glue that gives the surface tools their smart, edge-aligned
    orientation (the projection math lives in decal_math.dominant_tangent).

    With `near_point` (a world-space point) the chosen edge is the one NEAREST that
    point, so a shape drawn on a face lines up with the edge you started on -- the
    fix for the construction grid looking rotated on non-rectangular (e.g.
    boolean-cut parallelogram) faces, where the single longest edge isn't the one
    you mean. Without it the longest edge is used (decal / asset placement)."""
    from . import decal_math
    if obj is None or getattr(obj, 'type', None) != 'MESH':
        return None
    polys = obj.data.polygons
    if index < 0 or index >= len(polys):
        return None
    rot = matrix.to_3x3()
    verts = obj.data.vertices
    vids = list(polys[index].vertices)
    if near_point is not None:
        # Align to the face edge whose segment is closest to near_point.
        from mathutils.geometry import intersect_point_line
        wpts = [matrix @ verts[v].co for v in vids]
        best, best_d = None, None
        for i in range(len(vids)):
            a, b = wpts[i], wpts[(i + 1) % len(vids)]
            _pt, raw_t = intersect_point_line(near_point, a, b)
            t = max(0.0, min(1.0, raw_t))
            d = (near_point - a.lerp(b, t)).length
            if best_d is None or d < best_d:
                best_d, best = d, (b - a)
        tan = decal_math.dominant_tangent([tuple(best)], tuple(normal))
        return Vector(tan) if tan is not None else None
    edges = []
    for i in range(len(vids)):
        a = verts[vids[i]].co
        b = verts[vids[(i + 1) % len(vids)]].co
        edges.append(tuple(rot @ (b - a)))
    t = decal_math.dominant_tangent(edges, tuple(normal))
    return Vector(t) if t is not None else None
