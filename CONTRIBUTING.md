# Katkı Rehberi

## Kurulum (geliştirme)

Hızlı döngü için eklentiyi sembolik link ile Blender'ın extensions klasörüne
bağla, böylece her değişiklikte yeniden zip'lemen gerekmez:

```bash
# Linux/macOS örneği — yolu kendi sürümüne göre düzelt
ln -s "$(pwd)/hardflow" \
  ~/.config/blender/4.2/extensions/user_default/hardflow
```

Blender içinde tekrar yüklemek için: System Console açıkken
`F3 > Reload Scripts` ya da eklentiyi kapat/aç.

## Mimari kuralları

1. **Katman yönü tek yönlü:** `ui` ve `operators` → `core`. `core` asla yukarı
   bağımlı olmaz ve `bpy.ops`/`gpu`/`blf` kullanmaz (boolean.py'deki tek
   `modifier_apply` istisnası hariç). Bu sayede `core` saf ve test edilebilir
   kalır.
2. **Bir özellik = core'da saf fonksiyon + ince operator.** Mantığı operatöre
   gömme.
3. **Yeni sınıfı `__init__.py`'deki `_classes`'a ekle.** Aksi halde kayıt
   edilmez.
4. **API uyumu:** Hedef Blender 4.2 LTS+. 3.x'e özgü çağrılardan kaçın
   (`2D_UNIFORM_COLOR`, `blf.size`'ın eski dpi imzası, `LINE_LOOP` primitifi).

## PR akışı

- Tek bir özellik/düzeltme = tek PR.
- ROADMAP.md'deki bir maddeye denk geliyorsa kutucuğu işaretle.
- Yeni bir kullanıcı eylemi eklediysen README'deki tuş tablosunu güncelle.

## Stil

- PEP 8, ~90 karakter satır.
- Operator/sınıf adları `HARDFLOW_OT_*`, `HARDFLOW_MT_*` deseninde.
- Yorumlar Türkçe ya da İngilizce olabilir; tutarlı ol.
