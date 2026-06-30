# Pure custom-gizmo shape geometry (stdlib math only, no bpy).
#
# Lives apart from the gizmo classes so it imports cleanly headless and stays
# easy to unit-test: each function returns a flat tuple of (x, y, z) triangle
# vertices ready for Gizmo.new_custom_shape('TRIS', ...).
import math


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
