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
    cutter.matrix_parent_inverse = target.matrix_world.inverted()
