# Geometry generation with bmesh.
import bpy
import bmesh


def build_prism(corners, view_dir, thickness, name="hf_cutter"):
    """Turn a list of 3D corners on a plane into a closed prism (a cutter
    volume) by extruding along the view direction. corners must be at least 3
    points. Concave n-gons are accepted; self-intersecting polygons give broken
    results."""
    half = view_dir * (thickness * 0.5)
    front = [c - half for c in corners]
    back = [c + half for c in corners]

    bm = bmesh.new()
    vf = [bm.verts.new(co) for co in front]
    vb = [bm.verts.new(co) for co in back]

    try:
        bm.faces.new(vf)               # front cap
        bm.faces.new(list(reversed(vb)))  # back cap
    except ValueError:
        # repeated vertex at the same position, etc.
        bm.free()
        return None

    n = len(vf)
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new((vf[i], vf[j], vb[j], vb[i]))  # side walls
        except ValueError:
            pass

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def estimate_thickness(obj, factor=2.0, minimum=1.0):
    """Thickness sufficient for the cutter to pierce all the way through the
    object."""
    d = obj.dimensions
    return max(d.x, d.y, d.z, minimum) * factor


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
