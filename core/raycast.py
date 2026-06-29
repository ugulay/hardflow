# Ekran (2D) <-> dunya (3D) donusumleri.
from bpy_extras import view3d_utils
from mathutils import Vector
from mathutils.geometry import intersect_line_plane


def screen_to_plane(region, rv3d, coord, plane_co):
    """2D ekran koordinatini, plane_co'dan gecip kameraya bakan duzleme yansit."""
    return view3d_utils.region_2d_to_location_3d(
        region, rv3d, Vector((coord[0], coord[1])), plane_co
    )


def ray_to_plane(region, rv3d, coord, plane_co, plane_no):
    """Fare isinini (plane_co, plane_no) ile tanimli keyfi duzlemle kesistir.
    Duzlem normali bakisa dik (kenar-on) ise None doner. VIEW duzlemi icin
    plane_no = view_direction vererek screen_to_plane ile ayni sonucu uretir."""
    co = Vector((coord[0], coord[1]))
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, co)
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, co)
    return intersect_line_plane(origin, origin + direction, plane_co, plane_no)


def view_direction(rv3d):
    """Ekranin icine dogru bakan birim vektor."""
    return (rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))).normalized()


def view_right_up(rv3d):
    """Grid'i dogru hizalamak icin ekranin sag ve yukari eksenleri (dunyada)."""
    right = (rv3d.view_rotation @ Vector((1.0, 0.0, 0.0))).normalized()
    up = (rv3d.view_rotation @ Vector((0.0, 1.0, 0.0))).normalized()
    return right, up


def world_to_plane_uv(point, origin, right, up):
    """3D dunya noktasini, origin'den gecen (right, up) duzleminin yerel 2D
    (u, v) metre koordinatina projekte et."""
    d = point - origin
    return (d.dot(right), d.dot(up))


def plane_uv_to_world(u, v, origin, right, up):
    """Duzlem (u, v) metre koordinatini geri 3D dunya noktasina cevir."""
    return origin + right * u + up * v


def world_to_screen(region, rv3d, point):
    """3D dunya noktasini 2D ekran (region) koordinatina projekte et.
    Nokta kameranin arkasindaysa None dondurur."""
    return view3d_utils.location_3d_to_region_2d(region, rv3d, point)
