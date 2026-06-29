# Boolean islemleri. Hem destructive (uygula-sil) hem non-destructive
# (modifier birak) yollari var.
import bpy


def _new_bool(target, cutter, operation, solver):
    mod = target.modifiers.new("HF_Bool", 'BOOLEAN')
    mod.operation = operation
    mod.solver = solver
    mod.object = cutter
    return mod


def apply_boolean(context, target, cutter, operation='DIFFERENCE', solver='EXACT'):
    """Destructive: modifier ekle, uygula. cutter cagiran tarafindan silinir."""
    mod = _new_bool(target, cutter, operation, solver)
    with context.temp_override(active_object=target, object=target):
        bpy.ops.object.modifier_apply(modifier=mod.name)


def add_boolean(target, cutter, operation='DIFFERENCE', solver='EXACT'):
    """Non-destructive: sadece modifier ekle, dondur. cutter sahnede kalir."""
    return _new_bool(target, cutter, operation, solver)


def duplicate_object(context, obj, name_suffix="_slice"):
    """Mesh verisini de kopyalayarak bagimsiz bir nesne klonu olusturur."""
    new = obj.copy()
    new.data = obj.data.copy()
    new.name = obj.name + name_suffix
    context.collection.objects.link(new)
    return new
