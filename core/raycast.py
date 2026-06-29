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


def ray_cast_surface(context, region, rv3d, coord):
    """Shoot the mouse ray into the scene and return the first surface hit as
    (location, normal, object) in world space, or None if nothing is hit. Used
    by decal placement to stick a decal onto whatever is under the cursor."""
    co = Vector((coord[0], coord[1]))
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, co)
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, co)
    depsgraph = context.evaluated_depsgraph_get()
    hit, location, normal, _index, obj, _matrix = context.scene.ray_cast(
        depsgraph, origin, direction)
    if not hit:
        return None
    return location, normal, obj
