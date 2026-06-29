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
- [x] **Dünya-ölçekli grid** — `core/grid.py` `snap_world` + `world_grid_segments`,
      `core/raycast.py` `world_to_plane_uv`/`plane_uv_to_world`/`world_to_screen`.
      Snap artık projeksiyon düzleminin yerel (u,v) metre ekseninde; tercih
      `grid_world` (metre). Çekirdek matematik bpy'siz test edildi.
- [x] **Vertex / edge snap** — `core/snap.py` (saf 2D, test edildi): hedefin
      dünya köşelerini ekrana projekte edip en yakın vertex/orta-nokta/kenara
      kilitle. Operatörde `V` toggle, tercih `geo_snap`+`snap_pixels`, renkli
      imleç (sarı=köşe, yeşil=orta, mavi=kenar). Yoğun mesh'te otomatik kapanır.
- [x] **Açı kilidi** — Shift basılıyken çizim yönünü `angle_step` kademesine
      kilitle (`core/grid.py snap_angle`, test edildi).
- [x] **Grid düzlemini döndürme** — `←/→` ile düzlem VIEW / dünya X / Y / Z
      arasında geçer (`core/raycast.py ray_to_plane`); kesici düzlem normali
      boyunca extrude edilir. Dünya-eksenli grid = Grid Modeler hizalı çizim.

## v0.3 — Non-destructive iş akışı (Boxcutter ruhu)
- [x] Boolean'ları uygulamak yerine canlı modifier bırak — operatörde `N` ile
      toggle, tercih `non_destructive`. CUT/SLICE/MAKE üçü de destekli.
- [x] Kesici nesneleri ayrı "Hardflow Cutters" koleksiyonunda sakla (WIRE
      görünüm, render kapalı, hedefe parent) — `core/boolean.py stash_cutter`.
- [x] Kesicileri gizleme/koleksiyon toggle UI — N-panel "Kesiciler" bölümü:
      koleksiyon + nesne bazlı göster/gizle.
- [x] "Recut" temeli — N-panel'den kesiciyi seç (görünür yap + aktif et) ile
      mesh'ini düzenle; "Kesicileri Uygula (Bake)" ile hepsini destructive
      uygula (`operators/cutters.py`).

## v0.4 — Geometri kalitesi
- [x] Polygon için kendiyle-kesişme tespiti ve uyarı — `core/grid.py`
      `is_self_intersecting`; commit'te bozuk poly reddedilir (test edildi).
- [x] Kesim sonrası temizlik — tercih `cleanup_after_cut`; `core/geometry.py
      cleanup_mesh` (remove doubles + sınırlı çözme + başıboş sil).
- [x] Bevel sonrası ölü vertex temizliği — `HARDFLOW_OT_clean` (Hard Ops "clean").
- [x] Create face — çizim operatöründe `FACE` modu (tuş `4`): çizilen şekilden
      tek n-gen yüzey nesnesi (`geometry.build_face`). Extrude native `E` ile.
- [x] **Gelişmiş bevel** — `HARDFLOW_OT_bevel` modal/interaktif (sürükle=genişlik,
      tekerlek=segment) + profil, açı limiti, width-type ve **Weighted Normal**
      modifier (temiz hard-surface gölgeleme). İleride: özel profil eğrisi,
      bevel preset'leri, vertex bevel.

## v0.5 — Boru ve profil (Grid Modeler "pipes")
- [x] Çizilen çizgi boyunca curve + bevel ile boru üretimi —
      `HARDFLOW_OT_pipe` modal + `core/geometry.py build_pipe`; yarıçap tercihi
      `pipe_radius`. Profil şimdilik yuvarlak; ileride kare/özel kesit.

## v0.6 — UX cilası
- [x] N-panel: araçlar + ayarlar + aktif kesiciler listesi (`ui/panel.py`).
- [x] HUD ölçü göstergesi — çizilen şeklin metre cinsinden boyutu (Box W×H,
      Circle yarıçap/çap, Poly nokta + son segment).
- [x] Tema/renk canlı önizleme — N-panel'de çizgi/grid rengi (anında yansır).
- [x] Çoklu nesne desteği — `multi_object` tercihi; CUT/MAKE seçili tüm
      mesh'lere tek kesiciyle uygulanır.

## v0.7+ — Decaller (DECALmachine ruhu)
Yeni bir alt sistem; yüzeye yapışan detay geçişleri (panel çizgileri, logolar,
vida/uyarı işaretleri) ile hard-surface'i "bitmiş" gösterir. Mimariye uygun ayrı
bir `decals/` paketi: saf mantık `core/decal*.py`, eylemler `operators/decal*.py`,
arayüz `ui/decal_panel.py`. Decal'ler boolean değil, **shrinkwrap + malzeme**
katmanıdır; mevcut kesim çekirdeğinden bağımsız ilerleyebilir.

### v0.7 — Decal yerleştirme çekirdeği
- [ ] **Decal nesnesi** — yüzeye projekte edilen ince bir düzlem/mesh; hedefe
      `SHRINKWRAP` (PROJECT) + `parent` ile yapışır, yüzey eğrisini takip eder.
- [ ] **Yüzeye yerleştir** — `core/raycast.py` ray_cast ile tıklanan noktaya
      decal'i çağır; normal + yüzey teğetine göre hizala, fareyle döndür/ölçekle.
- [ ] **Decal türleri** — Info (logo/yazı/uyarı), Panel (panel çizgisi/dikiş),
      Subset (maskeli alt-malzeme). Her tür bir malzeme şablonu.
- [ ] **Decal koleksiyonu** — `Hardflow Decals` altında topla, gizle/göster
      (kesici koleksiyonuyla aynı desen — `core/boolean.py stash_cutter` örneği).

### v0.8 — Decal malzeme ve görünüm
- [ ] **PBR malzeme kurulumu** — normal + AO + curvature + emission kanalları,
      alpha ile yüzeye karışım (Eevee + Cycles uyumlu node grupları).
- [ ] **Parallax decal** — height/parallax ile sahte derinlik (panel kanalları).
- [ ] **Decal'i mesh'e bake et** — yüksek-poli detayını hedef normal map'ine
      aktar (yıkıcı "apply"; geri dönüşsüz seçenek).

### v0.9 — Kütüphane ve performans
- [ ] **Decal kütüphanesi** — diskten görüntü/preset yükle, N-panel'de ikon
      grid'i; kullanıcı kütüphanesi klasörü (tercihlerde yol).
- [ ] **Görüntüden decal üret** — PNG/alpha → hazır decal nesnesi + malzeme.
- [ ] **Trim sheet / trim decal** — tek atlas üzerinden UV dilimleri.
- [ ] **Atlasing** — sahnedeki decal'leri tek atlas dokusuna topla (draw-call
      ve malzeme sayısını düşür); oyun-hazır export.

## v1.0+ — Asset/kitbash sistemi (KitOps ruhu)
DECALmachine'den sonra. Hazır parça (INSERT) kütüphanesinden non-destructive
kitbashing: hard-surface detayları boolean/snap ile yüzeye yapıştır. Ayrı bir
`assets/` paketi; mevcut boolean + snap + kesici-koleksiyon çekirdeğini yeniden
kullanır (decal alt sisteminden bağımsız).
- [ ] **INSERT yerleştirme** — kütüphaneden bir parçayı imleç/yüzey normaline
      göre çağır; fareyle döndür/ölçekle (Boxcutter yerleştirme akışına benzer).
- [ ] **Boolean INSERT'ler** — parça otomatik kesici olur (CUT/MAKE), `core/
      boolean.py` + `stash_cutter` ile non-destructive bağlanır.
- [ ] **Asset kütüphanesi** — `.blend`/koleksiyon tabanlı INSERT'ler; N-panel'de
      ikon grid'i + kullanıcı kütüphane klasörü (tercih).
- [ ] **Wrap/Conform INSERT** — eğri yüzeye shrinkwrap ile sarılan parçalar.
- [ ] **Blender Asset Browser entegrasyonu** — INSERT'leri asset olarak işaretle,
      sürükle-bırak; mark-as-asset + katalog.
- [ ] **Material/auto-smooth aktarımı** — yerleştirilen parçaya hedefin gölgeleme
      ayarlarını uygula.

## Bilinen sınırlamalar
- Grid düzlemi bakış yönüne dik (nesne orijininden geçer); henüz nesne
  yüzeyine/dünya eksenlerine hizalı değil (bkz. v0.2 "grid düzlemini döndürme").
- Sadece Object Mode. Edit Mode akışı (`bmesh.from_edit_mesh`) henüz yok.
- Konkav poligonlar çalışır; kendiyle kesişenler bozuk kesici üretir.
- EXACT solver çakışan/ters-normal geometride başarısız olabilir — kesim
      yapmazsa hedefin normallerini düzelt veya kesiciyi biraz kaydır.
