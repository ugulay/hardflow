# UI localization for Hardflow.
#
# Blender translates interface strings through bpy.app.translations: an add-on
# registers a catalog `{locale: {(context, english): translated}}` and, when the
# user sets Blender's language and enables "Translate > Interface", every matching
# `layout.label`/operator label is shown translated. We register a Turkish (tr_TR)
# catalog here; adding another language is just another top-level dict entry.
#
# Layer rule: this is a thin bpy-only shim (no core, no gpu/blf); it is wired into
# __init__.register()/unregister() next to the other non-class registrations.
#
# Note the msgctxt is "*" (the default catch-all) for panel/menu text. That means
# a common word like "Cut" is translated wherever it appears while Turkish is
# active -- the accepted trade-off for add-on i18n, and only in effect when the
# user opts into a translated interface.
import bpy

# English source -> Turkish. Covers the visible N-panel sections, the Boolean
# draw modes/shapes, the hero tools, the build primitives and the common actions.
_TR = {
    # --- N-panel section headers ---
    "Boolean Draw": "Boolean Çizim",
    "Build": "İnşa",
    "Edit": "Düzenle",
    "Curves": "Eğriler",
    "Display & Mesh": "Görünüm & Mesh",
    "Help & Shortcuts": "Yardım & Kısayollar",
    "Snapping & Settings": "Yakalama & Ayarlar",
    "Cutter Options": "Kesici Seçenekleri",
    "Modifier Stack": "Değiştirici Yığını",
    "Cutters": "Kesiciler",
    "Gizmos": "Gizmolar",
    "Quick Start": "Hızlı Başlangıç",
    "Shape": "Şekil",
    "Mode": "Mod",
    "Sketch face": "Yüz Çiz",

    # --- Boolean draw modes ---
    "Cut": "Kes",
    "Slice": "Dilimle",
    "Make": "Birleştir",
    "Intersect": "Kesişim",
    "Join": "Ekle",
    "Knife": "Bıçak",
    "Draw": "Çiz",

    # --- draw shapes ---
    "Box": "Kutu",
    "Circle": "Daire",
    "N-gon": "Çokgen",
    "Polygon": "Çokgen",
    "Rectangle": "Dikdörtgen",
    "Slot": "Yuva",
    "Star": "Yıldız",
    "Arc": "Yay",
    "Vent": "Menfez",

    # --- hero / edit tools ---
    "Push/Pull": "İt/Çek",
    "Offset": "Ofset",
    "Edge Bevel": "Kenar Pahı",
    "Loop Cut": "Döngü Kesme",
    "Smart Sharpen": "Akıllı Keskinleştir",
    "Fix Shading": "Gölgelemeyi Düzelt",
    "Sort Stack": "Yığını Sırala",
    "Extract Cutter": "Kesici Çıkar",
    "Panel Line": "Panel Çizgisi",
    "Groove": "Oluk",
    "Bead": "Kaynak Dikişi",
    "Radial": "Radyal",

    # --- curves ---
    "Pipe": "Boru",
    "Cable": "Kablo",
    "Sweep": "Süpürme",

    # --- build primitives ---
    "Cube": "Küp",
    "Plane": "Düzlem",
    "Cylinder": "Silindir",
    "Cone": "Koni",
    "Sphere": "Küre",
    "Tube": "Tüp",
    "Grid": "Izgara",
    "Guide": "Kılavuz",
    "Loft": "Loft",

    # --- display & mesh ---
    "Wire": "Tel",
    "Sharp": "Keskin",
    "Random Colors": "Rastgele Renkler",
    "Copy Mat": "Materyal Kopyala",

    # --- common actions ---
    "Apply Cutters": "Kesicileri Uygula",
    "Boolean (Selected)": "Boolean (Seçili)",
    "Recalculate Normals": "Normalleri Yeniden Hesapla",
    "Cutter Scroll": "Kesici Kaydır",

    # --- snap toggle row ---
    "Grid": "Izgara",
    "Vertex": "Köşe",
    "Surface": "Yüzey",
}

# Blender's catalog format: {locale: {(msgctxt, msgid): msgstr}}. "*" is the
# default context that panel/menu text is looked up under.
TRANSLATIONS = {
    "tr_TR": {("*", src): dst for src, dst in _TR.items()},
}

# A stable, unique registration key (Blender raises if the same key is registered
# twice, so register() clears a stale one first).
_KEY = "hardflow"


def register():
    try:
        bpy.app.translations.unregister(_KEY)   # drop a stale catalog if any
    except Exception:
        pass
    try:
        bpy.app.translations.register(_KEY, TRANSLATIONS)
    except Exception as ex:   # never let an i18n hiccup strand the add-on
        print("Hardflow: translations not registered (%s)" % ex)


def unregister():
    try:
        bpy.app.translations.unregister(_KEY)
    except Exception:
        pass
