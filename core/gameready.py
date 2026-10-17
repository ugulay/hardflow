# Pure game-ready audit rules -- stdlib only, no bpy.
#
# A hard-surface model that looks finished in Blender is often not ready to
# hand to an engine: unapplied scale, inverted normals, n-gons, non-manifold
# edges, no UVs, texel density all over the place. Every one of those is a
# measurement plus a rule, and the rules are the part worth testing, so they
# live here: the operator measures the mesh with bmesh and hands plain numbers
# to these functions, which decide pass/warn/fail and phrase the finding.
#
# Severity vocabulary:
#   'OK'   -- nothing to do.
#   'WARN' -- will not break an import, but will cost you somewhere (density,
#             n-gons an engine triangulates its own way, loose geometry).
#   'FAIL' -- an engine or a baker will get this wrong: unapplied scale,
#             inverted normals, missing UVs, non-manifold shells.
import math

OK = 'OK'
WARN = 'WARN'
FAIL = 'FAIL'

_RANK = {OK: 0, WARN: 1, FAIL: 2}

# Fix keys the operator layer dispatches on. A finding carries one (or "" when
# there is nothing to press) so the panel can offer exactly the right button.
FIX_SCALE = 'APPLY_SCALE'
FIX_NORMALS = 'RECALC_NORMALS'
FIX_NGONS = 'TRIANGULATE'
FIX_LOOSE = 'DELETE_LOOSE'
FIX_SELECT_NONMANIFOLD = 'SELECT_NONMANIFOLD'
FIX_UNWRAP = 'UNWRAP'


def finding(key, level, label, detail="", fix=""):
    """One audit row: ``(key, level, label, detail, fix)``.

    A plain tuple on purpose -- it crosses into the UI layer, gets sorted and
    compared in tests, and needs no behaviour."""
    return (key, level, label, detail, fix)


def worst(findings):
    """The most severe level in `findings` ('OK' for an empty list)."""
    level = OK
    for f in findings:
        if _RANK[f[1]] > _RANK[level]:
            level = f[1]
    return level


def summary(findings):
    """``(level, ok, warn, fail)`` -- the headline for the panel."""
    counts = {OK: 0, WARN: 0, FAIL: 0}
    for f in findings:
        counts[f[1]] += 1
    return (worst(findings), counts[OK], counts[WARN], counts[FAIL])


def needs_fixing(findings):
    """Just the rows that have a fix button, worst first, so the panel can lead
    with what is actionable."""
    rows = [f for f in findings if f[4] and f[1] != OK]
    return sorted(rows, key=lambda f: -_RANK[f[1]])


# --- individual rules ------------------------------------------------------

def check_scale(scale, tol=1e-4):
    """Object scale must be applied: a non-1 scale travels differently through
    every exporter, and a NON-UNIFORM one also skews normal maps and physics."""
    sx, sy, sz = (float(s) for s in scale)
    uniform = (abs(sx - sy) <= tol and abs(sy - sz) <= tol)
    unit = all(abs(s - 1.0) <= tol for s in (sx, sy, sz))
    if unit:
        return finding('scale', OK, "Scale applied", "1.0, 1.0, 1.0")
    detail = "%.3f, %.3f, %.3f" % (sx, sy, sz)
    if not uniform:
        return finding('scale', FAIL, "Non-uniform scale not applied",
                       detail, FIX_SCALE)
    return finding('scale', FAIL, "Scale not applied", detail, FIX_SCALE)


def signed_volume(triangles):
    """Signed volume of a closed triangle mesh (divergence theorem).

    Positive when the face winding points outward. This is the one *reliable*
    inverted-normal test: comparing each normal against the centroid guesses
    wrong on anything concave, while the sign of the total volume is exact --
    for a closed mesh, which is why the caller checks watertightness first."""
    total = 0.0
    for a, b, c in triangles:
        total += (a[0] * (b[1] * c[2] - b[2] * c[1])
                  - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
    return total


def check_normals(closed, volume):
    """Inverted normals, judged by the sign of the enclosed volume.

    An open mesh has no inside, so the test does not apply -- say so rather
    than guess, and let the watertight rule carry that case."""
    if not closed:
        return finding('normals', OK, "Normals not checked",
                       "open mesh -- the volume test needs a closed shell")
    if volume < 0.0:
        return finding('normals', FAIL, "Normals point inward",
                       "enclosed volume is negative", FIX_NORMALS)
    return finding('normals', OK, "Normals point outward",
                   "volume %.4f m3" % volume)


def check_watertight(non_manifold_edges, boundary_edges):
    """Non-manifold edges break bakers, booleans and most engines; plain
    boundary edges (an open shell) are legitimate for a flat panel, so they are
    only worth a mention."""
    if non_manifold_edges:
        return finding('manifold', FAIL, "Non-manifold geometry",
                       "%d edge(s) shared by more than two faces"
                       % non_manifold_edges, FIX_SELECT_NONMANIFOLD)
    if boundary_edges:
        return finding('manifold', WARN, "Open mesh",
                       "%d boundary edge(s) -- fine for a shell, not for a "
                       "solid" % boundary_edges)
    return finding('manifold', OK, "Watertight", "no non-manifold edges")


def check_faces(tris, quads, ngons):
    """Face budget. An engine triangulates on import anyway; the problem with
    an n-gon is that it triangulates it *its* way, which is where shading
    surprises come from -- so n-gons warn, they do not fail."""
    total = tris + quads + ngons
    detail = "%d tri / %d quad / %d n-gon" % (tris, quads, ngons)
    if not total:
        return finding('faces', FAIL, "No faces", "the mesh is empty")
    if ngons:
        return finding('faces', WARN, "N-gons present", detail, FIX_NGONS)
    return finding('faces', OK, "Quads and tris only", detail)


def check_loose(loose_verts, loose_edges):
    """Stray verts and wire edges: invisible in the viewport, exported anyway,
    and they ruin an automatic bounding box."""
    if loose_verts or loose_edges:
        return finding('loose', WARN, "Loose geometry",
                       "%d vert(s), %d wire edge(s)" % (loose_verts,
                                                        loose_edges),
                       FIX_LOOSE)
    return finding('loose', OK, "No loose geometry")


def check_uv(has_uv, uv_faces=0, total_faces=0, out_of_bounds=0):
    """UVs must exist and sit inside 0-1. Out-of-bounds islands are legal (they
    tile), but in a game-ready check they are usually an accident, so they warn
    rather than fail."""
    if not has_uv:
        return finding('uv', FAIL, "No UV map",
                       "nothing to bake or texture onto", FIX_UNWRAP)
    if total_faces and uv_faces < total_faces:
        return finding('uv', FAIL, "Unwrapped partially",
                       "%d of %d face(s) have no UV area"
                       % (total_faces - uv_faces, total_faces), FIX_UNWRAP)
    if out_of_bounds:
        return finding('uv', WARN, "UVs outside 0-1",
                       "%d face(s) -- intentional only if the texture tiles"
                       % out_of_bounds)
    return finding('uv', OK, "UV map present", "%d face(s) unwrapped" % uv_faces)


def texel_density(world_area, uv_area, texture_size):
    """Texels per metre for a mesh covering `uv_area` (in UV units, where the
    whole 0-1 square is 1.0) over `world_area` square metres.

    The standard formula: a texture of N px spread over sqrt(uv/world) metres.
    Returns 0.0 for degenerate input rather than raising -- an empty or
    zero-area mesh has no density to report."""
    if world_area <= 0.0 or uv_area <= 0.0 or texture_size <= 0:
        return 0.0
    return float(texture_size) * math.sqrt(uv_area / world_area)


def check_texel(density, target, tolerance=0.25):
    """Compare measured density against the project's target, within a
    tolerance expressed as a FRACTION of the target (0.25 = accept 75-125%).

    Reported, never auto-fixed: correcting density means rescaling UV islands,
    which is a decision about which object is the reference, not something an
    audit should do behind your back."""
    if density <= 0.0:
        return finding('texel', OK, "Texel density not measured",
                       "no UVs or no area")
    if target <= 0.0:
        return finding('texel', OK, "Texel density", "%.0f px/m" % density)
    ratio = density / target
    detail = "%.0f px/m (target %.0f, %.0f%%)" % (density, target, ratio * 100.0)
    if abs(ratio - 1.0) <= tolerance:
        return finding('texel', OK, "Texel density on target", detail)
    return finding('texel', WARN, "Texel density off target", detail)


def audit(measurements, target_texel=512.0, texture_size=1024,
          texel_tolerance=0.25):
    """Run every rule over one object's measurements and return the findings,
    in report order.

    `measurements` is a plain dict so the whole audit is testable without
    Blender; operators/gameready.py fills it from bmesh."""
    m = measurements
    density = texel_density(m.get('world_area', 0.0), m.get('uv_area', 0.0),
                            texture_size)
    return [
        check_scale(m.get('scale', (1.0, 1.0, 1.0))),
        check_normals(m.get('closed', False), m.get('volume', 0.0)),
        check_watertight(m.get('non_manifold_edges', 0),
                         m.get('boundary_edges', 0)),
        check_faces(m.get('tris', 0), m.get('quads', 0), m.get('ngons', 0)),
        check_loose(m.get('loose_verts', 0), m.get('loose_edges', 0)),
        check_uv(m.get('has_uv', False), m.get('uv_faces', 0),
                 m.get('total_faces', 0), m.get('uv_out_of_bounds', 0)),
        check_texel(density, target_texel, texel_tolerance),
    ]
