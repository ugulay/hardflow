# Hardflow

Açık kaynak hard-surface boolean modelleme araç seti — Grid Modeler, Boxcutter
ve Hard Ops'un çekirdek iş akışlarını ücretsiz ve GPLv3 altında sunmayı
hedefler. Blender 4.2+ uzantı sistemiyle uyumludur.

> v0.1 — temel mimari ve birkaç çalışan özellik. Yol haritası için ROADMAP.md.

## Kurulum

Blender 4.2+: **Edit > Preferences > Get Extensions > (sağ üst ⌄) > Install
from Disk** → `hardflow` zip'ini seç.

## Kullanım

Object Mode'da bir mesh seç:

- **Alt+D** → pie menu (tüm araçlar)
- **Ctrl+Shift+D** → doğrudan çizim aracı

Çizim modunda:

| Tuş | İşlev |
|-----|-------|
| Sol tık | Nokta koy / şekli başlat-bitir |
| Enter | POLY şeklini kapat ve uygula |
| Backspace | Son POLY noktasını sil |
| Q / W / E | Shape: Box / Circle / Polygon |
| 1 / 2 / 3 | Mode: Cut / Slice / Make |
| X | Grid snap aç/kapat |
| Sağ tık / Esc | İptal |

**Mode'lar:** Cut = boolean DIFFERENCE · Slice = nesneyi ikiye böl · Make =
geometri ekle (UNION).

## Mimari

```
hardflow/
├── blender_manifest.toml   # uzantı kimliği (4.2+)
├── __init__.py             # kayıt orkestrasyonu + keymap
├── preferences.py          # ayarlar + get_prefs() erişimcisi
├── core/                   # saf mantık (UI'dan bağımsız, test edilebilir)
│   ├── raycast.py          # ekran <-> 3D projeksiyon
│   ├── grid.py             # snapping + şekil noktaları
│   ├── geometry.py         # bmesh ile kesici hacim üretimi
│   └── boolean.py          # destructive + non-destructive boolean
├── operators/              # kullanıcı eylemleri
│   ├── draw_cut.py         # ana modal çizim operatörü
│   └── modifiers.py        # akıllı bevel + mirror
└── ui/                     # GPU çizim, HUD, menüler
    ├── draw.py             # gpu + blf yardımcıları
    └── pie.py              # Hard Ops tarzı pie menu
```

Katman kuralı: `ui` ve `operators` → `core`'a bağımlı olabilir; `core` hiçbir
zaman `ui`'a bağımlı **olmaz**. Yeni bir özellik genelde core'a saf bir
fonksiyon + onu çağıran ince bir operator eklemek demektir.

## Lisans

GPLv3. `bpy` ile dağıtılan tüm Blender eklentileri pratikte GPL'dir; bu proje
de öyle. Tam lisans metni için LICENSE dosyasına bak.
