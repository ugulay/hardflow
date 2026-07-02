# Social Media / Share Templates

Copy-paste templates for announcing Hardflow releases and sharing the project.
Replace anything in `{{ ... }}` and attach a GIF or short clip — a 5–15 s screen
recording of **drawing a cut**, **a cable settling onto the scene**, or
**placing a decal/asset** converts far better than a still.

> **Assets to prepare once:** a square logo, a 16:9 hero image, and 2–3 short
> clips (cut, cable gravity settle, vent/radial array). Reuse them across every
> platform below.

---

## 🐦 X / Twitter (≤ 280 chars)

```
Hardflow {{1.21.0}} is out — a FREE, open-source hard-surface modeling toolkit
for Blender 4.2+.

New: freehand curve drawing, cables that settle onto your scene with real
gravity, custom sweep profiles, vent/grill cuts, radial arrays & panel lines.
GPLv3, no price tag.

⬇️ {{repo link}}
#b3d #blender #gamedev #hardsurface
```

### Thread follow-up (optional)

```
What's inside 👇
• Box/Circle/Poly/N-gon/Slot/Star/Arc/Vent → Cut / Slice / Make / Join / Intersect / Face / Knife
• World-scale grid + vertex/edge snap + numeric exact-size entry, Edit Mode
• In-draw inset/array (incl. radial bolt-circle)/mirror/bevel/rotate/stamp + live boolean preview
• Panel lines: selected edges → groove seams or raised weld beads in one click
• Non-destructive cutters + modifier-stack manager
• Build primitives: cube / plane / cylinder / cone / sphere / tube
• Push/Pull, Offset, Object-Mode Edge Bevel + Loop Cut, construction grid, loft
• Pipe / cable / Follow-Me sweep — freehand strokes, Smooth Path (editable
  Bezier), a gravity-settling cable with scene collision, CUSTOM cross-sections,
  and Detail Along Path (chains, clips, hoses)
• Full decal pipeline + bake + atlasing + create/match
• Heightmap decals: dedicated height map → parallax occlusion + normal relief
• Trim-sheet UV editor + background removal (chroma-key a green screen to alpha)
• Kitbash INSERT assets w/ live preview, auto-scale, asset-pack export
• Super Modeling Mode: SketchUp-fluid Ghost-Grid shell + atomic per-session undo,
  with draw-to-cut Cut / Add / Slice / Intersect verbs
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
hard-surface loop — draw-to-cut booleans, precision snapping, direct modeling,
curves, decals, and kitbash assets — in a single add-on.

{{GIF/clip — drawing a cut, a cable settling onto the scene, or a vent + radial array}}

### ✂️ Boolean workflow

- **Draw-to-cut** — Box / Circle / Polygon / N-gon / Slot / Star / Arc /
  **Vent (grill)** shapes, with Cut / Slice / Make / Join / Intersect / Face /
  Knife modes — in Object **and** Edit Mode.
- **Precision** — world-scale (meter) grid snap, vertex/edge snap, angle lock,
  a rotatable drawing plane, live grid density, and **numeric exact-size entry**
  (type a dimension to lock the shape's size).
- **In-draw ops** — inset, array (linear or **radial bolt-circle**), mirror,
  bevel-on-cut, in-plane rotation, and stamp/repeat, all while drawing — plus a
  **live boolean preview** of the real result before you commit
  (high-poly-friendly: it culls non-intersecting targets and skips idle frames).
- **Panel lines** — select edges, get a recessed **groove** seam or a raised
  **weld bead** in one click; open strips, closed loops, and T/X junctions all
  resolve cleanly — destructively or as live cutters.
- **Non-destructive** — live cutters in their own collection + a modifier-stack
  manager; bake when ready.

### 🧱 Modeling

- **Build & direct modeling** — cube / plane / cylinder / cone / sphere / tube
  primitives, Push/Pull, Offset, Object-Mode Edge Bevel + Loop Cut, a
  construction grid, guides, and loft/bridge.
- **Super Modeling Mode** — a SketchUp-fluid shell that shadows the native
  tools on its own Ghost-Grid snap chain (VIEW/SURFACE/X/Y/Z plane cycle,
  `Tab` cycles Knife → Extrude → Cut / Add / Slice / Intersect draw-to-cut
  booleans), with a per-tool undo journal: a whole tool session commits as
  **one** atomic Blender undo step.
- **Smart Bevel** — drops support/holding loops so the edge survives
  Subdivision; topology-safe on irregular post-boolean n-gons and validated
  against a live Subdivision pass (the loop pins the flat, fillet radius ≈ the
  bevel width).

### ➰ Curves & sweeps

- **Freehand drawing** — stroke a pipe/cable/sweep path (or click it point by
  point); the ink hugs the surface and reduces to clean anchors on release, and
  `C` smooths it into a Catmull-Rom spline that commits as an **editable
  Bezier**.
- **Cable gravity settle** — the rope relaxes with **real scene collision**, so
  it drapes over obstacles and rests on your geometry.
- **Custom profiles & details** — sweep **CUSTOM cross-sections** from a mesh
  outline or a curve bevel-object, and **Detail Along Path** repeats a detail
  mesh along the curve (chain links, cable clips, corrugated hoses).

### 🎨 Decals & trim sheets

- **Full decal pipeline** — placement, PBR material, bake, image library,
  atlasing, create/match/retrim/conform + an editable library.
- **Trim-sheet UV editor** — carve a sheet into free named rectangles right in
  the viewport, with **background removal** (chroma-key a flat/green-screen
  background to transparency).
- **Heightmap decals** — a **dedicated grayscale height map** (or the color's
  own luminance) drives depth independently of the albedo: **Parallax Occlusion
  Mapping** (recessed lines slide behind their lip at grazing angles) plus a
  **normal-relief bump** for real shaded depth, with an invert-polarity toggle.

### 📦 Kitbash assets

- **INSERTs** from a .blend library with a live preview, auto-scale,
  insert-grid snap, material inserts, and asset-pack export.

---

The pure-logic core is unit-tested (144/144, no Blender needed), every bpy path
is verified headless in Blender 5.1.2 (142 tests), and the modal tools'
interactive feel goes through a manual checklist — so bug reports are very
welcome.

**Repo / install:** {{repo link}}

Hardflow is and stays free — it's GPLv3, and the architecture is built so
features stay isolated, so feedback and contributions are welcome. If it
replaces a paid add-on for you, there's a Patreon to support development:
https://www.patreon.com/ugurgulay
```

---

## 🎨 BlenderArtists forum

**Title:** `Hardflow — free open-source hard-surface boolean toolkit (v{{1.21.0}})`

**Body:** same as the Reddit body above. BlenderArtists supports embedded video —
lead with a GIF/clip and put the install link near the top.

---

## 💼 LinkedIn

```
Excited to share Hardflow {{1.21.0}} — a free, open-source hard-surface modeling
toolkit for Blender 4.2+. 🛠️

One GPLv3 add-on for the whole loop: draw-to-cut booleans (now with vent/grill
cuts and radial bolt-circle arrays), panel lines from an edge selection,
freehand-drawn pipes with gravity-settling cables and custom sweep profiles,
direct modeling (Push/Pull, Offset, edge tools), a full decal pipeline (heightmap
parallax + normal relief), kitbash INSERT assets, and a SketchUp-fluid "Super
Modeling Mode" with a Subdivision-safe Smart Bevel and atomic per-session undo —
no license fee.

Built with a strict, testable architecture (pure logic separated from Blender's
API, 144/144 unit tests green). Open to contributors and feedback — and there's
a Patreon for anyone who wants to support development:
https://www.patreon.com/ugurgulay

⬇️ {{repo link}}

#Blender #3D #GameDev #OpenSource #HardSurface #IndieDev
```

---

## 🐘 Mastodon (≤ 500 chars)

```
Hardflow {{1.21.0}} 🚀 — free & open-source (GPLv3) hard-surface boolean toolkit
for #Blender 4.2+.

New: freehand curve drawing, cables that settle onto the scene with real
gravity, custom sweep profiles, vent/grill cuts, radial arrays & panel lines —
no price tag.

⬇️ {{repo link}}
#b3d #blender #gamedev #opensource #3D
```

---

## 📝 GitHub Release notes (template)

> The release workflow auto-fills the release body from the matching
> `CHANGELOG.md` section when a `v*` tag is pushed. Use this template when
> hand-editing a release for a bigger launch.

```
## Hardflow v{{1.21.0}}

The Curves upgrade — Pipe/Cable/Sweep grow from click-by-click placement into a
drawing/physics toolset.

### Highlights
- **Freehand curve drawing** — click *or* stroke-draw the path; the ink hugs the
  surface and reduces to clean anchors on release. `C` smooths the path into a
  Catmull-Rom spline, and a ROUND pipe commits an **editable Bezier**.
- **Cable gravity settle** — `G` relaxes the rope as an anchor-pinned particle
  chain with real scene collision: it **drapes over obstacles and rests on your
  geometry** (deterministic, no timeline). Shift+Wheel feeds slack.
- **CUSTOM cross-sections** — sweep a flat mesh's boundary outline, or ride a
  curve object as a native non-destructive bevel profile.
- **Detail Along Path** — repeat a detail mesh along the active curve (chain
  links, cable clips, corrugated hoses).

Pure core: 144/144. Headless (Blender 5.1.2): 142/142.

### Install
Blender 4.2+: Edit → Preferences → Get Extensions → ⌄ → Install from Disk →
select the hardflow zip.

### Support
Hardflow is free (GPLv3). If it's useful to you, you can support development on
Patreon: https://www.patreon.com/ugurgulay

**Full changelog:** see CHANGELOG.md
```

---

## ✅ Launch checklist

- [ ] Tag the release — pushing a `v*` tag builds the zip and publishes the
      GitHub Release automatically (`.github/workflows/release.yml`)
- [ ] Polish the release notes for a launch (template above, Patreon link at the end)
- [ ] Record fresh clips (cut, vent + radial array, cable gravity settle, panel
      lines, Smart Bevel + Subdivision)
- [ ] Post to X, Reddit, BlenderArtists, LinkedIn, Mastodon
- [ ] Pin the announcement in GitHub Discussions
- [ ] (Optional) Submit / update on the Blender Extensions Platform
