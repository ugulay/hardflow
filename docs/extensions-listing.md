# extensions.blender.org — Listing Content

Everything to paste into the Blender Extensions upload form, plus the generated
images. Regenerate the images any time with:

```
"F:\...\blender.exe" --background --factory-startup --python promo/render_listing_images.py
```

(add `-- --only featured|shapes|radial|curves|icon` to re-render one image).
Outputs land in `promo/out/`.

---

## 1. Release notes (the "Release notes" box, Markdown)

```markdown
Initial release on Blender Extensions — **Hardflow 1.21.0**.

Hardflow covers the whole hard-surface loop in one free, GPLv3 add-on:

**Boolean workflow**
- Draw-to-cut booleans: Box / Circle / Polygon / N-gon / Slot / Star / Arc /
  Vent (grill) shapes × Cut / Slice / Make / Join / Intersect / Knife modes,
  in Object and Edit Mode
- Live boolean preview before you commit (high-poly friendly), non-destructive
  cutters + a modifier-stack manager
- In-draw inset, linear and radial (bolt-circle) arrays, mirror, bevel-on-cut,
  rotation and stamp — all while drawing
- Precision: world-scale grid, vertex/edge snapping, angle lock, numeric
  exact-size entry
- Panel Lines: selected edges become recessed groove seams or raised weld beads

**Modeling**
- Push/Pull, Offset (recess / raised panel), Object-Mode Edge Bevel + Loop Cut,
  build primitives, construction grid + guides, loft
- Smart Bevel with subdivision-safe support loops, Smart Sharpen, boolean
  shading fixes, automatic modifier-stack sorting
- Super Modeling Mode: a SketchUp-style shell with draw-to-cut Knife / Extrude /
  Cut / Add / Slice / Intersect verbs — one tool session commits as one undo step

**Curves**
- Pipes, cables and Follow-Me sweeps with freehand stroke drawing and Smooth
  Path (commits an editable Bezier)
- Cable gravity settle with real scene collision — the rope drapes over your
  geometry
- Custom sweep cross-sections and Detail Along Path (chains, clips, hoses)

**Decals & assets**
- Full decal pipeline: placement, PBR material, bake, image library,
  create/match/retrim/conform
- Trim-sheet UV editor with chroma-key background removal; decal atlasing
- Heightmap decals: parallax occlusion + normal relief from a dedicated
  grayscale height map
- Kitbash INSERT assets with auto-scale, boolean INSERTs and asset-pack export

UI in English and Turkish. Manual, roadmap and source:
https://github.com/ugulay/hardflow
```

---

## 2. Listing description (the main "Description" field, Markdown)

```markdown
**Hardflow is one free, open-source (GPLv3) add-on that covers the whole
hard-surface loop** — draw-to-cut booleans, precision snapping, direct
modeling, curves, decals and kitbash assets — with no paid tiers.

## Boolean workflow
- **Draw-to-cut** — Box / Circle / Polygon / N-gon / Slot / Star / Arc /
  **Vent (grill)** shapes, with Cut / Slice / Make / Join / Intersect / Knife
  modes, in Object **and** Edit Mode.
- **Live boolean preview** of the real result before you commit —
  high-poly friendly (it culls non-intersecting targets and skips idle frames).
- **In-draw operations** — inset, array (linear or **radial bolt-circle**),
  mirror, bevel-on-cut, in-plane rotation and stamp/repeat, all while drawing.
- **Precision** — world-scale (meter) grid snap, vertex/edge snap, angle lock,
  a rotatable drawing plane, live grid density and **numeric exact-size entry**.
- **Panel Lines** — select edges, get a recessed groove seam or a raised weld
  bead in one click; open strips, closed loops and T/X junctions all resolve.
- **Non-destructive** — live cutters in their own collection, cutter scroll,
  extract-cutter, and a modifier-stack manager with smart auto-sorting.

## Modeling
- **Direct modeling** — Push/Pull, Offset (recess / raised panel), Object-Mode
  Edge Bevel + Loop Cut, build primitives, construction grid, guides, loft.
- **Smart Bevel** — support loops that survive Subdivision, safe on the n-gons
  booleans leave behind; plus Smart Sharpen and one-click boolean shading fixes.
- **Super Modeling Mode** — a SketchUp-style shell: draw footprints and Knife /
  Extrude / Cut / Add / Slice / Intersect them, with one atomic undo step per
  tool session.

## Curves
- **Pipes, cables, sweeps** — freehand stroke or click-by-click, Smooth Path
  (commits an editable Bezier), L/U/T/I/box or **custom cross-sections**.
- **Cable gravity settle** — the rope relaxes with real scene collision and
  drapes over your geometry.
- **Detail Along Path** — repeat a detail mesh along a curve (chain links,
  cable clips, corrugated hoses).

## Decals & assets
- Full decal pipeline: placement, PBR material, bake, library, atlasing,
  create/match/retrim/conform.
- **Trim-sheet UV editor** in the viewport, with chroma-key background removal.
- **Heightmap decals**: parallax occlusion + normal relief from a dedicated
  height map.
- Kitbash **INSERT** assets: auto-scale placement, boolean INSERTs, material
  INSERTs, asset-pack export.

UI in English and Turkish (tr_TR). GPLv3 — free forever, contributions
welcome: https://github.com/ugulay/hardflow
```

---

## 3. Icon

Upload `promo/out/icon_256.png` — 256 × 256 PNG, transparent background
(a chamfered dark block with a corner notch and a glowing boolean bore).

## 4. Featured image

Upload `promo/out/featured_1920x1080.png` — 1920 × 1080 PNG, 16:9
(required for approval submission).

## 5. Preview slots (image + description per slot)

| # | File | Description to paste |
|---|------|----------------------|
| 1 | `promo/out/featured_1920x1080.png` (or a UI screenshot) | One free GPLv3 toolkit for the whole hard-surface loop — booleans, snapping, curves, decals. |
| 2 | `promo/out/preview_1_shapes.png` | Draw-to-cut booleans: Box, Circle, N-gon, Slot, Star, Arc and Vent shapes with world-scale snapping. |
| 3 | `promo/out/preview_2_radial_vent.png` | In-draw operations: radial bolt-circle arrays, vent grills and panel-line grooves. |
| 4 | `promo/out/preview_3_curves.png` | Pipes, sweeps and cables with real gravity settle — the rope drapes over scene geometry. |

At least one preview is required; the order above tells the story
(hero → shapes → in-draw ops → curves).

**Strongly recommended extras** (converts better than stills — the form also
accepts MP4):

- a 10–20 s screen capture of **drawing a cut** (shape → live preview → commit),
- the **cable gravity settle** (`G`) landing on scene geometry,
- a **vent + radial array** drawn in one go.

Keep clips 16:9 (1920×1080), no music needed. Suggested slot descriptions:
"Draw a shape, watch the live boolean preview, commit — all snapped to the
world grid." / "Cable gravity settle: the rope collides with and rests on your
scene."

Real viewport screenshots (N-panel open + the framed HUD visible) also make
good preview slots — grab them while running `tests/manual_checklist.md`.

---

## 6. Other form fields (for reference)

- **Tagline** (from `blender_manifest.toml`): "Open source hard surface
  boolean modeling toolkit" (64-char limit on the site).
- **Website**: https://github.com/ugulay/hardflow
- **Tags**: Modeling, Mesh, Object (already in the manifest).
- **License**: GPL-3.0-or-later (already in the manifest).
