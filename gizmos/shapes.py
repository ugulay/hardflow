# Pure custom-gizmo shape geometry (stdlib math only, no bpy).
#
# Lives apart from the gizmo classes so it imports cleanly headless and stays
# easy to unit-test: each function returns a flat tuple of (x, y, z) triangle
# vertices ready for Gizmo.new_custom_shape('TRIS', ...).
import math


def ring_tris(segments=24, radius=0.9, width=0.09):
    """Triangle soup for a flat ring (annulus) lying in the local XY plane,
    centred on the origin.

    The Offset drag gizmo's handle: a border you grab and pull inward, which is
    literally what the tool does to a face's border, so the handle reads as the
    operation. Flat on purpose -- it sits in the plane of the face it insets,
    where an arrow would point away from the surface and mean "extrude"."""
    verts = []
    two_pi = math.pi * 2.0
    inner = max(radius - width, 0.0)
    ring = [(math.cos(two_pi * i / segments), math.sin(two_pi * i / segments))
            for i in range(segments)]
    for i in range(segments):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % segments]
        o0 = (x0 * radius, y0 * radius, 0.0)
        o1 = (x1 * radius, y1 * radius, 0.0)
        i0 = (x0 * inner, y0 * inner, 0.0)
        i1 = (x1 * inner, y1 * inner, 0.0)
        # Two triangles per segment, wound both ways so the ring is visible
        # from either side (a face can be oriented away from the viewer).
        verts += [i0, o0, o1, i0, o1, i1]
        verts += [i0, o1, o0, i0, i1, o1]
    return tuple(verts)


def arrow_tris(segments=12, shaft_radius=0.04, shaft_length=0.62,
               head_radius=0.13, head_length=0.42):
    """Triangle soup for a +Z arrow (a thin shaft cylinder topped by a cone),
    in gizmo-local space spanning z in [0, shaft_length + head_length]. Used by
    the Push/Pull drag gizmo as a draggable handle pointing along a face normal.
    """
    verts = []
    two_pi = math.pi * 2.0
    head_base = shaft_length
    tip = (0.0, 0.0, shaft_length + head_length)
    ring = [(math.cos(two_pi * i / segments), math.sin(two_pi * i / segments))
            for i in range(segments)]
    for i in range(segments):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % segments]
        # shaft wall (a quad split into two triangles)
        b0 = (x0 * shaft_radius, y0 * shaft_radius, 0.0)
        b1 = (x1 * shaft_radius, y1 * shaft_radius, 0.0)
        s0 = (x0 * shaft_radius, y0 * shaft_radius, head_base)
        s1 = (x1 * shaft_radius, y1 * shaft_radius, head_base)
        verts += [b0, b1, s1, b0, s1, s0]
        # shaft base cap
        verts += [(0.0, 0.0, 0.0), b1, b0]
        # cone wall
        h0 = (x0 * head_radius, y0 * head_radius, head_base)
        h1 = (x1 * head_radius, y1 * head_radius, head_base)
        verts += [h0, h1, tip]
        # cone base ring cap
        verts += [(0.0, 0.0, head_base), h1, h0]
    return tuple(verts)
