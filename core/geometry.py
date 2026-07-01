# Geometry generation with bmesh.
import math

import bpy
import bmesh

from . import bevel as _bevel
from . import topology as _topology


def snapshot_mesh(obj, name="hf_snapshot"):
    """Return an unlinked copy of obj's mesh data, for restoring it after a live
    modal preview (Push/Pull, Offset). The copy holds no users until restored,
    so free it with `free_mesh` when the modal ends."""
    snap = obj.data.copy()
    snap.name = name
    return snap


def restore_mesh(obj, snapshot):
    """Overwrite obj's mesh with the geometry stored in `snapshot` (from
    `snapshot_mesh`). Used each frame of a live preview to reset before
    re-applying the in-progress edit. Object Mode, no bpy.ops."""
    bm = bmesh.new()
    bm.from_mesh(snapshot)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def free_mesh(mesh):
    """Discard a snapshot mesh datablock once the preview is finished."""
    if mesh is not None and mesh.name in bpy.data.meshes:
        bpy.data.meshes.remove(mesh, do_unlink=True)


def _add_prism(bm, corners, view_dir, thickness, apex=None):
    """Append one closed prism to an existing bmesh. With apex=None every corner
    is extruded along the shared view_dir (Fixed orientation -> a straight
    prism). With apex set (a world-space camera position) each corner is extruded
    along its own ray from the apex, so the volume tapers toward the camera
    (Project orientation -> perspective). Returns True on success, False on a
    degenerate cap."""
    half = thickness * 0.5
    if apex is None:
        offs = [view_dir * half] * len(corners)
    else:
        offs = [(c - apex).normalized() * half for c in corners]
    vf = [bm.verts.new(c - o) for c, o in zip(corners, offs)]
    vb = [bm.verts.new(c + o) for c, o in zip(corners, offs)]
    try:
        f_front = bm.faces.new(vf)                   # front cap
        f_back = bm.faces.new(list(reversed(vb)))    # back cap
    except ValueError:
        bmesh.ops.delete(bm, geom=vf + vb, context='VERTS')
        return False
    # bmesh builds a face from colocated-but-distinct verts without raising, so
    # an all-identical / zero-area footprint slips past faces.new. Reject it by
    # area, cleaning up the geometry already added (matters for build_prisms,
    # which keeps appending to the same bmesh).
    if f_front.calc_area() <= 1e-12:
        bmesh.ops.delete(bm, geom=vf + vb, context='VERTS')
        return False
    n = len(vf)
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new((vf[i], vf[j], vb[j], vb[i]))  # side walls
        except ValueError:
            pass
    return True


def build_prism(corners, view_dir, thickness, name="hf_cutter", apex=None):
    """Turn a list of 3D corners on a plane into a closed prism (a cutter
    volume) by extruding along the view direction. corners must be at least 3
    points. Concave n-gons are accepted; self-intersecting polygons give broken
    results. apex (a camera position) tapers the prism with perspective; see
    `_add_prism`."""
    bm = bmesh.new()
    if not _add_prism(bm, corners, view_dir, thickness, apex):
        bm.free()
        return None
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_prisms(corner_sets, thickness, name="hf_cutter", apex=None):
    """Build ONE mesh holding a prism for every (corners, view_dir) pair in
    `corner_sets` -- the in-draw Array/Mirror copies baked into a single cutter
    (v1.4). apex (a camera position) tapers every prism with perspective for the
    Project orientation; None gives the straight Fixed extrude. Returns mesh
    data, or None if no prism could be built."""
    bm = bmesh.new()
    built = 0
    for corners, view_dir in corner_sets:
        if _add_prism(bm, corners, view_dir, thickness, apex):
            built += 1
    if built == 0:
        bm.free()
        return None
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_faces(corner_sets, name="hf_face"):
    """Build ONE mesh holding an n-gon face for every corner list in
    `corner_sets` (FACE mode with in-draw Array/Mirror copies). Each entry may be
    a bare corner list or a (corners, _ignored) pair. Returns mesh data or None."""
    bm = bmesh.new()
    built = 0
    for entry in corner_sets:
        corners = entry[0] if isinstance(entry, tuple) else entry
        try:
            bm.faces.new([bm.verts.new(co) for co in corners])
            built += 1
        except ValueError:
            pass
    if built == 0:
        bm.free()
        return None
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def _footprint_basis(view_dir):
    """A 2D (right, up) basis perpendicular to `view_dir`, for projecting the
    knife polygon and face centers into the same plane to test overlap."""
    from mathutils import Vector
    vd = Vector(view_dir).normalized()
    up = Vector((0.0, 0.0, 1.0))
    if abs(vd.dot(up)) > 0.999:
        up = Vector((0.0, 1.0, 0.0))
    right = vd.cross(up).normalized()
    up = vd.cross(right).normalized()
    return right, up


def _knife_footprint_faces(faces, local_corners, view_dir):
    """Subset of `faces` that actually sit under the drawn polygon, looking along
    `view_dir`: a face qualifies if its center projects inside the polygon, or any
    polygon corner projects inside the face. Restricting the bisect to these keeps
    a knife score local instead of slicing infinite planes across the whole mesh.
    Returns the matching faces, or all of them as a fallback when none match."""
    from mathutils import Vector
    from . import grid as gridmod
    right, up = _footprint_basis(view_dir)

    def proj(p):
        v = Vector(p)
        return (v.dot(right), v.dot(up))

    poly2 = [proj(c) for c in local_corners]
    if len(poly2) < 3:
        return faces
    out = []
    for f in faces:
        face2 = [proj(v.co) for v in f.verts]
        # Full polygon overlap (vertex-in-either + edge crossings), so a thin
        # score that only crosses a large face is caught too -- not just faces
        # whose center sits inside the drawn loop.
        if gridmod.polygons_overlap(poly2, face2):
            out.append(f)
    return out or list(faces)


def knife_polygon(obj, local_corners, view_dir):
    """Object Mode knife / zero-depth cut: score the closed polygon
    (`local_corners`, object-local) onto obj's mesh via bmesh on the object data
    (no Edit Mode needed). Each loop edge becomes a cutting plane swept along
    `view_dir`; only the faces under the drawn footprint are bisected, so a small
    score doesn't slice planes across the whole object. Returns the number of
    edges scored. The object-data counterpart of edit_knife_polygon."""
    from mathutils import Vector
    vd = Vector(view_dir).normalized()
    n = len(local_corners)
    if n < 2:
        return 0
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    scored = 0
    count = n if n >= 3 else n - 1
    for i in range(count):
        a = Vector(local_corners[i])
        b = Vector(local_corners[(i + 1) % n])
        edge = b - a
        if edge.length < 1e-9:
            continue
        plane_no = edge.cross(vd)
        if plane_no.length < 1e-9:
            continue
        plane_no.normalize()
        # Limit each pass to the faces under the footprint (re-gathered every
        # pass: a prior bisect changes the face set).
        faces = _knife_footprint_faces(bm.faces[:], local_corners, vd)
        verts = {v for f in faces for v in f.verts}
        edges = {e for f in faces for e in f.edges}
        geom = list(verts) + list(edges) + list(faces)
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=a,
                               plane_no=plane_no, clear_inner=False,
                               clear_outer=False)
        scored += 1
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return scored


def bisect_plane(obj, plane_co, plane_no, clear_inner=False, clear_outer=False):
    """Slice obj's whole mesh with one infinite plane (bmesh, no bpy.ops).
    `plane_co` / `plane_no` are object-local. clear_inner / clear_outer delete the
    geometry on the negative / positive side (a straight guillotine slice when
    both stay False just inserts the split loop). Returns the number of cut edges
    created. The single-plane primitive behind a future Slice verb; the
    footprint-limited variant is knife_polygon. Degenerate normal -> 0, no edit."""
    from mathutils import Vector
    no = Vector(plane_no)
    if no.length < 1e-9:
        return 0
    no.normalize()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6,
                                 plane_co=Vector(plane_co), plane_no=no,
                                 clear_inner=clear_inner, clear_outer=clear_outer)
    cut = sum(1 for e in res.get('geom_cut', ())
              if isinstance(e, bmesh.types.BMEdge))
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return cut


def estimate_thickness(obj, factor=2.0, minimum=1.0):
    """Thickness sufficient for the cutter to pierce all the way through the
    object."""
    d = obj.dimensions
    return max(d.x, d.y, d.z, minimum) * factor


def bevel_cutter(mesh, width, segments=2, profile=0.5):
    """Chamfer every edge of a cutter mesh in place, so a boolean CUT leaves
    bevelled recess walls instead of sharp ones (bevelled cut -- this
    bevels the *cutter*, distinct from bevel-on-cut which chamfers the target's
    cut edge). `width` <= 0 is a no-op. clamp_overlap keeps a thin cutter sane.
    Returns the mesh. Object Mode, pure bmesh."""
    if width <= 0.0:
        return mesh
    bm = bmesh.new()
    bm.from_mesh(mesh)
    if bm.edges:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=width,
                        offset_type='OFFSET', segments=max(1, int(segments)),
                        profile=profile, affect='EDGES', clamp_overlap=True)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def extract_faces(mesh, face_indices, thickness=0.0, name="HF_Extracted"):
    """Build a NEW mesh datablock from `face_indices` of `mesh` (its own local
    space), re-indexing the referenced vertices -- the 'Extract Cutter' patch.
    With `thickness` > 0 the patch is solidified into a closed volume + its
    normals recalculated, so it is a usable boolean cutter; thickness 0 leaves a
    flat face patch (still handy as a FACE / decal source). Returns the new mesh,
    or None when no valid faces were given. Object Mode, pure bmesh."""
    want = sorted({i for i in face_indices if i >= 0})
    if not want:
        return None
    src = bmesh.new()
    src.from_mesh(mesh)
    src.faces.ensure_lookup_table()
    nfaces = len(src.faces)
    dst = bmesh.new()
    vmap = {}
    made = 0
    for fi in want:
        if fi >= nfaces:
            continue
        f = src.faces[fi]
        verts = []
        for v in f.verts:
            nv = vmap.get(v.index)
            if nv is None:
                nv = dst.verts.new(v.co)
                vmap[v.index] = nv
            verts.append(nv)
        try:
            dst.faces.new(verts)
            made += 1
        except ValueError:
            pass                       # a duplicate face from overlapping input
    if made == 0:
        src.free()
        dst.free()
        return None
    if thickness > 0.0:
        dst.faces.ensure_lookup_table()
        bmesh.ops.solidify(dst, geom=list(dst.faces), thickness=thickness)
        bmesh.ops.recalc_face_normals(dst, faces=dst.faces)
    out = bpy.data.meshes.new(name)
    dst.to_mesh(out)
    dst.free()
    src.free()
    out.update()
    return out


def build_face(corners, name="hf_face"):
    """Build a single n-gon face from a list of corners on a plane (not a
    boolean; create face). At least 3 points."""
    bm = bmesh.new()
    verts = [bm.verts.new(co) for co in corners]
    try:
        bm.faces.new(verts)
    except ValueError:        # repeated vertex / invalid
        bm.free()
        return None
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_box(size=1.0, name="Hardflow_Cube"):
    """A unit cube of edge length `size`, centred on the origin -- a starting
    primitive for the direct-modeling tools (the caller positions it at the 3D
    cursor). Returns mesh data."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=max(1e-6, size))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_plane(size=1.0, name="Hardflow_Plane"):
    """A flat square of edge length `size` on the local XY plane, centred on the
    origin -- a starting surface for Push/Pull / Offset. Returns mesh data."""
    h = max(1e-6, size) * 0.5
    return build_face([(-h, -h, 0.0), (h, -h, 0.0), (h, h, 0.0), (-h, h, 0.0)],
                      name=name)


def build_line(length=2.0, axis='X', name="Hardflow_Guide"):
    """A single wire edge of `length`, centred on the origin along the chosen
    local axis -- a construction guide line to snap against (construction guides).
    The geometry snap picks up its two endpoints and the edge. Returns mesh data."""
    h = max(1e-6, length) * 0.5
    i = {'X': 0, 'Y': 1, 'Z': 2}.get(axis, 0)
    a = [0.0, 0.0, 0.0]
    b = [0.0, 0.0, 0.0]
    a[i] = -h
    b[i] = h
    bm = bmesh.new()
    va = bm.verts.new(a)
    vb = bm.verts.new(b)
    bm.edges.new((va, vb))
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_cylinder(radius=0.5, depth=1.0, segments=32, name="Hardflow_Cylinder"):
    """A capped cylinder of `radius` and `depth` (height along +/-Z), centred on
    the origin -- a starter primitive for the direct-modeling tools. `segments` is
    the number of sides. Returns mesh data; the caller positions the object."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False,
                          segments=max(3, int(segments)),
                          radius1=max(1e-4, radius), radius2=max(1e-4, radius),
                          depth=max(1e-4, depth))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_cone(radius=0.5, depth=1.0, segments=32, name="Hardflow_Cone"):
    """A cone: a `radius`-wide base tapering to a point over `depth` (+/-Z),
    centred on the origin. `segments` sides. Returns mesh data."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False,
                          segments=max(3, int(segments)),
                          radius1=max(1e-4, radius), radius2=0.0,
                          depth=max(1e-4, depth))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_uv_sphere(radius=0.5, segments=32, rings=16, name="Hardflow_Sphere"):
    """A UV sphere of `radius`, centred on the origin. `segments` = longitudinal
    divisions, `rings` = latitudinal. Returns mesh data."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=max(3, int(segments)),
                              v_segments=max(2, int(rings)),
                              radius=max(1e-4, radius))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_tube(radius=0.5, inner_radius=0.3, depth=1.0, segments=32,
               name="Hardflow_Tube"):
    """A hollow tube (a cylinder with a concentric bore): `radius` outer,
    `inner_radius` inner, `depth` tall (+/-Z), centred on the origin. `segments`
    sides. The inner radius is clamped below the outer. Returns mesh data. Pure
    bmesh built by hand (no create_cone bore primitive)."""
    segments = max(3, int(segments))
    outer = max(1e-4, radius)
    inner = max(1e-5, min(inner_radius, outer - 1e-4))
    h = max(1e-4, depth) * 0.5
    bm = bmesh.new()
    ob, ot, ib, it = [], [], [], []   # outer/inner bottom/top rings
    for i in range(segments):
        a = (i / segments) * math.tau
        c, s = math.cos(a), math.sin(a)
        ob.append(bm.verts.new((c * outer, s * outer, -h)))
        ot.append(bm.verts.new((c * outer, s * outer, h)))
        ib.append(bm.verts.new((c * inner, s * inner, -h)))
        it.append(bm.verts.new((c * inner, s * inner, h)))
    for i in range(segments):
        j = (i + 1) % segments
        for ring in ((ob[i], ob[j], ot[j], ot[i]),    # outer wall
                     (it[i], it[j], ib[j], ib[i]),     # inner wall
                     (ot[i], ot[j], it[j], it[i]),     # top annulus
                     (ib[i], ib[j], ob[j], ob[i])):    # bottom annulus
            try:
                bm.faces.new(ring)
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_pipe(points, radius=0.05, bevel_res=4, name="Hardflow_Pipe",
               closed=False):
    """Build a round-section pipe curve from a list of 3D points. At least 2
    points. `closed` makes the spline cyclic (a pipe/panel-line looping back to
    its start -- the Cut-to-Trim boundary ring). Returns curve data; the caller
    links it to an object."""
    if len(points) < 2:
        return None
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    spline = curve.splines.new('POLY')
    spline.points.add(len(points) - 1)   # one point already exists
    for i, p in enumerate(points):
        spline.points[i].co = (p[0], p[1], p[2], 1.0)
    spline.use_cyclic_u = closed
    curve.bevel_depth = radius
    curve.bevel_resolution = bevel_res
    curve.use_fill_caps = not closed     # a closed ring needs no end caps
    return curve


def profile_points(profile, radius):
    """2D cross-section outline for build_pipe_mesh / the Sweep tool. The box
    profiles ('SQUARE' -> radius x radius, 'RECT' -> 2*radius x radius) and the
    structural sections ('L' angle, 'U' channel, 'T' tee, 'I' I-beam, all sized to
    a ~2*radius envelope) return a closed list of (u, v) corners traced once
    around; 'ROUND' (or anything unknown) returns None so the round curve bevel
    path is used instead. The sections are concave but build_pipe_mesh sweeps them
    fine. Pure arithmetic."""
    r = radius
    t = r * 0.5            # flange / wall thickness for the structural sections
    if profile == 'SQUARE':
        return [(-r, -r), (r, -r), (r, r), (-r, r)]
    if profile == 'RECT':
        return [(-2 * r, -r), (2 * r, -r), (2 * r, r), (-2 * r, r)]
    if profile == 'L':     # angle: a bottom leg + a left leg
        return [(-r, -r), (r, -r), (r, -r + t), (-r + t, -r + t),
                (-r + t, r), (-r, r)]
    if profile == 'U':     # channel, open at the top
        return [(-r, -r), (r, -r), (r, r), (r - t, r), (r - t, -r + t),
                (-r + t, -r + t), (-r + t, r), (-r, r)]
    if profile == 'T':     # tee: a top flange + a centred stem
        return [(-r, r), (r, r), (r, r - t), (t * 0.5, r - t),
                (t * 0.5, -r), (-t * 0.5, -r), (-t * 0.5, r - t), (-r, r - t)]
    if profile == 'I':     # I-beam: top + bottom flange joined by a web
        w = r * 0.35       # half web width
        return [(-r, -r), (r, -r), (r, -r + t), (w, -r + t), (w, r - t),
                (r, r - t), (r, r), (-r, r), (-r, r - t), (-w, r - t),
                (-w, -r + t), (-r, -r + t)]
    return None


def build_pipe_mesh(points, profile_pts, name="Hardflow_Pipe"):
    """Sweep a closed 2D `profile_pts` cross-section along the 3D poly-line
    `points` to make a solid tube mesh -- the square / rectangular / custom pipe
    cross-sections (v1.6) the round curve bevel can't do. Frames are built with a
    stable up reference (parallel-ish transport). At least 2 points and a 3-point
    profile. Returns mesh data, or None when degenerate."""
    from mathutils import Vector
    pts = [Vector(p) for p in points]
    if len(pts) < 2 or len(profile_pts) < 3:
        return None

    # Per-point tangents (averaged at interior joints).
    tans = []
    for i in range(len(pts)):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == len(pts) - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[i + 1] - pts[i - 1])
        if t.length < 1e-9:
            t = Vector((0.0, 0.0, 1.0))
        tans.append(t.normalized())

    # Seed an up vector not parallel to the first tangent, then carry it along.
    up = Vector((0.0, 0.0, 1.0))
    if abs(tans[0].dot(up)) > 0.999:
        up = Vector((0.0, 1.0, 0.0))

    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        t = tans[i]
        side = up.cross(t)
        if side.length < 1e-9:
            side = Vector((1.0, 0.0, 0.0))
        side.normalize()
        vert_up = t.cross(side).normalized()
        up = vert_up           # carry forward to keep the frame from flipping
        ring = [bm.verts.new(p + side * u + vert_up * v) for u, v in profile_pts]
        rings.append(ring)

    m = len(profile_pts)
    built = 0
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(m):
            j = (k + 1) % m
            try:
                bm.faces.new((a[k], a[j], b[j], b[k]))
                built += 1
            except ValueError:
                pass
    if built == 0:                 # every side quad was degenerate -> no solid
        bm.free()
        return None
    for cap in (list(reversed(rings[0])), rings[-1]):
        try:                       # each cap independently: a bad start cap must
            bm.faces.new(cap)      # not skip the end cap
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_loft(loop_a, loop_b, caps=True, name="Hardflow_Loft"):
    """Bridge two equal-length point loops into a solid (loft / bridge): side
    quads between corresponding vertices, plus end caps. `loop_a`
    and `loop_b` are lists of 3D points of the SAME length (>= 3). Returns mesh
    data, or None when the loops are mismatched or degenerate."""
    from mathutils import Vector
    if len(loop_a) != len(loop_b) or len(loop_a) < 3:
        return None
    bm = bmesh.new()
    va = [bm.verts.new(Vector(p)) for p in loop_a]
    vb = [bm.verts.new(Vector(p)) for p in loop_b]
    n = len(va)
    for k in range(n):
        j = (k + 1) % n
        try:
            bm.faces.new((va[k], va[j], vb[j], vb[k]))
        except ValueError:
            pass
    if caps:
        try:
            bm.faces.new(list(reversed(va)))
            bm.faces.new(vb)
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_grid_mesh(segments, name="Hardflow_Grid"):
    """Build a wire reference grid (edges only, no faces) from a list of 2D line
    segments ((x1, y1), (x2, y2)) laid on the local XY plane -- the construction
    grid. The caller positions/orients the object. Vertices are
    de-duplicated so shared crossings weld. Returns mesh data, or None when the
    segment list is empty."""
    if not segments:
        return None
    bm = bmesh.new()
    cache = {}

    def vert(x, y):
        key = (round(x, 6), round(y, 6))
        v = cache.get(key)
        if v is None:
            v = bm.verts.new((x, y, 0.0))
            cache[key] = v
        return v

    for (x1, y1), (x2, y2) in segments:
        a, b = vert(x1, y1), vert(x2, y2)
        if a is not b:
            try:
                bm.edges.new((a, b))
            except ValueError:
                pass            # duplicate edge -> skip
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def extrude_faces(obj, face_indices, local_vec, keep_original=False):
    """Push/Pull: extrude the given faces (indices into obj.data.polygons) and
    move the new region by `local_vec` (an object-local Vector). Edits obj.data
    via bmesh in Object Mode. Returns True on success. Face indices must be valid
    on the base mesh -- generative modifiers that change the face count are not
    accounted for.

    `keep_original=False` removes the original (now interior) faces for a clean
    extrude, matching Edit Mode. `True` leaves the starting face in place --
    the Ctrl / "Copy" push-pull that stacks a new volume on the face."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    faces = [bm.faces[i] for i in face_indices if 0 <= i < len(bm.faces)]
    if not faces:
        bm.free()
        return False
    res = bmesh.ops.extrude_face_region(bm, geom=faces)
    moved = [g for g in res['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=local_vec, verts=moved)
    if not keep_original:
        # extrude_face_region leaves the source faces behind as the (interior)
        # bottom cap; drop them so the result is a clean, manifold extrude.
        bmesh.ops.delete(bm, geom=faces, context='FACES')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return True


def inset_faces(obj, face_indices, thickness, depth=0.0):
    """Offset/inset the given faces (indices into obj.data.polygons) inward by
    `thickness`, optionally raising/lowering the inner face by `depth`. Edits
    obj.data via bmesh in Object Mode. Returns True on success."""
    if thickness <= 0.0:
        return False
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    faces = [bm.faces[i] for i in face_indices if 0 <= i < len(bm.faces)]
    if not faces:
        bm.free()
        return False
    bmesh.ops.inset_region(bm, faces=faces, thickness=thickness, depth=depth,
                           use_even_offset=True, use_boundary=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return True


def inset_extrude_faces(obj, face_indices, thickness, local_vec):
    """Offset → Push/Pull combo: inset the given faces by `thickness`, then
    extrude the resulting inner face(s) by `local_vec` (object-local) -- one
    bmesh pass that makes a recess (negative vec) or raised panel (positive).
    `inset_region` keeps the input faces as the inner region, so they are what we
    extrude; the extrude is clean (drops the source face). Returns True on
    success, False on empty / out-of-range input."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    faces = [bm.faces[i] for i in face_indices if 0 <= i < len(bm.faces)]
    if not faces:
        bm.free()
        return False
    if thickness > 0.0:
        bmesh.ops.inset_region(bm, faces=faces, thickness=thickness,
                               use_even_offset=True, use_boundary=True)
    if local_vec.length > 1e-9:
        res = bmesh.ops.extrude_face_region(bm, geom=faces)
        moved = [g for g in res['geom'] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, vec=local_vec, verts=moved)
        bmesh.ops.delete(bm, geom=faces, context='FACES')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return True


# --- Edit Mode bridge (v1.3) --------------------------------------------
#
# These read/write the active edit-mesh via bmesh.from_edit_mesh /
# update_edit_mesh instead of object data, so the same modeling actions work
# mid-edit without a separate object. The operator owns entering/leaving Edit
# Mode (core stays free of bpy.ops); these just touch the live bmesh.


def selected_face_basis(obj):
    """Average local center + normal of obj's selected edit-mesh faces, as
    (center, normal) Vectors in object-local space, or None when nothing is
    selected. Drives the Edit Mode Push/Pull drag axis. Reads the live edit
    bmesh; obj must be in Edit Mode."""
    from mathutils import Vector
    bm = bmesh.from_edit_mesh(obj.data)
    faces = [f for f in bm.faces if f.select]
    if not faces:
        return None
    center = Vector((0.0, 0.0, 0.0))
    normal = Vector((0.0, 0.0, 0.0))
    for f in faces:
        center += f.calc_center_median()
        normal += f.normal
    center /= len(faces)
    if normal.length < 1e-9:
        normal = faces[0].normal.copy()
    return center, normal.normalized()


def flush_edit_mesh(obj):
    """Write the live edit-mesh (including selection) back to obj.data. Call this
    before snapshot_mesh in Edit Mode so the snapshot captures the current state."""
    bmesh.update_edit_mesh(obj.data)


def restore_edit_mesh(obj, snapshot):
    """Reload obj's live edit-mesh from `snapshot` (a mesh datablock captured with
    snapshot_mesh before editing, including its selection flags). The Edit Mode
    counterpart of restore_mesh: used each frame of a live modal preview to reset
    before re-applying the in-progress edit. obj must be in Edit Mode."""
    bm = bmesh.from_edit_mesh(obj.data)
    bm.clear()
    bm.from_mesh(snapshot)
    bmesh.update_edit_mesh(obj.data, destructive=True)


def edit_extrude_faces(obj, local_vec, keep_original=False):
    """Edit Mode Push/Pull: extrude obj's selected edit-mesh faces and move the
    new region by `local_vec` (object-local). With `keep_original=False` the
    original (now interior) faces are removed for a clean extrude; `True` keeps
    the starting face (Ctrl / "Copy" stack). The extruded cap is left
    selected. Returns True on success, False when no face is selected."""
    bm = bmesh.from_edit_mesh(obj.data)
    faces = [f for f in bm.faces if f.select]
    if not faces:
        return False
    res = bmesh.ops.extrude_face_region(bm, geom=faces)
    moved = [g for g in res['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=local_vec, verts=moved)
    if not keep_original:
        bmesh.ops.delete(bm, geom=faces, context='FACES')   # drop the old caps
    new_faces = {f for v in moved for f in v.link_faces}
    for f in bm.faces:
        f.select_set(f in new_faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.update_edit_mesh(obj.data)
    return True


def edit_inset_faces(obj, thickness, depth=0.0):
    """Edit Mode Offset: inset obj's selected edit-mesh faces by `thickness`
    (optionally raising the inner face by `depth`). The inner faces are left
    selected. Returns True on success, False when nothing is selected or the
    thickness is non-positive."""
    if thickness <= 0.0:
        return False
    bm = bmesh.from_edit_mesh(obj.data)
    faces = [f for f in bm.faces if f.select]
    if not faces:
        return False
    res = bmesh.ops.inset_region(bm, faces=faces, thickness=thickness,
                                 depth=depth, use_even_offset=True,
                                 use_boundary=True)
    inner = set(res.get('faces', []))
    if inner:
        for f in bm.faces:
            f.select_set(f in inner)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.update_edit_mesh(obj.data)
    return True


def edit_inset_extrude_faces(obj, thickness, local_vec):
    """Edit Mode Offset → Push/Pull combo: inset the selected faces by
    `thickness`, then extrude the inner faces by `local_vec` (object-local). The
    new cap is left selected. Returns True on success, False when nothing is
    selected."""
    bm = bmesh.from_edit_mesh(obj.data)
    faces = [f for f in bm.faces if f.select]
    if not faces:
        return False
    if thickness > 0.0:
        bmesh.ops.inset_region(bm, faces=faces, thickness=thickness,
                               use_even_offset=True, use_boundary=True)
    if local_vec.length > 1e-9:
        res = bmesh.ops.extrude_face_region(bm, geom=faces)
        moved = [g for g in res['geom'] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, vec=local_vec, verts=moved)
        bmesh.ops.delete(bm, geom=faces, context='FACES')
        new_faces = {f for v in moved for f in v.link_faces}
        for f in bm.faces:
            f.select_set(f in new_faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.update_edit_mesh(obj.data)
    return True


def edit_add_face(obj, local_corners, select=True, weld=True, weld_dist=1e-4):
    """Edit Mode draw: add the polygon `local_corners` (object-local points) as a
    new face into obj's edit-mesh -- the drawn shape becomes geometry inside the
    active mesh rather than a separate object. New geometry can be deselected by
    `select=False`. Returns True on success, False on a degenerate polygon.

    With `weld` (the default), the new face's vertices that land on existing mesh
    vertices (within `weld_dist`) are merged onto them, so the drawn face connects
    to the surrounding geometry instead of floating as a detached island -- the
    create-connected-faces behaviour."""
    if len(local_corners) < 3:
        return False
    bm = bmesh.from_edit_mesh(obj.data)
    new_verts = [bm.verts.new(co) for co in local_corners]
    try:
        face = bm.faces.new(new_verts)
    except ValueError:               # repeated vertex / duplicate face
        # The new verts were just created (faces.new failed before linking any
        # edge), so none belong to the surrounding mesh -- drop them all.
        for v in new_verts:
            if v.is_valid:
                bm.verts.remove(v)
        return False
    if face.calc_area() <= 1e-12:    # collinear / zero-area footprint -> useless
        bm.faces.remove(face)
        for v in new_verts:
            if v.is_valid:
                bm.verts.remove(v)
        return False
    if select:
        for f in bm.faces:
            f.select_set(False)
        face.select_set(True)
    bmesh.ops.recalc_face_normals(bm, faces=[face])
    if weld:
        # Merge the new face's verts onto coincident existing ones so the face
        # shares edges with the mesh it was drawn against (connected geometry).
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=weld_dist)
    bmesh.update_edit_mesh(obj.data, destructive=weld)
    return True


def nearest_edge_on_face(obj, face_index, local_point):
    """Return the (vi, vj) vertex-index pair of the polygon edge of
    `obj.data.polygons[face_index]` nearest to `local_point` (object-local), or
    None for a bad index. Lets the Object-Mode edge tools pick the edge under the
    cursor from a face raycast hit. Pure mesh-data read (no bpy.ops)."""
    from mathutils.geometry import intersect_point_line
    me = obj.data
    if not (0 <= face_index < len(me.polygons)):
        return None
    vs = list(me.polygons[face_index].vertices)
    best, best_d = None, None
    for k in range(len(vs)):
        a = me.vertices[vs[k]].co
        b = me.vertices[vs[(k + 1) % len(vs)]].co
        pt, t = intersect_point_line(local_point, a, b)
        t = max(0.0, min(1.0, t))
        d = (local_point - a.lerp(b, t)).length
        if best_d is None or d < best_d:
            best_d, best = d, (vs[k], vs[(k + 1) % len(vs)])
    return best


def nearest_face_to_point(obj, local_point):
    """Return the index of the base-mesh polygon whose center is nearest
    `local_point` (object-local), or -1 for an empty mesh. Maps an evaluated-mesh
    raycast hit (when generative modifiers push the hit face index past the base
    mesh) back onto a base face. Exact for deform-only modifiers; a best-effort
    nearest-pick for topology-changing ones (subdivision / array / mirror). Pure
    mesh-data read."""
    polys = obj.data.polygons
    best_i, best_d = -1, None
    for p in polys:
        d = (local_point - p.center).length_squared
        if best_d is None or d < best_d:
            best_d, best_i = d, p.index
    return best_i


def _next_loop_edge(edge, vert):
    """The edge continuing an edge loop through `vert`: only across a valence-4
    junction (a quad grid), the edge at `vert` that shares no face with `edge`.
    Returns a BMEdge or None (pole / boundary / triangle fan)."""
    if len(vert.link_edges) != 4:
        return None
    efaces = set(edge.link_faces)
    for oe in vert.link_edges:
        if oe is not edge and not (set(oe.link_faces) & efaces):
            return oe
    return None


def edge_loop(obj, edge_key):
    """Return the (vi, vj) edge keys of the edge loop through `edge_key`, walking
    both directions across valence-4 vertices (quad loops) and stopping at
    poles/boundaries. Returns [edge_key] when the edge isn't part of an
    extendable loop (e.g. an all-valence-3 mesh like a plain cube). Object Mode,
    pure bmesh read."""
    a, b = edge_key
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    nv = len(bm.verts)
    start = (bm.edges.get((bm.verts[a], bm.verts[b]))
             if (0 <= a < nv and 0 <= b < nv) else None)
    if start is None:
        bm.free()
        return [edge_key]
    loop, seen = [start], {start}
    for v0 in (start.verts[0], start.verts[1]):
        e, v = start, v0
        while True:
            ne = _next_loop_edge(e, v)
            if ne is None or ne in seen:
                break
            seen.add(ne)
            loop.append(ne)
            v = ne.other_vert(v)
            e = ne
    keys = [(e.verts[0].index, e.verts[1].index) for e in loop]
    bm.free()
    return keys


def _opposite_edge_in_quad(face, edge):
    """The edge across a quad `face` from `edge` (shares no vertex with it), or
    None for a non-quad. The 'ring' step, perpendicular to the edge loop."""
    if len(face.verts) != 4:
        return None
    ev = set(edge.verts)
    for oe in face.edges:
        if oe is not edge and not (set(oe.verts) & ev):
            return oe
    return None


def edge_ring(obj, edge_key):
    """Return the (vi, vj) edge keys of the edge ring through `edge_key` -- the
    parallel edges across a quad strip (the set a loop cut subdivides). Walks both
    faces of the edge via `_opposite_edge_in_quad`, stopping at boundaries /
    non-quads / closure. Returns [edge_key] when there's no ring. Pure bmesh."""
    a, b = edge_key
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    nv = len(bm.verts)
    start = (bm.edges.get((bm.verts[a], bm.verts[b]))
             if (0 <= a < nv and 0 <= b < nv) else None)
    if start is None:
        bm.free()
        return [edge_key]
    ring, seen = [start], {start}
    for f0 in start.link_faces:
        e, f = start, f0
        while True:
            oe = _opposite_edge_in_quad(f, e)
            if oe is None or oe in seen:
                break
            seen.add(oe)
            ring.append(oe)
            nxt = [nf for nf in oe.link_faces if nf is not f]
            if not nxt:
                break
            f, e = nxt[0], oe
    keys = [(e.verts[0].index, e.verts[1].index) for e in ring]
    bm.free()
    return keys


def _quad_partner(face, a_vert, edge, opp):
    """In quad `face`, the vertex of the opposite edge `opp` that joins `a_vert`
    (a vertex of `edge`) through a quad side edge -- so an oriented ring walk keeps
    the same side. Falls back to the geometrically nearest vertex of `opp`."""
    opp_verts = set(opp.verts)
    for fe in face.edges:
        if fe is edge or fe is opp:
            continue
        if a_vert in fe.verts:
            other = fe.other_vert(a_vert)
            if other in opp_verts:
                return other
    return min(opp.verts, key=lambda v: (v.co - a_vert.co).length_squared)


def _oriented_ring(start):
    """Ring edges from BMEdge `start`, each as (edge, a_vert, b_vert) with a_vert
    kept on a consistent side of the quad strip so a slide parameter moves the
    whole inserted loop the same way (no zig-zag). Walks both directions across
    opposite quad edges. Used by `loop_cut`'s slide."""
    a0, b0 = start.verts[0], start.verts[1]
    ring, seen = [(start, a0, b0)], {start}
    for f0 in start.link_faces:
        e, f, a_vert = start, f0, a0
        while True:
            oe = _opposite_edge_in_quad(f, e)
            if oe is None or oe in seen:
                break
            oa = _quad_partner(f, a_vert, e, oe)
            ob = oe.other_vert(oa)
            seen.add(oe)
            ring.append((oe, oa, ob))
            nxt = [nf for nf in oe.link_faces if nf is not f]
            if not nxt:
                break
            f, e, a_vert = nxt[0], oe, oa
    return ring


def loop_cut(obj, edge_key, cuts=1, slide=0.0):
    """Insert `cuts` edge loop(s) by subdividing the edge ring through `edge_key`
    (`edge_ring` + `bmesh.ops.subdivide_edges` with grid-fill so each quad in the
    strip is split). Object Mode. Returns the number of ring edges subdivided
    (0 on failure).

    `slide` in [-1, 1] positions a single inserted loop along the ring (0 = the
    midpoint, +1 toward one side, -1 the other), the loop-cut slide. It only
    applies for `cuts == 1`; multiple loops stay evenly spaced. The slide is made
    consistent across the strip via `_oriented_ring` so the loop doesn't zig-zag."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    nv = len(bm.verts)
    a, b = edge_key
    if not (0 <= a < nv and 0 <= b < nv):
        bm.free()
        return 0
    start = bm.edges.get((bm.verts[a], bm.verts[b]))
    if start is None:
        bm.free()
        return 0
    ring = _oriented_ring(start)
    edges = [e for (e, _a, _b) in ring]
    do_slide = cuts == 1 and abs(slide) > 1e-6
    # Identify original vs inserted verts by INDEX: subdivide_edges appends the
    # new verts after the originals (whose indices it preserves). A wrapper-set
    # `in` test fails after the op, and a custom int id gets interpolated onto the
    # new verts -- the index split is the reliable signal. The oriented ring is
    # recorded as index pairs BEFORE the op so each new vert can be matched to its
    # host edge and slid along it consistently.
    ring_idx = ([(av.index, bv.index) for (_e, av, bv) in ring]
                if do_slide else None)
    nv_before = len(bm.verts)
    bmesh.ops.subdivide_edges(bm, edges=edges, cuts=max(1, int(cuts)),
                              use_grid_fill=True)
    if do_slide:
        p = min(0.98, max(0.02, 0.5 + 0.5 * slide))
        bm.verts.ensure_lookup_table()
        lookup = {frozenset(k): k for k in ring_idx}
        for v in bm.verts:
            if v.index < nv_before:              # an original vert, not inserted
                continue
            # the new vertex sits on one ring edge: its two ORIGINAL neighbours
            # are that edge's endpoints. Reposition it along the oriented edge.
            ends = [n.index for n in (e.other_vert(v) for e in v.link_edges)
                    if n.index < nv_before]
            if len(ends) != 2:
                continue
            host = lookup.get(frozenset(ends))
            if host is None:
                continue
            a_idx, b_idx = host
            v.co = bm.verts[a_idx].co.lerp(bm.verts[b_idx].co, p)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return len(edges)


def bevel_object_edges(obj, edge_keys, width, segments=2, profile=0.5):
    """Object Mode: bevel the edges given as (vi, vj) vertex-index pairs into real
    chamfer geometry (bmesh.ops.bevel, affect EDGES). The destructive,
    pick-an-edge counterpart of `edit_bevel_edges` -- bevel one edge without
    entering Edit Mode. Returns the number of edges beveled, 0 when none match or
    width <= 0."""
    if width <= 0.0:
        return 0
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    wanted = set()
    nv = len(bm.verts)
    for a, b in edge_keys:
        if 0 <= a < nv and 0 <= b < nv:
            e = bm.edges.get((bm.verts[a], bm.verts[b]))
            if e is not None:
                wanted.add(e)
    if not wanted:
        bm.free()
        return 0
    n = len(wanted)
    bmesh.ops.bevel(bm, geom=list(wanted), offset=width, offset_type='OFFSET',
                    segments=max(1, int(segments)), profile=profile,
                    affect='EDGES', clamp_overlap=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return n


# --- Smart Bevel & topology cleanup (Super Modeling Mode) ---------------


def _join_tris(bm, faces):
    """Re-quad a triangle soup with `bmesh.ops.join_triangles`, tolerating older
    Blenders that lack the cmp_* comparison switches. In-place, no return."""
    kw = dict(angle_face_threshold=math.radians(40.0),
              angle_shape_threshold=math.radians(40.0))
    try:
        bmesh.ops.join_triangles(bm, faces=faces, cmp_seam=False, cmp_sharp=False,
                                 cmp_uvs=False, cmp_vcols=False,
                                 cmp_materials=False, **kw)
    except TypeError:                       # pre-cmp_* signature
        bmesh.ops.join_triangles(bm, faces=faces, **kw)


def _clean_boolean_slivers(bm, merge_dist=1e-4, degenerate_dist=1e-4,
                           collinear_eps=1e-6):
    """Stabilizing cleanup on `bm` before re-quadding (Module 4 / SubD stability):

      1. **merge coincident verts** (`remove_doubles`, `merge_dist`) -- a boolean
         drops duplicate verts along the seam;
      2. **collapse near-zero-area geometry** (`dissolve_degenerate`,
         `degenerate_dist`) -- the zero-length edges + sliver faces a cut leaves;
      3. **dissolve redundant mid-edge verts** -- a valence-2 vertex whose two
         neighbours are collinear with it (core.topology.redundant_vertex) adds
         nothing to a straight cut line but pinches a Subdivision surface.

    Each stage narrows the garbage a near-degenerate boolean result carries into a
    Subdivision modifier. In-place; returns the number of redundant verts
    dissolved. The caller wraps this so a cleanup hiccup never loses the mesh."""
    if merge_dist > 0.0 and bm.verts:
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=merge_dist)
    if degenerate_dist > 0.0 and bm.edges:
        bmesh.ops.dissolve_degenerate(bm, dist=degenerate_dist, edges=bm.edges[:])
    # Redundant valence-2 verts on a straight run -- collected AFTER the ops above
    # so every reference is live.
    redundant = []
    for v in bm.verts:
        le = v.link_edges
        if len(le) != 2:
            continue
        a = le[0].other_vert(v).co
        c = le[1].other_vert(v).co
        if _topology.redundant_vertex(tuple(a), tuple(v.co), tuple(c), collinear_eps):
            redundant.append(v)
    if redundant:
        bmesh.ops.dissolve_verts(bm, verts=redundant)
    return len(redundant)


def dissolve_boolean_ngons(obj, only_ngons=True, rejoin_quads=True,
                           clean_slivers=True, merge_dist=1e-4,
                           degenerate_dist=1e-4):
    """Clean up the n-gons a boolean cut (or a bevel) leaves behind: triangulate
    the 5+-sided faces, then -- when `rejoin_quads` -- join the fresh triangles
    back into quads where the surface stays flat, so the result is quad-friendly
    again instead of a triangle soup. Object Mode, bmesh only (no bpy.ops).

    When `clean_slivers` (Module 4 / MeshMachine-parity SubD stability), a
    stabilizing pass runs FIRST (_clean_boolean_slivers): merge doubles, collapse
    near-zero-area faces / zero-length edges, and dissolve redundant collinear
    valence-2 verts -- the degenerate garbage a boolean scatters that wrecks a
    Subdivision surface. Wrapped so a cleanup hiccup degrades to the plain re-quad
    rather than losing the mesh.

    `only_ngons` limits the re-quad pass to faces with more than 4 sides (tris and
    quads are left alone); pass False to re-triangulate every face. Returns the
    number of n-gon faces that were triangulated (0 when already clean)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    if clean_slivers:
        try:
            _clean_boolean_slivers(bm, merge_dist, degenerate_dist)
        except (RuntimeError, ValueError) as ex:
            print("[Hardflow] boolean sliver cleanup skipped: %s" % ex)
    ngons = [f for f in bm.faces if len(f.verts) > (4 if only_ngons else 2)]
    n = len(ngons)
    if n:
        res = bmesh.ops.triangulate(bm, faces=ngons)
        if rejoin_quads:
            fresh = [f for f in res.get('faces', ()) if f.is_valid]
            if fresh:
                _join_tris(bm, fresh)
    if n or clean_slivers:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return n


def _flank_support_loop(bm, face, shoulder_edge, offset, min_gap=0.02):
    """Insert one holding / support loop into `face`, parallel to `shoulder_edge`
    (the edge it shares with a new bevel face) and sitting `offset` meters out
    from it. Splits the two side edges incident to the shoulder at the clamped
    fraction and connects the new verts -- a face-local loop cut, deterministic
    and needing no ring walk.

    Works on any flank with 4+ sides: a quad's two side edges are opposite, an
    n-gon's are the two edges flanking the shoulder, and connecting the split
    points cleaves off a supporting loop either way (the non-quad boolean off-cut
    case). A triangle flank (< 4 verts) can't hold a parallel loop -> skipped.
    Each split fraction is clamped by `core.bevel.safe_support_fraction`, so a
    short side edge never yields a zero-area sliver. Returns True when a loop was
    added, False for a degenerate flank or a failed split."""
    if len(face.verts) < 4:                 # a tri flank can't hold a parallel loop
        return False
    sv = set(shoulder_edge.verts)
    sides = [e for e in face.edges
             if e is not shoulder_edge and len(set(e.verts) & sv) == 1]
    if len(sides) != 2:
        return False
    new_verts = []
    for e in sides:
        shared = set(e.verts) & sv
        if not shared:
            return False
        anchor = next(iter(shared))         # this side edge's end on the shoulder
        frac = _bevel.safe_support_fraction(offset, e.calc_length(), min_gap)
        if frac is None:                    # degenerate side edge
            return False
        try:
            _, nv = bmesh.utils.edge_split(e, anchor, frac)
        except (ValueError, RuntimeError):
            return False
        new_verts.append(nv)
    if len(new_verts) != 2 or new_verts[0] is new_verts[1] or not face.is_valid:
        return False
    try:
        bmesh.utils.face_split(face, new_verts[0], new_verts[1])
    except (ValueError, RuntimeError):
        return False
    return True


def smart_bevel_edges(obj, edge_keys, width, segments=2, profile=0.5,
                      support=True, tightness=0.5, clean_ngons=True):
    """Smart, topology-preserving Object-Mode bevel -- the hard-surface upgrade
    over `bevel_object_edges`. Three steps, all in one bmesh session:

      1. bevel `edge_keys` into real chamfer geometry (bmesh.ops.bevel);
      2. when `support`, drop a holding / support loop on each face flanking the
         new bevel so the chamfer stays crisp under a Subdivision modifier
         (placement from core/bevel.support_loop_positions, `tightness` in [0,1]);
      3. when `clean_ngons`, triangulate + re-quad any n-gons the bevel produced.

    bmesh only, no bpy.ops. Returns a summary dict:
        {'beveled': edges_beveled, 'supports': loops_added,
         'skipped': flanks_skipped_by_the_safety_barrier, 'ngons': ngons_cleaned}

    The support step is topology-safe: a flank too small to hold a loop (a thin
    boolean off-cut, a non-quad sliver) is skipped by the
    `core.bevel.flank_can_support` barrier and counted in `skipped`, so an
    irregular post-boolean mesh never collapses -- it just gets fewer loops.

    EXPERIMENTAL: the exact holding-loop position wants a live cube ->
    Subdivision pass to tune (tracked in tests/manual_checklist.md). Width <= 0
    is a no-op."""
    summary = {'beveled': 0, 'supports': 0, 'skipped': 0, 'ngons': 0}
    if width <= 0.0:
        return summary
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    nv = len(bm.verts)
    wanted = []
    for a, b in edge_keys:
        if 0 <= a < nv and 0 <= b < nv:
            e = bm.edges.get((bm.verts[a], bm.verts[b]))
            if e is not None:
                wanted.append(e)
    if not wanted:
        bm.free()
        return summary

    res = bmesh.ops.bevel(bm, geom=wanted, offset=width, offset_type='OFFSET',
                          segments=max(1, int(segments)), profile=profile,
                          affect='EDGES', clamp_overlap=True)
    summary['beveled'] = len(wanted)
    bevel_faces = set(f for f in res.get('faces', ()) if f.is_valid)

    if support and bevel_faces:
        # Bevel-exact placement: the offset is tightened for a rounded (multi-
        # segment) bevel, which already braces the edge along its own profile.
        offsets = _bevel.support_loop_positions(
            width, tightness, count=1, segments=segments)
        offset = offsets[0] if offsets else 0.0
        if offset > 0.0:
            # A shoulder edge borders the bevel strip: exactly one bevel face and
            # one original (flanking) face. Add the holding loop on the flank.
            shoulders, done_edges = [], set()
            for f in bevel_faces:
                for e in f.edges:
                    if len(e.link_faces) != 2:
                        continue
                    flanks = [lf for lf in e.link_faces if lf not in bevel_faces]
                    if len(flanks) == 1:
                        shoulders.append((e, flanks[0]))
            for e, flank in shoulders:
                if e in done_edges or not e.is_valid or not flank.is_valid:
                    continue
                done_edges.add(e)
                # Safety barrier: skip a flank too small to hold a loop (thin
                # boolean off-cut / non-quad sliver) -- forcing one in collapses
                # the face. Gate on the shortest side edge the loop would ride.
                sv = set(e.verts)
                side_lens = [se.calc_length() for se in flank.edges
                             if se is not e and len(set(se.verts) & sv) == 1]
                if not side_lens or not _bevel.flank_can_support(
                        min(side_lens), width):
                    summary['skipped'] += 1
                    continue
                if _flank_support_loop(bm, flank, e, offset):
                    summary['supports'] += 1
                else:
                    summary['skipped'] += 1

    if clean_ngons:
        ngons = [f for f in bm.faces if len(f.verts) > 4]
        if ngons:
            summary['ngons'] = len(ngons)
            r2 = bmesh.ops.triangulate(bm, faces=ngons)
            fresh = [f for f in r2.get('faces', ()) if f.is_valid]
            if fresh:
                _join_tris(bm, fresh)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return summary


def edit_knife_polygon(obj, local_corners, view_dir):
    """Edit Mode knife / zero-depth cut: score the drawn closed polygon
    (`local_corners`, object-local) onto obj's mesh without adding or removing
    volume. Each loop edge becomes a cutting plane (the edge swept along
    `view_dir`); the mesh is bisected along it, splitting the faces it crosses.
    Returns the number of edges scored.

    The cut is restricted to the currently selected faces when any are selected
    (so you select the target face, then knife on it); with nothing selected it
    falls back to the whole mesh. A per-segment bisect is a coarse knife -- it
    scores the loop's edge planes rather than clipping to the exact footprint --
    which suits scoring panel lines onto a flat face."""
    from mathutils import Vector
    vd = Vector(view_dir).normalized()
    n = len(local_corners)
    if n < 2:
        return 0
    bm = bmesh.from_edit_mesh(obj.data)
    sel_faces = [f for f in bm.faces if f.select]
    scored = 0
    closed = n >= 3
    count = n if closed else n - 1
    for i in range(count):
        a = Vector(local_corners[i])
        b = Vector(local_corners[(i + 1) % n])
        edge = b - a
        if edge.length < 1e-9:
            continue
        plane_no = edge.cross(vd)
        if plane_no.length < 1e-9:
            continue
        plane_no.normalize()
        # Re-gather the target geometry each pass: a prior bisect changes it.
        # Restrict to selected faces (if any) AND to the drawn footprint so the
        # score stays local instead of slicing the whole selection.
        base = [f for f in bm.faces if f.select] if sel_faces else bm.faces[:]
        faces = _knife_footprint_faces(base, local_corners, vd)
        verts = {v for f in faces for v in f.verts}
        edges = {e for f in faces for e in f.edges}
        geom = list(verts) + list(edges) + list(faces)
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=a,
                               plane_no=plane_no, clear_inner=False,
                               clear_outer=False)
        scored += 1
    bmesh.update_edit_mesh(obj.data)
    return scored


# --- Edge weights (v1.5) ------------------------------------------------


def _edge_weight_layers(bm, want_bevel, want_crease):
    """Get/create the 4.x edge bevel-weight + crease float attribute layers.
    Returns (bevel_layer, crease_layer); a layer is None when not requested and
    absent. Wrapped in try/except so an API rename never crashes the caller."""
    bw = cr = None
    try:
        bw = bm.edges.layers.float.get('bevel_weight_edge')
        if bw is None and want_bevel:
            bw = bm.edges.layers.float.new('bevel_weight_edge')
        cr = bm.edges.layers.float.get('crease_edge')
        if cr is None and want_crease:
            cr = bm.edges.layers.float.new('crease_edge')
    except (AttributeError, ValueError):
        pass
    return bw, cr


def edit_set_edge_weights(obj, bevel_weight=None, crease=None, only_selected=True):
    """Edit Mode: set bevel weight and/or crease on the selected edges (or all
    edges when only_selected is False). `None` leaves that attribute untouched.
    Returns the edge count changed. The edge bevel-weight / crease workflow that
    feeds a weight-limited Bevel or a creased Subdivision."""
    bm = bmesh.from_edit_mesh(obj.data)
    bw, cr = _edge_weight_layers(bm, bevel_weight is not None, crease is not None)
    n = 0
    for e in bm.edges:
        if only_selected and not e.select:
            continue
        if bevel_weight is not None and bw is not None:
            e[bw] = bevel_weight
        if crease is not None and cr is not None:
            e[cr] = crease
        n += 1
    bmesh.update_edit_mesh(obj.data)
    return n


def mark_sharp_edges(obj, angle_threshold, set_sharp=True, set_bevel_weight=True,
                     bevel_weight=1.0, crease=None, shade_smooth=True):
    """Object-Mode: (re)mark an object's hard edges for the Smart Sharpen /
    Initialize HardSurface pass (HardOps parity). An edge is *hard* when its
    dihedral face angle reaches `angle_threshold` (radians), or when it is a
    boundary / non-manifold edge (not exactly two faces -- always hard). Every
    edge is cleared first, then the hard ones are:

      * marked **sharp** (``edge.smooth = False``) when `set_sharp`,
      * given a **bevel weight** (``bevel_weight``) on the 4.x
        ``bevel_weight_edge`` attribute when `set_bevel_weight`, so a
        weight-limited Bevel modifier acts only on them,
      * optionally **creased** (``crease``) for a creased Subdivision.

    Clearing first makes it idempotent: re-running with a looser/tighter angle
    re-derives the full hard-edge set instead of accumulating stale marks. With
    `shade_smooth` every face is set smooth so the sharp edges + a Weighted Normal
    read as crisp hard-surface. bmesh only, no bpy.ops. Returns the hard-edge
    count. The whole call is safe to wrap in the operator's try/except."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bw = cr = None
    if set_bevel_weight:
        bw = bm.edges.layers.float.get('bevel_weight_edge')
        if bw is None:
            bw = bm.edges.layers.float.new('bevel_weight_edge')
    if crease is not None:
        cr = bm.edges.layers.float.get('crease_edge')
        if cr is None:
            cr = bm.edges.layers.float.new('crease_edge')
    if shade_smooth:
        for f in bm.faces:
            f.smooth = True
    n = 0
    for e in bm.edges:
        faces = e.link_faces
        if len(faces) != 2:
            hard = True                         # boundary / non-manifold = hard
        else:
            try:
                hard = e.calc_face_angle() >= angle_threshold
            except (ValueError, RuntimeError):
                hard = False                    # degenerate face -> leave soft
        if set_sharp:
            e.smooth = not hard                 # smooth False == sharp
        if bw is not None:
            e[bw] = bevel_weight if hard else 0.0
        if cr is not None:
            e[cr] = crease if hard else 0.0
        if hard:
            n += 1
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return n


def cleanup_mesh(obj, merge_dist=1e-4, dissolve_angle=0.0873, remove_loose=True):
    """Mesh cleanup after boolean/bevel: merge (remove doubles) + limited
    dissolve (merge coplanar faces) + delete loose geometry. Object Mode.
    dissolve_angle in radians (default ~5 degrees); if 0 the dissolve is
    skipped."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=merge_dist)
    if dissolve_angle > 0.0:
        bmesh.ops.dissolve_limit(
            bm, angle_limit=dissolve_angle,
            verts=list(bm.verts), edges=list(bm.edges))
    if remove_loose:
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
