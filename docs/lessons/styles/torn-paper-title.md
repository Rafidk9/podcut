# HyperFrames style: torn-paper scrap title ("Unusual Paper Titles")

A learned reference style — a **crumpled paper ball that unfurls into a flat torn-paper scrap** carrying a heavy condensed headline, a light subtitle, highlighter swipes, washi-tape strips and hand-drawn pen marks. Scrapbook / zine / analogue-collage energy against a flat saturated background.

Load this when building or editing anything described as a *paper title, torn paper, crumpled paper, paper scrap, ripped paper, zine/scrapbook title, washi tape title*, or a request to reuse "the paper style" / "the Unusual Paper Titles style".

**Reference implementation (working, verified — clone/adapt this, don't rebuild from scratch):**
`C:\Users\AU-0011-PFEC-G\Downloads\podcut\podcut\videos\torn-paper-title\` (in the `podcut` git repo, branch `worktree-torn-paper-title`, cut from `main`)
- `index.html` — the composition (20-slice 3D unfurl, fixed-seed deterministic)
- `STYLE.md` — this spec, repo-local copy
- `README.md` — how the unfurl works + the three transform traps that will bite you
- `shot-plan.json` — the IR (beats, technique, fidelity notes)
- `reference/` — the extracted frames listed below
- `assets/fonts/` — vendored Anton + Exo 2

Built via `/hyperframes` → `/motion-graphics` (category `kinetic-type`), 7s @ 30fps, 1920×1080, MP4 + transparent VP9 overlay. `npx hyperframes check` passes with 0 errors.

## Source & provenance

Reverse-engineered from a purchased Adobe **.mogrt** (Premiere Pro Motion Graphics Template), not authored here:

- Archive: `C:\Users\AU-0011-PFEC-G\Downloads\Unusual-Paper-Title-Motiondrum.zip`
  - `Assets/Unusual-Paper-Titles.mogrt` (458 MB — `project.aegraphic` + `definition.json` + `thumb.png`)
  - `Support/Tutorial.mp4` (2:49 Premiere screen-recording — the only usable moving reference)
  - `Support/Media-Links.txt` (font + music credits)
- Extracted reference frames (durable, this is what to look at first):
  `C:\Users\AU-0011-PFEC-G\.claude\styles\hyperframes\assets\torn-paper-title\`
  - `00-hero-thumb.png` — the template's own hero still, cleanest single look at the design
  - `01-nine-style-variants.jpg` — 3×3 grid of all 9 layout variants
  - `02-reveal-frames-10fps.jpg` — the ball→unfurl reveal, frame by frame
  - `03-outro-frames-10fps.jpg` — the flat→crumple outro, frame by frame
  - `definition.json` — the mogrt's full control schema (authoritative for fonts/sizes/colors)

**The .mogrt itself is the highest-fidelity path.** If the deliverable can be made in Premiere Pro, use the template directly (Essential Graphics → Browse → install the .mogrt) rather than rebuilding. Everything below is for when it must be rebuilt in HyperFrames/HTML.

## Canvas & specs (from `definition.json`)

- 1920×1080, 30 fps, comp named `Final`, **~7 s** total.
- Effects the original leans on: `ADBE Roughen Edges` (the torn edge), `Fill`, `Tint`, `Easy Levels2`, `Geometry2`, plus Color/Point/Slider controls. Renderer `ADBE Escher` (Cinema 4D).
- Source media: `.mov` + `.png`. **The 460 MB `project.aegraphic` holds pre-rendered 3D paper-unfold footage.** It is *not* carvable — no `ftyp`/`moov` atoms, and the 13 embedded 1920×1080 PNG headers are wrapped in non-standard AE chunks with no reachable `IEND`. Don't spend time trying to extract it again; that was checked and it's a dead end.

## Palette (exact, from the mogrt's colour controls)

| Role | Hex | Notes |
|---|---|---|
| Paper | `#FFFFFF` | tints to warm grey in the crumple shading, never flat white |
| Element 1 — tape | `#ECF167` | yellow-lime, the washi/masking-tape strip |
| Element 2 — highlighter | `#FE96EB` | pink, the marker swipe under the subtitle |
| Element 3 — ink | `#000000` | pen marks, underline, doodle |
| Element 4 — shading | `#4F4F4F` | crumple shadow / grey detail |
| Text 1 & Text 2 | `#000000` | both default black |
| Background (demo) | `#FA5F6E`-ish coral/red | the tutorial's own backdrop, **not** part of the template — the mogrt renders on alpha |

The template renders with **transparency**; the background is whatever it's laid over. Pick a flat saturated field (the demo coral, or any strong single colour) — no gradients, no texture.

## Typography

- **Headline** — [Anton](https://fonts.google.com/specimen/Anton) Regular, **186 px** at 1080p (≈17% of frame height). ALL CAPS, black, tight tracking. It's a heavy condensed grotesque; don't substitute a generic bold sans, the condensed proportion is the whole look.
- **Subtitle** — [Exo 2](https://fonts.google.com/specimen/Exo+2) Regular, **127 px** (≈12% of frame height). Lowercase, black, noticeably lighter weight — the contrast between the two is the typographic idea.
- Both are Google Fonts, free, self-hostable.
- Music used in the promo: `https://uppbeat.io/track/soundroll/wrong-way` (licence-gated, not redistributable).

## Element anatomy (what's on the scrap)

Layered back to front:

1. **Torn paper scrap** — near-horizontal rectangle, ~64% of frame width × ~39% of frame height, rotated a few degrees off-axis (roughly −3° to +4°). All four edges ragged/torn, never straight. Surface carries soft grey crumple shading — creases and a faint fold running through it, because it *was* just a ball.
2. **Hand-drawn inner border** — a thin wobbly pen rectangle inset ~15–20 px from the scrap edge. Present in most variants; imperfect, hand-traced, corners not closed.
3. **Faint doodle scribble** — a loose looping biro squiggle drawn across the paper *behind* the text, light grey, low contrast. Cheap and important: it's what sells "someone's notebook".
4. **Headline** (Anton) sitting on the paper, picking up the paper's warp.
5. **Subtitle** (Exo 2).
6. **Pink highlighter swipe** `#FE96EB` — a brush-like band behind/under the subtitle with soft irregular ends, overshooting the text on one side.
7. **Yellow-lime tape strip** `#ECF167` — a crumpled masking-tape rectangle, semi-opaque, with its own creases. Placed **overhanging the scrap's edge** (usually top-left), so it reads as stuck on top.
8. **Hand-drawn accent mark** — exactly one of: a thick tapered underline stroke, a double `=`, an arrow, or a short dash.

## The 9 layout variants

`Style Selection` is an integer 1–9. All share the anatomy above; they permute:

- **Stack order** — headline-above-subtitle (majority) vs. subtitle-above-headline (variants where `cool style` sits on top, small, with the headline dropped below).
- **Tape placement** — wide strip top-left overhanging the top edge / vertical strip down the left side / strip along the bottom edge.
- **Highlighter position** — under the subtitle, or bleeding out past the scrap's right edge.
- **Accent mark** — tapered underline / `=` / arrow / dash.
- **Edge treatment** — plain torn on all sides, or one variant with a **notebook spiral tear** (perforated, serrated edge) down one side.

See `01-nine-style-variants.jpg` before picking one.

## Motion, beat by beat

Total ≈7 s. Timings below are read off the tutorial at 10 fps and are **approximate** — the screen-recording stutters during playback, so treat the *sequence of poses* as authoritative and the durations as a starting point.

1. **Ball** (`0.0s`) — a tight crumpled paper ball, ~8% of the final width, sitting near frame centre. Holds briefly.
2. **Inflate & open** (`~0.2s`) — the ball swells and loosens into a lumpy fold.
3. **Unfurl** (`~0.2–1.2s`) — it opens into a taco/tube shape, wider than tall, then unrolls outward. **The text is mapped onto the deforming 3D surface** — it stretches, skews and un-skews with the paper as it flattens. This is the signature move; a title that merely fades in over a static paper png does not read as this style.
4. **Flatten & settle** (`~1.2–1.5s`) — surface goes flat, rotation settles to its final few degrees. The tape strip lands near the top as the paper reaches flat.
5. **Accents land last** — the pink highlighter swipe and the pen accent mark appear at the tail of the settle, after the text is already readable.
6. **Hold** (`~1.5–6.5s`) — near-static, with a very slight continuous drift/breath. Not frozen.
7. **Crumple out** (`~6.5–7.0s`) — the reverse, and **fast**: flat scrap folds, crumples back into a ball and vanishes in roughly 0.5 s. The exit is about 3× quicker than the entrance. That asymmetry is deliberate — don't make the outro symmetrical with the intro.

## Rebuilding this in HyperFrames

**Route 3 is already built** — see the reference implementation at the top; start there rather than from scratch. Its `README.md` documents the slice technique and the three transform traps (horizontal-displacement gaps, overlays escaping the torn clip, a staggered exit overrunning the duration). The ranking below is why it was chosen.

The hard part is beat 3. Ranked by fidelity:

1. **Use the .mogrt in Premiere.** Highest fidelity, zero rebuild. Default to this if the deliverable allows it.
2. **Three.js** (via `hyperframes-animation`'s Three.js adapter) — a subdivided plane, the composed title rendered to a canvas texture, vertex displacement from a crumple noise/normal map animated from balled-up to flat. This is the only HTML route that genuinely reproduces text-warping-with-the-paper.
3. **CSS 3D + SVG filters** — segment the scrap into vertical strips with individual `rotateX/Y` and stagger their unfold; `feTurbulence` + `feDisplacementMap` on the whole group for the ragged edge and crumple wobble; a `clip-path` polygon with many short irregular segments for the torn outline. Cheaper, seek-safe, and it *approximates* — the text won't truly deform. Acceptable for short/small-format work; say so rather than claiming a match.

Regardless of route:
- Keep it **seek-safe and deterministic** — no `Date.now()` / `Math.random()`. Pre-generate the torn-edge polygon and the doodle path as fixed data at build time.
- The torn edge is `Roughen Edges` in the original: an irregular, high-frequency displacement of the alpha boundary. In SVG, `feTurbulence` (fractalNoise, low `baseFrequency`) into `feDisplacementMap` on the alpha is the closest analogue.
- Render on transparency if it's going to be an overlay; the coral background is demo-only.

## Gotchas

- **Don't substitute the fonts.** Anton's condensed weight against Exo 2's lighter lowercase is the typographic contrast the design rests on; a generic bold/regular pair flattens it.
- **Don't make the paper flat white.** The grey crumple shading (`#4F4F4F` family) is what makes it read as paper rather than a white rectangle.
- **Tape must overhang the scrap edge.** Contained inside the scrap it reads as a printed yellow box, not tape.
- **Straight edges kill it.** Every edge — scrap outline, tape ends, highlighter swipe, pen border — has to be irregular.
- **Outro is much faster than the intro** (~0.5 s vs ~1.3 s). Symmetrical timing feels wrong.
- **Verify at full resolution**, not contact-sheet scale — the torn edge, doodle and crumple shading all disappear in thumbnails, which makes a too-clean rebuild look correct when it isn't.

## Process notes

- Route for a rebuild: `/hyperframes` → `/motion-graphics` (short, unnarrated, motion-first, <10 s — this is a title/lower-third/logo-sting shape). Longer or narrated pieces route elsewhere; see `/hyperframes`'s routing table.
- For the Three.js route, load `hyperframes-animation` for the adapter API before authoring.
