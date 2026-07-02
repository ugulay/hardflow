# Social Media / Share Templates

Copy-paste templates for announcing Hardflow releases and sharing the project.
Replace anything in `{{ ... }}` and attach a GIF or short clip — a 5–15 s screen
recording of **drawing a cut**, **Push/Pull**, or **placing a decal/asset**
converts far better than a still.

> **Assets to prepare once:** a square logo, a 16:9 hero image, and 2–3 short
> clips (cut, Push/Pull, decal/asset). Reuse them across every platform below.

---

## 🐦 X / Twitter (≤ 280 chars)

```
Hardflow {{1.19.0}} is out — a FREE, open-source hard-surface boolean modeling
toolkit for Blender 4.2+.

New: Smart Bevel now drops support loops that survive Subdivision — validated
against a live subdivision pass. Plus heightmap decals, draw-to-cut booleans,
snapping, kitbash assets & sweeps. GPLv3.

⬇️ {{repo link}}
#b3d #blender #gamedev #hardsurface
```

### Thread follow-up (optional)

```
What's inside 👇
• Box/Circle/Poly/N-gon/Slot/Star/Arc → Cut / Slice / Make / Join / Intersect / Face / Knife
• World-scale grid + vertex/edge snap + numeric exact-size entry, Edit Mode
• In-draw inset/array/mirror/bevel/rotate/stamp + live boolean preview
• Non-destructive cutters + modifier-stack manager
• Build primitives: cube / plane / cylinder / cone / sphere / tube
• Push/Pull, Offset, Object-Mode Edge Bevel + Loop Cut, construction grid, loft
• Pipe / cable / Follow-Me sweep (L/U/T/I/box sections)
• Full decal pipeline + bake + atlasing + create/match
• Heightmap decals: dedicated height map → parallax occlusion + normal relief
• Trim-sheet UV editor + background removal (chroma-key a green screen to alpha)
• Kitbash INSERT assets w/ live preview, auto-scale, asset-pack export
• Super Modeling Mode: SketchUp-fluid Ghost-Grid shell + atomic per-session undo,
  now with draw-to-cut Cut / Add / Slice / Intersect verbs
• Smart Bevel: support loops that survive Subdivision — validated, fillet ≈ bevel width
```

---

## 👽 Reddit (r/blender, r/blenderhelp, r/gamedev)

**Title:**
```
I built Hardflow — a free, open-source hard-surface boolean toolkit for Blender (GPLv3)
```

**Body:**
```
Hardflow is one free GPLv3 extension for Blender 4.2+ covering the whole
hard-surface loop:

- **Draw-to-cut booleans** — Box / Circle / Polygon / N-gon / Slot / Star / Arc,
  with Cut / Slice / Make / Join / Intersect / Face / Knife modes — in Object
  **and** Edit Mode.
- **Precision** — world-scale (meter) grid snap, vertex/edge snap, angle lock,
  rotatable drawing plane, live grid density, and **numeric exact-size entry**
  (type a dimension to lock the shape's size).
- **In-draw ops** — inset, array, mirror, bevel-on-cut, in-plane rotation, and
  stamp/repeat, all while drawing, plus a **live boolean preview** of the real
  result before you commit (now high-poly-friendly — it culls non-intersecting
  targets and skips idle frames).
- **Non-destructive** — live cutters in their own collection + a modifier-stack
  manager; bake when ready.
- **Build & direct modeling** — cube / plane / cylinder / cone / sphere / tube
  primitives, Push/Pull, Offset, Object-Mode Edge Bevel + Loop Cut, a
  construction grid, guides, and loft/bridge.
- **Super Modeling Mode** — a streamlined SketchUp-fluid shell that shadows the
  native tools on its own Ghost-Grid snap chain (VIEW/SURFACE/X/Y/Z plane cycle,
  `Tab` cycles Knife → Extrude → **Cut / Add / Slice / Intersect** draw-to-cut
  booleans), with a per-tool undo journal so a whole tool session commits as
  **one** atomic Blender undo step.
- **Smart Bevel** — a hard-surface bevel that drops support/holding loops so the
  edge survives Subdivision, topology-safe on irregular post-boolean n-gons and
  validated against a live Subdivision pass (the loop pins the flat, fillet radius
  ≈ the bevel width).
- **Curves & sweeps** — surface-draping pipe (round/square/rect), sagging cable,
  and a Follow-Me sweep that runs an L/U/T/I/box section along a drawn path.
- **Decals & trim sheets** — place, PBR material, bake, image library, a
  free-rectangle **trim-sheet UV editor** with **background removal** (chroma-key
  a flat/green-screen background to transparency), atlasing, plus
  create/match/retrim/conform + an editable library.
- **Heightmap decals** — an image decal can carry a **dedicated grayscale height
  map** (or use the color's own luminance) that drives depth independently of the
  albedo: it feeds both **Parallax Occlusion Mapping** (recessed panel lines slide
  behind their lip at grazing angles) and a **normal-relief Bump** for real shaded
  depth, with an invert-polarity toggle.
- **Kitbash assets** — INSERTs from a .blend library with a live preview,
  auto-scale, insert-grid snap, material inserts, and asset-pack export.

The pure-logic core is unit-tested (124/124, no Blender needed) and every bpy path
is verified headless in Blender 5.1.2 (135 tests); the modal tools' interactive
feel is checked via a manual checklist, so bug reports are very welcome.

Repo / install: {{repo link}}

Feedback and contributions welcome — it's GPLv3 and the architecture is built so
features stay isolated.
```

---

## 🎨 BlenderArtists forum

**Title:** `Hardflow — free open-source hard-surface boolean toolkit (v{{1.19.0}})`

**Body:** same as the Reddit body above. BlenderArtists supports embedded video —
lead with a GIF/clip and put the install link near the top.

---

## 💼 LinkedIn

```
Excited to share Hardflow {{1.19.0}} — a free, open-source hard-surface modeling
toolkit for Blender 4.2+. 🛠️

One GPLv3 add-on for the whole loop: draw-to-cut booleans, world-scale snapping,
direct modeling (Push/Pull, Offset, edge tools), profile sweeps, a full decal
pipeline (now with heightmap decals — parallax + normal relief), kitbash INSERT
assets, and a SketchUp-fluid "Super Modeling Mode" with a Subdivision-safe Smart
Bevel and atomic per-session undo — no license fee.

Built with a strict, testable architecture (pure logic separated from Blender's
API, 124/124 unit tests green). Open to contributors and feedback.

⬇️ {{repo link}}

#Blender #3D #GameDev #OpenSource #HardSurface #IndieDev
```

---

## 🐘 Mastodon (≤ 500 chars)

```
Hardflow {{1.19.0}} 🚀 — free & open-source (GPLv3) hard-surface boolean toolkit
for #Blender 4.2+.

New: Smart Bevel that survives Subdivision — validated. Plus heightmap decals
(parallax + relief), draw-to-cut booleans, world-scale snapping, kitbash assets,
and profile sweeps — no price tag.

⬇️ {{repo link}}
#b3d #blender #gamedev #opensource #3D
```

---

## 📝 GitHub Release notes (template)

```
## Hardflow v{{1.19.0}}

Smart Bevel, validated — the hard-surface bevel that drops support/holding loops so
the edge survives Subdivision is now measured against a live Subdivision pass and
de-experimentalised.

### Highlights
- **Validated support-loop placement** — a headless Blender 5.1.2 probe bevels a
  cube edge, adds a Catmull-Clark Subdivision modifier, and circle-fits the corner
  cross-section: the holding loop pins the flanking flat near the bevel and the
  subdivided fillet stays crisp at radius ≈ the bevel width. Smart Bevel is no
  longer labelled experimental (the `S` toggle stays the opt-in).
- **"Expected radius" HUD readout** — in Smart mode the Edge Bevel HUD shows `~r=…`,
  the fillet radius the bevel will settle to under Subdivision, so you see the
  outcome while you drag (`core/bevel.beveled_fillet_radius` ≈ width × (1 + 0.3/segments)).
- **Honest fillet-radius model** — the pure `subdiv_fillet_radius` /
  `support_offset_for_radius` pair is now documented as the distinct *lone-loop-
  against-a-sharp-edge* case (radius ≈ offset), separate from a beveled fillet whose
  radius is set by the width.

Pure core: 124/124. Headless (Blender 5.1.2): 135/135.

### Install
Blender 4.2+: Edit → Preferences → Get Extensions → ⌄ → Install from Disk →
select the hardflow zip.

**Full changelog:** see CHANGELOG.md
```

---

## ✅ Launch checklist

- [ ] Tag the release and write GitHub Release notes (template above)
- [ ] Attach the built `hardflow-{{1.19.0}}.zip` to the release
- [ ] Record fresh clips (cut, Push/Pull, decal/asset, sweep, Smart Bevel + Subdivision)
- [ ] Post to X, Reddit, BlenderArtists, LinkedIn, Mastodon
- [ ] Pin the announcement in GitHub Discussions
- [ ] (Optional) Submit / update on the Blender Extensions Platform
```
