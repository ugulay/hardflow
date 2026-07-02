# Recording Hardflow GIFs

A repeatable recipe for the README/docs demo GIFs — a consistent scene, a
shot list, and a Windows capture → optimized-GIF pipeline.

> Hardflow's tools are **interactive modal** operators (you drag the mouse and
> the HUD updates live). There is no headless way to render them — the value is
> the gesture itself, so these are real screen recordings. This guide makes them
> fast to shoot and consistent.

## 1. Set up the scene

Open a fresh `.blend`, then run [`docs/demo_scene.py`](demo_scene.py):

- **Text Editor ▸ Open ▸ `docs/demo_scene.py` ▸ Run Script** (or `F3` ▸
  "Run Script").

It drops a beveled plate (the cut/push-pull/decal surface), a small plate, and
a cylinder into an **"HF Demo"** collection, selects the main plate, and frames
+ shades the viewport (3/4 perspective, MATCAP + cavity — the hard-surface look).
Re-run it any time to reset between takes; it only clears its own collection.

Before recording:

- Open the **N-panel ▸ Hardflow** tab so the panel + HUD are both in frame.
- **Window ▸ Toggle System Console** off-screen (so a stray error is visible to
  you but not the recording).
- Set the UI scale you want (Preferences ▸ Interface ▸ Resolution Scale) — record
  at the scale the final GIF should read at.
- Keep the mouse cursor **visible** in the capture (it's a tool demo — viewers
  need to see the gesture).

## 2. Shot list

Keep each clip **2–6 s**, one idea per GIF, and end on the result so it loops
cleanly. Keys below match the defaults (see the README key table).

| # | Clip | Setup | Gesture | Notes |
|---|------|-------|---------|-------|
| 1 | **Draw-to-cut (hero)** | Plate selected | `Ctrl+Shift+D` → `Q` (Box) → click, drag, click → cut appears | The money shot. Consider pressing `J` first to show the live boolean preview. |
| 2 | **Mode cycle** | mid-draw | Draw a box, `Tab` through Cut → Slice → Make → Intersect → Knife | Show the HUD label changing. |
| 3 | **Shape montage** | Plate | `W` Circle · `R` N-gon · `T` Slot · `Y` Star · `U` Arc, one cut each | Fast cuts back-to-back. |
| 4 | **Numeric size** | mid-draw | Start a box, type `0.5`, Enter | Show the exact-size lock. |
| 5 | **Push/Pull** | Plate | Pie `Alt+Q` → Push/Pull → hover face, drag out, click | Show the distance readout at the cursor. `C` to copy/stack. |
| 6 | **Offset → recess** | Plate | Offset tool → drag inset → `E` → drag depth | The instant panel/recess. |
| 7 | **Edge Bevel + Smart** | Plate | Edge Bevel → drag width, `[ ]` segments, `S` Smart Bevel | Show the `+N loops` HUD readout. |
| 8 | **Loop Cut** | Plate | Loop Cut → hover edge, `[ ]` count, drag to slide | Object-mode, no Edit Mode. |
| 9 | **HardFlow Mode** | Plate | `Ctrl+Shift+X` → click points → `Tab` verb cycle (Knife → Extrude → Cut) | Show the framed HUD + plane guides. |
| 10 | **Pipe / Sweep** | Plate | Pipe over the surface, `P` to cycle round/square, or Sweep an L/I section | Surface-draping curve. |
| 11 | **Decal** | Plate | Decals ▸ Panel → hover, wheel to scale, `[ ]` roll, click | Show the live preview under the cursor. |
| 12 | **Pie menu** | anything | `Alt+Q`, glide to a category | Quick, brand-y opener GIF. |

## 3. Capture

Two options — pick one and stick to it for a consistent look.

### Option A — ScreenToGif (easiest, free/OSS)

<https://www.screentogif.com/> — records a screen region straight to GIF with a
built-in editor.

1. **Recorder** → size the capture rectangle to just the 3D viewport + N-panel
   (a fixed ~900–1100 px wide window reads well on GitHub).
2. Record at **20–30 fps**.
3. In the editor: **trim** to the useful range, then
   **Edit ▸ Reduce Frame Count** (keep ~every 2nd frame if it's smooth) and
   **Save As ▸ GIF** with the *quantizer* set to reduce the palette.
4. Aim for **≤ 5 MB** per GIF (GitHub renders inline; large GIFs load slowly).

### Option B — OBS → ffmpeg (best quality/size ratio)

1. Record the viewport in **OBS** to `.mp4` (a small "Windowed Projector" or a
   cropped scene keeps it tight).
2. Two-pass palette conversion (crisp colors, small file):

   ```bash
   # 1) build an optimized palette from the clip
   ffmpeg -i in.mp4 -vf "fps=20,scale=960:-1:flags=lanczos,palettegen=stats_mode=diff" palette.png

   # 2) apply it
   ffmpeg -i in.mp4 -i palette.png -lavfi "fps=20,scale=960:-1:flags=lanczos,paletteuse=dither=bayer:bayer_scale=3" out.gif
   ```

   Tips: width **800–1000 px**, **fps 15–24**, trim to **≤ 6 s**. Trim first
   (`-ss <start> -t <dur>`) to keep the file small.

### Prefer video?

GitHub renders **`.mp4`/`.webm` uploaded through the web editor** inline, but it
will **not** play a video committed as a repo file from a Markdown `![]()` — so
for committed assets, **GIF is the reliable choice**. (Alternative: commit a
poster `.png` that links to a video.)

## 4. Wire into the docs

- Put the files in `docs/gifs/` with descriptive names, e.g.
  `docs/gifs/draw-cut.gif`, `docs/gifs/push-pull.gif`.
- Add a **"See it in action"** section near the top of the README (right after
  the intro), leading with the draw-to-cut hero GIF, and/or slot the smaller
  clips beside their bullets in **Features**.

Example:

```markdown
## See it in action

<p align="center">
  <img src="docs/gifs/draw-cut.gif" width="720" alt="Draw a box, get a boolean cut">
</p>
```
