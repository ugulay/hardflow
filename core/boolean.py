# Boolean operations. Provides both destructive (apply-and-delete) and
# non-destructive (leave a modifier) paths.
import bpy


def _new_bool(target, cutter, operation, solver):
    mod = target.modifiers.new("HF_Bool", 'BOOLEAN')
    mod.operation = operation
    mod.solver = solver
    mod.object = cutter
    return mod


def apply_boolean(context, target, cutter, operation='DIFFERENCE', solver='EXACT'):
    """Destructive: add a modifier and apply it. The cutter is deleted by the
    caller."""
    mod = _new_bool(target, cutter, operation, solver)
    with context.temp_override(active_object=target, object=target):
        bpy.ops.object.modifier_apply(modifier=mod.name)


def add_boolean(target, cutter, operation='DIFFERENCE', solver='EXACT'):
    """Non-destructive: just add a modifier and return it. The cutter stays in
    the scene."""
    return _new_bool(target, cutter, operation, solver)


def _remove_bool_mods(target):
    for m in [m for m in target.modifiers if m.name.startswith("HF_Bool")]:
        target.modifiers.remove(m)


def apply_boolean_fallback(context, target, cutter, operation='DIFFERENCE',
                           solver='EXACT'):
    """Destructive apply that retries with the FAST solver when the preferred one
    raises -- boolean INSERTs / cutters on messy targets (KitOps robustness). Any
    half-added modifier is cleaned up between attempts. Returns the solver string
    that succeeded, or None when both fail."""
    for attempt in (solver, 'FAST'):
        try:
            apply_boolean(context, target, cutter, operation, attempt)
            return attempt
        except RuntimeError:
            _remove_bool_mods(target)
        if attempt == 'FAST':
            break
    return None


def recalc_normals(obj):
    """Recalculate outward-facing normals on a mesh object (bmesh, no bpy.ops).
    The inverted/inconsistent-normal cutter is the single most common reason the
    EXACT solver fails; flipping the cutter consistent before a retry recovers
    most of those cases. Safe on generated/disposable cutter meshes."""
    import bmesh
    me = obj.data
    if me.is_editmode:
        # In Edit Mode the mesh is owned by the open bmesh; write back through
        # it (bm.to_mesh would raise) and don't free it.
        bm = bmesh.from_edit_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bmesh.update_edit_mesh(me)
        return
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()


def mesh_health(obj):
    """Cheap diagnostic of the mesh problems that break booleans. Returns a dict:
    `non_manifold` (open / non-manifold edges -- not exactly two faces),
    `degenerate` (near-zero-area faces), `loose` (vertices with no edge). Pure
    bmesh, no scene side effects -- used to explain *why* a cut failed."""
    import bmesh
    me = obj.data
    editmode = me.is_editmode
    # In Edit Mode read the live edit-mesh bmesh (from_mesh would see stale data);
    # in Object Mode use a disposable copy.
    bm = bmesh.from_edit_mesh(me) if editmode else bmesh.new()
    if not editmode:
        bm.from_mesh(me)
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
    loose = sum(1 for v in bm.verts if not v.link_edges)
    if not editmode:
        bm.free()  # never free a bmesh owned by the edit-mesh
    return {'non_manifold': non_manifold, 'degenerate': degenerate,
            'loose': loose}


def _health_summary(obj):
    """One-line description of an object's boolean-breaking problems, or ''."""
    h = mesh_health(obj)
    bits = []
    if h['non_manifold']:
        bits.append("%d non-manifold/open edges" % h['non_manifold'])
    if h['degenerate']:
        bits.append("%d zero-area faces" % h['degenerate'])
    if h['loose']:
        bits.append("%d loose vertices" % h['loose'])
    return "; ".join(bits)


# Heuristic thresholds for the auto-solver choice. EXACT tolerates a few open
# edges (e.g. an intentional shell), so only divert badly-broken targets to FAST.
# Tune once live-Blender timings exist.
_SOLVER_NONMANIFOLD_LIMIT = 6
_SOLVER_HEALTH_MAX_VERTS = 200000


def choose_solver(target, preferred='EXACT', max_verts=_SOLVER_HEALTH_MAX_VERTS):
    """Pick the solver to *try first* from the target's health. EXACT is accurate
    but slow and brittle; on a badly non-manifold / degenerate target it will
    almost always fail after a slow pass, so start with FAST instead and skip the
    doomed attempt. Clean meshes keep the preferred (accurate) solver. Only acts
    when `preferred` is EXACT and the mesh is light enough to scan cheaply;
    `robust_boolean` still falls back, so this only changes the *order*."""
    if preferred != 'EXACT' or len(target.data.vertices) > max_verts:
        return preferred
    h = mesh_health(target)
    if h['non_manifold'] >= _SOLVER_NONMANIFOLD_LIMIT or h['degenerate'] >= 1:
        return 'FAST'
    return 'EXACT'


def robust_boolean(context, target, cutter, operation='DIFFERENCE',
                   solver='EXACT'):
    """Destructive boolean that tries hard to succeed and explains itself when it
    can't. Returns (ok, solver_used, message):

      * pick the starting solver from the target's health (`choose_solver`) --
        skip a doomed EXACT pass on visibly-broken geometry;
      * try that solver, then FAST (`apply_boolean_fallback`);
      * if both fail, recalculate the cutter's normals and retry once -- the
        usual fix for the EXACT solver choking on an inverted cutter;
      * if it still fails, diagnose the *target* (non-manifold / degenerate /
        loose geometry) so the message tells the user what to repair.

    The target is never modified beyond the boolean itself; only the cutter's
    normals (it is disposable) may be rewritten."""
    start = choose_solver(target, solver)
    used = apply_boolean_fallback(context, target, cutter, operation, start)
    if used is not None:
        if used == solver:
            msg = "Cut done"
        elif start != solver and used == start:
            msg = ("Cut done (%s solver: target geometry is too broken for %s)"
                   % (used, solver))
        else:
            msg = "Cut done (%s solver fallback)" % used
        return True, used, msg

    recalc_normals(cutter)
    used = apply_boolean_fallback(context, target, cutter, operation, start)
    if used is not None:
        return True, used, "Cut done (after cutter normal repair, %s solver)" % used

    detail = _health_summary(target) or "geometry the solver can't resolve"
    return (False, None,
            "Boolean failed on '%s' (%s). Try Mesh > Normals > Recalculate "
            "Outside, or remove doubles, on the target." % (target.name, detail))


def duplicate_object(context, obj, name_suffix="_slice"):
    """Create an independent clone of an object, copying the mesh data too."""
    new = obj.copy()
    new.data = obj.data.copy()
    new.name = obj.name + name_suffix
    context.collection.objects.link(new)
    return new


CUTTER_COLLECTION = "Hardflow Cutters"


def cutter_collection(context):
    """Get/create the collection that gathers non-destructive cutters."""
    coll = bpy.data.collections.get(CUTTER_COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(CUTTER_COLLECTION)
        context.scene.collection.children.link(coll)
    return coll


def stash_cutter(context, cutter, target):
    """Move the cutter to a separate collection, show it as wire, parent it to
    the target. Since the boolean modifier stays live on the target, the cutter
    is kept in the scene (BoxCutter-style non-destructive flow)."""
    for c in list(cutter.users_collection):
        c.objects.unlink(cutter)
    cutter_collection(context).objects.link(cutter)
    cutter.display_type = 'WIRE'
    cutter.hide_render = True
    # When the target moves/rotates, the cutter follows; keep its world pose fixed.
    cutter.parent = target
    cutter.matrix_parent_inverse = target.matrix_world.inverted_safe()
