# bmesh ile geometri uretimi.
import bpy
import bmesh


def build_prism(corners, view_dir, thickness, name="hf_cutter"):
    """Bir duzlem uzerindeki 3D kose listesini, bakis yonunde extrude ederek
    kapali bir prizmaya (kesici hacme) cevirir. corners en az 3 nokta.
    Konkav n-gen kabul eder; kendiyle kesisen poligonlar bozuk sonuc verir."""
    half = view_dir * (thickness * 0.5)
    front = [c - half for c in corners]
    back = [c + half for c in corners]

    bm = bmesh.new()
    vf = [bm.verts.new(co) for co in front]
    vb = [bm.verts.new(co) for co in back]

    try:
        bm.faces.new(vf)               # on kapak
        bm.faces.new(list(reversed(vb)))  # arka kapak
    except ValueError:
        # ayni konumda tekrar eden kose vs.
        bm.free()
        return None

    n = len(vf)
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new((vf[i], vf[j], vb[j], vb[i]))  # yan duvarlar
        except ValueError:
            pass

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def estimate_thickness(obj, factor=2.0, minimum=1.0):
    """Kesicinin nesneyi delip gecmesi icin yeterli kalinlik."""
    d = obj.dimensions
    return max(d.x, d.y, d.z, minimum) * factor


def build_face(corners, name="hf_face"):
    """Bir duzlem uzerindeki kose listesinden tek bir n-gen yuzey uretir
    (boolean degil; Grid Modeler 'create face'). En az 3 nokta."""
    bm = bmesh.new()
    verts = [bm.verts.new(co) for co in corners]
    try:
        bm.faces.new(verts)
    except ValueError:        # tekrar eden kose / gecersiz
        bm.free()
        return None
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def build_pipe(points, radius=0.05, bevel_res=4, name="Hardflow_Pipe"):
    """3D nokta listesinden, yuvarlak kesitli boru curve'u uretir (Grid Modeler
    'pipes'). En az 2 nokta. Curve data dondurur; cagiran nesneye baglar."""
    if len(points) < 2:
        return None
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    spline = curve.splines.new('POLY')
    spline.points.add(len(points) - 1)   # zaten 1 nokta var
    for i, p in enumerate(points):
        spline.points[i].co = (p[0], p[1], p[2], 1.0)
    curve.bevel_depth = radius
    curve.bevel_resolution = bevel_res
    curve.use_fill_caps = True
    return curve


def cleanup_mesh(obj, merge_dist=1e-4, dissolve_angle=0.0873, remove_loose=True):
    """Boolean/bevel sonrasi mesh temizligi: kaynak (remove doubles) + sinirli
    cozme (coplanar yuzleri birlestir) + başıboş geometri sil. Object Mode.
    dissolve_angle radyan (varsayilan ~5 derece); 0 ise cozme atlanir."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=merge_dist)
    if dissolve_angle > 0.0:
        bmesh.ops.dissolve_limited(
            bm, angle_limit=dissolve_angle,
            verts=list(bm.verts), edges=list(bm.edges))
    if remove_loose:
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
