# Yol Haritası

Rakip araçların özellikleri ve Hardflow'da nereye/nasıl oturdukları. Her madde
mümkün olduğunca tek bir modüle izole edilmiştir ki katkı verenler birbirine
çarpmadan ilerleyebilsin.

## v0.1 — Mevcut (çekirdek döngü çalışıyor)
- [x] Modal çizim operatörü (Box / Circle / Polygon)
- [x] Cut / Slice / Make modları (boolean DIFFERENCE / INTERSECT / UNION)
- [x] Ekran-uzayı grid snap + canlı GPU çizim + HUD
- [x] Akıllı bevel ve mirror operatörleri
- [x] Pie menu, tercihler, keymap

## v0.2 — Snapping ve hassasiyet (en yüksek değer)
Grid Modeler'ın asıl gücü burada.
- [ ] **Dünya-ölçekli grid** — `core/grid.py`: snap'i ekran yerine projeksiyon
      düzleminin yerel 2D ekseninde yap. Böylece grid her yüzeyde tutarlı kalır
      ("absolute size" modu).
- [ ] **Vertex / edge snap** — `core/raycast.py`: `obj.ray_cast` + en yakın
      köşe/kenar arama; çizim noktasını mevcut geometriye kilitle.
- [ ] **Açı kilidi** — Shift basılıyken 15°/45° kademeleri.
- [ ] **Grid düzlemini döndürme** — ok tuşlarıyla düzlem normalini değiştir.

## v0.3 — Non-destructive iş akışı (Boxcutter ruhu)
- [ ] Boolean'ları uygulamak yerine canlı modifier yığını olarak tut
      (`core/boolean.py`'de `add_boolean` zaten hazır — operatöre seçenek ekle).
- [ ] Kesici nesneleri ayrı bir koleksiyonda sakla, gizle, sonradan düzenle.
- [ ] "Recut" — eski bir kesimi geri çağırıp değiştir.

## v0.4 — Geometri kalitesi
- [ ] Polygon için kendiyle-kesişme tespiti ve uyarı.
- [ ] Kesim sonrası n-gon'ları temizle / iste-bağlı triangulate.
- [ ] Bevel sonrası ölü vertex temizliği (Hard Ops'un "clean" fonksiyonu).
- [ ] Inset / extrude modu (Grid Modeler "create face").

## v0.5 — Boru ve profil (Grid Modeler "pipes")
- [ ] Çizilen çizgi boyunca curve + bevel ile boru üretimi.

## v0.6 — UX cilası
- [ ] N-panel: aktif kesiciler listesi, ayarlar.
- [ ] blf HUD'u zenginleştir (mod ikonları, ölçü göstergesi).
- [ ] Tema/renk tercihlerini canlı önizleme.
- [ ] Çoklu yüzey / çoklu nesne desteği.

## Bilinen sınırlamalar (v0.1)
- Snap ekran-uzayında; kamera açısına göre dünya ölçeği değişir.
- Sadece Object Mode. Edit Mode akışı (`bmesh.from_edit_mesh`) henüz yok.
- Konkav poligonlar çalışır; kendiyle kesişenler bozuk kesici üretir.
- EXACT solver çakışan/ters-normal geometride başarısız olabilir — kesim
      yapmazsa hedefin normallerini düzelt veya kesiciyi biraz kaydır.
