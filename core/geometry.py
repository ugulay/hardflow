# Geometry generation with bmesh.
import math

import bpy
import bmesh

from . import transform


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


def estimate_thickness(obj, factor=2.0, minimum=1.0):
    """Thickness sufficient for the cutter to pierce all the way through the
    object."""
    d = obj.dimensions
    return max(d.x, d.y, d.z, minimum) * factor


def bevel_cutter(mesh, width, segments=2, profile=0.5):
    """Chamfer every edge of a cutter mesh in place, so a boolean CUT leaves
    bevelled recess walls instead of sharp ones (Boxcutter bevelled cut -- this
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


def build_face(corners, name="hf_face"):
    """Build a single n-gon face from a list of corners on a plane (not a
    boolean; Grid Modeler 'create face'). At least 3 points."""
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
    primitive for the SketchUp-style tools (the caller positions it at the 3D
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
    local axis -- a construction guide line to snap against (SketchUp guides).
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


def build_pipe(points, radius=0.05, bevel_res=4, name="Hardflow_Pipe"):
    """Build a round-section pipe curve from a list of 3D points (Grid Modeler
    'pipes'). At least 2 points. Returns curve data; the caller links it to an
    object."""
    if len(points) < 2:
        return None
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    spline = curve.splines.new('POLY')
    spline.points.add(len(points) - 1)   # one point already exists
    for i, p in enumerate(points):
        spline.points[i].co = (p[0], p[1], p[2], 1.0)
    curve.bevel_depth = radius
    curve.bevel_resolution = bevel_res
    curve.use_fill_caps = True
    return curve


def profile_points(profile, radius):
    """2D cross-section offsets for build_pipe_mesh. 'SQUARE' -> a radius x radius
    box, 'RECT' -> 2*radius x radius, otherwise a `max(3, ...)`-sided ring is left
    to the round curve path. Returns a list of (u, v) tuples or None for round."""
    r = radius
    if profile == 'SQUARE':
        return [(-r, -r), (r, -r), (r, r), (-r, r)]
    if profile == 'RECT':
        return [(-2 * r, -r), (2 * r, -r), (2 * r, r), (-2 * r, r)]
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
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(m):
            j = (k + 1) % m
            try:
                bm.faces.new((a[k], a[j], b[j], b[k]))
            except ValueError:
                pass
    try:
        bm.faces.new(list(reversed(rings[0])))   # start cap
        bm.faces.new(rings[-1])                   # end cap
    except ValueError:
        pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_loft(loop_a, loop_b, caps=True, name="Hardflow_Loft"):
    """Bridge two equal-length point loops into a solid (Grid Modeler loft /
    bridge): side quads between corresponding vertices, plus end caps. `loop_a`
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
    segments ((x1, y1), (x2, y2)) laid on the local XY plane -- the SketchUp
    construction grid. The caller positions/orients the object. Vertices are
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


def extrude_faces(obj, face_indices, local_vec):
    """Push/Pull: extrude the given faces (indices into obj.data.polygons) and
    move the new region by `local_vec` (an object-local Vector). Edits obj.data
    via bmesh in Object Mode. Returns True on success. Face indices must be valid
    on the base mesh -- generative modifiers that change the face count are not
    accounted for."""
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


def symmetrize_mesh(obj, direction='+X'):
    """Symmetrize the mesh in place: keep one side and mirror it onto the other
    across the object-local axis plane (Hard Ops symmetrize). `direction` is a
    bmesh axis-and-side string ('-X','+X','-Y','+Y','-Z','+Z'); '+X' keeps the
    +X half and mirrors it to -X. Object Mode, no bpy.ops."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    # bmesh.ops.symmetrize wants the positive side as a bare axis ('X','Y','Z')
    # and the negative side prefixed ('-X'). Normalize '+X' -> 'X' so callers may
    # pass either convention (the operator UI still labels them '+X to -X').
    direction = direction.lstrip('+')
    bmesh.ops.symmetrize(bm, input=bm.verts[:] + bm.edges[:] + bm.faces[:],
                         direction=direction)
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()


def mark_sharp_by_angle(obj, angle):
    """Mark edges sharp where the angle between their two faces exceeds `angle`
    (radians) and smooth the rest -- the basis of the Hard Ops "sharpen" flow.
    All faces are set to smooth shading so the sharp edges read as hard creases.
    Boundary / non-manifold edges are left smooth. Returns the sharp-edge count."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for face in bm.faces:
        face.smooth = True
    sharp = 0
    for edge in bm.edges:
        if len(edge.link_faces) == 2:
            if edge.calc_face_angle() > angle:
                edge.smooth = False
                sharp += 1
            else:
                edge.smooth = True
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return sharp


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


def edit_extrude_faces(obj, local_vec):
    """Edit Mode Push/Pull: extrude obj's selected edit-mesh faces and move the
    new region by `local_vec` (object-local). The original (now interior) faces
    are removed and the extruded cap is left selected. Returns True on success,
    False when no face is selected."""
    bm = bmesh.from_edit_mesh(obj.data)
    faces = [f for f in bm.faces if f.select]
    if not faces:
        return False
    res = bmesh.ops.extrude_face_region(bm, geom=faces)
    moved = [g for g in res['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=local_vec, verts=moved)
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


def edit_add_face(obj, local_corners, select=True, weld=True, weld_dist=1e-4):
    """Edit Mode draw: add the polygon `local_corners` (object-local points) as a
    new face into obj's edit-mesh -- the drawn shape becomes geometry inside the
    active mesh rather than a separate object. New geometry can be deselected by
    `select=False`. Returns True on success, False on a degenerate polygon.

    With `weld` (the default), the new face's vertices that land on existing mesh
    vertices (within `weld_dist`) are merged onto them, so the drawn face connects
    to the surrounding geometry instead of floating as a detached island -- the
    Grid Modeler 'create connected faces' behaviour."""
    if len(local_corners) < 3:
        return False
    bm = bmesh.from_edit_mesh(obj.data)
    new_verts = [bm.verts.new(co) for co in local_corners]
    try:
        face = bm.faces.new(new_verts)
    except ValueError:               # repeated vertex / duplicate face
        for v in new_verts:
            if v.is_valid and not v.link_edges:
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


def edit_bevel_edges(obj, width, segments=2, profile=0.5):
    """Edit Mode real edge bevel: bevel obj's selected edit-mesh edges
    (bmesh.ops.bevel, affecting EDGES) into actual chamfer geometry. Returns the
    number of selected edges beveled, 0 when none are selected or the width is
    non-positive. The destructive on-selection counterpart of the whole-object
    Bevel *modifier* -- this is the Hard Ops / SketchUp edge bevel users expect in
    Edit Mode."""
    if width <= 0.0:
        return 0
    bm = bmesh.from_edit_mesh(obj.data)
    edges = [e for e in bm.edges if e.select]
    if not edges:
        # Vertex select mode may not flush selection up to the edge flag; treat
        # an edge as selected when both of its endpoints are.
        edges = [e for e in bm.edges
                 if e.verts[0].select and e.verts[1].select]
    if not edges:
        return 0
    n = len(edges)
    bmesh.ops.bevel(bm, geom=edges, offset=width, offset_type='OFFSET',
                    segments=max(1, int(segments)), profile=profile,
                    affect='EDGES', clamp_overlap=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.update_edit_mesh(obj.data, destructive=True)
    return n


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


# --- Hard Ops parity: dice / panel, edge weights, presets (v1.5) --------


def dice_mesh(obj, counts, mark_sharp=False):
    """Hard Ops dice / panel: bisect obj's mesh on a regular grid -- `counts` is
    an (nx, ny, nz) tuple of pieces per object-local axis. Cut planes are placed
    across the mesh's local bounding box (transform.dice_coordinates), splitting
    the faces they cross into a grid (the basis for greeble / panel breaks). With
    mark_sharp the new cut edges are flagged sharp. Returns the number of bisect
    passes run. Object Mode, no bpy.ops."""
    from mathutils import Vector
    verts = obj.data.vertices
    if not verts:
        return 0
    mins = [min(v.co[i] for v in verts) for i in range(3)]
    maxs = [max(v.co[i] for v in verts) for i in range(3)]
    axes = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    passes = 0
    for i, count in enumerate(counts):
        for coord in transform.dice_coordinates(mins[i], maxs[i], count):
            plane_co = Vector((0.0, 0.0, 0.0))
            plane_co[i] = coord
            ret = bmesh.ops.bisect_plane(
                bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6,
                plane_co=plane_co, plane_no=axes[i],
                clear_inner=False, clear_outer=False)
            if mark_sharp:
                for e in ret.get('geom_cut', []):
                    if isinstance(e, bmesh.types.BMEdge):
                        e.smooth = False
            passes += 1
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return passes


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


def set_sharp_edge_weights(obj, bevel_weight=0.0, crease=0.0):
    """Set bevel weight + crease on edges already flagged sharp (run after
    mark_sharp_by_angle) so a weight-limited bevel / subsurf crease can act on
    them -- the Hard Ops SSharp/CSharp weighting tiers. Returns the edge count
    weighted. Object Mode."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bw, cr = _edge_weight_layers(bm, bevel_weight != 0.0, crease != 0.0)
    n = 0
    for e in bm.edges:
        if not e.smooth:                 # smooth == False -> sharp
            if bw is not None:
                e[bw] = bevel_weight
            if cr is not None:
                e[cr] = crease
            n += 1
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    return n


def edit_set_edge_weights(obj, bevel_weight=None, crease=None, only_selected=True):
    """Edit Mode: set bevel weight and/or crease on the selected edges (or all
    edges when only_selected is False). `None` leaves that attribute untouched.
    Returns the edge count changed. The Hard Ops edge bevel-weight / crease
    workflow that feeds a weight-limited Bevel or a creased Subdivision."""
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


# Sharpen tiers (Hard Ops SSharp / CSharp): each combines mark-sharp with a
# bevel-weight / crease weighting + which clean-up modifiers to add.
SHARPEN_PRESETS = {
    'WN': dict(bevel_weight=0.0, crease=0.0, add_bevel=False, weighted_normal=True),
    'SSHARP': dict(bevel_weight=1.0, crease=0.0, add_bevel=True,
                   weighted_normal=True),
    'CSHARP': dict(bevel_weight=0.0, crease=1.0, add_bevel=False,
                   weighted_normal=True),
}


# --- parametric greeble builders (v1.5 step / taper / knurl) -------------


def build_steps(count=5, rise=0.1, run=0.1, width=1.0, name="Hardflow_Steps"):
    """Build a stepped block (a staircase greeble) of `count` steps, each `rise`
    tall and `run` deep, `width` wide, climbing +Z from the origin. Pure bmesh;
    returns mesh data. The caller positions the object."""
    count = max(1, int(count))
    bm = bmesh.new()
    for i in range(count):
        z0 = 0.0
        z1 = (i + 1) * rise
        y0 = i * run
        y1 = count * run
        verts = [
            bm.verts.new((0.0, y0, z0)), bm.verts.new((width, y0, z0)),
            bm.verts.new((width, y1, z0)), bm.verts.new((0.0, y1, z0)),
            bm.verts.new((0.0, y0, z1)), bm.verts.new((width, y0, z1)),
            bm.verts.new((width, y1, z1)), bm.verts.new((0.0, y1, z1)),
        ]
        f = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
             (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        for a, b, c, d in f:
            try:
                bm.faces.new((verts[a], verts[b], verts[c], verts[d]))
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_taper(bottom=1.0, top=0.5, height=1.0, name="Hardflow_Taper"):
    """Build a tapered box / frustum: a `bottom`-wide square base tapering to a
    `top`-wide square cap over `height` (+Z). top=0 yields a pyramid. Pure bmesh;
    returns mesh data."""
    b, t, h = bottom * 0.5, top * 0.5, height
    bm = bmesh.new()
    base = [bm.verts.new(c) for c in
            ((-b, -b, 0.0), (b, -b, 0.0), (b, b, 0.0), (-b, b, 0.0))]
    if t <= 1e-6:
        apex = bm.verts.new((0.0, 0.0, h))
        bm.faces.new(list(reversed(base)))
        for i in range(4):
            bm.faces.new((base[i], base[(i + 1) % 4], apex))
    else:
        cap = [bm.verts.new(c) for c in
               ((-t, -t, h), (t, -t, h), (t, t, h), (-t, t, h))]
        bm.faces.new(list(reversed(base)))
        bm.faces.new(cap)
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((base[i], base[j], cap[j], cap[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_knurl(radius=0.5, height=1.0, teeth=16, depth=0.05,
                name="Hardflow_Knurl"):
    """Build a knurled cylinder: a `teeth`-sided cylinder whose rim alternates
    between `radius` and `radius - depth` to read as a grippy knurl, `height`
    tall (+Z). Pure bmesh; returns mesh data."""
    teeth = max(3, int(teeth))
    bm = bmesh.new()
    bottom, top = [], []
    n = teeth * 2
    for i in range(n):
        a = (i / n) * math.tau
        r = radius if i % 2 == 0 else max(1e-4, radius - depth)
        x, y = math.cos(a) * r, math.sin(a) * r
        bottom.append(bm.verts.new((x, y, 0.0)))
        top.append(bm.verts.new((x, y, height)))
    bm.faces.new(list(reversed(bottom)))
    bm.faces.new(top)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


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
