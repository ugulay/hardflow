# Hardflow

Açık kaynak hard-surface boolean modelleme araç seti — Grid Modeler, Boxcutter
ve Hard Ops'un çekirdek iş akışlarını ücretsiz ve GPLv3 altında sunmayı
hedefler. Blender 4.2+ uzantı sistemiyle uyumludur.

> Geliştirme aşamasında. Çekirdek kesim döngüsü, dünya-ölçekli + vertex/edge
> snapping ve non-destructive akış çalışır durumda. Tam yol haritası (decaller
> dahil) için ROADMAP.md.

## Özellikler

- **Modal çizim ile boolean** — Box / Circle / Polygon şekilleri; Cut (kes),
  Slice (ikiye böl), Make (ekle), Face (yüzey oluştur) modları.
- **Dünya-ölçekli grid snap** — kameradan bağımsız, metre cinsinden tutarlı grid
  (Grid Modeler "absolute size" mantığı); düzlem `←/→` ile VIEW / X / Y / Z.
- **Çoklu nesne** — CUT/MAKE'i seçili tüm mesh'lere tek kesiciyle uygula.
- **Boru (pipe)** — çizilen çizgiden yuvarlak kesitli boru; **Clean** ile mesh
  temizliği (Hard Ops tarzı).
- **Vertex / edge snap** — çizim noktasını mevcut geometrinin köşe / kenar /
  kenar-ortasına kilitle; renkli imleç geri bildirimi.
- **Açı kilidi** — Shift ile çizim yönünü 15° (ayarlanabilir) kademelere kilitle.
- **Non-destructive mod** — boolean'ı uygulamak yerine canlı modifier bırak;
  kesicileri ayrı koleksiyonda sakla (Boxcutter ruhu).
- **Gelişmiş bevel** — interaktif (sürükle=genişlik, tekerlek=segment), profil +
  açı limiti + width-type + **Weighted Normal** (temiz gölgeleme); mirror
  (bisect + clip). Hard Ops ruhu.
- **Pie menu**, tercihler paneli, özelleştirilebilir snap ayarları.

## Kurulum

Blender 4.2+: **Edit > Preferences > Get Extensions > (sağ üst ⌄) > Install
from Disk** → `hardflow` zip'ini seç.

## Kullanım

Object Mode'da bir mesh seç:

- **Alt+Q** → pie menu (tüm araçlar)
- **Ctrl+Shift+D** → doğrudan çizim aracı

Çizim modunda:

| Tuş | İşlev |
|-----|-------|
| Sol tık | Nokta koy / şekli başlat-bitir |
| Enter | POLY şeklini kapat ve uygula |
| Backspace | Son POLY noktasını sil |
| Q / W / E | Shape: Box / Circle / Polygon |
| 1 / 2 / 3 / 4 | Mode: Cut / Slice / Make / Face |
| ← / → | Çizim düzlemi: VIEW / X / Y / Z |
| X | Dünya-ölçekli grid snap aç/kapat |
| V | Vertex/edge snap aç/kapat |
| Shift (basılı) | Çizim yönünü açı kademesine kilitle |
| N | Non-destructive (canlı modifier) aç/kapat |
| Sağ tık / Esc | İptal |

**Mode'lar:** Cut = boolean DIFFERENCE · Slice = nesneyi ikiye böl · Make =
geometri ekle (UNION) · Face = çizilen şekilden yüzey oluştur (boolean değil).

**Diğer araçlar:** Bevel · Mirror · **Clean** (mesh temizliği) · **Pipe**
(çizgiden boru) · **Kesicileri Uygula** — hepsi N-panel ve pie menüde.

**Snap imleç renkleri:** 🟡 köşe · 🟢 kenar ortası · 🔵 kenar üzeri.

## Mimari

```
hardflow/
├── blender_manifest.toml   # uzantı kimliği (4.2+)
├── __init__.py             # kayıt orkestrasyonu + keymap
├── preferences.py          # ayarlar + get_prefs() erişimcisi
├── core/                   # saf mantık (UI'dan bağımsız, test edilebilir)
│   ├── raycast.py          # ekran <-> 3D projeksiyon, düzlem (u,v)
│   ├── grid.py             # dünya-ölçekli + açı snap, şekil noktaları
│   ├── snap.py             # vertex/edge geometri snap (saf 2D)
│   ├── geometry.py         # bmesh ile kesici hacim üretimi
│   └── boolean.py          # destructive + non-destructive boolean
├── operators/              # kullanıcı eylemleri
│   ├── draw_cut.py         # ana modal çizim operatörü (cut/slice/make/face)
│   ├── modifiers.py        # akıllı bevel + mirror + clean
│   ├── cutters.py          # non-destructive kesici yönetimi (uygula/seç/sil)
│   └── pipe.py             # çizgiden boru üretimi
├── ui/                     # GPU çizim, HUD, menüler
│   ├── draw.py             # gpu + blf yardımcıları
│   ├── pie.py              # Hard Ops tarzı pie menu
│   └── panel.py            # N-panel: araçlar, ayarlar, kesici listesi
└── tests/                  # testler
    ├── test_core.py        # saf çekirdek, Blender'sız (python tests/test_core.py)
    └── test_blender.py     # headless (blender --background --python ...)
```

`core/grid.py` ve `core/snap.py` bilinçli olarak `bpy`'siz tutulur; bu yüzden
matematik katmanı normal CPython ile (`python tests/test_core.py`) test edilir.

Katman kuralı: `ui` ve `operators` → `core`'a bağımlı olabilir; `core` hiçbir
zaman `ui`'a bağımlı **olmaz**. Yeni bir özellik genelde core'a saf bir
fonksiyon + onu çağıran ince bir operator eklemek demektir.

## Lisans

GPLv3. `bpy` ile dağıtılan tüm Blender eklentileri pratikte GPL'dir; bu proje
de öyle. Tam lisans metni için LICENSE dosyasına bak.
