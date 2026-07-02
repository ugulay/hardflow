# Boolean operations. Provides both destructive (apply-and-delete) and
# non-destructive (leave a modifier) paths.
import bpy


def _solver_available(solver):
    """True when the Boolean modifier exposes `solver` in this Blender build. The
    MANIFOLD solver only exists from Blender 4.5."""
    try:
        items = bpy.types.BooleanModifier.bl_rna.properties['solver'].enum_items
        return solver in {i.identifier for i in items}
    except (KeyError, AttributeError):
        return False


def _coerce_solver(solver):
    """Map a solver identifier to one this Blender supports. Blender 5.0 renamed
    the FAST solver to FLOAT, so a 'FAST' request prefers 'FLOAT' before giving up
    on the always-present 'EXACT' (assigning an unavailable solver raises). Without
    this, every FAST fallback silently degrades to the slow EXACT solver on 5.x."""
    if _solver_available(solver):
        return solver
    if solver == 'FAST' and _solver_available('FLOAT'):
        return 'FLOAT'
    return 'EXACT'


# Transient name for the destructive apply modifier. Deliberately DISTINCT from
# the live "HF_Bool" name the non-destructive path uses: a failed apply must only
# ever remove the modifier it just added, never the user's existing
# non-destructive cutters (which are also named "HF_Bool").
_APPLY_MOD_NAME = "HF_BoolApply"


def _new_bool(target, cutter, operation, solver, name="HF_Bool"):
    mod = target.modifiers.new(name, 'BOOLEAN')
    mod.operation = operation
    mod.solver = _coerce_solver(solver)
    mod.object = cutter
    return mod


def apply_boolean(context, target, cutter, operation='DIFFERENCE', solver='EXACT'):
    """Destructive: add a modifier and apply it. The cutter is deleted by the
    caller. On failure only the just-added modifier is removed (matched by its
    exact name, not the "HF_Bool" prefix) so a doomed attempt never disturbs the
    target's other modifiers, and the RuntimeError propagates to the fallback
    chain."""
    mod = _new_bool(target, cutter, operation, solver, name=_APPLY_MOD_NAME)
    name = mod.name  # Blender may auto-suffix if the name is already taken
    try:
        with context.temp_override(active_object=target, object=target):
            bpy.ops.object.modifier_apply(modifier=name)
    except RuntimeError:
        leftover = target.modifiers.get(name)
        if leftover is not None:
            target.modifiers.remove(leftover)
        raise


def add_boolean(target, cutter, operation='DIFFERENCE', solver='EXACT'):
    """Non-destructive: just add a modifier and return it. The cutter stays in
    the scene."""
    return _new_bool(target, cutter, operation, solver)


def _dedupe(seq):
    """Order-preserving de-duplication."""
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _apply_boolean_chain(context, target, cutter, operation, solvers):
    """Try each solver in order until one applies. apply_boolean removes its own
    half-added modifier when it raises, so a failed attempt leaves the target
    exactly as it was. Returns the solver that succeeded, or None."""
    for attempt in solvers:
        try:
            apply_boolean(context, target, cutter, operation, attempt)
            return attempt
        except RuntimeError:
            continue
    return None


def apply_boolean_fallback(context, target, cutter, operation='DIFFERENCE',
                           solver='EXACT'):
    """Destructive apply that retries with the FAST solver when the preferred one
    raises -- boolean INSERTs / cutters on messy targets (robustness). Any
    half-added modifier is cleaned up between attempts. Returns the solver string
    that succeeded, or None when both fail."""
    return _apply_boolean_chain(context, target, cutter, operation,
                                _dedupe([solver, 'FAST']))


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


def _is_watertight_manifold(obj):
    """True when `obj` is fully closed-manifold with no degenerate / loose
    geometry -- the precondition the MANIFOLD solver needs on each operand."""
    h = mesh_health(obj)
    return h['non_manifold'] == 0 and h['degenerate'] == 0 and h['loose'] == 0


def choose_solver(target, preferred='EXACT', max_verts=_SOLVER_HEALTH_MAX_VERTS,
                  cutter=None):
    """Pick the solver to *try first* from the target's health. Only acts when
    `preferred` is EXACT (the default) and the mesh is light enough to scan
    cheaply; `robust_boolean` still falls back, so this only changes the *order*:

      * badly non-manifold / degenerate target -> start with FAST and skip a slow,
        doomed EXACT pass;
      * fully clean, closed manifold target -> start with the MANIFOLD solver
        (Blender 4.5+), which is far faster than EXACT and just as accurate on
        watertight input (`non_manifold == 0` already implies closed manifold).
        MANIFOLD needs *both* operands watertight, so it is only picked when the
        `cutter` (when supplied and light enough to scan) is clean too -- a
        non-manifold cutter could otherwise produce a silently-wrong result;
      * otherwise keep the accurate EXACT solver.
    """
    if preferred != 'EXACT' or len(target.data.vertices) > max_verts:
        return preferred
    h = mesh_health(target)
    if h['non_manifold'] >= _SOLVER_NONMANIFOLD_LIMIT or h['degenerate'] >= 1:
        return 'FAST'
    target_clean = (h['non_manifold'] == 0 and h['degenerate'] == 0
                    and h['loose'] == 0)
    cutter_ok = (cutter is None
                 or (len(cutter.data.vertices) <= max_verts
                     and _is_watertight_manifold(cutter)))
    if target_clean and cutter_ok and _solver_available('MANIFOLD'):
        return 'MANIFOLD'
    return 'EXACT'


def _fallback_chain(start, preferred):
    """Ordered solvers `robust_boolean` tries. Manifold-first stays accurate by
    escalating through EXACT before the lossy FAST pass; a health-forced FAST
    start (broken target) skips a slow EXACT attempt that would just fail."""
    if start == 'MANIFOLD':
        return _dedupe(['MANIFOLD', 'EXACT', 'FAST'])
    if start == 'FAST':
        return ['FAST']
    return _dedupe([start, 'FAST'])


def _solver_message(used, preferred, start):
    """Human-readable outcome. Quiet on the happy path (the planned solver worked,
    including a Manifold clean-mesh fast-path); only narrate a health-forced FAST
    downgrade or a genuine mid-chain fallback."""
    if used == start:
        if used == 'FAST' and preferred != 'FAST':
            return ("Cut done (FAST solver: target geometry is too broken for %s)"
                    % preferred)
        return "Cut done"
    return "Cut done (%s solver fallback)" % used


def robust_boolean(context, target, cutter, operation='DIFFERENCE',
                   solver='EXACT'):
    """Destructive boolean that tries hard to succeed and explains itself when it
    can't. Returns (ok, solver_used, message):

      * pick the starting solver from the target's health (`choose_solver`):
        Manifold on clean meshes, FAST on broken ones, else EXACT;
      * try the ordered fallback chain (`_fallback_chain`) -- a Manifold start
        escalates through EXACT before FAST, so the fast path never costs accuracy;
      * if every solver fails, recalculate the cutter's normals and retry the
        chain once -- the usual fix for a solver choking on an inverted cutter;
      * if it still fails, diagnose the *target* (non-manifold / degenerate /
        loose geometry) so the message tells the user what to repair.

    The target is never modified beyond the boolean itself; only the cutter's
    normals (it is disposable) may be rewritten."""
    start = choose_solver(target, solver, cutter=cutter)
    chain = _fallback_chain(start, solver)
    used = _apply_boolean_chain(context, target, cutter, operation, chain)
    if used is not None:
        return True, used, _solver_message(used, solver, start)

    recalc_normals(cutter)
    used = _apply_boolean_chain(context, target, cutter, operation, chain)
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
    is kept in the scene (non-destructive flow)."""
    for c in list(cutter.users_collection):
        c.objects.unlink(cutter)
    cutter_collection(context).objects.link(cutter)
    cutter.display_type = 'WIRE'
    cutter.hide_render = True
    # When the target moves/rotates, the cutter follows; keep its world pose fixed.
    cutter.parent = target
    cutter.matrix_parent_inverse = target.matrix_world.inverted_safe()


# --- shading fix: snapshot clean normals, transfer them back after a cut ------

HELPER_COLLECTION = "Hardflow Helpers"


def helper_collection(context):
    """Get/create a hidden collection for internal helper objects (the normal
    source snapshots). Excluded from selection and hidden in render."""
    coll = bpy.data.collections.get(HELPER_COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(HELPER_COLLECTION)
        context.scene.collection.children.link(coll)
        coll.hide_render = True
        coll.hide_viewport = True
    return coll


def has_normal_source(obj, name_suffix="_normals"):
    """True when a normal-source helper already exists for `obj`. Lets a caller
    tell a freshly-created snapshot from one `capture_normal_source` reuses, so a
    failed-cut rollback only removes helpers IT created and never a helper a prior
    successful cut's Data Transfer still references."""
    src = bpy.data.objects.get(obj.name + name_suffix)
    return src is not None and src.get("hf_normal_source_of") == obj.name


def capture_normal_source(context, obj, name_suffix="_normals"):
    """Snapshot `obj`'s CURRENT mesh (its clean, pre-cut normals) into a hidden
    helper object parented to it, and return that helper. Call this BEFORE a
    destructive boolean; afterwards `add_normal_transfer` binds a Data Transfer
    modifier that reflects these clean normals onto the n-gon faces the cut
    leaves, so the shading never smears. Re-uses / refreshes an existing snapshot
    for the same object so re-cuts don't pile up helpers."""
    src_name = obj.name + name_suffix
    src = bpy.data.objects.get(src_name)
    fresh = obj.data.copy()
    if src is not None and src.get("hf_normal_source_of") == obj.name:
        old = src.data
        src.data = fresh
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    else:
        src = bpy.data.objects.new(src_name, fresh)
        src["hf_normal_source_of"] = obj.name
        helper_collection(context).objects.link(src)
    src.hide_viewport = True
    src.hide_render = True
    src.hide_select = True
    src.parent = obj
    src.matrix_parent_inverse = obj.matrix_world.inverted_safe()
    return src


def add_normal_transfer(obj, source, name="HF_FixShading"):
    """Bind a Data Transfer modifier on `obj` that copies `source`'s per-face
    (loop) normals back onto `obj`, using nearest-polygon-normal mapping so the
    n-gon faces a boolean leaves take the underlying flat surface normal instead
    of a smeared average. Custom split normals are enabled so the transfer shows;
    Blender < 4.1 gated that behind `use_auto_smooth`. Idempotent (updates the
    same modifier); wrapped so an API mismatch degrades quietly. Returns the
    modifier or None."""
    try:
        me = obj.data
        if hasattr(me, "use_auto_smooth"):
            me.use_auto_smooth = True
        mod = obj.modifiers.get(name)
        if mod is None or mod.type != 'DATA_TRANSFER':
            if mod is not None:
                obj.modifiers.remove(mod)
            mod = obj.modifiers.new(name, 'DATA_TRANSFER')
        mod.object = source
        mod.use_loop_data = True
        mod.data_types_loops = {'CUSTOM_NORMAL'}
        mod.loop_mapping = 'NEAREST_POLYNOR'
        return mod
    except (RuntimeError, AttributeError, TypeError) as ex:  # noqa: BLE001
        print("[Hardflow] boolean normal transfer skipped: %s" % ex)
        return None
