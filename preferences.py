# Eklenti tercihleri ve her yerden erisilebilen prefs yardimcisi.
import bpy
from bpy.types import AddonPreferences
from bpy.props import (BoolProperty, IntProperty, FloatProperty,
                       FloatVectorProperty, EnumProperty)


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
        description="Eski ekran-uzayi grid araligi (legacy, kullanilmiyor)",
        default=24, min=2, max=256,
    )
    grid_world: FloatProperty(
        name="Grid Size (m)",
        description="Dunya-olcekli grid araligi (metre); projeksiyon duzleminde "
                    "tutarli, kameradan bagimsiz snap",
        default=0.1, min=0.001, soft_max=10.0,
    )
    geo_snap: BoolProperty(
        name="Vertex/Edge Snap",
        description="Cizim noktasini mevcut geometrinin vertex/kenar/orta "
                    "noktasina kilitle (grid'i ezer)",
        default=True,
    )
    snap_pixels: IntProperty(
        name="Snap Distance (px)",
        description="Geometri snap'i icin ekran-uzayi yakalama yaricapi",
        default=12, min=4, max=64,
    )
    angle_step: IntProperty(
        name="Angle Step (deg)",
        description="Shift basiliyken cizim yonunun kilitlenecegi aci kademesi",
        default=15, min=1, max=90,
    )
    pipe_radius: FloatProperty(
        name="Pipe Radius (m)",
        description="Boru aracinin yuvarlak kesit yaricapi",
        default=0.05, min=0.001, soft_max=1.0,
    )
    non_destructive: BoolProperty(
        name="Non-Destructive",
        description="Boolean'i uygulamak yerine canli modifier birak; kesicileri "
                    "ayri 'Hardflow Cutters' koleksiyonunda sakla (BoxCutter tarzi)",
        default=False,
    )
    multi_object: BoolProperty(
        name="Çoklu Nesne",
        description="CUT/MAKE'i seçili tüm mesh nesnelere uygula (tek kesici, "
                    "çoklu hedef)",
        default=False,
    )
    cleanup_after_cut: BoolProperty(
        name="Cut Sonrası Temizle",
        description="Destructive kesim sonrasi mesh'i temizle (remove doubles + "
                    "coplanar yuzleri birlestir)",
        default=False,
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
        col.prop(self, "grid_world")
        col.prop(self, "geo_snap")
        col.prop(self, "snap_pixels")
        col.prop(self, "angle_step")
        col.prop(self, "pipe_radius")
        col.prop(self, "non_destructive")
        col.prop(self, "multi_object")
        col.prop(self, "cleanup_after_cut")
        col.prop(self, "default_solver")
        row = col.row(align=True)
        row.prop(self, "line_color")
        row.prop(self, "fill_color")
        row.prop(self, "grid_color")
        col.separator()
        col.label(text="Kisayollar: pie menu = Alt+Q, dogrudan cut = Ctrl+Shift+D")
