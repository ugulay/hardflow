# Social Media / Share Templates

Copy-paste templates for announcing Hardflow releases and sharing the project.
Replace anything in `{{ ... }}` and attach a GIF or short clip — a 5–15 s screen
recording of **drawing a cut**, **Push/Pull**, or **placing a decal/asset**
converts far better than a still.

> **Assets to prepare once:** a square logo, a 16:9 hero image, and 2–3 short
> clips (cut, bevel, decal/asset). Reuse them across every platform below.

---

## 🐦 X / Twitter (≤ 280 chars)

```
Hardflow {{1.2.0}} is out — a FREE, open-source hard-surface boolean modeling
toolkit for Blender 4.2+.

Draw-to-cut booleans, world-scale snapping, decals, kitbash assets &
SketchUp-style Push/Pull — no price tag. GPLv3.

⬇️ {{repo link}}
#b3d #blender #gamedev #hardsurface
```

### Thread follow-up (optional)

```
What's inside 👇
• Box/Circle/Poly/N-gon → Cut / Slice / Make / Face
• World-scale grid + vertex/edge snap
• Non-destructive cutters (Boxcutter spirit)
• Bevel/Mirror/Array/Radial/Symmetrize/Sharpen (Hard Ops)
• Full decal pipeline + bake + atlasing (DECALmachine)
• KitOps-style INSERT assets w/ live preview
• Push/Pull, Offset, Construction grid (SketchUp)
```

---

## 👽 Reddit (r/blender, r/blenderhelp, r/gamedev)

**Title:**
```
I built Hardflow — a free, open-source hard-surface boolean toolkit for Blender
(Grid Modeler + Boxcutter + Hard Ops + DECALmachine + KitOps, GPLv3)
```

**Body:**
```
Hardflow brings the core workflows of the big paid hard-surface add-ons into one
free GPLv3 extension for Blender 4.2+:

- **Draw-to-cut booleans** — Box / Circle / Polygon / N-gon, with Cut / Slice /
  Make / Face modes.
- **Precision** — world-scale (meter) grid snap, vertex/edge snap, angle lock,
  rotatable drawing plane.
- **Non-destructive** — keep live cutters in their own collection; bake when ready.
- **Hard Ops tools** — interactive bevel, mirror, array, radial array,
  symmetrize, sharpen.
- **Decals** — DECALmachine-style: place, PBR material, parallax, bake, image
  library, trim sheets, atlasing.
- **Kitbash assets** — KitOps-style INSERTs from a .blend library, with a live
  preview of the real object before you click.
- **SketchUp-style** — Push/Pull, Offset, and a construction-grid reference object.

The pure-logic core is unit-tested (44/44, no Blender needed); live in-Blender
verification is ongoing, so bug reports are very welcome.

Repo / install: {{repo link}}

Feedback and contributions welcome — it's GPLv3 and the architecture is built so
features stay isolated.
```

---

## 🎨 BlenderArtists forum

**Title:** `Hardflow — free open-source hard-surface boolean toolkit (v{{1.2.0}})`

**Body:** same as the Reddit body above. BlenderArtists supports embedded video —
lead with a GIF/clip and put the install link near the top.

---

## 💼 LinkedIn

```
Excited to share Hardflow {{1.2.0}} — a free, open-source hard-surface modeling
toolkit for Blender 4.2+. 🛠️

It bundles the core workflows of Grid Modeler, Boxcutter, Hard Ops, DECALmachine,
and KitOps into one GPLv3 add-on: draw-to-cut booleans, world-scale snapping, a
full decal pipeline, KitOps-style kitbash assets, and SketchUp-style Push/Pull —
no license fee.

Built with a strict, testable architecture (pure logic separated from Blender's
API, 44/44 unit tests green). Open to contributors and feedback.

⬇️ {{repo link}}

#Blender #3D #GameDev #OpenSource #HardSurface #IndieDev
```

---

## 🐘 Mastodon (≤ 500 chars)

```
Hardflow {{1.2.0}} 🚀 — free & open-source (GPLv3) hard-surface boolean toolkit
for #Blender 4.2+.

Draw-to-cut booleans, world-scale snapping, decals, kitbash assets, and
SketchUp-style Push/Pull — all without a price tag.

⬇️ {{repo link}}
#b3d #blender #gamedev #opensource #3D
```

---

## 📝 GitHub Release notes (template)

```
## Hardflow v{{1.2.0}}

{{One-line summary of the milestone.}}

### Highlights
- {{feature}}
- {{feature}}

### Install
Blender 4.2+: Edit → Preferences → Get Extensions → ⌄ → Install from Disk →
select the hardflow zip.

**Full changelog:** see CHANGELOG.md
```

---

## ✅ Launch checklist

- [ ] Tag the release and write GitHub Release notes (template above)
- [ ] Attach the built `hardflow-{{1.2.0}}.zip` to the release
- [ ] Record fresh clips (cut, bevel, decal/asset, Push/Pull)
- [ ] Post to X, Reddit, BlenderArtists, LinkedIn, Mastodon
- [ ] Pin the announcement in GitHub Discussions
- [ ] (Optional) Submit / update on the Blender Extensions Platform
