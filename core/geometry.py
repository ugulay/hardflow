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
