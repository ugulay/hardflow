# CLAUDE.md — Hardflow

Bu dosya Claude Code'un projeyi her oturumda doğru bağlamla ele alması içindir.

## Proje nedir

Hardflow, Blender 4.2+ için **açık kaynak (GPLv3) hard-surface boolean
modelleme** araç setidir. Hedef: Grid Modeler, Boxcutter ve Hard Ops'un
çekirdek iş akışlarını ücretsiz sunmak. Şu an **v0.1** — temel mimari kurulu,
birkaç özellik çalışıyor. Tam yol haritası `ROADMAP.md`'de.

## İLK İŞ: Blender içinde smoke test

Bu kod **yazıldı ve sözdizimi doğrulandı, ama henüz canlı Blender'da
çalıştırılmadı.** Herhangi bir özellik geliştirmeden önce:

1. Eklentiyi kur, etkinleştir, hata almadan register olduğunu doğrula.
2. Object Mode'da bir küp seç → Ctrl+Shift+D → Box çiz → Cut'ın çalıştığını gör.
3. Pie menu (Alt+Q), bevel, mirror, slice, make modlarını tek tek dene.
4. Özellikle şüpheli iki nokta: `core/boolean.py`'deki `temp_override` +
   `modifier_apply` çağrısı, ve `operators/draw_cut.py`'deki `_build_and_apply`
   geometri/projeksiyon matematiği. Bunlar runtime'da test edilmedi.

Hata çıkarsa önce bunları düzelt, sonra ROADMAP'e geç.

## Mimari — değişmez kural

Katman bağımlılığı **tek yönlüdür**:

```
ui  ─┐
     ├─► core      (core ASLA yukarı bakmaz)
ops ─┘
```

- `core/` saf mantıktır: `bpy.ops`, `gpu`, `blf` **kullanmaz**. Tek istisna:
  `core/boolean.py` içindeki `modifier_apply` (bilinçli kabul edildi).
- `core` test edilebilir kalmalı. Yeni bir özellik = `core`'a saf fonksiyon +
  onu çağıran ince bir `operator`.
- UI çizimi `ui/draw.py`'de toplanır; operatörler oraya delege eder.

## Dosya haritası

| Yol | Sorumluluk |
|-----|-----------|
| `__init__.py` | Kayıt orkestrasyonu, `_classes` tuple, keymap |
| `preferences.py` | Ayarlar + `get_prefs(context)` erişimcisi |
| `core/raycast.py` | Ekran↔3D projeksiyon + düzlem (u,v) (`screen_to_plane`, `view_direction`, `world_to_plane_uv`, `plane_uv_to_world`, `world_to_screen`) |
| `core/grid.py` | Dünya-ölçekli + açı snap, şekil noktaları (`snap_world`, `world_grid_segments`, `snap_angle`, `box_points`, `circle_points`) |
| `core/snap.py` | Vertex/edge geometri snap, saf 2D (`nearest_point`, `closest_point_on_segment`, `nearest_on_segments`) |
| `core/geometry.py` | bmesh üretimi (`build_prism`, `build_face`, `build_pipe`, `estimate_thickness`, `cleanup_mesh`) |
| `core/boolean.py` | boolean + kesici yönetimi (`apply_boolean`, `add_boolean`, `duplicate_object`, `stash_cutter`, `cutter_collection`) |
| `operators/draw_cut.py` | Ana modal çizim operatörü (`HARDFLOW_OT_draw`): cut/slice/make/face, düzlem döndürme, ölçü HUD |
| `operators/modifiers.py` | Bevel + mirror + clean (`HARDFLOW_OT_bevel/mirror/clean`) |
| `operators/cutters.py` | Non-destructive kesici yönetimi (`HARDFLOW_OT_apply_cutters/select_cutter/remove_cutter`) |
| `operators/pipe.py` | Çizgiden boru (`HARDFLOW_OT_pipe`) |
| `ui/draw.py` | GPU + blf yardımcıları |
| `ui/pie.py` | Pie menu (`HARDFLOW_MT_pie`) |
| `ui/panel.py` | N-panel: araçlar, snap ayarları, kesici listesi (`HARDFLOW_PT_*`) |
| `tests/test_core.py` | Blender'sız saf çekirdek testleri (`python tests/test_core.py`) |

## Kayıt kuralı

Yeni her sınıf `__init__.py` içindeki `_classes` tuple'ına eklenmelidir,
aksi halde register edilmez. Keymap'ler `_register_keymaps()` içinde.

## Blender API kısıtları (4.2 LTS+ hedef)

- 2D çizim shader'ı: `'UNIFORM_COLOR'` / `'POLYLINE_UNIFORM_COLOR'`.
  **`'2D_UNIFORM_COLOR'` KULLANMA** (3.x'te kaldırıldı).
- `blf.size(font_id, size)` — eski dpi parametresi yok.
- `batch_for_shader` primitifleri: `LINE_STRIP`, `LINES`, `TRIS`, `POINTS`.
  **`LINE_LOOP` / `TRI_FAN` kullanma** (deprecated).
- Context override için `with context.temp_override(...)`.

## Geliştirme döngüsü

Yeniden zip'lemeden hızlı iterasyon için symlink kur:

```bash
ln -s "$(pwd)" ~/.config/blender/4.2/extensions/user_default/hardflow
```

Blender'da değişikliği yüklemek: `F3 > Reload Scripts` ya da eklentiyi
kapat/aç. System Console'u açık tut (Window > Toggle System Console).

Not: `bpy` Blender dışında çalışmaz; birim testleri Blender'ın Python'u içinde
ya da headless `blender --background --python test.py` ile koşar. `core/`
modüllerinin çoğu bpy'siz mock'lanarak test edilebilir (bilinçli tasarım).

## Konvansiyonlar

- Sınıf adları: `HARDFLOW_OT_*` (operator), `HARDFLOW_MT_*` (menu),
  `HARDFLOW_Preferences`.
- Operator `bl_idname`: `mesh.hardflow_*` veya `object.hardflow_*`.
- PEP 8, ~90 karakter satır.
- Lisans GPLv3 — yeni dosyalara da geçerli.
