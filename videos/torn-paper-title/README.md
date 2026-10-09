# torn-paper-title

A 7s HyperFrames motion graphic: a crumpled paper ball unfurls into a torn-paper scrap carrying a title, holds, then crumples away. 1920×1080, 30 fps, renders to MP4 or a transparent overlay.

The design language, palette, type scale and reference frames live in **`STYLE.md`**. Read it before changing anything visual. `shot-plan.json` is the IR (beats, technique, fidelity notes).

> This style is **off-brand for PFEC** (lime/pink scrapbook, not navy/gold Poppins). It's a general-purpose composition, not a PFEC brand asset — see the note at the top of `STYLE.md`.

## Commands

```bash
npm run check                       # lint + runtime + layout + motion + contrast
npx hyperframes snapshot --at 0.08,0.6,1.35,2.5,6.65   # proof frames -> snapshots/
npm run dev                         # preview server (long-running)
npm run render                      # -> renders/video.mp4
```

Transparent overlay: add `data-hidden` to the `#bg` element in `index.html`, then

```bash
npx hyperframes render . --format webm -o ./renders/overlay-alpha.webm
```

VP9 stores alpha as a side channel, so `ffprobe` reports `pix_fmt=yuv420p` — that is **not** a missing alpha channel. Check `stream_tags=alpha_mode` (`ALPHA_MODE=1`) instead, or decode a frame to RGBA and read the corner pixels.

`renders/` and the full-resolution `snapshots/frame-*.png` are gitignored (reproducible); `snapshots/contact-sheet.jpg` is kept as the at-a-glance proof of the whole arc.

## How the unfurl works

The signature move is the title deforming *with* the paper as it opens. The source template gets this by displacement-mapping text onto pre-rendered 3D paper footage — 460 MB of it, not extractable and not reproducible in HTML.

This composition approximates it with **slice geometry**: the artwork is authored once, then rendered into **20 vertical strips**, each holding a full copy offset by `-i * stripWidth` and cropped by `overflow: hidden`. Each strip is independently transformed inside a shared `perspective`, so the composed title bends piecewise with the sheet. Strips start in a crumpled pose whose curl grows left-to-right (a rolled tube) and flatten on a staggered sweep, which is what makes the unfurl read as *unrolling* rather than 20 flaps opening at once.

It approximates — it is not true surface displacement. Route 2 in `STYLE.md`'s lineage (Three.js vertex displacement on a subdivided plane) would match more closely at considerably more cost.

### Three things that will bite you if you touch the transforms

1. **`rotateY`, `rotateZ`, `x` and `z` on a vertical strip all open gaps.** Anything that moves a slice horizontally relative to its neighbour lets the backdrop stripe through and the sheet reads as venetian blinds. `z` is the sneaky one — under perspective, a slice offset from the vanishing point parallaxes sideways as `z` changes. Keep all four small; carry the motion on `rotateX` (and `y`), where neighbours stay touching. Strips are also drawn 4 px wider than their slot so they overlap by a hair and hide sub-pixel seams.
2. **Per-strip overlays must live inside the torn clip.** The fold-shading `.shade` originally sat at the top of `.art`, whose box is the full 1400×560 frame — so it painted over the empty margin around the scrap and tinted the *backdrop*, showing up as coloured bands washing across the frame mid-unfurl. It belongs inside `.scrap`, where the `clip-path` constrains it.
3. **The exit has to land inside the duration, not merely be in flight at the end.** With a staggered crumple, the last slice finishes `stagger.each × strips` after the tween starts; if that overruns `data-duration` the final frame is a half-scale legible title instead of a vanished ball.

## Determinism

The torn silhouette, tape and highlighter shapes, paper creases, biro doodle and every per-strip crumple pose are generated at load from a fixed-seed `mulberry32` PRNG. No render-time clocks, no unseeded randomness, no network. `assets/fonts/*.woff2` are vendored (`fetch_fonts.py` refetches them) so text metrics can't shift between renders.

## Layout-check waivers

`npx hyperframes check` flags the slice technique by construction; both waivers were applied **after** snapshots confirmed the frames render correctly:

- `data-layout-allow-overflow` on `.art` — it is deliberately 20× wider than the `.strip` cropping it. That *is* the mechanism.
- `data-layout-allow-overlap` on `.h1` / `.h2` — 20 copies stack at identical page coordinates; on screen each is cropped to its own slice and none ever coincide.

The one remaining warning is `composition_file_too_large` (~330 lines). Splitting a single-scene piece into sub-compositions would hurt readability here more than it helps, so it stands.

## Retheming

- **Text** — the `.h1` / `.h2` strings in the `ART` template literal.
- **Palette** — the `.hl` / `.tape` / `#bg` CSS values, all in one block at the top.
- **Other layout variants** — `reference/01-nine-style-variants.jpg` shows the other eight; they permute stack order, tape placement and accent mark, which are all position changes in the same `ART` template.
- **PFEC recolor** — tape → gold `#FFC500`, ink → navy `#100796`, backdrop → navy; the paper and its shading should stay neutral or it stops reading as paper. Worth checking against podcut's editorial preferences in the root `CLAUDE.md` before shipping one.
