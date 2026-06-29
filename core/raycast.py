# Ekran (2D) <-> dunya (3D) donusumleri.
from bpy_extras import view3d_utils
from mathutils import Vector


def screen_to_plane(region, rv3d, coord, plane_co):
    """2D ekran koordinatini, plane_co'dan gecip kameraya bakan duzleme yansit."""
    return view3d_utils.region_2d_to_location_3d(
        region, rv3d, Vector((coord[0], coord[1])), plane_co
    )


def view_direction(rv3d):
    """Ekranin icine dogru bakan birim vektor."""
    return (rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))).normalized()


def view_right_up(rv3d):
    """Grid'i dogru hizalamak icin ekranin sag ve yukari eksenleri (dunyada)."""
    right = (rv3d.view_rotation @ Vector((1.0, 0.0, 0.0))).normalized()
    up = (rv3d.view_rotation @ Vector((0.0, 1.0, 0.0))).normalized()
    return right, up
