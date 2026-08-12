# Style: torn-paper scrap title

The design language this composition implements. Reverse-engineered from a purchased Adobe **.mogrt** (Premiere Pro Motion Graphics Template) called *Unusual Paper Titles* — the template is not redistributable and is not in this repo; what's here is the spec plus reference frames extracted from it.

A crumpled paper ball unfurls into a flat torn-paper scrap carrying a heavy condensed headline, a light subtitle, highlighter swipes, washi-tape strips and hand-drawn pen marks. Scrapbook / zine / analogue-collage energy against a flat saturated field.

> **Off-brand for PFEC, deliberately.** PodCut's standing editorial preferences are navy `#100796` / gold `#FFC500` Poppins. This style is lime/pink scrapbook collage and does **not** follow them. It lives here as a general-purpose composition, not a PFEC brand asset. A PFEC-palette recolor would be a separate variant — see "Retheming" in `README.md`.

## Reference frames

In `reference/` — look at these before changing anything visual:

| File | What it shows |
| --- | --- |
| `00-hero-thumb.png` | the template's own hero still — cleanest single look at the design |
| `01-nine-style-variants.jpg` | all 9 layout variants the .mogrt ships |
| `02-reveal-frames-10fps.jpg` | the ball → unfurl reveal, frame by frame |
| `03-outro-frames-10fps.jpg` | the flat → crumple outro, frame by frame |
| `definition.json` | the .mogrt's control schema — authoritative for fonts, sizes, colours |

## Canvas

1920×1080, 30 fps, ~7 s, renders on transparency. The source template leans on After Effects' `Roughen Edges`, `Fill`, `Tint`, `Easy Levels2` and `Geometry2`.

## Palette

| Role | Hex | Notes |
| --- | --- | --- |
| Paper | `#FFFFFF` | tints to warm grey in the crumple shading — never flat white |
| Tape | `#ECF167` | yellow-lime washi/masking strip |
| Highlighter | `#FE96EB` | pink marker swipe under the subtitle |
| Ink | `#000000` | pen marks, underline, doodle |
| Shading | `#4F4F4F` | crumple shadow / grey detail |
| Backdrop | `#FA5F6E` | **demo only** — the template renders on alpha |

## Typography

- **Headline** — Anton Regular, **186 px** at 1080p (~17% of frame height), ALL CAPS, black.
- **Subtitle** — Exo 2 Regular, **127 px** (~12%), lowercase, black.

Both self-hosted in `assets/fonts/` (fetched by `fetch_fonts.py`) so renders don't depend on the network. The contrast between Anton's condensed weight and Exo 2's lighter lowercase is the typographic idea — a generic bold/regular pair flattens it.

## Element anatomy

Back to front:

1. **Torn paper scrap** — ~64% frame width × ~39% height, rotated a few degrees off-axis, all four edges ragged, soft grey crumple shading across the surface.
2. **Hand-drawn inner border** — thin wobbly pen rectangle inset ~18 px, corners not closed.
3. **Faint biro doodle** — a loose self-crossing loop behind the text, low contrast. Cheap and important: it's what sells "someone's notebook".
4. **Headline** (Anton), **subtitle** (Exo 2).
5. **Pink highlighter swipe** — brush-like band under the subtitle, overshooting past the scrap's left torn edge.
6. **Yellow-lime tape strip** — crumpled, semi-opaque, overhanging the scrap's top edge.
7. **One hand-drawn accent** — tapered underline, double `=`, arrow, or dash.

## The 9 layout variants

The .mogrt exposes `Style Selection` 1–9. All share the anatomy above and permute: stack order (headline-above-subtitle vs subtitle-above-headline), tape placement (top-left / left vertical / bottom), highlighter position, accent mark, and edge treatment (one variant has a notebook spiral tear). **This composition implements variant 1.** See `reference/01-nine-style-variants.jpg`.

## Motion

Approximate — read off a screen-recording that stutters during playback, so the *sequence of poses* is authoritative and durations are a starting point.

1. **Ball** (0.0s) — tight crumpled ball, ~8% of final width. No readable text.
2. **Inflate** (~0.2s) — swells and loosens.
3. **Unfurl** (~0.2–1.2s) — opens into a tube and unrolls. **The text deforms with the paper**; a title that merely fades in over a static paper PNG does not read as this style.
4. **Flatten & settle** (~1.2–1.5s) — tape lands as the surface reaches flat.
5. **Accents land last** — highlighter and pen mark arrive *after* the text is readable.
6. **Hold** (~1.5–6.4s) — near-static with a slight breath. Not frozen.
7. **Crumple out** (~6.4–7.0s) — reverse, and **~3× faster than the entrance**. A symmetrical outro feels wrong.

## Gotchas

- **Don't substitute the fonts** — the Anton/Exo 2 weight contrast carries the design.
- **Don't make the paper flat white** — the grey crumple shading is what makes it read as paper.
- **Tape must overhang the scrap edge** — contained inside it, it reads as a printed yellow box.
- **Straight edges kill it** — scrap outline, tape ends, highlighter, pen border all have to be irregular.
- **The outro is much faster than the intro.**
- **Verify at full resolution** — torn edge, doodle and crumple shading all vanish at contact-sheet scale, which makes a too-clean rebuild look correct when it isn't.
