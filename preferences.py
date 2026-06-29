# Eklenti tercihleri ve her yerden erisilebilen prefs yardimcisi.
import bpy
from bpy.types import AddonPreferences
from bpy.props import BoolProperty, IntProperty, FloatVectorProperty, EnumProperty


def get_prefs(context=None):
    """Bu modulun __package__'i temel eklenti paketidir (or. 'hardflow' ya da
    'bl_ext.user_default.hardflow'), bu yuzden alt modullerden cagrilsa bile
    dogru anahtari verir."""
    context = context or bpy.context
    return context.preferences.addons[__package__].preferences


class HARDFLOW_Preferences(AddonPreferences):
    bl_idname = __package__

    snap_enabled: BoolProperty(
        name="Grid Snap",
        description="Cizim noktalarini grid'e kilitle",
        default=True,
    )
    grid_size: IntProperty(
        name="Grid Size (px)",
        description="Ekran-uzayi grid araligi",
        default=24, min=2, max=256,
    )
    default_solver: EnumProperty(
        name="Boolean Solver",
        items=[
            ('EXACT', "Exact", "Daha dogru, daha yavas"),
            ('FAST', "Fast", "Daha hizli, daha kirilgan"),
        ],
        default='EXACT',
    )
    line_color: FloatVectorProperty(
        name="Line Color", subtype='COLOR', size=4,
        default=(0.15, 0.8, 1.0, 1.0), min=0.0, max=1.0,
    )
    fill_color: FloatVectorProperty(
        name="Fill Color", subtype='COLOR', size=4,
        default=(0.15, 0.8, 1.0, 0.12), min=0.0, max=1.0,
    )
    grid_color: FloatVectorProperty(
        name="Grid Color", subtype='COLOR', size=4,
        default=(1.0, 1.0, 1.0, 0.06), min=0.0, max=1.0,
    )

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "snap_enabled")
        col.prop(self, "grid_size")
        col.prop(self, "default_solver")
        row = col.row(align=True)
        row.prop(self, "line_color")
        row.prop(self, "fill_color")
        row.prop(self, "grid_color")
        col.separator()
        col.label(text="Kisayollar: pie menu = Alt+D, dogrudan cut = Ctrl+Shift+D")
