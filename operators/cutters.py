# Non-destructive kesici yonetimi: uygula (bake), sec, sil.
# N-panel'deki "Kesiciler" listesi bu operatorlere delege eder.
import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, StringProperty

from ..core import boolean


def _still_used(cutter, ignore=None):
    """Herhangi bir nesne hala bu cutter'i boolean modifier'da kullaniyor mu?"""
    for ob in bpy.data.objects:
        if ob is ignore:
            continue
        for m in ob.modifiers:
            if getattr(m, "object", None) is cutter:
                return True
    return False


class HARDFLOW_OT_apply_cutters(Operator):
    bl_idname = "object.hardflow_apply_cutters"
    bl_label = "Kesicileri Uygula"
    bl_description = ("Aktif nesnedeki tum canli Hardflow boolean'larini uygula "
                      "(bake); artik kullanilmayan kesicileri sil")
    bl_options = {'REGISTER', 'UNDO'}

    delete_cutters: BoolProperty(
        name="Kesicileri Sil",
        description="Uygulamadan sonra baska yerde kullanilmayan kesicileri sil",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return bool(obj) and any(m.name.startswith("HF_Bool")
                                 for m in obj.modifiers)

    def execute(self, context):
        obj = context.active_object
        used = []
        for mod in list(obj.modifiers):
            if not mod.name.startswith("HF_Bool"):
                continue
            if mod.type == 'BOOLEAN' and mod.object is not None:
                used.append(mod.object)
            with context.temp_override(active_object=obj, object=obj):
                bpy.ops.object.modifier_apply(modifier=mod.name)

        removed = 0
        if self.delete_cutters:
            for cutter in set(used):
                if not _still_used(cutter):
                    bpy.data.objects.remove(cutter, do_unlink=True)
                    removed += 1
        self.report({'INFO'}, "Kesiciler uygulandi (%d silindi)" % removed)
        return {'FINISHED'}


class HARDFLOW_OT_select_cutter(Operator):
    bl_idname = "object.hardflow_select_cutter"
    bl_label = "Kesiciyi Seç"
    bl_description = "Kesiciyi gorunur yap, sec ve aktif et (duzenlemek icin)"
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        cutter = bpy.data.objects.get(self.name)
        if cutter is None:
            self.report({'WARNING'}, "Kesici bulunamadi")
            return {'CANCELLED'}
        for o in list(context.selected_objects):
            o.select_set(False)
        cutter.hide_viewport = False
        cutter.hide_set(False)
        cutter.select_set(True)
        context.view_layer.objects.active = cutter
        return {'FINISHED'}


class HARDFLOW_OT_remove_cutter(Operator):
    bl_idname = "object.hardflow_remove_cutter"
    bl_label = "Kesiciyi Sil"
    bl_description = ("Kesiciyi sahneden sil; onu kullanan boolean modifier'lar "
                      "etkisiz kalir (geri al ile donulebilir)")
    bl_options = {'REGISTER', 'UNDO'}

    name: StringProperty()

    def execute(self, context):
        cutter = bpy.data.objects.get(self.name)
        if cutter is None:
            return {'CANCELLED'}
        bpy.data.objects.remove(cutter, do_unlink=True)
        return {'FINISHED'}
