# Changelog

Bu projedeki dikkate değer değişiklikler. Sürümleme [SemVer](https://semver.org)
mantığında; proje 1.0 öncesi olduğundan minor sürümler özellik ekler.

## [Unreleased]

### Eklendi
- **Dünya-ölçekli grid snap** — snap artık ekran-piksel yerine projeksiyon
  düzleminin yerel (u,v) metre ekseninde; kameradan/zoom'dan bağımsız tutarlı
  grid. Tercih: `grid_world` (metre).
- **Vertex / edge snap** — çizim noktasını mevcut geometrinin köşe / kenar /
  kenar-ortasına kilitle; renkli imleç (🟡 köşe, 🟢 orta, 🔵 kenar). `V` ile
  toggle; `geo_snap` + `snap_pixels` tercihleri. Yoğun mesh'te otomatik kapanır.
- **Açı kilidi** — Shift basılıyken çizim yönü açı kademesine kilitlenir
  (`angle_step`, varsayılan 15°).
- **Non-destructive mod** — boolean'ı uygulamak yerine canlı modifier bırakır;
  kesiciler "Hardflow Cutters" koleksiyonunda (wire, render kapalı, hedefe
  parent) saklanır. `N` ile toggle; `non_destructive` tercihi.
- **N-panel** — View3D kenar çubuğunda araçlar, snap ayarları ve saklı kesici
  listesi.
- **Kendiyle-kesişme tespiti** — bozuk poligon kesim öncesi reddedilir.
- **Grid düzlemini döndürme** — `←/→` ile düzlem VIEW / dünya X / Y / Z; kesici
  düzlem normali boyunca extrude (`ray_to_plane`).
- **Create Face modu** — çizim aracında `4` tuşu: çizilen şekilden tek n-gen
  yüzey nesnesi (boolean değil).
- **Kesici yönetimi** — N-panel'den kesici seç/sil + "Kesicileri Uygula (Bake)"
  (`operators/cutters.py`).
- **Clean operatörü** — remove doubles + coplanar birleştirme + başıboş silme
  (Hard Ops "clean"); ayrıca `cleanup_after_cut` ile kesim sonrası otomatik.
- **Pipe aracı** — çizilen çizgiden yuvarlak kesitli boru (`HARDFLOW_OT_pipe`,
  `pipe_radius`).
- **Gelişmiş bevel** — interaktif modal (sürükle=genişlik, tekerlek=segment),
  profil + açı limiti + width-type ve **Weighted Normal** modifier (temiz
  hard-surface gölgeleme).
- **Çoklu nesne** — `multi_object`: CUT/MAKE seçili tüm mesh'lere uygulanır.
- **HUD ölçü göstergesi** — çizim sırasında metre cinsinden boyut.
- **Test paketi** — `tests/test_core.py` (11, bpy'siz) + `tests/test_blender.py`
  (headless: build_prism/boolean/cutters/clean/pipe/face/multi-object).
- **ROADMAP** — DECALmachine tarzı decal alt sistemi (v0.7–v0.9) eklendi.

### Düzeltildi
- Bevel: Blender 4.1+'da kaldırılan `Mesh.use_auto_smooth` çağrısı (operatör
  çöküyordu) kaldırıldı; smooth shading ile değiştirildi.
- GPU çizim: `UNIFORM_COLOR` shader'ına vec3 (z=0) beslenmesi sağlandı.
- Kesici nesneler boolean başarısız olsa bile `try/finally` ile temizleniyor.
- Pie menü kısayolu `Alt+D` → `Alt+Q` (Alt+D Object Mode'da Duplicate Linked
  ile çakışıyordu).
- POLY commit'inde gezinen imleç artık fazladan vertex olarak eklenmiyor.

## [0.1.0]
- İlk modüler mimari: modal çizim operatörü (Box/Circle/Polygon),
  Cut/Slice/Make modları, ekran-uzayı grid snap, akıllı bevel + mirror,
  pie menu, tercihler, keymap.
